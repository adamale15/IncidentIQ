"""
Hybrid retrieval combining dense vector search and sparse BM25 search.
"""
import logging
import uuid
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.config import settings
from app.ingestion.embeddings import EmbeddingGenerator
from app.ingestion.sparse import BM25SparseVectorGenerator

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Hybrid retrieval using dense + sparse vectors with RRF."""
    
    def __init__(self):
        """Initialize retriever."""
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.embedding_generator = EmbeddingGenerator()
        self.sparse_generator = BM25SparseVectorGenerator()
        
        self.dense_weight = settings.DENSE_WEIGHT
        self.sparse_weight = settings.SPARSE_WEIGHT
        self.top_k = settings.TOP_K_RETRIEVAL
    
    async def retrieve(
        self,
        query: str,
        workspace_id: uuid.UUID,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks using hybrid search.
        
        Args:
            query: Search query
            workspace_id: Workspace UUID
            filters: Optional metadata filters (service, severity, date_range)
            top_k: Number of results to return
            
        Returns:
            List of retrieved chunks with scores
        """
        k = top_k or self.top_k
        
        logger.info(f"Hybrid retrieval for query: '{query}' (top_k={k})")
        
        # Step 1: Generate query embedding
        query_embedding = await self.embedding_generator.generate_query_embedding(query)
        
        # Step 2: Build Qdrant filter
        qdrant_filter = self._build_filter(workspace_id, filters)
        
        # Step 3: Dense vector search
        dense_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=("dense", query_embedding),
            query_filter=qdrant_filter,
            limit=k * 2,  # Get more for fusion
            with_payload=True
        )
        
        # Step 4: Sparse vector search
        sparse_results = []
        try:
            query_sparse = self.sparse_generator.generate_qdrant_sparse_vector(query)
            sparse_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=("bm25", query_sparse),
                query_filter=qdrant_filter,
                limit=k * 2,
                with_payload=True
            )
        except Exception as exc:
            logger.warning("Sparse retrieval unavailable, falling back to dense-only search: %s", exc)
        
        # Step 5: Reciprocal Rank Fusion
        fused_results = self._reciprocal_rank_fusion(
            dense_results,
            sparse_results,
            k=k
        )
        
        logger.info(f"Retrieved {len(fused_results)} chunks after hybrid fusion")
        
        return fused_results
    
    def _build_filter(
        self,
        workspace_id: uuid.UUID,
        filters: Optional[Dict[str, Any]] = None
    ) -> Filter:
        """
        Build Qdrant filter from metadata filters.
        
        Args:
            workspace_id: Workspace UUID
            filters: Metadata filters
            
        Returns:
            Qdrant Filter object
        """
        must_conditions = [
            FieldCondition(
                key="workspace_id",
                match=MatchValue(value=str(workspace_id))
            )
        ]
        
        if not filters:
            return Filter(must=must_conditions)
        
        # Service filter
        if filters.get("service"):
            services = filters["service"] if isinstance(filters["service"], list) else [filters["service"]]
            must_conditions.append(
                FieldCondition(
                    key="service",
                    match=MatchValue(value=services[0])  # Simplified for now
                )
            )
        
        # Severity filter
        if filters.get("severity"):
            must_conditions.append(
                FieldCondition(
                    key="severity",
                    match=MatchValue(value=filters["severity"])
                )
            )
        
        # Date range filter (requires range condition - simplified for now)
        # TODO: Add date range filtering
        
        return Filter(must=must_conditions)
    
    def _reciprocal_rank_fusion(
        self,
        dense_results: List,
        sparse_results: List,
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Fuse dense and sparse results using Reciprocal Rank Fusion.
        
        Args:
            dense_results: Results from dense search
            sparse_results: Results from sparse search
            k: RRF constant (default 60)
            
        Returns:
            Fused and sorted results
        """
        scores: Dict[Any, Dict[str, Any]] = {}
        
        # Score dense results
        for rank, result in enumerate(dense_results, start=1):
            point_id = result.id
            rrf_score = self.dense_weight / (k + rank)
            if point_id not in scores:
                scores[point_id] = {
                    "rrf_score": rrf_score,
                    "dense_score": result.score,
                    "sparse_score": 0,
                    "payload": result.payload,
                    "id": point_id
                }
            else:
                scores[point_id]["rrf_score"] += rrf_score
                scores[point_id]["dense_score"] = result.score
        
        # Score sparse results
        for rank, result in enumerate(sparse_results, start=1):
            point_id = result.id
            rrf_score = self.sparse_weight / (k + rank)
            
            if point_id in scores:
                scores[point_id]["rrf_score"] += rrf_score
                scores[point_id]["sparse_score"] = result.score
            else:
                scores[point_id] = {
                    "rrf_score": rrf_score,
                    "dense_score": 0,
                    "sparse_score": result.score,
                    "payload": result.payload,
                    "id": point_id
                }
        
        # Sort by RRF score and take top k
        sorted_results = sorted(
            scores.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )[:self.top_k]
        
        # Format results
        formatted_results = []
        for result in sorted_results:
            formatted_results.append({
                "id": result["id"],
                "content": result["payload"]["content"],
                "score": result["rrf_score"],
                "dense_score": result["dense_score"],
                "sparse_score": result["sparse_score"],
                "metadata": {
                    "chunk_type": result["payload"].get("chunk_type"),
                    "service": result["payload"].get("service"),
                    "severity": result["payload"].get("severity"),
                    "date": result["payload"].get("date"),
                    "team": result["payload"].get("team"),
                    "document_title": result["payload"].get("document_title"),
                    "source_type": result["payload"].get("source_type")
                }
            })
        
        return formatted_results
