"""Synthetic test helpers; no private design data or network access."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from pgcheck.reader import load_export
from pgcheck.synthetic import create_t01


class ExportCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix=".pgcheck-test-", dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.export = create_t01(self.base / "export")

    def dataset(self):
        return copy.deepcopy(load_export(self.export))

    def mutate_file(self, name, transform):
        path = self.export / name
        value = json.loads(path.read_text(encoding="utf-8"))
        transform(value)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def refresh_counts(self, data):
        for stem in ("cells", "instances", "nets", "connections", "unresolved"):
            data.manifest["counts"][stem] = len(getattr(data, stem))

    def edge(self, data, instance="instance:load0", port="VDD", kind="instance_port"):
        return next(row for row in data.connections
                    if row["instance_id"] == instance and row["port"] == port
                    and row["kind"] == kind)

    def unresolved_edge(self, data, edge=None):
        edge = edge if edge is not None else self.edge(data)
        edge.update(status="unresolved", evidence="none", net_id=None,
                    reason="synthetic DB access failure")
        data.unresolved.append({"id": "unresolved:test", "path": edge["path"],
                                "code": "DB_ACCESS", "message": "synthetic DB access failure",
                                "severity": "error", "object_id": edge["id"]})
        data.manifest["status"] = "incomplete"
        self.refresh_counts(data)
        return edge
