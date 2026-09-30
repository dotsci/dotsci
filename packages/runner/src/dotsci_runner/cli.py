"""Command line interface for the DotSci runner toolkit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from . import __version__
from .compare import REPRODUCED, compare_targets
from .hashing import verify_inputs
from .runlog import RunLog
from .manifest import ManifestError, _schema, load_manifest


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"ok: {manifest['claim_id']}")
    return 0


def _cmd_verify_inputs(args: argparse.Namespace) -> int:
    log = RunLog()
    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    checks = verify_inputs(manifest, args.data_dir)
    failed = 0
    for check in checks:
        if check.ok:
            log.info("input_check", f"{check.name} hash ok", {"sha256": check.actual})
        else:
            failed += 1
            log.error(
                "input_check",
                f"{check.name} {check.reason}",
                {"expected": check.expected, "actual": check.actual},
            )
    if failed:
        log.error("outcome", "input_mismatch", {"failed": failed})
        return 1
    log.info("outcome", "all inputs verified", {"count": len(checks)})
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    log = RunLog()
    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        results = json.loads(Path(args.results).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"could not read results: {exc}", file=sys.stderr)
        return 1
    if not isinstance(results, dict):
        print("results must be a JSON object mapping target name to value", file=sys.stderr)
        return 1

    comparisons, outcome = compare_targets(manifest["targets"], results)
    for comparison in comparisons:
        step = "compare"
        name = comparison["name"]
        if comparison["match"]:
            log.info(step, f"{name} within tolerance")
        else:
            log.warn(step, f"{name} outside tolerance or missing")
    log.info("outcome", outcome)

    record = {
        "spec_version": "0.1",
        "job_id": args.job_id,
        "claim_id": manifest["claim_id"],
        "role": args.role,
        "input_hashes": {},
        "output_hashes": {},
        "environment": {
            "image_digest": manifest["environment"]["image_digest"],
            **({"seed": manifest["environment"]["seed"]} if "seed" in manifest["environment"] else {}),
        },
        "comparisons": [
            {**c, "rerun": _finite(c["rerun"]), "difference": _finite(c["difference"])}
            for c in comparisons
        ],
        "outcome": outcome,
        "notes": "",
    }

    text = json.dumps(record, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if outcome == REPRODUCED else 1


def _finite(value: float) -> float:
    """JSON has no NaN. A missing result is recorded as 0.0 and marked match=false."""
    return value if value == value and value not in (float("inf"), float("-inf")) else 0.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dotsci-runner", description="DotSci runner toolkit")
    parser.add_argument("--version", action="version", version=f"dotsci-runner {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="validate a manifest against the schema")
    p_validate.add_argument("manifest")
    p_validate.set_defaults(func=_cmd_validate)

    p_inputs = sub.add_parser("verify-inputs", help="check input file hashes against a manifest")
    p_inputs.add_argument("manifest")
    p_inputs.add_argument("--data-dir", required=True)
    p_inputs.set_defaults(func=_cmd_verify_inputs)

    p_compare = sub.add_parser("compare", help="compare rerun values to manifest targets")
    p_compare.add_argument("manifest")
    p_compare.add_argument("--results", required=True)
    p_compare.add_argument("--job-id", default="local")
    p_compare.add_argument("--role", choices=["runner", "challenger"], default="runner")
    p_compare.add_argument("--out")
    p_compare.set_defaults(func=_cmd_compare)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
