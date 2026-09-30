import json
from pathlib import Path

import pytest

from dotsci_runner.manifest import ManifestError, load_manifest, validation_errors

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = REPO_ROOT / "spec" / "examples" / "manifest.example.json"


def test_example_manifest_is_valid():
    manifest = load_manifest(EXAMPLE)
    assert manifest["claim_id"] == "example-0001"


def test_missing_required_field_is_rejected():
    data = json.loads(EXAMPLE.read_text())
    del data["targets"]
    errors = validation_errors(data)
    assert any("targets" in e for e in errors)


def test_bad_hash_is_rejected():
    data = json.loads(EXAMPLE.read_text())
    data["datasets"][0]["sha256"] = "not-a-hash"
    assert validation_errors(data)


def test_branch_name_is_not_a_pinned_commit():
    data = json.loads(EXAMPLE.read_text())
    data["code"]["commit"] = "main"
    assert validation_errors(data)


def test_missing_tolerance_is_rejected():
    data = json.loads(EXAMPLE.read_text())
    del data["targets"][0]["tolerance"]
    assert validation_errors(data)


def test_unknown_field_is_rejected():
    data = json.loads(EXAMPLE.read_text())
    data["surprise"] = True
    assert validation_errors(data)


def test_load_missing_file(tmp_path):
    with pytest.raises(ManifestError):
        load_manifest(tmp_path / "nope.json")


def test_load_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(ManifestError):
        load_manifest(bad)


def test_schemas_in_package_match_spec_folder():
    package_dir = REPO_ROOT / "packages" / "runner" / "src" / "dotsci_runner" / "schemas"
    for name in ("manifest.schema.json", "run.schema.json"):
        assert (package_dir / name).read_text() == (REPO_ROOT / "spec" / name).read_text()
