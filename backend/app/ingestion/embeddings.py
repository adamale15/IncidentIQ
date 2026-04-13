"""
Embedding generation using Google Gemini.
"""
import logging
import asyncio
from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate embeddings using Gemini text-embedding-004."""
    
    def __init__(self, batch_size: int = 100):
        """
        Initialize embedding generator.
        
        Args:
            batch_size: Number of texts to embed in one batch
        """
        self.batch_size = batch_size
        self.model_name = settings.GEMINI_EMBEDDING_MODEL
        
        # Configure Gemini
        genai.configure(api_key=settings.GEMINI_API_KEY)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (768-dimensional)
        """
        if not texts:
            return []
        
        embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            logger.info(f"Generating embeddings for batch {i // self.batch_size + 1} "
                       f"({len(batch)} texts)")
            
            try:
                batch_embeddings = await self._embed_batch(batch)
                embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Error generating embeddings for batch: {e}", exc_info=True)
                raise
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        return embeddings
    
    async def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a single batch of texts.
        
        Args:
            texts: Batch of texts
            
        Returns:
            List of embedding vectors
        """
        # Gemini embed_content is synchronous, wrap in async
        loop = asyncio.get_event_loop()
        
        def _sync_embed():
            result = genai.embed_content(
                model=self.model_name,
                content=texts,
                task_type="retrieval_document"
            )
            return result['embedding']
        
        embeddings = await loop.run_in_executor(None, _sync_embed)
        
        # Handle both single and batch responses
        if isinstance(embeddings[0], float):
            # Single embedding returned as flat list
            return [embeddings]
        else:
            # Multiple embeddings
            return embeddings
    
    async def generate_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for a query string.
        
        Args:
            query: Query text
            
        Returns:
            Embedding vector (768-dimensional)
        """
        loop = asyncio.get_event_loop()
        
        def _sync_embed():
            result = genai.embed_content(
                model=self.model_name,
                content=query,
                task_type="retrieval_query"
            )
            return result['embedding']
        
        embedding = await loop.run_in_executor(None, _sync_embed)
        
        logger.debug(f"Generated query embedding (dim: {len(embedding)})")
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
