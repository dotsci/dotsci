"""End to end tests for run_job and the run CLI command.

These use a stand-in docker executable (a small Python script) because CI and dev machines may not
have a Docker daemon. They verify orchestration: preflight checks, outcome mapping, hashing,
timeouts, and output inspection. They do not prove container isolation.
"""

import contextlib
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema

from dotsci_runner.cli import main
from dotsci_runner.job import run_job
from dotsci_runner.runlog import RunLog
from dotsci_runner.sandbox import SandboxError, check_code_checkout

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = REPO_ROOT / "spec" / "examples" / "manifest.example.json"
RUN_SCHEMA = json.loads((REPO_ROOT / "spec" / "run.schema.json").read_text())
DIGEST = "sha256:" + "a" * 64
IMAGE = f"registry.example.org/claim@{DIGEST}"

FAKE_DOCKER = """#!/usr/bin/env python3
import os, sys, time
args = sys.argv[1:]
if args and args[0] in ("kill", "rm"):
    sys.exit(0)
mode = os.environ.get("FAKE_DOCKER_MODE", "ok")
out = None
for i, a in enumerate(args):
    if a == "--mount" and "dst=/work/out" in args[i + 1]:
        for part in args[i + 1].split(","):
            if part.startswith("src="):
                out = part[4:]
if mode == "daemon_error":
    sys.stderr.write("daemon not running\\n")
    sys.exit(125)
if mode == "hang":
    time.sleep(30)
    sys.exit(0)
if mode == "fail":
    sys.stdout.write("boom\\n")
    sys.exit(1)
if mode == "nores":
    sys.exit(0)
if mode == "symlink":
    os.symlink("/etc/passwd", os.path.join(out, "results.json"))
    sys.exit(0)
if mode == "badjson":
    open(os.path.join(out, "results.json"), "w").write("[1, 2, 3]")
    sys.exit(0)
with open(os.path.join(out, "results.json"), "w") as fh:
    fh.write(os.environ.get("FAKE_RESULTS", "{}"))
with open(os.path.join(out, "table.csv"), "w") as fh:
    fh.write("a,b\\n1,2\\n")
print("analysis done")
"""


@contextlib.contextmanager
def env(**values):
    old = {k: os.environ.get(k) for k in values}
    os.environ.update({k: str(v) for k, v in values.items()})
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _setup(tmp_path: Path):
    """Create code repo, data dir, fake docker, and a manifest that matches them."""
    code = tmp_path / "code"
    code.mkdir()
    _git(code, "init", "-q")
    (code / "analysis.py").write_text("print('hi')\n")
    _git(code, "add", "analysis.py")
    _git(code, "commit", "-q", "-m", "init")
    commit = _git(code, "rev-parse", "HEAD")

    data = tmp_path / "data"
    data.mkdir()
    payload = b"1,2,3\n"
    (data / "measurements.csv").write_bytes(payload)

    docker = tmp_path / "fake-docker"
    docker.write_text(FAKE_DOCKER)
    docker.chmod(0o755)
    docker_cmd = str(docker)

    manifest = json.loads(EXAMPLE.read_text())
    manifest["datasets"] = [
        {"name": "measurements.csv", "sha256": hashlib.sha256(payload).hexdigest()}
    ]
    manifest["code"]["commit"] = commit
    manifest["environment"]["image_digest"] = DIGEST
    manifest["environment"]["timeout_seconds"] = 1
    return manifest, code, data, docker_cmd


def _run(tmp_path, manifest, code, data, docker, **kwargs):
    import io
    return run_job(
        manifest,
        code_dir=code,
        data_dir=data,
        out_dir=tmp_path / "out",
        image_ref=kwargs.pop("image_ref", IMAGE),
        docker_bin=docker,
        log=RunLog(io.StringIO()),
        grace_seconds=0,
        **kwargs,
    )


def test_reproduced_run_produces_valid_record_with_hashes(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    with env(FAKE_DOCKER_MODE="ok", FAKE_RESULTS=json.dumps({"primary_effect": 0.42, "sample_size": 1200})):
        record = _run(tmp_path, manifest, code, data, docker, job_id="j1")
    assert record["outcome"] == "reproduced"
    assert record["input_hashes"] == {"measurements.csv": hashlib.sha256(b"1,2,3\n").hexdigest()}
    assert set(record["output_hashes"]) == {"results.json", "table.csv"}
    jsonschema.validate(record, RUN_SCHEMA)


def test_out_of_tolerance_is_not_reproduced(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    with env(FAKE_DOCKER_MODE="ok", FAKE_RESULTS=json.dumps({"primary_effect": 0.9, "sample_size": 1200})):
        record = _run(tmp_path, manifest, code, data, docker)
    assert record["outcome"] == "not_reproduced"
    jsonschema.validate(record, RUN_SCHEMA)


def test_missing_target_value_cannot_reproduce_and_is_noted(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    with env(FAKE_DOCKER_MODE="ok", FAKE_RESULTS=json.dumps({"primary_effect": 0.41})):
        record = _run(tmp_path, manifest, code, data, docker)
    assert record["outcome"] == "not_reproduced"
    assert "sample_size" in record["notes"]
    jsonschema.validate(record, RUN_SCHEMA)


def test_dataset_hash_mismatch_stops_before_running(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    (data / "measurements.csv").write_bytes(b"tampered")
    with env(FAKE_DOCKER_MODE="ok", FAKE_RESULTS="{}"):
        record = _run(tmp_path, manifest, code, data, docker)
    assert record["outcome"] == "input_mismatch"
    assert "hash mismatch" in record["notes"]
    assert not (tmp_path / "out" / "results.json").exists()
    jsonschema.validate(record, RUN_SCHEMA)


def test_dirty_checkout_is_input_mismatch(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    (code / "extra.py").write_text("x = 1\n")
    record = _run(tmp_path, manifest, code, data, docker)
    assert record["outcome"] == "input_mismatch"
    assert "uncommitted" in record["notes"]


def test_wrong_commit_is_input_mismatch(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    manifest["code"]["commit"] = "0" * 40
    record = _run(tmp_path, manifest, code, data, docker)
    assert record["outcome"] == "input_mismatch"
    assert "does not match manifest commit" in record["notes"]


def test_image_tag_is_input_mismatch(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    record = _run(tmp_path, manifest, code, data, docker, image_ref="registry.example.org/claim:latest")
    assert record["outcome"] == "input_mismatch"
    assert "pinned by digest" in record["notes"]


def test_dataset_name_cannot_escape_data_dir(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    (tmp_path / "secret.txt").write_text("x")
    manifest["datasets"][0]["name"] = "../secret.txt"
    record = _run(tmp_path, manifest, code, data, docker)
    assert record["outcome"] == "input_mismatch"
    assert "invalid dataset name" in record["notes"]


def test_nonzero_exit_is_spec_issue(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    with env(FAKE_DOCKER_MODE="fail"):
        record = _run(tmp_path, manifest, code, data, docker)
    assert record["outcome"] == "spec_issue"
    assert "exited with code 1" in record["notes"]
    jsonschema.validate(record, RUN_SCHEMA)


def test_timeout_is_spec_issue(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    with env(FAKE_DOCKER_MODE="hang"):
        record = _run(tmp_path, manifest, code, data, docker)
    assert record["outcome"] == "spec_issue"
    assert "timed out" in record["notes"]


def test_missing_results_is_spec_issue(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    with env(FAKE_DOCKER_MODE="nores"):
        record = _run(tmp_path, manifest, code, data, docker)
    assert record["outcome"] == "spec_issue"
    assert "results.json was not written" in record["notes"]


def test_malformed_results_is_spec_issue(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    with env(FAKE_DOCKER_MODE="badjson"):
        record = _run(tmp_path, manifest, code, data, docker)
    assert record["outcome"] == "spec_issue"
    assert "must be an object" in record["notes"]


def test_symlink_in_output_is_rejected_not_followed(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    with env(FAKE_DOCKER_MODE="symlink"):
        record = _run(tmp_path, manifest, code, data, docker)
    assert record["outcome"] == "spec_issue"
    assert "symlink" in record["notes"]
    assert record["output_hashes"] == {}


def test_docker_daemon_failure_raises_instead_of_recording(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    with env(FAKE_DOCKER_MODE="daemon_error"):
        try:
            _run(tmp_path, manifest, code, data, docker)
        except SandboxError as exc:
            assert "daemon not running" in str(exc)
        else:
            raise AssertionError("expected SandboxError")


def test_missing_docker_binary_raises(tmp_path):
    manifest, code, data, _ = _setup(tmp_path)
    try:
        _run(tmp_path, manifest, code, data, str(tmp_path / "no-such-docker"))
    except SandboxError as exc:
        assert "docker not found" in str(exc)
    else:
        raise AssertionError("expected SandboxError")


def test_non_empty_output_dir_is_refused(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "old.json").write_text("{}")
    try:
        _run(tmp_path, manifest, code, data, docker)
    except SandboxError as exc:
        assert "must be empty" in str(exc)
    else:
        raise AssertionError("expected SandboxError")


def test_check_code_checkout_accepts_short_commit(tmp_path):
    manifest, code, data, docker = _setup(tmp_path)
    assert check_code_checkout(code, manifest["code"]["commit"][:7]) is None


def test_cli_dry_run_prints_isolated_command(tmp_path, capsys):
    manifest, code, data, docker = _setup(tmp_path)
    mpath = tmp_path / "m.json"
    mpath.write_text(json.dumps(manifest))
    (tmp_path / "out").mkdir()
    rc = main([
        "run", str(mpath), "--code-dir", str(code), "--data-dir", str(data),
        "--out-dir", str(tmp_path / "out"), "--image", IMAGE, "--dry-run",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "--network none" in out and "--read-only" in out and "--cap-drop ALL" in out


def test_cli_run_writes_record_and_exit_code(tmp_path, capsys):
    manifest, code, data, docker = _setup(tmp_path)
    mpath = tmp_path / "m.json"
    mpath.write_text(json.dumps(manifest))
    record_path = tmp_path / "run.json"
    log_path = tmp_path / "run.log.jsonl"
    with env(FAKE_DOCKER_MODE="ok", FAKE_RESULTS=json.dumps({"primary_effect": 0.42, "sample_size": 1200})):
        rc = main([
            "run", str(mpath), "--code-dir", str(code), "--data-dir", str(data),
            "--out-dir", str(tmp_path / "out"), "--image", IMAGE, "--docker", docker,
            "--grace-seconds", "0", "--record", str(record_path), "--log-file", str(log_path),
        ])
    assert rc == 0
    record = json.loads(record_path.read_text())
    assert record["outcome"] == "reproduced"
    jsonschema.validate(record, RUN_SCHEMA)
    lines = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert {"t", "level", "step", "msg", "data"} <= set(lines[0])
    assert lines[-1]["step"] == "outcome"


def test_cli_docker_failure_exits_2(tmp_path, capsys):
    manifest, code, data, docker = _setup(tmp_path)
    mpath = tmp_path / "m.json"
    mpath.write_text(json.dumps(manifest))
    with env(FAKE_DOCKER_MODE="daemon_error"):
        rc = main([
            "run", str(mpath), "--code-dir", str(code), "--data-dir", str(data),
            "--out-dir", str(tmp_path / "out"), "--image", IMAGE, "--docker", docker,
            "--grace-seconds", "0",
        ])
    assert rc == 2
    assert "error:" in capsys.readouterr().err
