import json
import os
import subprocess
import sys
from pathlib import Path

from dotsci_runner.compare import compare_targets
from dotsci_runner.hashing import verify_inputs
from dotsci_runner.manifest import load_manifest

DEMO = Path(__file__).resolve().parents[3] / "examples" / "demo-claim"


def test_demo_manifest_is_valid():
    manifest = load_manifest(DEMO / "manifest.json")
    assert manifest["claim_id"] == "demo-0001"


def test_demo_data_matches_pinned_hash():
    manifest = load_manifest(DEMO / "manifest.json")
    checks = verify_inputs(manifest, DEMO / "data")
    assert checks and all(c.ok for c in checks)


def test_demo_analysis_reproduces_targets(tmp_path):
    env = dict(os.environ, DOTSCI_DATA_DIR=str(DEMO / "data"), DOTSCI_OUT_DIR=str(tmp_path))
    subprocess.run([sys.executable, str(DEMO / "analysis.py")], check=True, env=env)
    values = json.loads((tmp_path / "results.json").read_text())
    manifest = load_manifest(DEMO / "manifest.json")
    _, outcome = compare_targets(manifest["targets"], values)
    assert outcome == "reproduced"
