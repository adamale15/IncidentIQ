"""
Regression detection helpers.
"""
from typing import Dict, Optional


def detect_regression(current: Dict[str, float], baseline: Optional[Dict[str, float]], threshold: float) -> Dict[str, bool]:
    if not baseline:
        return {key: False for key in current.keys()}

    regressions: Dict[str, bool] = {}
    for key, current_value in current.items():
        baseline_value = baseline.get(key)
        if baseline_value in [None, 0]:
            regressions[key] = False
            continue
        regressions[key] = current_value < (baseline_value * (1 - threshold))
    return regressions
