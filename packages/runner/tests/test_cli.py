import hashlib
import io
import json
from pathlib import Path

import jsonschema

from dotsci_runner.cli import main
from dotsci_runner.runlog import RunLog

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = REPO_ROOT / "spec" / "examples" / "manifest.example.json"
RUN_SCHEMA = json.loads((REPO_ROOT / "spec" / "run.schema.json").read_text())


def test_validate_command_ok(capsys):
    assert main(["validate", str(EXAMPLE)]) == 0
    assert "example-0001" in capsys.readouterr().out


def test_validate_command_rejects_bad_manifest(tmp_path, capsys):
    bad = tmp_path / "m.json"
    bad.write_text("{}")
    assert main(["validate", str(bad)]) == 1
    assert "failed validation" in capsys.readouterr().err


def test_compare_reproduced_writes_valid_run_record(tmp_path):
    results = tmp_path / "results.json"
    results.write_text(json.dumps({"primary_effect": 0.42, "sample_size": 1200}))
    out = tmp_path / "run.json"
    code = main(["compare", str(EXAMPLE), "--results", str(results), "--out", str(out), "--job-id", "j1"])
    assert code == 0
    record = json.loads(out.read_text())
    assert record["outcome"] == "reproduced"
    assert record["job_id"] == "j1"
    jsonschema.validate(record, RUN_SCHEMA)


def test_compare_not_reproduced_exit_code_and_valid_record(tmp_path):
    results = tmp_path / "results.json"
    results.write_text(json.dumps({"primary_effect": 0.90}))
    out = tmp_path / "run.json"
    code = main(["compare", str(EXAMPLE), "--results", str(results), "--out", str(out)])
    assert code == 1
    record = json.loads(out.read_text())
    assert record["outcome"] == "not_reproduced"
    jsonschema.validate(record, RUN_SCHEMA)


def test_verify_inputs_command(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "measurements.csv").write_bytes(b"x\n")
    manifest = json.loads(EXAMPLE.read_text())
    manifest["datasets"][0]["sha256"] = hashlib.sha256(b"x\n").hexdigest()
    mpath = tmp_path / "m.json"
    mpath.write_text(json.dumps(manifest))
    assert main(["verify-inputs", str(mpath), "--data-dir", str(data)]) == 0
    (data / "measurements.csv").write_bytes(b"tampered\n")
    assert main(["verify-inputs", str(mpath), "--data-dir", str(data)]) == 1


def test_runlog_format():
    stream = io.StringIO()
    log = RunLog(stream)
    log.info("step_one", "hello", {"k": 1})
    line = json.loads(stream.getvalue().strip())
    assert set(line) == {"t", "level", "step", "msg", "data"}
    assert line["level"] == "info" and line["data"] == {"k": 1}
    assert line["t"].endswith("Z")
