"""
Query router for API endpoints.
"""
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.retrieval.hybrid import HybridRetriever

logger = logging.getLogger(__name__)

router = APIRouter()


class QueryRequest(BaseModel):
    """Query request model."""
    question: str = Field(..., description="Question to ask")
    workspace_id: str = Field(..., description="Workspace UUID")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional metadata filters")
    top_k: Optional[int] = Field(None, description="Number of results to return")


class RetrievedChunk(BaseModel):
    """Retrieved chunk model."""
    id: str
    content: str
    score: float
    dense_score: float
    sparse_score: float
    metadata: Dict[str, Any]


class QueryResponse(BaseModel):
    """Query response model."""
    question: str
    chunks: List[RetrievedChunk]
    latency_ms: int


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Query endpoint for hybrid retrieval.
    
    Args:
        request: Query request
        db: Database session
        
    Returns:
        Retrieved chunks with scores
    """
    import time
    start_time = time.time()
    
    try:
        # Parse workspace ID
        workspace_id = uuid.UUID(request.workspace_id)
        
        # Initialize retriever
        retriever = HybridRetriever()
        
        # Retrieve chunks
        chunks = await retriever.retrieve(
            query=request.question,
            workspace_id=workspace_id,
            filters=request.filters,
            top_k=request.top_k
        )
        
        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"Query completed in {latency_ms}ms, returned {len(chunks)} chunks")
        
        return QueryResponse(
            question=request.question,
            chunks=[RetrievedChunk(**chunk) for chunk in chunks],
            latency_ms=latency_ms
        )
        
    except ValueError as e:
        logger.error(f"Invalid workspace ID: {e}")
        raise HTTPException(status_code=400, detail="Invalid workspace ID")
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "query"}
