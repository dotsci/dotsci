"""JSONL logging in the DotSci log format."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import IO, Any


class RunLog:
    """Write one JSON object per line: t, level, step, msg, data."""

    def __init__(self, stream: IO[str] | None = None) -> None:
        self._stream = stream if stream is not None else sys.stderr
        self.entries: list[dict[str, Any]] = []

    def _emit(self, level: str, step: str, msg: str, data: dict[str, Any] | None) -> dict[str, Any]:
        entry = {
            "t": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "level": level,
            "step": step,
            "msg": msg,
            "data": data or {},
        }
        self.entries.append(entry)
        self._stream.write(json.dumps(entry, allow_nan=False, default=str) + "\n")
        self._stream.flush()
        return entry

    def info(self, step: str, msg: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._emit("info", step, msg, data)

    def warn(self, step: str, msg: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._emit("warn", step, msg, data)

    def error(self, step: str, msg: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._emit("error", step, msg, data)
