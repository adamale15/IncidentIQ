"""
Evaluation router for running and viewing evals.
"""
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvalResult, EvalRun
from app.db.session import get_db
from app.evaluation.ragas_runner import RagasRunner

router = APIRouter()


class EvalRunRequest(BaseModel):
    workspace_id: str = Field(..., description="Workspace UUID")
    run_type: str = Field(default="manual")
    dataset_path: Optional[str] = Field(default=None)


@router.post("/eval/run")
async def run_eval(request: EvalRunRequest, db: AsyncSession = Depends(get_db)):
    try:
        workspace_id = uuid.UUID(request.workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    runner = RagasRunner()
    result = await runner.run(
        workspace_id=workspace_id,
        db_session=db,
        run_type=request.run_type,
        dataset_path=request.dataset_path,
    )
    return result


@router.get("/eval/runs")
async def list_eval_runs(workspace_id: str, db: AsyncSession = Depends(get_db)):
    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID")

    stmt = (
        select(EvalRun)
        .where(EvalRun.workspace_id == workspace_uuid)
        .order_by(desc(EvalRun.created_at))
    )
    result = await db.execute(stmt)
    runs = result.scalars().all()
    return [
        {
            "id": str(run.id),
            "run_type": run.run_type.value,
            "faithfulness": run.faithfulness,
            "answer_relevancy": run.answer_relevancy,
            "context_precision": run.context_precision,
            "context_recall": run.context_recall,
            "total_questions": run.total_questions,
            "avg_latency_ms": run.avg_latency_ms,
            "created_at": run.created_at,
        }
        for run in runs
    ]


@router.get("/eval/runs/{run_id}")
async def get_eval_run(run_id: str, db: AsyncSession = Depends(get_db)):
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID")

    run_stmt = select(EvalRun).where(EvalRun.id == run_uuid)
    run_result = await db.execute(run_stmt)
    run = run_result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Eval run not found")

    result_stmt = select(EvalResult).where(EvalResult.eval_run_id == run_uuid)
    result_result = await db.execute(result_stmt)
    rows = result_result.scalars().all()

    return {
        "run": {
            "id": str(run.id),
            "workspace_id": str(run.workspace_id),
            "run_type": run.run_type.value,
            "faithfulness": run.faithfulness,
            "answer_relevancy": run.answer_relevancy,
            "context_precision": run.context_precision,
            "context_recall": run.context_recall,
            "total_questions": run.total_questions,
            "avg_latency_ms": run.avg_latency_ms,
            "created_at": run.created_at,
        },
        "results": [
            {
                "id": str(row.id),
                "question": row.question,
                "expected_answer": row.expected_answer,
                "generated_answer": row.generated_answer,
                "retrieved_chunks": [str(chunk_id) for chunk_id in (row.retrieved_chunks or [])],
                "faithfulness": row.faithfulness,
                "answer_relevancy": row.answer_relevancy,
                "context_precision": row.context_precision,
                "context_recall": row.context_recall,
                "latency_ms": row.latency_ms,
            }
            for row in rows
        ],
    }
