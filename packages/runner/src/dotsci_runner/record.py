"""Build run records that match spec/run.schema.json."""

from __future__ import annotations

import math
from typing import Any


def _finite(value: float) -> float:
    """JSON has no NaN. A missing result is recorded as 0.0 with match=false and a note."""
    return value if math.isfinite(value) else 0.0


def build_run_record(
    manifest: dict[str, Any],
    comparisons: list[dict[str, Any]],
    outcome: str,
    *,
    job_id: str = "local",
    role: str = "runner",
    input_hashes: dict[str, str] | None = None,
    output_hashes: dict[str, str] | None = None,
    notes: str = "",
    logs_uri: str | None = None,
) -> dict[str, Any]:
    missing = [c["name"] for c in comparisons if not math.isfinite(c["rerun"])]
    if missing:
        addition = "no rerun value for: " + ", ".join(missing)
        notes = f"{notes}; {addition}" if notes else addition

    environment: dict[str, Any] = {"image_digest": manifest["environment"]["image_digest"]}
    if "seed" in manifest["environment"]:
        environment["seed"] = manifest["environment"]["seed"]

    record: dict[str, Any] = {
        "spec_version": "0.1",
        "job_id": job_id,
        "claim_id": manifest["claim_id"],
        "role": role,
        "input_hashes": input_hashes or {},
        "output_hashes": output_hashes or {},
        "environment": environment,
        "comparisons": [
            {**c, "rerun": _finite(c["rerun"]), "difference": _finite(c["difference"])}
            for c in comparisons
        ],
        "outcome": outcome,
        "notes": notes,
    }
    if logs_uri:
        record["logs_uri"] = logs_uri
    return record
