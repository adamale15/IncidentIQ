"""
Cross-encoder reranking for retrieved chunks.
"""
import asyncio
from typing import Any, Dict, List

from sentence_transformers import CrossEncoder


class CrossEncoderReranker:
    """Rerank candidate chunks using a lightweight cross-encoder."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name)

    async def rerank(self, query: str, chunks: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        if not chunks:
            return []

        pairs = [[query, chunk["content"]] for chunk in chunks]
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(None, lambda: self.model.predict(pairs).tolist())

        reranked: List[Dict[str, Any]] = []
        for chunk, score in zip(chunks, scores):
            enriched = dict(chunk)
            enriched["rerank_score"] = float(score)
            reranked.append(enriched)

        reranked.sort(key=lambda item: item["rerank_score"], reverse=True)
        return reranked[:top_k]
