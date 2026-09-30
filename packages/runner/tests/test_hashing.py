import hashlib
import json
from pathlib import Path

from dotsci_runner.hashing import sha256_file, verify_inputs

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = REPO_ROOT / "spec" / "examples" / "manifest.example.json"


def _manifest_for(name: str, sha256: str) -> dict:
    data = json.loads(EXAMPLE.read_text())
    data["datasets"] = [{"name": name, "sha256": sha256}]
    return data


def test_sha256_file_matches_hashlib(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello dotsci")
    assert sha256_file(f) == hashlib.sha256(b"hello dotsci").hexdigest()


def test_sha256_file_handles_multiple_chunks(tmp_path):
    f = tmp_path / "big.bin"
    payload = b"a" * 5000
    f.write_bytes(payload)
    assert sha256_file(f, chunk_size=64) == hashlib.sha256(payload).hexdigest()


def test_verify_inputs_ok(tmp_path):
    (tmp_path / "data.csv").write_bytes(b"1,2,3\n")
    digest = hashlib.sha256(b"1,2,3\n").hexdigest()
    checks = verify_inputs(_manifest_for("data.csv", digest), tmp_path)
    assert len(checks) == 1 and checks[0].ok


def test_verify_inputs_detects_mismatch(tmp_path):
    (tmp_path / "data.csv").write_bytes(b"1,2,3\n")
    checks = verify_inputs(_manifest_for("data.csv", "0" * 64), tmp_path)
    assert not checks[0].ok
    assert checks[0].reason == "hash mismatch"


def test_verify_inputs_detects_missing_file(tmp_path):
    checks = verify_inputs(_manifest_for("gone.csv", "0" * 64), tmp_path)
    assert not checks[0].ok
    assert checks[0].reason == "file not found"
