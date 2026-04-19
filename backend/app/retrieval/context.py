"""
Context assembly utilities for answer generation.
"""
from typing import Any, Dict, List, Tuple


CHUNK_PRIORITY = {
    "root_cause": 0,
    "timeline": 1,
    "resolution": 2,
    "discussion": 3,
    "alert": 4,
    "runbook_step": 5,
    "summary": 6,
    "generic": 7,
}


class ContextAssembler:
    """Deduplicate, order, and truncate chunks for prompt construction."""

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens
        self.max_chars = max_tokens * 4

    def assemble(self, chunks: List[Dict[str, Any]], query_type: str) -> Tuple[str, List[Dict[str, Any]]]:
        unique_chunks = self._dedupe(chunks)
        ordered_chunks = self._order(unique_chunks, query_type)
        selected_chunks = self._truncate(ordered_chunks)
        context = self._build_context(selected_chunks)
        return context, selected_chunks

    def _dedupe(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        output: List[Dict[str, Any]] = []
        for chunk in chunks:
            key = (chunk["metadata"].get("document_title"), chunk["content"].strip())
            if key in seen:
                continue
            seen.add(key)
            output.append(chunk)
        return output

    def _order(self, chunks: List[Dict[str, Any]], query_type: str) -> List[Dict[str, Any]]:
        def key_fn(chunk: Dict[str, Any]):
            chunk_type = str(chunk["metadata"].get("chunk_type", "generic"))
            priority = CHUNK_PRIORITY.get(chunk_type, 99)
            if query_type == "timeline" and chunk_type == "timeline":
                priority = -1
            return (priority, -float(chunk.get("rerank_score", chunk.get("score", 0))))

        return sorted(chunks, key=key_fn)

    def _truncate(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        selected = []
        total = 0
        for chunk in chunks:
            length = len(chunk["content"])
            if total + length > self.max_chars and selected:
                break
            selected.append(chunk)
            total += length
        return selected

    def _build_context(self, chunks: List[Dict[str, Any]]) -> str:
        blocks = []
        for idx, chunk in enumerate(chunks, start=1):
            meta = chunk["metadata"]
            blocks.append(
                "\n".join(
                    [
                        f"[Chunk {idx}]",
                        f"Title: {meta.get('document_title', 'Unknown')}",
                        f"Source Type: {meta.get('source_type', 'unknown')}",
                        f"Chunk Type: {meta.get('chunk_type', meta.get('section_title', 'generic'))}",
                        f"Service: {meta.get('service', meta.get('services', []))}",
                        f"Severity: {meta.get('severity', 'unknown')}",
                        "Content:",
                        chunk["content"],
                    ]
                )
            )
        return "\n\n".join(blocks)
