import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((ROOT / "spec" / "lab-message.schema.json").read_text())
EXAMPLE = json.loads((ROOT / "spec" / "examples" / "lab-message.example.json").read_text())


def _errors(message):
    return list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(message))


def test_example_message_is_valid():
    assert _errors(EXAMPLE) == []


def test_all_message_types_are_accepted():
    for kind in ("note", "question", "finding", "handoff", "blocker"):
        assert _errors({"type": kind, "to": "all", "body": "x"}) == []


def test_unknown_type_is_rejected():
    assert _errors({"type": "shout", "to": "all", "body": "x"})


def test_body_length_limit():
    assert _errors({"type": "note", "to": "all", "body": "a" * 1500}) == []
    assert _errors({"type": "note", "to": "all", "body": "a" * 1501})


def test_missing_and_extra_fields_are_rejected():
    assert _errors({"type": "note", "body": "x"})
    assert _errors({"type": "note", "to": "all", "body": "x", "extra": 1})
