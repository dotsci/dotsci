import json
from pathlib import Path

from dotsci_runner.cli import main
from dotsci_runner.manifest import canonical_json, load_manifest, manifest_hash

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "spec" / "examples" / "manifest.example.json"
KNOWN_VECTOR = "51705a2c9eb3e7e410a58f696a770c3ac3885a0cf43eb7fc88f5e47c11d4d30d"


def test_canonical_form_is_sorted_and_compact():
    assert canonical_json({"b": 1, "a": [True, None]}) == b'{"a":[true,null],"b":1}'


def test_known_vector():
    assert manifest_hash({"b": 1, "a": [True, None]}) == KNOWN_VECTOR


def test_key_order_and_whitespace_do_not_change_the_hash(tmp_path):
    manifest = load_manifest(EXAMPLE)
    reordered = dict(reversed(list(manifest.items())))
    path = tmp_path / "m.json"
    path.write_text(json.dumps(reordered, indent=8))
    assert manifest_hash(load_manifest(path)) == manifest_hash(manifest)


def test_any_content_change_changes_the_hash():
    manifest = load_manifest(EXAMPLE)
    before = manifest_hash(manifest)
    manifest["targets"][0]["published"] = 0.42
    assert manifest_hash(manifest) != before


def test_non_ascii_text_is_hashed_as_utf8():
    assert canonical_json({"name": "é"}) == '{"name":"é"}'.encode("utf-8")


def test_nan_is_rejected():
    try:
        canonical_json({"x": float("nan")})
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_hash_command_prints_both_formats(capsys):
    assert main(["hash", str(EXAMPLE)]) == 0
    plain = capsys.readouterr().out.strip()
    assert plain == "sha256:" + manifest_hash(load_manifest(EXAMPLE))
    assert main(["hash", str(EXAMPLE), "--bytes32"]) == 0
    assert capsys.readouterr().out.strip() == "0x" + plain.split(":")[1]


def test_hash_command_rejects_invalid_manifest(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    assert main(["hash", str(bad)]) == 1
