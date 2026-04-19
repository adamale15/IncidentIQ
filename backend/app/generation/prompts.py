"""
Prompt templates for answer generation.
"""
from typing import Dict


SYSTEM_PROMPT = (
    "You are an SRE incident assistant. Answer only from the provided context. "
    "If the context is insufficient, say so clearly. "
    "Every factual claim must include a citation in the format [Source: document_title]."
)


QUERY_TYPE_INSTRUCTIONS: Dict[str, str] = {
    "simple_lookup": "Answer directly and concisely. Prefer procedural steps when available.",
    "causal_reasoning": "Explain the likely root cause and chain of events from the retrieved evidence.",
    "comparison": "Compare incidents by similarities, differences, and resolution patterns.",
    "timeline": "Reconstruct the incident in chronological order.",
}


def build_prompt(question: str, context: str, query_type: str) -> str:
    instruction = QUERY_TYPE_INSTRUCTIONS.get(query_type, QUERY_TYPE_INSTRUCTIONS["simple_lookup"])
    return "\n\n".join(
        [
            SYSTEM_PROMPT,
            f"Instruction: {instruction}",
            f"Context:\n{context}",
            f"Question: {question}",
            "Answer:",
        ]
    )
