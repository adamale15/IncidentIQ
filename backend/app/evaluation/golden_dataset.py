"""
Golden dataset loader.
"""
import json
from typing import Any, Dict, List

from app.config import settings


def load_golden_dataset(path: str = None) -> List[Dict[str, Any]]:
    dataset_path = path or settings.EVAL_GOLDEN_DATASET_PATH
    with open(dataset_path, "r", encoding="utf-8") as handle:
        return json.load(handle)
