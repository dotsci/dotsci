"""Replay the shared conformance vectors for manifest hashing."""

import json
from pathlib import Path

from dotsci_runner.manifest import canonical_json, manifest_hash

VECTORS = Path(__file__).resolve().parents[3] / "spec" / "vectors" / "manifest-hash.json"
DATA = json.loads(VECTORS.read_text(encoding="utf-8"))


def test_vectors_are_present():
    assert DATA["version"] == 1 and len(DATA["cases"]) >= 8


def test_canonical_text_matches_every_vector():
    for case in DATA["cases"]:
        assert canonical_json(case["manifest"]).decode("utf-8") == case["canonical"], case["name"]


def test_hash_matches_every_vector():
    for case in DATA["cases"]:
        assert manifest_hash(case["manifest"]) == case["sha256"], case["name"]


def test_key_order_variants_share_a_hash():
    by_name = {c["name"]: c for c in DATA["cases"]}
    assert by_name["key_order_ignored"]["sha256"] == by_name["key_order_ignored_reversed"]["sha256"]
    a = {"b": 1, "a": {"d": [3, 2, 1], "c": None}}
    b = {"a": {"c": None, "d": [3, 2, 1]}, "b": 1}
    assert manifest_hash(a) == manifest_hash(b) == by_name["key_order_ignored"]["sha256"]


def test_float_forms_are_pinned():
    case = next(c for c in DATA["cases"] if c["name"] == "floats_use_shortest_repr")
    assert case["canonical"] == '{"a":0.1,"b":1e-07,"c":1e+22,"d":5.0,"e":0.63}'
