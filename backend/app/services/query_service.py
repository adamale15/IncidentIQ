"""
Query orchestration service.
"""
import json
import time
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

from app.generation.citations import attach_citations
from app.generation.llm import LLMGenerator
from app.retrieval.context import ContextAssembler
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.query_parser import QueryParser
from app.retrieval.reranker import CrossEncoderReranker


class QueryService:
    """Full query pipeline orchestration."""

    def __init__(self):
        self.parser = QueryParser()
        self.retriever = HybridRetriever()
        self.reranker = CrossEncoderReranker()
        self.context_assembler = ContextAssembler()
        self.generator = LLMGenerator()

    async def run_query(
        self,
        question: str,
        workspace_id: uuid.UUID,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        started = time.time()
        analysis = self.parser.parse(question)

        merged_filters = dict(analysis["filters"])
        if filters:
            merged_filters.update(filters)

        retrieved = await self.retriever.retrieve(
            query=analysis["rewritten_query"],
            workspace_id=workspace_id,
            filters=merged_filters,
            top_k=top_k,
        )
        reranked = await self.reranker.rerank(
            query=analysis["rewritten_query"],
            chunks=retrieved,
            top_k=top_k or 5,
        )
        context, selected_chunks = self.context_assembler.assemble(reranked, analysis["query_type"])
        generation = await self.generator.generate_answer(question, context, analysis["query_type"])
        answer = generation["answer"]
        citations = attach_citations(answer, selected_chunks)

        return {
            "question": question,
            "analysis": analysis,
            "filters": merged_filters,
            "chunks": selected_chunks,
            "context": context,
            "answer": answer,
            "citations": citations,
            "latency_ms": int((time.time() - started) * 1000),
            "model_used": generation["model_used"],
        }

    async def stream_query(
        self,
        question: str,
        workspace_id: uuid.UUID,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        result = await self.run_query(question, workspace_id, filters=filters, top_k=top_k)
        yield self._sse("meta", {"analysis": result["analysis"], "latency_ms": result["latency_ms"]})
        async for chunk in self.generator.stream_answer(question, result["context"], result["analysis"]["query_type"]):
            yield self._sse("chunk", {"text": chunk})
        yield self._sse(
            "done",
            {
                "answer": result["answer"],
                "chunks": result["chunks"],
                "citations": result["citations"],
                "latency_ms": result["latency_ms"],
                "model_used": result["model_used"],
            },
        )

    def _sse(self, event: str, payload: Dict[str, Any]) -> str:
        return "event: %s\ndata: %s\n\n" % (event, json.dumps(payload, default=str))
