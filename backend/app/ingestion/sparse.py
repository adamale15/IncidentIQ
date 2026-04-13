"""
BM25 sparse vector generation for keyword-based retrieval.
"""
import logging
import re
from typing import List, Dict, Any
from collections import Counter
import math

logger = logging.getLogger(__name__)


class BM25SparseVectorGenerator:
    """Generate BM25 sparse vectors for chunks."""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 generator.
        
        Args:
            k1: Term frequency saturation parameter (default: 1.5)
            b: Length normalization parameter (default: 0.75)
        """
        self.k1 = k1
        self.b = b
        self.avg_doc_length = 0
        self.corpus_size = 0
        self.idf_cache = {}
    
    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into terms.
        
        Args:
            text: Input text
            
        Returns:
            List of tokens
        """
        # Lowercase and split on non-alphanumeric
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        return tokens
    
    def compute_term_frequencies(self, text: str) -> Dict[str, int]:
        """
        Compute term frequencies for a document.
        
        Args:
            text: Document text
            
        Returns:
            Dictionary of term frequencies
        """
        tokens = self.tokenize(text)
        return dict(Counter(tokens))
    
    def generate_sparse_vector(self, text: str, vocab_map: Dict[str, int] = None) -> Dict[int, float]:
        """
        Generate sparse BM25 vector for text.
        
        Args:
            text: Input text
            vocab_map: Optional vocabulary mapping term -> index
            
        Returns:
            Sparse vector as {index: score} dict
        """
        tokens = self.tokenize(text)
        term_freqs = Counter(tokens)
        doc_length = len(tokens)
        
        sparse_vector = {}
        
        for term, freq in term_freqs.items():
            # Simple TF-IDF-like scoring for BM25
            # In practice, this would use corpus statistics
            tf_component = (freq * (self.k1 + 1)) / (freq + self.k1)
            
            if vocab_map and term in vocab_map:
                idx = vocab_map[term]
            else:
                # Use hash of term as index if no vocab map
                idx = hash(term) % (2**31)  # Keep positive
            
            sparse_vector[idx] = tf_component
        
        return sparse_vector
    
    def generate_qdrant_sparse_vector(self, text: str) -> Dict[str, Any]:
        """
        Generate sparse vector in Qdrant format.
        
        Args:
            text: Input text
            
        Returns:
            Qdrant sparse vector format: {"indices": [...], "values": [...]}
        """
        sparse_dict = self.generate_sparse_vector(text)
        
        indices = list(sparse_dict.keys())
        values = list(sparse_dict.values())
        
        return {
            "indices": indices,
            "values": values
        }
    
    def generate_sparse_vectors_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Generate sparse vectors for multiple texts.
        
        Args:
            texts: List of text strings
            
        Returns:
            List of Qdrant sparse vector dictionaries
        """
        logger.info(f"Generating BM25 sparse vectors for {len(texts)} texts")
        
        sparse_vectors = []
        for text in texts:
            sparse_vec = self.generate_qdrant_sparse_vector(text)
            sparse_vectors.append(sparse_vec)
        
        logger.info(f"Generated {len(sparse_vectors)} sparse vectors")
        return sparse_vectors


class BatchSparseVectorGenerator:
    """Utility for managing large-scale sparse vector generation."""
    
    def __init__(self, generator: BM25SparseVectorGenerator = None):
        """
        Initialize batch sparse vector generator.
        
        Args:
            generator: BM25SparseVectorGenerator instance
        """
        self.generator = generator or BM25SparseVectorGenerator()
    
    def generate_for_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate sparse vectors for chunks.
        
        Args:
            chunks: List of chunk dictionaries with 'content' key
            
        Returns:
            List of chunks with added 'sparse_vector' key
        """
        texts = [chunk['content'] for chunk in chunks]
        
        sparse_vectors = self.generator.generate_sparse_vectors_batch(texts)
        
        # Add sparse vectors to chunks
        for chunk, sparse_vec in zip(chunks, sparse_vectors):
            chunk['sparse_vector'] = sparse_vec
        
        return chunks
