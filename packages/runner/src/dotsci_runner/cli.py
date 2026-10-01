"""Command line interface for the DotSci runner toolkit."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from . import __version__
from .compare import REPRODUCED, compare_targets
from .hashing import verify_inputs
from .job import preflight, run_job
from .manifest import ManifestError, load_manifest, manifest_hash
from .record import build_run_record
from .runlog import RunLog
from .sandbox import Limits, SandboxError, build_docker_command


class _Tee:
    """Write log lines to several streams."""

    def __init__(self, *streams) -> None:
        self._streams = streams

    def write(self, text: str) -> int:
        for stream in self._streams:
            stream.write(text)
        return len(text)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"ok: {manifest['claim_id']}")
    return 0


def _cmd_hash(args: argparse.Namespace) -> int:
    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    digest = manifest_hash(manifest)
    print(f"0x{digest}" if args.bytes32 else f"sha256:{digest}")
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


def _emit_record(record: dict, out: str | None) -> None:
    text = json.dumps(record, indent=2)
    if out:
        Path(out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


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
        name = comparison["name"]
        if comparison["match"]:
            log.info("compare", f"{name} within tolerance")
        else:
            log.warn("compare", f"{name} outside tolerance or missing")
    log.info("outcome", outcome)

    record = build_run_record(manifest, comparisons, outcome, job_id=args.job_id, role=args.role)
    _emit_record(record, args.out)
    return 0 if outcome == REPRODUCED else 1


def _cmd_run(args: argparse.Namespace) -> int:
    log_file = open(args.log_file, "a", encoding="utf-8") if args.log_file else None
    log = RunLog(_Tee(sys.stderr, log_file) if log_file else sys.stderr)
    try:
        try:
            manifest = load_manifest(args.manifest)
        except ManifestError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        limits = Limits(cpus=args.cpus, memory=args.memory, pids=args.pids, tmp_size=args.tmp_size)

        if args.dry_run:
            problems, _ = preflight(
                manifest,
                code_dir=args.code_dir,
                data_dir=args.data_dir,
                image_ref=args.image,
                git_bin=args.git,
            )
            if problems:
                for problem in problems:
                    log.error("preflight", problem)
                return 1
            log.info("preflight", "datasets, code checkout, and image digest verified")
            cmd = build_docker_command(
                image_ref=args.image,
                code_dir=args.code_dir,
                data_dir=args.data_dir,
                out_dir=args.out_dir,
                command=manifest["entrypoint"]["command"],
                name="dotsci-dry-run",
                working_dir=manifest["entrypoint"].get("working_dir"),
                seed=manifest["environment"].get("seed"),
                limits=limits,
                runtime=args.runtime,
                docker_bin=args.docker,
            )
            print(shlex.join(cmd))
            return 0

        record = run_job(
            manifest,
            code_dir=args.code_dir,
            data_dir=args.data_dir,
            out_dir=args.out_dir,
            image_ref=args.image,
            job_id=args.job_id,
            role=args.role,
            limits=limits,
            runtime=args.runtime,
            log=log,
            docker_bin=args.docker,
            git_bin=args.git,
            grace_seconds=args.grace_seconds,
        )
        _emit_record(record, args.record)
        return 0 if record["outcome"] == REPRODUCED else 1
    except SandboxError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        if log_file:
            log_file.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dotsci-runner", description="DotSci runner toolkit")
    parser.add_argument("--version", action="version", version=f"dotsci-runner {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="validate a manifest against the schema")
    p_validate.add_argument("manifest")
    p_validate.set_defaults(func=_cmd_validate)

    p_hash = sub.add_parser("hash", help="print the canonical hash of a manifest (the value registered for a claim)")
    p_hash.add_argument("manifest")
    p_hash.add_argument("--bytes32", action="store_true", help="print as 0x-prefixed hex, ready for a contract call")
    p_hash.set_defaults(func=_cmd_hash)

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

    p_run = sub.add_parser("run", help="verify inputs, run the entrypoint in the sandbox, and record the result")
    p_run.add_argument("manifest")
    p_run.add_argument("--code-dir", required=True, help="clean checkout of the pinned commit")
    p_run.add_argument("--data-dir", required=True, help="directory holding the manifest's datasets")
    p_run.add_argument("--out-dir", required=True, help="empty directory for the analysis output")
    p_run.add_argument("--image", required=True, help="image reference pinned by digest: repository@sha256:...")
    p_run.add_argument("--job-id", default="local")
    p_run.add_argument("--role", choices=["runner", "challenger"], default="runner")
    p_run.add_argument("--record", help="write the run record here instead of stdout")
    p_run.add_argument("--log-file", help="also append JSONL logs to this file")
    p_run.add_argument("--cpus", type=float, default=2.0)
    p_run.add_argument("--memory", default="4g")
    p_run.add_argument("--pids", type=int, default=256)
    p_run.add_argument("--tmp-size", default="512m")
    p_run.add_argument("--runtime", help="container runtime, for example runsc for gVisor")
    p_run.add_argument("--docker", default="docker", help="docker executable")
    p_run.add_argument("--git", default="git", help="git executable")
    p_run.add_argument("--grace-seconds", type=int, default=10)
    p_run.add_argument("--dry-run", action="store_true", help="run the checks and print the docker command only")
    p_run.set_defaults(func=_cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
