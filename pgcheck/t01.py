"""Hand-written T01 oracle. Never derives expected edges from exporter output."""
from __future__ import annotations

from .reader import Dataset
from .validator import Issue, ValidationReport, validate

EXPECTED = {
    "U_LOAD0": {"VDD": "VDD_A", "VSS": "VSS_A", "EN": "CTRL"},
    "U_LOAD1": {"VDD": "VDD_B", "VSS": "VSS_A", "EN": "CTRL"},
}
TOP_PORTS = {"VDD_A": "inputOutput", "VDD_B": "inputOutput",
             "VSS_A": "inputOutput", "CTRL": "input"}
LOAD_PORTS = {"VDD": "inputOutput", "VSS": "inputOutput", "EN": "input"}


def check_t01(data: Dataset) -> ValidationReport:
    report = validate(data)
    if any(i.code == "SCHEMA" for i in report.issues):
        return report

    def fail(message: str, path: str = "") -> None:
        report.issues.append(Issue("T01", message, path))

    cells = {c["id"]: c for c in data.cells}
    instances = {i["id"]: i for i in data.instances}
    nets = {n["id"]: n for n in data.nets}
    root = instances.get(data.manifest["root_instance_id"])
    if root is None:
        fail("Missing T01 root")
        return report
    if data.manifest["top"]["cell"] != "PGC_T01_TOP" or data.manifest["top"]["view"] != "schematic":
        fail("Expected PGC_T01_TOP/schematic")
    if len(data.instances) != 3 or len(data.cells) != 2:
        fail("Expected root plus exactly two logical LOAD occurrences and two cell definitions")
    children = [i for i in data.instances if i["parent_id"] == root["id"]]
    if sorted(i["name"] for i in children) != sorted(EXPECTED):
        fail("Expected U_LOAD0 and U_LOAD1 as the root's direct children")

    for instance in [root] + children:
        cell = cells.get(instance["cell_id"])
        if cell is None:
            fail("Missing selected T01 cell", instance["path"])
            continue
        is_root = instance["id"] == root["id"]
        ports = TOP_PORTS if is_root else LOAD_PORTS
        if {t["name"]: t["direction"] for t in cell["terminals"]} != ports:
            fail(f"Terminal names/directions differ from {ports!r}", instance["path"])
        if sorted(cell["local_net_names"]) != sorted(ports):
            fail("Local net names differ from fixed T01 oracle", instance["path"])
        if not is_root:
            expected_master = {"library": data.manifest["top"]["library"],
                               "cell": "PGC_T01_LOAD", "view": "symbol"}
            if instance["master"] != expected_master:
                fail("LOAD must be placed from same-library PGC_T01_LOAD/symbol", instance["path"])
            if instance["selected"] != dict(expected_master, view="schematic"):
                fail("LOAD selected view must be PGC_T01_LOAD/schematic", instance["path"])
        for port in ports:
            edges = [e for e in data.connections if e["kind"] == "cell_port"
                     and e["instance_id"] == instance["id"] and e["port"] == port]
            if len(edges) != 1 or edges[0]["status"] != "connected":
                fail(f"Expected connected cell_port {port}", instance["path"])
            elif nets.get(edges[0]["net_id"], {}).get("name") != port:
                fail(f"cell_port {port} must connect to same-name local net", instance["path"])
        if not is_root and instance["name"] in EXPECTED:
            for port, net_name in EXPECTED[instance["name"]].items():
                edges = [e for e in data.connections if e["kind"] == "instance_port"
                         and e["instance_id"] == instance["id"] and e["port"] == port]
                if len(edges) != 1 or edges[0]["status"] != "connected":
                    fail(f"Expected connected {instance['name']}.{port}", instance["path"])
                elif nets.get(edges[0]["net_id"], {}).get("name") != net_name:
                    fail(f"Expected {instance['name']}.{port} -> {net_name}", instance["path"])
    if len({i["cell_id"] for i in children}) != 1:
        fail("Both LOAD occurrences must share one selected cell definition")
    if len(data.connections) != 16:
        fail("Expected 6 instance_port and 10 cell_port edges")
    return report
