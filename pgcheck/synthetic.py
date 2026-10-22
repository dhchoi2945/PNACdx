"""Independent, offline T01 example data; never an internal acceptance result."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4


def create_t01(directory: str | Path) -> Path:
    """Write a hand-authored T01 export into an exclusively created directory.

    This fixture deliberately does not call the SKILL exporter or T01 oracle.
    Existing output directories are rejected, including otherwise empty ones.
    The manifest is written last so an interrupted export cannot appear complete.
    """
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=False)
    library = "PGCHECK_SYNTHETIC"
    top_spec = {"library": library, "cell": "PGC_T01_TOP", "view": "schematic"}
    load_spec = {"library": library, "cell": "PGC_T01_LOAD", "view": "schematic"}
    symbol_spec = {"library": library, "cell": "PGC_T01_LOAD", "view": "symbol"}
    top_ports = [("VDD_A", "inputOutput"), ("VDD_B", "inputOutput"),
                 ("VSS_A", "inputOutput"), ("CTRL", "input")]
    load_ports = [("VDD", "inputOutput"), ("VSS", "inputOutput"), ("EN", "input")]
    top_path = f"/{library}/PGC_T01_TOP/schematic"
    cells = [
        {"id": "cell:top", "path": f"/cells/{library}/PGC_T01_TOP/schematic",
         **top_spec, "db_id": 'synthetic-top:"DB"\\진단',
         "terminals": [{"id": f"terminal:top:{name}", "name": name, "direction": direction}
                       for name, direction in top_ports],
         "local_net_names": [name for name, _ in top_ports]},
        {"id": "cell:load", "path": f"/cells/{library}/PGC_T01_LOAD/schematic",
         **load_spec, "db_id": "synthetic-load:λ",
         "terminals": [{"id": f"terminal:load:{name}", "name": name, "direction": direction}
                       for name, direction in load_ports],
         "local_net_names": [name for name, _ in load_ports]},
    ]
    instances = [
        {"id": "instance:root", "path": top_path, "name": "PGC_T01_TOP", "parent_id": None,
         "cell_id": "cell:top", "master": dict(top_spec), "selected": dict(top_spec),
         "placement": None},
        {"id": "instance:load0", "path": top_path + "/U_LOAD0", "name": "U_LOAD0",
         "parent_id": "instance:root", "cell_id": "cell:load",
         "master": dict(symbol_spec), "selected": dict(load_spec),
         "placement": {"x": 0.0, "y": 0.0, "orientation": "R0",
                       "coordinate_system": "parent_local", "units": "synthetic_micron"}},
        {"id": "instance:load1", "path": top_path + "/U_LOAD1", "name": "U_LOAD1",
         "parent_id": "instance:root", "cell_id": "cell:load",
         "master": dict(symbol_spec), "selected": dict(load_spec),
         "placement": {"x": 10.5, "y": -2.0, "orientation": "R0",
                       "coordinate_system": "parent_local", "units": None}},
    ]
    nets = []
    connections = []
    for occurrence, cell, ports, path in [
        ("root", "top", top_ports, top_path),
        ("load0", "load", load_ports, top_path + "/U_LOAD0"),
        ("load1", "load", load_ports, top_path + "/U_LOAD1"),
    ]:
        for name, _ in ports:
            net_id = f"net:{occurrence}:{name}"
            nets.append({"id": net_id, "path": path + "/nets/" + name,
                         "name": name, "cell_id": f"cell:{cell}",
                         "occurrence_id": f"instance:{occurrence}"})
            connections.append({
                "id": f"connection:cell:{occurrence}:{name}",
                "path": path + "/ports/" + name,
                "kind": "cell_port", "owner_instance_id": f"instance:{occurrence}",
                "instance_id": f"instance:{occurrence}", "port": name,
                "terminal_id": f"terminal:{cell}:{name}", "net_id": net_id,
                "status": "connected", "evidence": "db", "reason": None,
            })
    # Explicit independent wiring table, never derived from exporter output.
    expected_edges = [
        ("load0", "U_LOAD0", "VDD", "VDD_A"),
        ("load0", "U_LOAD0", "VSS", "VSS_A"),
        ("load0", "U_LOAD0", "EN", "CTRL"),
        ("load1", "U_LOAD1", "VDD", "VDD_B"),
        ("load1", "U_LOAD1", "VSS", "VSS_A"),
        ("load1", "U_LOAD1", "EN", "CTRL"),
    ]
    for occurrence, name, port, net in expected_edges:
        connections.append({
            "id": f"connection:instance:{occurrence}:{port}",
            "path": top_path + "/" + name + "/parent_ports/" + port,
            "kind": "instance_port", "owner_instance_id": "instance:root",
            "instance_id": f"instance:{occurrence}", "port": port,
            "terminal_id": f"terminal:load:{port}", "net_id": f"net:root:{net}",
            "status": "connected", "evidence": "db", "reason": None,
        })
    records = {"cells": cells, "instances": instances, "nets": nets,
               "connections": connections, "unresolved": []}
    for stem, rows in records.items():
        with (target / f"{stem}.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    manifest = {
        "schema_version": "1.0", "run_id": "synthetic-" + uuid4().hex,
        "status": "complete", "root_instance_id": "instance:root", "top": top_spec,
        "files": {stem: f"{stem}.jsonl" for stem in records},
        "counts": {stem: len(rows) for stem, rows in records.items()},
        "capabilities": {
            "binding_policy": "explicit_schematic", "saved_status": "NOT_TESTED",
            "connectivity_status": "NOT_TESTED", "placement_support": "synthetic",
            "pin_helper_policy": "exclude known basic pin helper masters only",
        },
        "validation_context": "synthetic",
        "notes": '합성 데이터 전용; quote="; backslash=\\; newline=\n; tab=\t; unicode=λ',
        "internal_checks": {"ciw": "NOT_TESTED", "safe_generator": "NOT_TESTED",
                            "overwrite_protection": "NOT_TESTED", "batch": "NOT_TESTED"},
    }
    with (target / "manifest.json").open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
    return target
