"""Strict UTF-8 JSONL reader; never modifies an exported directory."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FILES = {name: name + ".jsonl" for name in
         ("cells", "instances", "nets", "connections", "unresolved")}


class ExportReadError(ValueError):
    """An export could not be decoded safely and completely."""


@dataclass
class Dataset:
    manifest: dict[str, Any]
    cells: list[dict[str, Any]]
    instances: list[dict[str, Any]]
    nets: list[dict[str, Any]]
    connections: list[dict[str, Any]]
    unresolved: list[dict[str, Any]]
    source: Path | None = None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ExportReadError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ExportReadError(f"Non-finite JSON number: {value}")


def _decode(text: str, location: str) -> dict[str, Any]:
    try:
        value = json.loads(text, object_pairs_hook=_unique_object,
                           parse_constant=_invalid_constant)
    except (ValueError, RecursionError) as exc:
        raise ExportReadError(f"{location}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExportReadError(f"{location}: expected JSON object")
    # json.loads accepts escaped lone surrogate code points. They are not valid
    # UTF-8 scalar values, even if their source bytes consist entirely of ASCII.
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (UnicodeError, ValueError) as exc:
        raise ExportReadError(f"{location}: invalid Unicode or non-finite number") from exc
    return value


def load_export(directory: str | Path) -> Dataset:
    root = Path(directory)
    try:
        manifest = _decode((root / "manifest.json").read_text(encoding="utf-8"),
                           "manifest.json")
        records: dict[str, list[dict[str, Any]]] = {}
        # The manifest cannot redirect the reader outside the selected directory.
        for name, filename in FILES.items():
            records[name] = []
            with (root / filename).open(encoding="utf-8", newline="") as stream:
                for line_number, line in enumerate(stream, 1):
                    location = f"{filename}:{line_number}"
                    if not line.strip():
                        raise ExportReadError(f"{location}: empty JSONL line")
                    records[name].append(_decode(line, location))
    except (OSError, UnicodeError) as exc:
        raise ExportReadError(f"Cannot read export {root}: {exc}") from exc
    return Dataset(manifest=manifest, source=root, **records)
