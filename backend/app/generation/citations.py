"""
Citation extraction helpers.
"""
import re
from typing import Any, Dict, List


CITATION_PATTERN = re.compile(r"\[Source:\s*([^\]]+)\]")


def extract_citations(answer: str) -> List[str]:
    return CITATION_PATTERN.findall(answer)


def attach_citations(answer: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    citations = extract_citations(answer)
    attached = []
    for citation in citations:
        for chunk in chunks:
            title = chunk["metadata"].get("document_title", "")
            if title and title in citation:
                attached.append(
                    {
                        "citation": citation,
                        "chunk_id": str(chunk["id"]),
                        "document_title": title,
                    }
                )
                break
    return attached
