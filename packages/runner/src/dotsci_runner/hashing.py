"""Hash files and verify inputs against a manifest."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the lowercase hex SHA-256 of a file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class InputCheck:
    name: str
    expected: str
    actual: str | None
    ok: bool
    reason: str | None = None


def verify_inputs(manifest: dict[str, Any], data_dir: str | Path) -> list[InputCheck]:
    """Check every dataset in the manifest against files in data_dir.

    A missing file or a hash that differs produces a failed check. Nothing is skipped.
    """
    base = Path(data_dir)
    results: list[InputCheck] = []
    for dataset in manifest["datasets"]:
        name = dataset["name"]
        expected = dataset["sha256"]
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts:
            results.append(InputCheck(name, expected, None, False, "invalid dataset name"))
            continue
        path = base / name
        if not path.is_file():
            results.append(InputCheck(name, expected, None, False, "file not found"))
            continue
        actual = sha256_file(path)
        if actual != expected:
            results.append(InputCheck(name, expected, actual, False, "hash mismatch"))
        else:
            results.append(InputCheck(name, expected, actual, True))
    return results


def hashes_of(paths: dict[str, str | Path]) -> dict[str, str]:
    """Hash a mapping of label to file path, for use in a run record."""
    return {label: sha256_file(path) for label, path in paths.items()}
