"""Compare rerun values against published targets."""

from __future__ import annotations

import math
from typing import Any

REPRODUCED = "reproduced"
NOT_REPRODUCED = "not_reproduced"


def within_tolerance(published: float, rerun: float, tolerance: dict[str, Any]) -> bool:
    """Apply an absolute or relative tolerance.

    absolute: |rerun - published| <= value
    relative: |rerun - published| <= value * |published|
    Non-finite rerun values never match.
    """
    if not math.isfinite(rerun):
        return False
    difference = abs(rerun - published)
    kind = tolerance["type"]
    value = tolerance["value"]
    if kind == "absolute":
        return difference <= value
    if kind == "relative":
        return difference <= value * abs(published)
    raise ValueError(f"unknown tolerance type: {kind}")


def compare_targets(
    targets: list[dict[str, Any]], results: dict[str, float]
) -> tuple[list[dict[str, Any]], str]:
    """Compare every target to the rerun results.

    Returns (comparisons, outcome). A target missing from results counts as not matched,
    so a run cannot reach 'reproduced' by leaving values out.
    """
    comparisons: list[dict[str, Any]] = []
    all_match = True
    for target in targets:
        name = target["name"]
        published = float(target["published"])
        tolerance = target["tolerance"]
        if name not in results:
            all_match = False
            comparisons.append(
                {
                    "name": name,
                    "published": published,
                    "rerun": float("nan"),
                    "difference": float("nan"),
                    "tolerance": tolerance,
                    "match": False,
                }
            )
            continue
        rerun = float(results[name])
        match = within_tolerance(published, rerun, tolerance)
        all_match = all_match and match
        comparisons.append(
            {
                "name": name,
                "published": published,
                "rerun": rerun,
                "difference": rerun - published,
                "tolerance": tolerance,
                "match": match,
            }
        )
    return comparisons, (REPRODUCED if all_match else NOT_REPRODUCED)
