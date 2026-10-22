"""Occurrence-aware structural and referential integrity validation."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from .reader import Dataset, FILES
from .schema import SCHEMAS, schema_errors


@dataclass
class Issue:
    code: str
    message: str
    path: str = ""
    severity: str = "error"


@dataclass
class ValidationReport:
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    @property
    def status(self) -> str:
        return "PASS" if self.ok else "FAIL"

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "issues": [asdict(i) for i in self.issues]}


def validate(data: Dataset) -> ValidationReport:
    report = ValidationReport()

    def fail(code: str, message: str, path: str = "") -> None:
        report.issues.append(Issue(code, message, path))

    groups = {name: getattr(data, name) for name in FILES}
    for path, message in schema_errors(data.manifest, SCHEMAS["manifest"], "manifest"):
        fail("SCHEMA", message, path)
    for name, rows in groups.items():
        if not isinstance(rows, list):
            fail("SCHEMA", "records must be a list", name)
            continue
        for index, row in enumerate(rows):
            for path, message in schema_errors(row, SCHEMAS[name], f"{name}[{index}]"):
                fail("SCHEMA", message, path)
    # Do not let a malformed type crash deeper integrity checks.
    if report.issues:
        return report

    all_ids: dict[str, str] = {}

    def register(identifier: str, location: str) -> None:
        if identifier in all_ids:
            fail("DUPLICATE_ID", f"ID {identifier!r} already used at {all_ids[identifier]}", location)
        else:
            all_ids[identifier] = location

    for name, rows in groups.items():
        for row in rows:
            register(row["id"], f"{name}:{row['path']}")
    cells = {c["id"]: c for c in data.cells}
    insts = {i["id"]: i for i in data.instances}
    nets = {n["id"]: n for n in data.nets}
    terminals = {}
    seen_cell_keys = set()
    for cell in data.cells:
        key = tuple(cell[k] for k in ("library", "cell", "view"))
        if key in seen_cell_keys:
            fail("DUPLICATE_CELL", f"Repeated cell definition {key}", cell["path"])
        seen_cell_keys.add(key)
        names = [t["name"] for t in cell["terminals"]]
        if len(set(names)) != len(names):
            fail("DUPLICATE_PORT", "Repeated terminal name", cell["path"])
        if len(set(cell["local_net_names"])) != len(cell["local_net_names"]):
            fail("DUPLICATE_LOCAL_NET", "Repeated local net name", cell["path"])
        for terminal in cell["terminals"]:
            register(terminal["id"], f"terminal:{cell['path']}/{terminal['name']}")
            terminals[terminal["id"]] = (cell["id"], terminal["name"])
    for name, rows in groups.items():
        if data.manifest["counts"][name] != len(rows):
            fail("COUNT", f"Manifest count differs from {len(rows)}", name)
    if data.manifest["status"] != "complete":
        fail("INCOMPLETE", "Exporter did not declare a complete extraction", "manifest.status")
    if data.unresolved:
        fail("UNRESOLVED", f"{len(data.unresolved)} unresolved diagnostics present", "unresolved")
        for diagnostic in data.unresolved:
            report.issues.append(Issue("UNRESOLVED:" + diagnostic["code"],
                                       diagnostic["message"], diagnostic["path"],
                                       diagnostic["severity"]))

    root_id = data.manifest["root_instance_id"]
    root = insts.get(root_id)
    if root is None:
        fail("ROOT", "root_instance_id does not exist", "manifest.root_instance_id")
    roots = [i for i in data.instances if i["parent_id"] is None]
    if len(roots) != 1 or (roots and roots[0]["id"] != root_id):
        fail("ROOT", "Exactly one root occurrence must match the manifest")
    sibling_names = set()
    occurrence_paths = set()
    used_cells = set()
    for instance in data.instances:
        iid, cid, parent = instance["id"], instance["cell_id"], instance["parent_id"]
        if instance["path"] in occurrence_paths:
            fail("DUPLICATE_PATH", "Occurrences have the same structural path", instance["path"])
        occurrence_paths.add(instance["path"])
        sibling = (parent, instance["name"])
        if sibling in sibling_names:
            fail("DUPLICATE_INSTANCE", "Duplicate instance name in parent", instance["path"])
        sibling_names.add(sibling)
        if parent is not None and parent not in insts:
            fail("PARENT_REF", f"Missing parent {parent!r}", instance["path"])
        elif parent is not None:
            escaped = instance["name"].replace("~", "~0").replace("/", "~1")
            if instance["path"] != insts[parent]["path"] + "/" + escaped:
                fail("PARENT_PATH", "Path must extend parent path with escaped instance name", instance["path"])
        visited = set()
        cursor = instance
        while cursor is not None:
            if cursor["id"] in visited:
                fail("PARENT_CYCLE", "Cycle in occurrence parent chain", instance["path"])
                break
            visited.add(cursor["id"])
            cursor = insts.get(cursor["parent_id"])
        if cid is None:
            if instance["selected"] is not None:
                fail("SELECTION", "Unresolved occurrence must have null selected view", instance["path"])
            if not any(u["object_id"] == iid for u in data.unresolved):
                fail("UNRESOLVED_DIAGNOSTIC", "Missing diagnostic for unresolved occurrence", instance["path"])
            fail("UNRESOLVED_INSTANCE", "Occurrence has no selected cell", instance["path"])
        elif cid not in cells:
            fail("CELL_REF", f"Missing cell {cid!r}", instance["path"])
        else:
            used_cells.add(cid)
            selected = {k: cells[cid][k] for k in ("library", "cell", "view")}
            if instance["selected"] != selected:
                fail("SELECTION", "Selected view differs from cell definition", instance["path"])
            if any(instance["master"][k] != selected[k] for k in ("library", "cell")):
                fail("BINDING", "Phase 0 explicit binding must preserve library and cell", instance["path"])
        if parent is None and instance["placement"] is not None:
            fail("PLACEMENT", "Root has no parent-local placement", instance["path"])
    if root and root["selected"] != data.manifest["top"]:
        fail("TOP", "Manifest top differs from selected root view")
    if used_cells != set(cells):
        fail("UNUSED_CELL", "Cell definitions must belong to at least one occurrence")

    occurrence_nets: dict[str, list[str]] = defaultdict(list)
    for net in data.nets:
        occurrence = insts.get(net["occurrence_id"])
        if occurrence is None:
            fail("NET_OCCURRENCE_REF", "Net occurrence does not exist", net["path"])
        elif occurrence["cell_id"] != net["cell_id"]:
            fail("NET_SCOPE", "Net cell differs from its occurrence's cell", net["path"])
        if net["cell_id"] not in cells:
            fail("NET_CELL_REF", "Net cell does not exist", net["path"])
        occurrence_nets[net["occurrence_id"]].append(net["name"])
    for instance in data.instances:
        if instance["cell_id"] in cells:
            expected = cells[instance["cell_id"]]["local_net_names"]
            if Counter(occurrence_nets[instance["id"]]) != Counter(expected):
                fail("NET_COVERAGE", "Local nets missing, duplicated or unexpected", instance["path"])

    seen_edges: dict[tuple[str, str, str], int] = Counter()
    for edge in data.connections:
        location = edge["path"]
        occurrence = insts.get(edge["instance_id"])
        owner = insts.get(edge["owner_instance_id"])
        net = nets.get(edge["net_id"])
        seen_edges[(edge["kind"], edge["instance_id"], edge["port"])] += 1
        if occurrence is None or owner is None:
            fail("CONNECTION_INSTANCE_REF", "Connection instance/owner does not exist", location)
        elif edge["kind"] == "cell_port":
            if owner["id"] != occurrence["id"]:
                fail("CONNECTION_OWNER", "cell_port owner must be its occurrence", location)
        elif occurrence["parent_id"] != owner["id"]:
            fail("CONNECTION_OWNER", "instance_port owner must be direct parent", location)
        tid = edge["terminal_id"]
        if tid is not None:
            if tid not in terminals:
                fail("TERMINAL_REF", "Connection terminal does not exist", location)
            elif occurrence and terminals[tid] != (occurrence["cell_id"], edge["port"]):
                fail("TERMINAL_SCOPE", "Port/terminal does not belong to selected child cell", location)
        if edge["status"] == "connected":
            if net is None or tid is None or edge["evidence"] != "db":
                fail("CONNECTED_STATE", "Connected edge needs real net, terminal and DB evidence", location)
        else:
            if edge["net_id"] is not None:
                fail("DISCONNECTED_STATE", "Unconnected/unresolved edge must have null net", location)
            if edge["status"] == "unconnected" and (edge["evidence"] != "db" or tid is None):
                fail("UNCONNECTED_STATE", "Unconnected requires successful DB inspection and terminal", location)
            if edge["status"] == "unresolved":
                if not edge["reason"]:
                    fail("UNRESOLVED_REASON", "Unresolved edge needs a reason", location)
                if not any(u["object_id"] == edge["id"] for u in data.unresolved):
                    fail("UNRESOLVED_DIAGNOSTIC", "Unresolved edge needs a matching diagnostic", location)
                fail("UNRESOLVED_CONNECTION", edge["reason"] or "Unresolved edge", location)
        if edge["status"] != "unresolved" and edge["reason"] is not None:
            fail("CONNECTION_REASON", "Resolved connection reason must be null", location)
        if net and (not owner or net["occurrence_id"] != owner["id"]):
            fail("CONNECTION_NET_SCOPE", "Connection net must belong to owner occurrence", location)
    for key, count in seen_edges.items():
        if count != 1:
            fail("DUPLICATE_CONNECTION", f"Repeated connection {key!r}")
        kind, iid, port = key
        occurrence = insts.get(iid)
        cell = cells.get(occurrence["cell_id"]) if occurrence else None
        if cell and port not in {t["name"] for t in cell["terminals"]}:
            # Mismatched placed/selected ports may appear only as unresolved.
            rows = [e for e in data.connections if
                    (e["kind"], e["instance_id"], e["port"]) == key]
            if kind == "cell_port" or any(e["status"] != "unresolved" for e in rows):
                fail("UNEXPECTED_PORT", f"Port {port!r} absent from selected cell")
    for instance in data.instances:
        if instance["cell_id"] not in cells:
            continue
        for terminal in cells[instance["cell_id"]]["terminals"]:
            for kind in ("cell_port", "instance_port"):
                if kind == "instance_port" and instance["parent_id"] is None:
                    continue
                key = (kind, instance["id"], terminal["name"])
                if seen_edges[key] != 1:
                    fail("PORT_COVERAGE", f"Expected exactly one {kind} for {terminal['name']}", instance["path"])
    for diagnostic in data.unresolved:
        target = diagnostic["object_id"]
        if target is not None and (target not in all_ids or all_ids[target].startswith("unresolved:")):
            fail("DIAGNOSTIC_REF", "Unresolved diagnostic references a missing/diagnostic object", diagnostic["path"])
    return report
