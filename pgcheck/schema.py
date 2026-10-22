"""Small, explicit JSON Schema subset validated without third-party packages."""
from __future__ import annotations

import math
from typing import Any, Iterator

S = {"type": "string", "minLength": 1}
NS = {"type": ["string", "null"], "minLength": 1}
NUM = {"type": "number"}


def obj(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required}


def arr(items: dict) -> dict:
    return {"type": "array", "items": items}


CV = obj({"library": S, "cell": S, "view": S})
PLACEMENT = obj({"x": NUM, "y": NUM, "orientation": S,
                 "coordinate_system": {"const": "parent_local"}, "units": NS})
PLACEMENT["type"] = ["object", "null"]
SELECTED = dict(CV, type=["object", "null"])
TERMINAL = obj({"id": S, "name": S, "direction": S})
SCHEMAS = {
    "manifest": obj({
        "schema_version": {"const": "1.0"}, "run_id": S,
        "status": {"enum": ["complete", "incomplete"]},
        "root_instance_id": S, "top": CV,
        "files": obj({name: {"const": name + ".jsonl"} for name in
                      ("cells", "instances", "nets", "connections", "unresolved")}),
        "counts": obj({name: {"type": "integer", "minimum": 0} for name in
                       ("cells", "instances", "nets", "connections", "unresolved")}),
        "capabilities": obj({key: S for key in (
            "binding_policy", "saved_status", "connectivity_status",
            "placement_support", "pin_helper_policy")}),
        "validation_context": {"enum": ["synthetic", "virtuoso_unverified", "virtuoso_internal"]},
    }),
    "cells": obj({"id": S, "path": S, "library": S, "cell": S, "view": S,
                  "db_id": S, "terminals": arr(TERMINAL), "local_net_names": arr(S)}),
    "instances": obj({"id": S, "path": S, "name": S, "parent_id": NS,
                      "cell_id": NS, "master": CV, "selected": SELECTED,
                      "placement": PLACEMENT}),
    "nets": obj({"id": S, "path": S, "name": S, "cell_id": S, "occurrence_id": S}),
    "connections": obj({
        "id": S, "path": S, "kind": {"enum": ["instance_port", "cell_port"]},
        "owner_instance_id": S, "instance_id": S, "port": S, "terminal_id": NS,
        "net_id": NS, "status": {"enum": ["connected", "unconnected", "unresolved"]},
        "evidence": {"enum": ["db", "none"]}, "reason": NS,
    }),
    "unresolved": obj({"id": S, "path": S, "code": S, "message": S,
                       "severity": {"enum": ["error", "warning"]}, "object_id": NS}),
}


def schema_errors(value: Any, schema: dict, path: str) -> Iterator[tuple[str, str]]:
    """Yield (path, message) for the supported JSON Schema 2020-12 subset."""
    if "const" in schema and value != schema["const"]:
        yield path, f"expected {schema['const']!r}"
    if "enum" in schema and value not in schema["enum"]:
        yield path, f"expected one of {schema['enum']!r}"
    types = schema.get("type", [])
    if isinstance(types, str):
        types = [types]
    predicates = {
        "null": lambda: value is None,
        "string": lambda: isinstance(value, str),
        "object": lambda: isinstance(value, dict),
        "array": lambda: isinstance(value, list),
        "integer": lambda: isinstance(value, int) and not isinstance(value, bool),
        "number": lambda: isinstance(value, (float, int)) and not isinstance(value, bool)
            and (not isinstance(value, float) or math.isfinite(value)),
    }
    if types and not any(predicates[k]() for k in types):
        yield path, f"expected type {types!r}"
        return
    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        yield path, "string must not be empty"
    if value is None:
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            yield path, f"must be >= {schema['minimum']}"
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                yield f"{path}.{key}", "required field missing"
        for key, subschema in schema.get("properties", {}).items():
            if key in value:
                yield from schema_errors(value[key], subschema, f"{path}.{key}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            yield from schema_errors(item, schema["items"], f"{path}[{index}]")
