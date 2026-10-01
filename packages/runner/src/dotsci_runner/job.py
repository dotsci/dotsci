"""Run a replication job end to end: verify, execute in the sandbox, compare, record."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .compare import compare_targets
from .hashing import sha256_file, verify_inputs
from .record import build_run_record
from .runlog import RunLog
from .sandbox import (
    DEFAULT_TIMEOUT_SECONDS,
    Limits,
    SandboxError,
    build_docker_command,
    check_code_checkout,
    check_image,
    container_name,
    run_in_sandbox,
)

MAX_RESULTS_BYTES = 1024 * 1024
DOCKER_DAEMON_ERROR = 125


def preflight(
    manifest: dict[str, Any],
    *,
    code_dir: str | Path,
    data_dir: str | Path,
    image_ref: str,
    git_bin: str = "git",
) -> tuple[list[str], dict[str, str]]:
    """Verify datasets, code checkout, and image digest. Returns (problems, input_hashes)."""
    problems: list[str] = []
    input_hashes: dict[str, str] = {}
    for check in verify_inputs(manifest, data_dir):
        if check.ok and check.actual:
            input_hashes[check.name] = check.actual
        else:
            problems.append(f"dataset {check.name}: {check.reason}")
    problem = check_code_checkout(code_dir, manifest["code"]["commit"], git_bin=git_bin)
    if problem:
        problems.append(f"code: {problem}")
    problem = check_image(image_ref, manifest["environment"]["image_digest"])
    if problem:
        problems.append(f"image: {problem}")
    return problems, input_hashes


def inspect_output(out_dir: Path) -> tuple[dict[str, float] | None, dict[str, str], list[str]]:
    """Read results.json and hash every output file. Symlinks are rejected, never followed."""
    problems: list[str] = []
    output_hashes: dict[str, str] = {}
    for root, dirs, files in os.walk(out_dir, followlinks=False):
        for entry in [*dirs, *files]:
            path = Path(root) / entry
            if path.is_symlink():
                problems.append(f"output contains a symlink: {path.relative_to(out_dir).as_posix()}")
        if not problems:
            for filename in files:
                path = Path(root) / filename
                output_hashes[path.relative_to(out_dir).as_posix()] = sha256_file(path)
    if problems:
        return None, {}, problems

    results_path = out_dir / "results.json"
    if not results_path.is_file():
        return None, output_hashes, ["results.json was not written to the output directory"]
    if results_path.stat().st_size > MAX_RESULTS_BYTES:
        return None, output_hashes, ["results.json is larger than 1 MiB"]
    try:
        results = json.loads(results_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, output_hashes, [f"results.json could not be read: {exc}"]
    if not isinstance(results, dict) or not all(
        isinstance(v, (int, float)) and not isinstance(v, bool) for v in results.values()
    ):
        return None, output_hashes, ["results.json must be an object mapping target names to numbers"]
    return results, output_hashes, []


def run_job(
    manifest: dict[str, Any],
    *,
    code_dir: str | Path,
    data_dir: str | Path,
    out_dir: str | Path,
    image_ref: str,
    job_id: str = "local",
    role: str = "runner",
    limits: Limits | None = None,
    runtime: str | None = None,
    log: RunLog | None = None,
    docker_bin: str = "docker",
    git_bin: str = "git",
    grace_seconds: int = 10,
) -> dict[str, Any]:
    """Run one job and return a run record. Raises SandboxError for usage or docker problems."""
    log = log or RunLog()
    limits = limits or Limits()
    out = Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise SandboxError(f"output directory must be empty: {out}")
    out.mkdir(parents=True, exist_ok=True)

    def record(outcome: str, *, comparisons=None, input_hashes=None, output_hashes=None, notes="") -> dict[str, Any]:
        log.info("outcome", outcome, {"notes": notes} if notes else None)
        return build_run_record(
            manifest,
            comparisons or [],
            outcome,
            job_id=job_id,
            role=role,
            input_hashes=input_hashes,
            output_hashes=output_hashes,
            notes=notes,
        )

    problems, input_hashes = preflight(
        manifest, code_dir=code_dir, data_dir=data_dir, image_ref=image_ref, git_bin=git_bin
    )
    if problems:
        for problem in problems:
            log.error("preflight", problem)
        return record("input_mismatch", notes="; ".join(problems))
    log.info("preflight", "datasets, code checkout, and image digest verified", {"datasets": len(input_hashes)})

    timeout = manifest["environment"].get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    name = container_name(job_id)
    cmd = build_docker_command(
        image_ref=image_ref,
        code_dir=code_dir,
        data_dir=data_dir,
        out_dir=out,
        command=manifest["entrypoint"]["command"],
        name=name,
        working_dir=manifest["entrypoint"].get("working_dir"),
        seed=manifest["environment"].get("seed"),
        limits=limits,
        runtime=runtime,
        docker_bin=docker_bin,
    )
    log.info(
        "sandbox_start",
        "starting container",
        {"name": name, "image": image_ref, "timeout_seconds": timeout, "cpus": limits.cpus, "memory": limits.memory},
    )
    result = run_in_sandbox(cmd, name=name, timeout_seconds=timeout, docker_bin=docker_bin, grace_seconds=grace_seconds)
    log.info(
        "sandbox_exit",
        "container finished",
        {
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "stdout_tail": result.stdout_tail,
            "stderr_tail": result.stderr_tail,
        },
    )

    if result.exit_code == DOCKER_DAEMON_ERROR:
        raise SandboxError(f"docker could not start the container: {result.stderr_tail.strip()[-500:]}")
    if result.timed_out:
        return record("spec_issue", input_hashes=input_hashes, notes=f"entrypoint timed out after {timeout} seconds")
    if result.exit_code != 0:
        return record("spec_issue", input_hashes=input_hashes, notes=f"entrypoint exited with code {result.exit_code}")

    results, output_hashes, problems = inspect_output(out)
    if problems:
        for problem in problems:
            log.error("output_check", problem)
        return record("spec_issue", input_hashes=input_hashes, output_hashes=output_hashes, notes="; ".join(problems))

    assert results is not None
    comparisons, outcome = compare_targets(manifest["targets"], results)
    for comparison in comparisons:
        if comparison["match"]:
            log.info("compare", f"{comparison['name']} within tolerance")
        else:
            log.warn("compare", f"{comparison['name']} outside tolerance or missing")
    return record(outcome, comparisons=comparisons, input_hashes=input_hashes, output_hashes=output_hashes)
