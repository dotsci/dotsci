"""Calibrate tolerances from repeated honest reruns of one claim.

A manifest tolerance says what "the same" means. Setting it by guesswork leads to two
failures: too tight, and honest reruns disagree (a spec_issue); too loose, and a wrong
result passes. This module looks at several run records of the same claim and reports,
per target, how much honest reruns actually vary and what that implies.

It never changes a manifest. The tolerance is part of the claim and stays a human
decision (see docs/writing-a-claim.md). The output is evidence for that decision.

Per target the verdict is one of:

- stable_match: every rerun is within the declared tolerance of the published value.
- stable_miss: every rerun is outside it. The reruns agree with each other, so noise is
  not the explanation and a wider tolerance would be tuning to an outcome.
- unstable: some reruns match and some do not. Honest reruns of the same manifest
  disagree, which is a spec_issue. Pin more, or widen the tolerance with a reason.

The suggested tolerance is the smallest one under which every observed rerun would match
the published value, multiplied by a margin the caller chooses. With few reruns it is a
lower bound, and the report says so.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any

from .dispute import NOT_COMPARABLE, diff_runs, validate_run_record

STABLE_MATCH = "stable_match"
STABLE_MISS = "stable_miss"
UNSTABLE = "unstable"

# Fewer reruns than this and the observed spread says little about the true spread.
MIN_RERUNS_FOR_CONFIDENCE = 5


class CalibrationError(ValueError):
    """Raised when the run records cannot be calibrated together."""


@dataclass(frozen=True)
class TargetCalibration:
    name: str
    published: float
    tolerance: dict[str, Any]
    n: int
    mean: float
    stdev: float | None  # None with fewer than two reruns
    minimum: float
    maximum: float
    spread: float  # maximum - minimum
    bias: float  # mean - published
    max_deviation: float  # largest |rerun - published|
    matches: int
    verdict: str
    suggested_absolute: float
    suggested_relative: float | None  # None when published is 0

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class Calibration:
    claim_id: str
    runs: int
    targets: tuple[TargetCalibration, ...]
    warnings: tuple[str, ...]

    @property
    def spec_issue(self) -> bool:
        return any(t.verdict == UNSTABLE for t in self.targets)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "runs": self.runs,
            "spec_issue": self.spec_issue,
            "warnings": list(self.warnings),
            "targets": [t.to_dict() for t in self.targets],
        }


def calibrate(records: list[dict[str, Any]], *, margin: float) -> Calibration:
    """Summarize repeated reruns of one claim.

    margin multiplies the smallest tolerance that would have matched every rerun. It
    must be at least 1. A margin of 1 fits the observed reruns exactly and leaves no
    room for the next one.
    """
    if not (math.isfinite(margin) and margin >= 1):
        raise CalibrationError("margin must be a finite number of at least 1")
    if len(records) < 2:
        raise CalibrationError("need at least two run records to see any variation")

    for index, record in enumerate(records):
        errors = validate_run_record(record)
        if errors:
            raise CalibrationError(f"run {index + 1} is not a valid run record: {errors[0]}")

    first = records[0]
    for index, record in enumerate(records[1:], start=2):
        evidence = diff_runs(first, record)
        if evidence.verdict == NOT_COMPARABLE:
            raise CalibrationError(f"run {index} is not comparable with run 1: {'; '.join(evidence.reasons)}")

    names = [c["name"] for c in first["comparisons"]]
    for index, record in enumerate(records[1:], start=2):
        if [c["name"] for c in record["comparisons"]] != names:
            raise CalibrationError(f"run {index} reports different targets than run 1")

    targets = []
    for position, name in enumerate(names):
        rows = [record["comparisons"][position] for record in records]
        values = [row["rerun"] for row in rows]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
            raise CalibrationError(f"target {name!r} has a non-finite rerun value, so it cannot be calibrated")
        published = rows[0]["published"]
        matches = sum(1 for row in rows if row["match"])
        deviations = [abs(v - published) for v in values]
        max_dev = max(deviations)

        if matches == len(rows):
            verdict = STABLE_MATCH
        elif matches == 0:
            verdict = STABLE_MISS
        else:
            verdict = UNSTABLE

        mean = statistics.fmean(values)
        suggested_abs = max_dev * margin
        suggested_rel = None if published == 0 else suggested_abs / abs(published)
        targets.append(
            TargetCalibration(
                name=name, published=published, tolerance=rows[0]["tolerance"], n=len(values),
                mean=mean, stdev=statistics.stdev(values) if len(values) > 1 else None,
                minimum=min(values), maximum=max(values), spread=max(values) - min(values),
                bias=mean - published, max_deviation=max_dev, matches=matches, verdict=verdict,
                suggested_absolute=suggested_abs, suggested_relative=suggested_rel,
            )
        )

    warnings = []
    if len(records) < MIN_RERUNS_FOR_CONFIDENCE:
        warnings.append(
            f"only {len(records)} reruns: the suggested tolerances are lower bounds, "
            f"use at least {MIN_RERUNS_FOR_CONFIDENCE} before relying on them"
        )
    if all(t.spread == 0 for t in targets):
        warnings.append("every rerun was identical, so this analysis looks deterministic under the pinned seed")
    return Calibration(first["claim_id"], len(records), tuple(targets), tuple(warnings))


def render(calibration: Calibration) -> str:
    """Plain text report."""
    lines = [f"claim: {calibration.claim_id}", f"reruns: {calibration.runs}"]
    for t in calibration.targets:
        kind, value = t.tolerance["type"], t.tolerance["value"]
        lines.append(f"{t.name}: {t.verdict} ({t.matches}/{t.n} within declared {kind} tolerance {value})")
        lines.append(f"  published {t.published}, mean {t.mean:.6g}, range [{t.minimum:.6g}, {t.maximum:.6g}], spread {t.spread:.6g}")
        suggestion = f"  smallest tolerance matching every rerun: absolute {t.suggested_absolute:.6g}"
        if t.suggested_relative is not None:
            suggestion += f" or relative {t.suggested_relative:.6g}"
        lines.append(suggestion)
        if t.verdict == UNSTABLE:
            lines.append("  honest reruns disagree on this target: spec_issue")
        elif t.verdict == STABLE_MISS:
            lines.append("  reruns agree with each other and miss the published value: widening would be tuning")
    for warning in calibration.warnings:
        lines.append(f"warning: {warning}")
    lines.append("spec_issue: " + ("yes" if calibration.spec_issue else "no"))
    return "\n".join(lines)

