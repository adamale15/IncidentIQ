"""
Complete ingestion pipeline orchestration.
"""
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, SparseVectorParams, SparseIndexParams
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.connectors.base import BaseConnector
from app.ingestion.chunker import ChunkerFactory
from app.ingestion.embeddings import BatchEmbeddingGenerator
from app.ingestion.sparse import BatchSparseVectorGenerator
from app.db.models import Document, Chunk

logger = logging.getLogger(__name__)


class QdrantManager:
    """Manage Qdrant vector database operations."""
    
    def __init__(self, vector_size: int):
        """Initialize Qdrant client."""
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.vector_size = vector_size
    
    def create_collection_if_not_exists(self):
        """Create Qdrant collection with hybrid search support."""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)

            if exists:
                collection_info = self.client.get_collection(self.collection_name)
                vectors = collection_info.config.params.vectors
                current_size = None

                if isinstance(vectors, dict) and "dense" in vectors:
                    current_size = vectors["dense"].size
                elif hasattr(vectors, "size"):
                    current_size = vectors.size

                if current_size == self.vector_size:
                    logger.info("Collection '%s' already exists", self.collection_name)
                    return

                logger.warning(
                    "Recreating collection '%s' because vector size changed from %s to %s",
                    self.collection_name,
                    current_size,
                    self.vector_size,
                )
                self.client.delete_collection(self.collection_name)

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    "bm25": SparseVectorParams(
                        index=SparseIndexParams()
                    )
                }
            )
            
            logger.info(f"Created collection '{self.collection_name}' with hybrid search")
            
        except Exception as e:
            logger.error(f"Error creating collection: {e}", exc_info=True)
            raise
    
    def upsert_chunks(self, chunks: List[Dict[str, Any]], workspace_id: uuid.UUID) -> List[uuid.UUID]:
        """
        Upsert chunks to Qdrant.
        
        Args:
            chunks: List of chunks with embeddings and sparse vectors
            workspace_id: Workspace UUID
            
        Returns:
            List of point IDs (UUIDs)
        """
        if not chunks:
            return []
        
        points = []
        point_ids = []
        
        for chunk in chunks:
            point_id = uuid.uuid4()
            point_ids.append(point_id)
            
            # Build payload
            payload = {
                "content": chunk["content"],
                "chunk_type": chunk["chunk_type"],
                "workspace_id": str(workspace_id),
                "source_type": chunk["metadata"].get("source_type", ""),
                "service": chunk["metadata"].get("services", []),
                "severity": chunk["metadata"].get("severity", ""),
                "date": chunk["metadata"].get("date").isoformat() if chunk["metadata"].get("date") else None,
                "team": chunk["metadata"].get("team", ""),
                "document_id": str(chunk.get("document_id", "")),
                "document_title": chunk["metadata"].get("title", "")
            }
            
            # Create point with dense and sparse vectors
            point = PointStruct(
                id=str(point_id),
                vector={
                    "dense": chunk["embedding"],
                    "bm25": chunk["sparse_vector"]
                },
                payload=payload
            )
            
            points.append(point)
            
            # Store point_id in chunk for PostgreSQL
            chunk["qdrant_point_id"] = point_id
        
        # Upsert to Qdrant
        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            logger.info(f"Upserted {len(points)} points to Qdrant")
        except Exception as e:
            logger.error(f"Error upserting to Qdrant: {e}", exc_info=True)
            raise
        
        return point_ids
    
    def delete_workspace_chunks(self, workspace_id: uuid.UUID):
        """
        Delete all chunks for a workspace.
        
        Args:
            workspace_id: Workspace UUID
        """
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector={
                    "filter": {
                        "must": [
                            {
                                "key": "workspace_id",
                                "match": {"value": str(workspace_id)}
                            }
                        ]
                    }
                }
            )
            logger.info(f"Deleted chunks for workspace {workspace_id}")
        except Exception as e:
            logger.error(f"Error deleting workspace chunks: {e}", exc_info=True)
            raise


class IngestionPipeline:
    """Orchestrate the complete ingestion pipeline."""
    
    def __init__(self):
        """Initialize pipeline components."""
        self.embedding_generator = BatchEmbeddingGenerator()
        self.qdrant_manager = QdrantManager(
            vector_size=self.embedding_generator.generator.vector_size
        )
        self.sparse_generator = BatchSparseVectorGenerator()
        
        # Ensure Qdrant collection exists
        self.qdrant_manager.create_collection_if_not_exists()
    
    async def ingest_from_connector(
        self,
        connector: BaseConnector,
        workspace_id: uuid.UUID,
        data_source_id: uuid.UUID,
        db_session: AsyncSession
    ) -> Dict[str, int]:
        """
        Run complete ingestion pipeline from a connector.
        
        Args:
            connector: Data source connector
            workspace_id: Workspace UUID
            data_source_id: Data source UUID
            db_session: Database session
            
        Returns:
            Statistics: {"documents": count, "chunks": count}
        """
        logger.info(f"Starting ingestion for workspace {workspace_id}, source {data_source_id}")
        
        # Step 1: Connect and fetch documents
        connected = await connector.connect()
        if not connected:
            raise RuntimeError("Failed to connect to data source")
        
        documents = await connector.fetch_documents()
        logger.info(f"Fetched {len(documents)} documents")
        
        if not documents:
            return {"documents": 0, "chunks": 0}
        
        # Step 2: Save documents to PostgreSQL
        doc_models = []
        for doc in documents:
            doc_model = Document(
                workspace_id=workspace_id,
                data_source_id=data_source_id,
                title=doc["title"],
                source_url=doc.get("source_url"),
                source_type=connector.get_source_type().value,
                incident_date=doc["metadata"].get("date"),
                severity=doc["metadata"].get("severity"),
                services=doc["metadata"].get("services", []),
                teams=doc["metadata"].get("team", "").split(",") if doc["metadata"].get("team") else [],
                raw_content=doc["content"],
                content_hash=doc.get("content_hash", "")
            )
            db_session.add(doc_model)
            doc_models.append(doc_model)
        
        await db_session.flush()  # Get IDs without committing
        
        # Step 3: Chunk documents
        all_chunks = []
        for doc, doc_model in zip(documents, doc_models):
            chunker = ChunkerFactory.get_chunker(connector.get_source_type().value)
            chunks = chunker.chunk(doc["content"], doc["metadata"])
            
            # Add document reference
            for chunk in chunks:
                chunk["document_id"] = doc_model.id
                chunk["metadata"]["title"] = doc["title"]
                chunk["metadata"]["source_type"] = connector.get_source_type().value
            
            all_chunks.extend(chunks)
        
        logger.info(f"Created {len(all_chunks)} chunks from {len(documents)} documents")
        
        # Step 4: Generate embeddings
        all_chunks = await self.embedding_generator.embed_chunks(all_chunks)
        
        # Step 5: Generate sparse vectors
        all_chunks = self.sparse_generator.generate_for_chunks(all_chunks)
        
        # Step 6: Upsert to Qdrant
        point_ids = self.qdrant_manager.upsert_chunks(all_chunks, workspace_id)
        
        # Step 7: Save chunks to PostgreSQL
        for chunk in all_chunks:
            chunk_model = Chunk(
                document_id=chunk["document_id"],
                workspace_id=workspace_id,
                content=chunk["content"],
                chunk_type=chunk["chunk_type"],
                start_char=chunk.get("start_char"),
                end_char=chunk.get("end_char"),
                chunk_metadata=chunk["metadata"],
                qdrant_point_id=chunk["qdrant_point_id"]
            )
            db_session.add(chunk_model)
        
        await db_session.commit()
        
        logger.info(f"Ingestion complete: {len(documents)} documents, {len(all_chunks)} chunks")
        
        return {
            "documents": len(documents),
            "chunks": len(all_chunks)
        }
    
    async def ingest_documents_directly(
        self,
        documents: List[Dict[str, Any]],
        workspace_id: uuid.UUID,
        data_source_id: uuid.UUID,
        source_type: str,
        db_session: AsyncSession
    ) -> Dict[str, int]:
        """
        Ingest documents directly without a connector (for synthetic data).
        
        Args:
            documents: List of document dictionaries
            workspace_id: Workspace UUID
            data_source_id: Data source UUID
            source_type: Type of source
            db_session: Database session
            
        Returns:
            Statistics: {"documents": count, "chunks": count}
        """
        logger.info(f"Starting direct ingestion of {len(documents)} documents")
        
        # Save documents to PostgreSQL
        doc_models = []
        for doc in documents:
            doc_model = Document(
                workspace_id=workspace_id,
                data_source_id=data_source_id,
                title=doc["title"],
                source_url=doc.get("source_url"),
                source_type=source_type,
                incident_date=doc["metadata"].get("date"),
                severity=doc["metadata"].get("severity"),
                services=doc["metadata"].get("services", []),
                teams=doc["metadata"].get("team", "").split(",") if doc["metadata"].get("team") else [],
                raw_content=doc["content"],
                content_hash=doc.get("content_hash", "")
            )
            db_session.add(doc_model)
            doc_models.append(doc_model)
        
        await db_session.flush()
        
        # Chunk documents
        all_chunks = []
        for doc, doc_model in zip(documents, doc_models):
            chunker = ChunkerFactory.get_chunker(source_type)
            chunks = chunker.chunk(doc["content"], doc["metadata"])
            
            for chunk in chunks:
                chunk["document_id"] = doc_model.id
                chunk["metadata"]["title"] = doc["title"]
                chunk["metadata"]["source_type"] = source_type
            
            all_chunks.extend(chunks)
        
        # Generate embeddings and sparse vectors
        all_chunks = await self.embedding_generator.embed_chunks(all_chunks)
        all_chunks = self.sparse_generator.generate_for_chunks(all_chunks)
        
        # Upsert to Qdrant
        point_ids = self.qdrant_manager.upsert_chunks(all_chunks, workspace_id)
        
        # Save chunks to PostgreSQL
        for chunk in all_chunks:
            chunk_model = Chunk(
                document_id=chunk["document_id"],
                workspace_id=workspace_id,
                content=chunk["content"],
                chunk_type=chunk["chunk_type"],
                start_char=chunk.get("start_char"),
                end_char=chunk.get("end_char"),
                chunk_metadata=chunk["metadata"],
                qdrant_point_id=chunk["qdrant_point_id"]
            )
            db_session.add(chunk_model)
        
        await db_session.commit()
        
        logger.info(f"Direct ingestion complete: {len(documents)} documents, {len(all_chunks)} chunks")
        
        return {
            "documents": len(documents),
            "chunks": len(all_chunks)
        }
