"""Run a manifest's entrypoint inside a locked-down container.

No analysis code runs on the host. The host verifies inputs, builds a docker command, runs it,
and inspects the output directory afterwards.
"""

from __future__ import annotations

import re
import secrets
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

WORK_DIR = "/work"
CONTAINER_USER = "10001:10001"
DEFAULT_TIMEOUT_SECONDS = 3600
_DIGEST_RE = re.compile(r"@(sha256:[a-f0-9]{64})$")
_TAIL_CHARS = 16 * 1024


class SandboxError(RuntimeError):
    """A usage or environment problem (bad paths, docker unavailable). Not a verification outcome."""


@dataclass(frozen=True)
class Limits:
    cpus: float = 2.0
    memory: str = "4g"
    pids: int = 256
    tmp_size: str = "512m"


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int
    timed_out: bool
    stdout_tail: str
    stderr_tail: str


def container_name(job_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "-", job_id)[:40] or "job"
    return f"dotsci-{cleaned}-{secrets.token_hex(4)}"


def image_digest(image_ref: str) -> str | None:
    match = _DIGEST_RE.search(image_ref)
    return match.group(1) if match else None


def check_image(image_ref: str, expected_digest: str) -> str | None:
    """Return a problem description, or None if the image reference matches the manifest."""
    actual = image_digest(image_ref)
    if actual is None:
        return "image reference must be pinned by digest (repository@sha256:...); tags are not accepted"
    if actual != expected_digest:
        return f"image digest {actual} does not match manifest digest {expected_digest}"
    return None


def safe_working_dir(working_dir: str | None) -> str:
    """Resolve the manifest's working_dir inside /work/code, rejecting anything that escapes it."""
    path = PurePosixPath(working_dir or ".")
    if path.is_absolute() or ".." in path.parts:
        raise SandboxError(f"working_dir must be a relative path inside the code directory: {working_dir}")
    return str(PurePosixPath(WORK_DIR) / "code" / path)


def _git(git_bin: str, code_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [git_bin, "-C", str(code_dir), *args],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise SandboxError(f"git not found: {git_bin}") from exc


def check_code_checkout(code_dir: str | Path, expected_commit: str, git_bin: str = "git") -> str | None:
    """Confirm code_dir is a clean checkout of the pinned commit. Returns a problem or None."""
    base = Path(code_dir)
    head = _git(git_bin, base, "rev-parse", "HEAD")
    if head.returncode != 0:
        return "code directory is not a git checkout"
    actual = head.stdout.strip().lower()
    if not actual.startswith(expected_commit.lower()):
        return f"checked out commit {actual[:12]} does not match manifest commit {expected_commit}"
    status = _git(git_bin, base, "status", "--porcelain", "--untracked-files=all", "--ignored")
    if status.returncode != 0:
        return "could not read git status"
    if status.stdout.strip():
        return "code directory has uncommitted, untracked, or ignored files"
    return None


def build_docker_command(
    *,
    image_ref: str,
    code_dir: str | Path,
    data_dir: str | Path,
    out_dir: str | Path,
    command: str,
    name: str,
    working_dir: str | None = None,
    seed: int | None = None,
    limits: Limits | None = None,
    runtime: str | None = None,
    docker_bin: str = "docker",
) -> list[str]:
    """Build the docker run argument list. Pure function, no side effects."""
    limits = limits or Limits()
    if not command.strip():
        raise SandboxError("entrypoint command is empty")

    mounts: dict[str, Path] = {}
    for label, path in (("code", code_dir), ("data", data_dir), ("out", out_dir)):
        resolved = Path(path).resolve()
        if not resolved.is_dir():
            raise SandboxError(f"{label} directory not found: {path}")
        if "," in str(resolved):
            raise SandboxError(f"{label} directory path must not contain a comma: {resolved}")
        mounts[label] = resolved

    cmd = [
        docker_bin, "run",
        "--rm",
        "--init",
        "--name", name,
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", CONTAINER_USER,
        "--pids-limit", str(limits.pids),
        "--memory", limits.memory,
        "--memory-swap", limits.memory,
        "--cpus", str(limits.cpus),
        "--ulimit", "core=0",
        "--tmpfs", f"/tmp:rw,nosuid,size={limits.tmp_size}",
    ]
    if runtime:
        cmd += ["--runtime", runtime]
    cmd += [
        "--mount", f"type=bind,src={mounts['code']},dst={WORK_DIR}/code,readonly",
        "--mount", f"type=bind,src={mounts['data']},dst={WORK_DIR}/data,readonly",
        "--mount", f"type=bind,src={mounts['out']},dst={WORK_DIR}/out",
        "--workdir", safe_working_dir(working_dir),
        "--env", f"DOTSCI_DATA_DIR={WORK_DIR}/data",
        "--env", f"DOTSCI_OUT_DIR={WORK_DIR}/out",
        "--env", "HOME=/tmp",
    ]
    if seed is not None:
        cmd += ["--env", f"DOTSCI_SEED={seed}"]
    cmd += [image_ref, "sh", "-c", command]
    return cmd


def _tail(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value[-_TAIL_CHARS:]


def run_in_sandbox(
    cmd: list[str],
    *,
    name: str,
    timeout_seconds: int,
    docker_bin: str = "docker",
    grace_seconds: int = 10,
) -> SandboxResult:
    """Run the docker command. On timeout, kill and remove the container by name."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_seconds + grace_seconds,
        )
    except FileNotFoundError as exc:
        raise SandboxError(f"docker not found: {docker_bin}") from exc
    except subprocess.TimeoutExpired as exc:
        # Killing the docker client does not stop the container, so stop it explicitly.
        for action in (["kill", name], ["rm", "-f", name]):
            subprocess.run([docker_bin, *action], capture_output=True)
        return SandboxResult(-1, True, _tail(exc.stdout), _tail(exc.stderr))
    return SandboxResult(proc.returncode, False, _tail(proc.stdout), _tail(proc.stderr))
