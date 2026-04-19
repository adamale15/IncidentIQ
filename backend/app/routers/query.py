"""
Query router for API endpoints.
"""
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.query_service import QueryService

router = APIRouter()


class QueryRequest(BaseModel):
    question: str = Field(..., description="Question to ask")
    workspace_id: str = Field(..., description="Workspace UUID")
    filters: Optional[Dict[str, Any]] = Field(default=None)
    top_k: Optional[int] = Field(default=None)
    stream: bool = Field(default=False)


class RetrievedChunk(BaseModel):
    id: str
    content: str
    score: float
    dense_score: float = 0.0
    sparse_score: float = 0.0
    rerank_score: float = 0.0
    metadata: Dict[str, Any]


class QueryResponse(BaseModel):
    question: str
    answer: str
    analysis: Dict[str, Any]
    chunks: List[RetrievedChunk]
    citations: List[Dict[str, Any]]
    latency_ms: int
    model_used: str


@router.post("/query")
async def query_endpoint(request: QueryRequest):
    try:
        workspace_id = uuid.UUID(request.workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    service = QueryService()

    if request.stream:
        generator = service.stream_query(
            question=request.question,
            workspace_id=workspace_id,
            filters=request.filters,
            top_k=request.top_k,
        )
        return StreamingResponse(generator, media_type="text/event-stream")

    try:
        result = await service.run_query(
            question=request.question,
            workspace_id=workspace_id,
            filters=request.filters,
            top_k=request.top_k,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

    return QueryResponse(
        question=result["question"],
        answer=result["answer"],
        analysis=result["analysis"],
        chunks=[RetrievedChunk(**chunk) for chunk in result["chunks"]],
        citations=result["citations"],
        latency_ms=result["latency_ms"],
        model_used=result["model_used"],
    )


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "query"}
