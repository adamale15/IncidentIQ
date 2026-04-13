"""
Embedding generation with a local default model for development/testing.
"""
import asyncio
import logging
from typing import Any, Dict, List

from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate embeddings using a local sentence-transformers model by default."""

    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self.provider = settings.EMBEDDING_PROVIDER.lower()
        self.model_name = settings.LOCAL_EMBEDDING_MODEL
        self._model = SentenceTransformer(self.model_name)
        self.vector_size = self._model.get_sentence_embedding_dimension()

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        if not texts:
            return []

        embeddings: List[List[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            logger.info(
                "Generating embeddings for batch %s (%s texts) with %s",
                i // self.batch_size + 1,
                len(batch),
                self.model_name,
            )
            batch_embeddings = await self._embed_batch(batch)
            embeddings.extend(batch_embeddings)

        logger.info("Generated %s embeddings", len(embeddings))
        return embeddings

    async def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a single batch of texts."""
        loop = asyncio.get_event_loop()

        def _sync_embed() -> List[List[float]]:
            vectors = self._model.encode(texts, normalize_embeddings=True)
            return vectors.tolist()

        return await loop.run_in_executor(None, _sync_embed)

    async def generate_query_embedding(self, query: str) -> List[float]:
        """Generate an embedding for a query string."""
        loop = asyncio.get_event_loop()

        def _sync_embed() -> List[float]:
            vector = self._model.encode([query], normalize_embeddings=True)[0]
            return vector.tolist()

        embedding = await loop.run_in_executor(None, _sync_embed)
        logger.debug("Generated query embedding (dim: %s)", len(embedding))
        return embedding


class BatchEmbeddingGenerator:
    """Utility for managing large-scale embedding generation."""
    
    def __init__(self, embedding_generator: EmbeddingGenerator = None):
        """
        Initialize batch embedding generator.
        
        Args:
            embedding_generator: EmbeddingGenerator instance
        """
        self.generator = embedding_generator or EmbeddingGenerator()
    
    async def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for a list of chunks.
        
        Args:
            chunks: List of chunk dictionaries with 'content' key
            
        Returns:
            List of chunks with added 'embedding' key
        """
        texts = [chunk['content'] for chunk in chunks]
        
        logger.info(f"Generating embeddings for {len(texts)} chunks")
        embeddings = await self.generator.generate_embeddings(texts)
        
        # Add embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk['embedding'] = embedding
        
        return chunks
    
    async def embed_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for document contents.
        
        Args:
            documents: List of document dictionaries with 'content' key
            
        Returns:
            List of documents with added 'embedding' key
        """
        texts = [doc['content'] for doc in documents]
        
        logger.info(f"Generating embeddings for {len(texts)} documents")
        embeddings = await self.generator.generate_embeddings(texts)
        
        # Add embeddings to documents
        for doc, embedding in zip(documents, embeddings):
            doc['embedding'] = embedding
        
        return documents
