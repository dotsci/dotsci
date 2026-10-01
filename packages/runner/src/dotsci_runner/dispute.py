"""Dispute evidence: compare two run records of the same claim.

A challenger who disagrees with a runner has to say exactly which comparison differs
and by how much (see skill.md). This module produces that statement from two run
records, instead of leaving it to be written by hand.

Two runs are only comparable if they ran the same claim on the same pinned inputs in
the same pinned environment. If they did not, the difference is in the setup, not in
the result, and the evidence says so instead of reporting a disagreement.

Comparison values may differ slightly between honest reruns. What matters for the
verdict is whether the runs agree on each target's match status. The numeric
difference is always reported, so reviewers can see it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jsonschema import Draft202012Validator

from .manifest import _schema

AGREE = "agree"
DISAGREE = "disagree"
NOT_COMPARABLE = "not_comparable"


class RunRecordError(ValueError):
    """Raised when a run record does not match the run schema."""


def validate_run_record(record: Any) -> list[str]:
    """Human-readable schema errors for a run record, or an empty list."""
    if not isinstance(record, dict):
        return ["(root): run record must be a JSON object"]
    validator = Draft202012Validator(_schema("run.schema.json"))
    errors = sorted(validator.iter_errors(record), key=lambda e: list(e.absolute_path))
    return [f"{'.'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}" for e in errors]


@dataclass(frozen=True)
class FileDifference:
    name: str
    status: str  # "different", "only_a", "only_b"
    a: str | None = None
    b: str | None = None


@dataclass(frozen=True)
class ComparisonDifference:
    name: str
    status: str  # "agree", "differ", "only_a", "only_b"
    a_rerun: float | None = None
    b_rerun: float | None = None
    a_match: bool | None = None
    b_match: bool | None = None
    value_difference: float | None = None  # |a_rerun - b_rerun|


@dataclass(frozen=True)
class Evidence:
    verdict: str
    claim_id: str | None
    reasons: tuple[str, ...] = ()  # why the runs are not comparable, or why they disagree
    inputs: tuple[FileDifference, ...] = ()
    outputs: tuple[FileDifference, ...] = ()  # informational, never decisive
    comparisons: tuple[ComparisonDifference, ...] = field(default_factory=tuple)
    outcome_a: str | None = None
    outcome_b: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "claim_id": self.claim_id,
            "reasons": list(self.reasons),
            "outcome_a": self.outcome_a,
            "outcome_b": self.outcome_b,
            "inputs": [d.__dict__ for d in self.inputs],
            "outputs": [d.__dict__ for d in self.outputs],
            "comparisons": [c.__dict__ for c in self.comparisons],
        }


def _file_differences(a: dict[str, str], b: dict[str, str]) -> tuple[FileDifference, ...]:
    result = []
    for name in sorted(set(a) | set(b)):
        if name not in b:
            result.append(FileDifference(name, "only_a", a=a[name]))
        elif name not in a:
            result.append(FileDifference(name, "only_b", b=b[name]))
        elif a[name] != b[name]:
            result.append(FileDifference(name, "different", a=a[name], b=b[name]))
    return tuple(result)


def diff_runs(a: dict[str, Any], b: dict[str, Any]) -> Evidence:
    """Compare run record a (for example the runner's) with b (for example the challenger's).

    Both records must already be valid. Use validate_run_record first.
    """
    outcome_a, outcome_b = a["outcome"], b["outcome"]
    if a["claim_id"] != b["claim_id"]:
        return Evidence(
            NOT_COMPARABLE, None,
            reasons=(f"different claims: {a['claim_id']!r} and {b['claim_id']!r}",),
            outcome_a=outcome_a, outcome_b=outcome_b,
        )

    claim_id = a["claim_id"]
    inputs = _file_differences(a["input_hashes"], b["input_hashes"])
    outputs = _file_differences(a["output_hashes"], b["output_hashes"])

    setup_problems: list[str] = []
    for item in inputs:
        setup_problems.append(f"input {item.name} is {item.status.replace('_', ' ')}")
    for key in ("image_digest", "seed"):
        if a["environment"].get(key) != b["environment"].get(key):
            setup_problems.append(
                f"environment {key} differs: {a['environment'].get(key)!r} and {b['environment'].get(key)!r}"
            )

    by_a = {c["name"]: c for c in a["comparisons"]}
    by_b = {c["name"]: c for c in b["comparisons"]}
    comparisons: list[ComparisonDifference] = []
    for name in sorted(set(by_a) | set(by_b)):
        ca, cb = by_a.get(name), by_b.get(name)
        if ca is None:
            comparisons.append(ComparisonDifference(name, "only_b", b_rerun=cb["rerun"], b_match=cb["match"]))
        elif cb is None:
            comparisons.append(ComparisonDifference(name, "only_a", a_rerun=ca["rerun"], a_match=ca["match"]))
        else:
            comparisons.append(
                ComparisonDifference(
                    name,
                    "agree" if ca["match"] == cb["match"] else "differ",
                    a_rerun=ca["rerun"], b_rerun=cb["rerun"],
                    a_match=ca["match"], b_match=cb["match"],
                    value_difference=abs(ca["rerun"] - cb["rerun"]),
                )
            )

    if setup_problems:
        return Evidence(
            NOT_COMPARABLE, claim_id, reasons=tuple(setup_problems), inputs=inputs, outputs=outputs,
            comparisons=tuple(comparisons), outcome_a=outcome_a, outcome_b=outcome_b,
        )

    reasons: list[str] = []
    if outcome_a != outcome_b:
        reasons.append(f"outcomes differ: {outcome_a} and {outcome_b}")
    for c in comparisons:
        if c.status == "differ":
            reasons.append(
                f"{c.name}: a {'matches' if c.a_match else 'does not match'} the published value, "
                f"b {'matches' if c.b_match else 'does not match'} "
                f"(a={c.a_rerun}, b={c.b_rerun}, difference {c.value_difference})"
            )
        elif c.status in ("only_a", "only_b"):
            reasons.append(f"{c.name}: only reported by {c.status[-1]}")
    return Evidence(
        DISAGREE if reasons else AGREE, claim_id, reasons=tuple(reasons), inputs=inputs, outputs=outputs,
        comparisons=tuple(comparisons), outcome_a=outcome_a, outcome_b=outcome_b,
    )


def render(evidence: Evidence) -> str:
    """Plain text summary suitable for a challenge's notes."""
    lines = [f"verdict: {evidence.verdict}", f"claim: {evidence.claim_id}"]
    lines.append(f"outcomes: a={evidence.outcome_a}, b={evidence.outcome_b}")
    for reason in evidence.reasons:
        lines.append(f"- {reason}")
    if evidence.verdict == AGREE:
        lines.append("both runs agree on every comparison")
    for c in evidence.comparisons:
        if c.status in ("agree", "differ"):
            lines.append(f"  {c.name}: a={c.a_rerun} b={c.b_rerun} difference={c.value_difference} [{c.status}]")
    if evidence.outputs:
        lines.append(f"output files that differ (informational): {len(evidence.outputs)}")
    return "\n".join(lines)
