"""
Lightweight evaluation harness for the query pipeline.
"""
import statistics
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import EvalResult, EvalRun, EvalRunType
from app.evaluation.golden_dataset import load_golden_dataset
from app.evaluation.regression import detect_regression
from app.services.query_service import QueryService


class RagasRunner:
    """Heuristic eval harness that stores run and per-question metrics."""

    def __init__(self):
        self.query_service = QueryService()

    async def run(
        self,
        workspace_id: uuid.UUID,
        db_session: AsyncSession,
        run_type: str = "manual",
        dataset_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        dataset = load_golden_dataset(dataset_path)
        eval_results: List[Dict[str, Any]] = []

        for row in dataset:
            result = await self.query_service.run_query(
                question=row["question"],
                workspace_id=workspace_id,
                filters=row.get("metadata"),
                top_k=5,
            )
            metrics = self._score(row["expected_answer"], result["answer"], result["chunks"])
            eval_results.append(
                {
                    "question": row["question"],
                    "expected_answer": row["expected_answer"],
                    "generated_answer": result["answer"],
                    "retrieved_chunks": [
                        uuid.UUID(str(chunk["id"]))
                        for chunk in result["chunks"]
                        if self._looks_like_uuid(chunk["id"])
                    ],
                    "latency_ms": result["latency_ms"],
                    **metrics,
                }
            )

        aggregate = self._aggregate(eval_results)
        baseline = await self._load_baseline(workspace_id, db_session)
        regressions = detect_regression(aggregate, baseline, settings.EVAL_REGRESSION_THRESHOLD)

        eval_run = EvalRun(
            workspace_id=workspace_id,
            run_type=EvalRunType(run_type),
            faithfulness=aggregate["faithfulness"],
            answer_relevancy=aggregate["answer_relevancy"],
            context_precision=aggregate["context_precision"],
            context_recall=aggregate["context_recall"],
            total_questions=len(eval_results),
            avg_latency_ms=int(aggregate["avg_latency_ms"]),
        )
        db_session.add(eval_run)
        await db_session.flush()

        for row in eval_results:
            db_session.add(EvalResult(eval_run_id=eval_run.id, **row))

        await db_session.commit()

        return {
            "run_id": str(eval_run.id),
            "aggregate": aggregate,
            "regressions": regressions,
            "results": eval_results,
        }

    def _score(self, expected_answer: str, generated_answer: str, chunks: List[Dict[str, Any]]) -> Dict[str, float]:
        expected_terms = set(expected_answer.lower().split())
        generated_terms = set(generated_answer.lower().split())
        overlap = len(expected_terms & generated_terms)
        expected_size = max(len(expected_terms), 1)
        generated_size = max(len(generated_terms), 1)

        answer_relevancy = overlap / expected_size
        faithfulness = min(1.0, overlap / generated_size + 0.2)
        context_precision = min(1.0, len(chunks) / max(len(chunks), 1))
        context_recall = min(1.0, overlap / expected_size)

        return {
            "faithfulness": round(faithfulness, 4),
            "answer_relevancy": round(answer_relevancy, 4),
            "context_precision": round(context_precision, 4),
            "context_recall": round(context_recall, 4),
        }

    def _aggregate(self, results: List[Dict[str, Any]]) -> Dict[str, float]:
        return {
            "faithfulness": statistics.mean(row["faithfulness"] for row in results),
            "answer_relevancy": statistics.mean(row["answer_relevancy"] for row in results),
            "context_precision": statistics.mean(row["context_precision"] for row in results),
            "context_recall": statistics.mean(row["context_recall"] for row in results),
            "avg_latency_ms": statistics.mean(row["latency_ms"] for row in results),
        }

    async def _load_baseline(self, workspace_id: uuid.UUID, db_session: AsyncSession) -> Optional[Dict[str, float]]:
        stmt = (
            select(EvalRun)
            .where(EvalRun.workspace_id == workspace_id)
            .order_by(desc(EvalRun.created_at))
            .limit(1)
        )
        result = await db_session.execute(stmt)
        previous = result.scalar_one_or_none()
        if not previous:
            return None
        return {
            "faithfulness": previous.faithfulness or 0,
            "answer_relevancy": previous.answer_relevancy or 0,
            "context_precision": previous.context_precision or 0,
            "context_recall": previous.context_recall or 0,
            "avg_latency_ms": float(previous.avg_latency_ms or 0),
        }

    def _looks_like_uuid(self, value: Any) -> bool:
        try:
            uuid.UUID(str(value))
            return True
        except Exception:
            return False
