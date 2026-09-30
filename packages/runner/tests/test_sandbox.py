from pathlib import Path

import pytest

from dotsci_runner.sandbox import (
    Limits,
    SandboxError,
    build_docker_command,
    check_image,
    container_name,
    safe_working_dir,
)

DIGEST = "sha256:" + "a" * 64
IMAGE = f"registry.example.org/claim@{DIGEST}"


def _dirs(tmp_path: Path):
    for name in ("code", "data", "out"):
        (tmp_path / name).mkdir()
    return tmp_path / "code", tmp_path / "data", tmp_path / "out"


def _cmd(tmp_path: Path, **overrides):
    code, data, out = _dirs(tmp_path)
    kwargs = dict(
        image_ref=IMAGE,
        code_dir=code,
        data_dir=data,
        out_dir=out,
        command="python analysis.py",
        name="dotsci-test",
    )
    kwargs.update(overrides)
    return build_docker_command(**kwargs)


def _pair(cmd, flag, value):
    return any(cmd[i] == flag and cmd[i + 1] == value for i in range(len(cmd) - 1))


def test_isolation_flags_are_present(tmp_path):
    cmd = _cmd(tmp_path)
    assert _pair(cmd, "--network", "none")
    assert "--read-only" in cmd
    assert _pair(cmd, "--cap-drop", "ALL")
    assert _pair(cmd, "--security-opt", "no-new-privileges")
    assert _pair(cmd, "--user", "10001:10001")
    assert "--rm" in cmd and "--init" in cmd
    assert _pair(cmd, "--ulimit", "core=0")


def test_resource_limits_follow_limits_object(tmp_path):
    cmd = _cmd(tmp_path, limits=Limits(cpus=1.5, memory="2g", pids=64, tmp_size="128m"))
    assert _pair(cmd, "--cpus", "1.5")
    assert _pair(cmd, "--memory", "2g")
    assert _pair(cmd, "--memory-swap", "2g")
    assert _pair(cmd, "--pids-limit", "64")
    assert _pair(cmd, "--tmpfs", "/tmp:rw,nosuid,size=128m")


def test_code_and_data_are_read_only_and_out_is_writable(tmp_path):
    cmd = _cmd(tmp_path)
    mounts = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--mount"]
    by_dst = {m.split("dst=")[1].split(",")[0]: m for m in mounts}
    assert by_dst["/work/code"].endswith(",readonly")
    assert by_dst["/work/data"].endswith(",readonly")
    assert not by_dst["/work/out"].endswith(",readonly")
    assert len(mounts) == 3


def test_environment_and_command(tmp_path):
    cmd = _cmd(tmp_path, seed=0)
    assert _pair(cmd, "--env", "DOTSCI_SEED=0")
    assert _pair(cmd, "--env", "DOTSCI_OUT_DIR=/work/out")
    assert _pair(cmd, "--env", "DOTSCI_DATA_DIR=/work/data")
    assert cmd[-4:] == [IMAGE, "sh", "-c", "python analysis.py"]


def test_seed_is_omitted_when_not_set(tmp_path):
    cmd = _cmd(tmp_path)
    assert not any(a.startswith("DOTSCI_SEED") for a in cmd)


def test_runtime_is_optional(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    assert "--runtime" not in _cmd(first)
    assert _pair(_cmd(second, runtime="runsc"), "--runtime", "runsc")


def test_working_dir_inside_code_dir(tmp_path):
    cmd = _cmd(tmp_path, working_dir="analysis/src")
    assert _pair(cmd, "--workdir", "/work/code/analysis/src")


def test_working_dir_default_is_code_root():
    assert safe_working_dir(None) == "/work/code"
    assert safe_working_dir(".") == "/work/code"


def test_working_dir_cannot_escape():
    for bad in ("..", "../x", "a/../../b", "/etc"):
        with pytest.raises(SandboxError):
            safe_working_dir(bad)


def test_missing_directory_is_rejected(tmp_path):
    code, data, out = _dirs(tmp_path)
    with pytest.raises(SandboxError):
        build_docker_command(
            image_ref=IMAGE, code_dir=code, data_dir=tmp_path / "nope", out_dir=out,
            command="x", name="n",
        )


def test_comma_in_path_is_rejected(tmp_path):
    bad = tmp_path / "a,b"
    bad.mkdir()
    code, data, out = _dirs(tmp_path)
    with pytest.raises(SandboxError):
        build_docker_command(
            image_ref=IMAGE, code_dir=bad, data_dir=data, out_dir=out, command="x", name="n",
        )


def test_empty_command_is_rejected(tmp_path):
    with pytest.raises(SandboxError):
        _cmd(tmp_path, command="   ")


def test_image_must_be_pinned_by_digest():
    assert check_image(IMAGE, DIGEST) is None
    assert "pinned by digest" in check_image("registry.example.org/claim:latest", DIGEST)
    assert "does not match" in check_image(f"registry.example.org/claim@sha256:{'b' * 64}", DIGEST)


def test_container_names_are_safe_and_unique():
    a = container_name("job 1/../x")
    b = container_name("job 1/../x")
    assert a != b
    assert all(c.isalnum() or c in "-_." for c in a)
    assert a.startswith("dotsci-")
