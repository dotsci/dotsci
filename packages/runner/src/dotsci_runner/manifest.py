"""Load and validate replication manifests."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class ManifestError(ValueError):
    """Raised when a manifest cannot be loaded or fails validation."""


def _schema(name: str) -> dict[str, Any]:
    text = resources.files("dotsci_runner").joinpath("schemas", name).read_text(encoding="utf-8")
    return json.loads(text)


def validation_errors(manifest: dict[str, Any]) -> list[str]:
    """Return human-readable schema errors, or an empty list if valid."""
    validator = Draft202012Validator(_schema("manifest.schema.json"))
    errors = sorted(validator.iter_errors(manifest), key=lambda e: list(e.absolute_path))
    messages = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "(root)"
        messages.append(f"{location}: {error.message}")
    return messages


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Read a manifest file and validate it. Raises ManifestError on any problem."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError("manifest must be a JSON object")

    errors = validation_errors(data)
    if errors:
        raise ManifestError("manifest failed validation:\n" + "\n".join(errors))
    return data
