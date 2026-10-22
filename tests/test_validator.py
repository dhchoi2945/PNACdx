import copy
import json

from pgcheck.validator import Issue, ValidationReport, validate
from tests.helpers import ExportCase


class ValidatorTests(ExportCase):
    def assert_invalid(self, data):
        report = validate(data)
        self.assertFalse(report.ok, report.as_dict())
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(report.issues)
        self.assertTrue(any(issue.severity == "error" for issue in report.issues))
        return report

    def test_valid_dataset_and_serializable_report(self):
        report = validate(self.dataset())
        self.assertTrue(report.ok, report.as_dict())
        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.issues, [])
        self.assertEqual(json.loads(json.dumps(report.as_dict()))["status"], "PASS")

    def test_report_helpers_preserve_issue_fields_and_severity(self):
        report = ValidationReport([Issue("OPTIONAL_PLACEMENT", "Coordinate unavailable", "instances[1]", "warning")])
        self.assertTrue(report.ok)
        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.as_dict()["issues"][0],
                         {"code": "OPTIONAL_PLACEMENT", "message": "Coordinate unavailable",
                          "path": "instances[1]", "severity": "warning"})
        report.issues.append(Issue("BAD_REF", "Reference missing"))
        self.assertFalse(report.ok)
        self.assertEqual(report.status, "FAIL")

    def test_malformed_collections_fail_cleanly_before_integrity_checks(self):
        for stream in ("cells", "instances", "nets", "connections", "unresolved"):
            with self.subTest(stream=stream):
                data = self.dataset()
                setattr(data, stream, {})
                self.assert_invalid(data)

    def test_duplicate_cell_definition_and_sibling_names_rejected(self):
        data = self.dataset()
        data.cells[1].update(library=data.cells[0]["library"],
                             cell=data.cells[0]["cell"], view=data.cells[0]["view"])
        self.assert_invalid(data)
        data = self.dataset()
        data.instances[2]["name"] = data.instances[1]["name"]
        self.assert_invalid(data)

    def test_duplicate_occurrence_paths_rejected(self):
        data = self.dataset()
        data.instances[2]["path"] = data.instances[1]["path"]
        self.assert_invalid(data)

    def test_child_path_must_extend_the_parent_structural_path(self):
        data = self.dataset()
        data.instances[1]["path"] = "/unrelated/U_LOAD0"
        self.assert_invalid(data)

    def test_instance_name_path_components_are_escaped(self):
        data = self.dataset()
        child = data.instances[1]
        child["name"] = "U/LOAD~0"
        child["path"] = data.instances[0]["path"] + "/U~1LOAD~00"
        self.assertTrue(validate(data).ok, validate(data).as_dict())
        child["path"] = data.instances[0]["path"] + "/U/LOAD~0"
        self.assert_invalid(data)

    def test_unknown_unconnected_port_cannot_be_accepted(self):
        data = self.dataset()
        edge = copy.deepcopy(self.edge(data))
        edge.update(id="connection:unexpected", path=edge["path"] + "_EXTRA", port="EXTRA",
                    terminal_id=None, net_id=None, status="unconnected", evidence="db")
        data.connections.append(edge)
        self.refresh_counts(data)
        report = self.assert_invalid(data)
        self.assertTrue(any(issue.code == "UNEXPECTED_PORT" for issue in report.issues))

    def test_missing_required_manifest_fields(self):
        for field in ("schema_version", "run_id", "status", "root_instance_id", "top", "files",
                      "counts", "capabilities", "validation_context"):
            with self.subTest(field=field):
                data = self.dataset()
                del data.manifest[field]
                self.assert_invalid(data)

    def test_missing_required_record_fields(self):
        required = {
            "cells": ("id", "path", "library", "cell", "view", "db_id", "terminals", "local_net_names"),
            "instances": ("id", "path", "name", "parent_id", "cell_id", "master", "selected", "placement"),
            "nets": ("id", "path", "name", "cell_id", "occurrence_id"),
            "connections": ("id", "path", "kind", "owner_instance_id", "instance_id", "port",
                            "terminal_id", "net_id", "status", "evidence", "reason"),
        }
        for stream, fields in required.items():
            for field in fields:
                with self.subTest(stream=stream, field=field):
                    data = self.dataset()
                    del getattr(data, stream)[0][field]
                    self.assert_invalid(data)

    def test_required_terminal_and_unresolved_fields(self):
        for field in ("id", "name", "direction"):
            with self.subTest(terminal=field):
                data = self.dataset()
                del data.cells[0]["terminals"][0][field]
                self.assert_invalid(data)
        for field in ("id", "path", "code", "message", "severity", "object_id"):
            with self.subTest(unresolved=field):
                data = self.dataset()
                self.unresolved_edge(data)
                del data.unresolved[0][field]
                self.assert_invalid(data)

    def test_manifest_enum_types_counts_and_filenames(self):
        changes = [
            ("schema_version", "9"), ("run_id", ""), ("status", "PASS"),
            ("validation_context", "approved"), ("capabilities", []),
            ("counts", {"cells": True}), ("counts", {"cells": -1}),
            ("files", {"cells": "../cells.jsonl"}), ("top", {"library": 3}),
        ]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                data = self.dataset()
                data.manifest[key] = value
                self.assert_invalid(data)

    def test_capability_states_and_policies_must_be_explicit(self):
        for key in ("binding_policy", "saved_status", "connectivity_status",
                    "placement_support", "pin_helper_policy"):
            with self.subTest(missing=key):
                data = self.dataset()
                del data.manifest["capabilities"][key]
                report = self.assert_invalid(data)
                self.assertTrue(any(issue.path == "manifest.capabilities." + key
                                    for issue in report.issues))
        data = self.dataset()
        data.manifest["capabilities"] = {}
        self.assert_invalid(data)

    def test_capability_values_must_be_nonempty_strings(self):
        for key in ("binding_policy", "saved_status", "connectivity_status",
                    "placement_support", "pin_helper_policy"):
            for value in (None, "", True):
                with self.subTest(key=key, value=value):
                    data = self.dataset()
                    data.manifest["capabilities"][key] = value
                    self.assert_invalid(data)

    def test_record_count_mismatch(self):
        data = self.dataset()
        data.manifest["counts"]["nets"] += 1
        self.assert_invalid(data)

    def test_duplicate_ids_across_all_object_types(self):
        for stream in ("cells", "instances", "nets", "connections"):
            with self.subTest(stream=stream):
                data = self.dataset()
                getattr(data, stream)[0]["id"] = data.cells[0]["terminals"][0]["id"]
                self.assert_invalid(data)
        data = self.dataset()
        data.cells[1]["terminals"][0]["id"] = data.cells[0]["terminals"][0]["id"]
        self.assert_invalid(data)

    def test_same_cell_definition_cannot_have_duplicate_local_net_names(self):
        data = self.dataset()
        data.cells[0]["local_net_names"].append("VDD_A")
        self.assert_invalid(data)

    def test_duplicate_terminal_names_rejected(self):
        data = self.dataset()
        term = copy.deepcopy(data.cells[0]["terminals"][0])
        term["id"] = "terminal:new"
        data.cells[0]["terminals"].append(term)
        self.assert_invalid(data)

    def test_references_must_exist(self):
        changes = [("instances", "parent_id"), ("instances", "cell_id"),
                   ("nets", "cell_id"), ("nets", "occurrence_id"),
                   ("connections", "owner_instance_id"), ("connections", "instance_id"),
                   ("connections", "terminal_id"), ("connections", "net_id")]
        for stream, key in changes:
            with self.subTest(stream=stream, key=key):
                data = self.dataset()
                getattr(data, stream)[1][key] = "does-not-exist"
                self.assert_invalid(data)

    def test_unresolved_object_reference_must_exist(self):
        data = self.dataset()
        self.unresolved_edge(data)
        data.unresolved[0]["object_id"] = "does-not-exist"
        self.assert_invalid(data)

    def test_root_must_exist_be_unique_and_have_null_parent(self):
        data = self.dataset()
        data.manifest["root_instance_id"] = "missing-root"
        self.assert_invalid(data)
        data = self.dataset()
        data.instances[1]["parent_id"] = None
        self.assert_invalid(data)
        data = self.dataset()
        data.instances[0]["parent_id"] = data.instances[1]["id"]
        self.assert_invalid(data)

    def test_cycles_and_self_parent_rejected_without_recursion_failure(self):
        data = self.dataset()
        data.instances[1]["parent_id"] = data.instances[1]["id"]
        self.assert_invalid(data)
        data = self.dataset()
        data.instances[1]["parent_id"] = data.instances[2]["id"]
        data.instances[2]["parent_id"] = data.instances[1]["id"]
        self.assert_invalid(data)

    def test_instance_master_and_selection_are_explicit(self):
        data = self.dataset()
        data.instances[1]["selected"]["cell"] = "WRONG_CELL"
        self.assert_invalid(data)
        data = self.dataset()
        data.instances[1]["cell_id"] = None
        data.instances[1]["selected"] = None
        self.assert_invalid(data)

    def test_net_cell_must_match_its_occurrence(self):
        data = self.dataset()
        next(net for net in data.nets if net["occurrence_id"] == "instance:load0")["cell_id"] = "cell:top"
        self.assert_invalid(data)

    def test_local_net_coverage_and_unique_occurrence_names(self):
        data = self.dataset()
        data.nets.pop()
        self.refresh_counts(data)
        self.assert_invalid(data)
        data = self.dataset()
        duplicate = copy.deepcopy(data.nets[0])
        duplicate["id"] = "net:duplicate"
        data.nets.append(duplicate)
        self.refresh_counts(data)
        self.assert_invalid(data)

    def test_identical_names_never_merge_across_occurrences(self):
        data = self.dataset()
        edge = self.edge(data, "instance:load1", "VDD", "cell_port")
        edge["net_id"] = "net:load0:VDD"
        self.assert_invalid(data)

    def test_instance_ports_require_direct_parent_scope(self):
        data = self.dataset()
        self.edge(data)["net_id"] = "net:load0:VDD"
        self.assert_invalid(data)
        data = self.dataset()
        self.edge(data)["owner_instance_id"] = "instance:load1"
        self.assert_invalid(data)

    def test_cell_port_owner_matches_occurrence(self):
        data = self.dataset()
        self.edge(data, kind="cell_port")["owner_instance_id"] = "instance:root"
        self.assert_invalid(data)

    def test_connection_terminal_matches_selected_cell_and_port_name(self):
        data = self.dataset()
        self.edge(data)["terminal_id"] = "terminal:top:VDD_A"
        self.assert_invalid(data)
        data = self.dataset()
        self.edge(data)["terminal_id"] = "terminal:load:VSS"
        self.assert_invalid(data)

    def test_each_port_must_have_exactly_one_edge_of_each_required_kind(self):
        for kind in ("cell_port", "instance_port"):
            with self.subTest(kind=kind):
                data = self.dataset()
                data.connections.remove(self.edge(data, kind=kind))
                self.refresh_counts(data)
                self.assert_invalid(data)
                data = self.dataset()
                duplicate = copy.deepcopy(self.edge(data, kind=kind))
                duplicate["id"] = "connection:duplicate"
                data.connections.append(duplicate)
                self.refresh_counts(data)
                self.assert_invalid(data)

    def test_root_does_not_have_parent_instance_port(self):
        data = self.dataset()
        edge = self.edge(data, "instance:root", "VDD_A", "cell_port")
        edge["kind"] = "instance_port"
        self.assert_invalid(data)

    def test_connected_requires_net_terminal_and_db_evidence(self):
        for field, value in (("net_id", None), ("terminal_id", None), ("evidence", "none")):
            with self.subTest(field=field):
                data = self.dataset()
                self.edge(data)[field] = value
                self.assert_invalid(data)

    def test_successfully_inspected_unconnected_port_is_valid(self):
        data = self.dataset()
        self.edge(data).update(status="unconnected", net_id=None, evidence="db")
        self.assertTrue(validate(data).ok, validate(data).as_dict())

    def test_unconnected_cannot_hide_access_failure_or_have_net(self):
        data = self.dataset()
        self.edge(data).update(status="unconnected", evidence="none", net_id=None)
        self.assert_invalid(data)
        data = self.dataset()
        self.edge(data).update(status="unconnected", evidence="db")
        self.assert_invalid(data)

    def test_unresolved_is_reported_and_never_passes(self):
        data = self.dataset()
        self.unresolved_edge(data)
        report = validate(data)
        self.assertFalse(report.ok)
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(report.issues)
        detail = next(issue for issue in report.issues if issue.code == "UNRESOLVED:DB_ACCESS")
        self.assertEqual(detail.message, data.unresolved[0]["message"])
        self.assertEqual(detail.path, data.unresolved[0]["path"])
        self.assertEqual(detail.severity, data.unresolved[0]["severity"])

    def test_unresolved_connection_requires_reason_and_matching_diagnostic(self):
        data = self.dataset()
        edge = self.unresolved_edge(data)
        edge["reason"] = None
        self.assert_invalid(data)
        data = self.dataset()
        self.unresolved_edge(data)
        data.unresolved.clear()
        self.refresh_counts(data)
        self.assert_invalid(data)

    def test_complete_cannot_contain_unresolved_records(self):
        data = self.dataset()
        self.unresolved_edge(data)
        data.manifest["status"] = "complete"
        self.assert_invalid(data)

    def test_incomplete_cannot_be_reported_pass(self):
        data = self.dataset()
        data.manifest["status"] = "incomplete"
        self.assert_invalid(data)

    def test_optional_null_placement_is_valid(self):
        data = self.dataset()
        for occurrence in data.instances:
            occurrence["placement"] = None
        self.assertTrue(validate(data).ok, validate(data).as_dict())

    def test_placement_types_scope_and_finite_numbers(self):
        for key, value in (("x", float("inf")), ("y", True), ("orientation", None),
                           ("coordinate_system", "global"), ("units", 123)):
            with self.subTest(key=key):
                data = self.dataset()
                data.instances[1]["placement"][key] = value
                self.assert_invalid(data)

    def test_root_placement_must_be_null(self):
        data = self.dataset()
        data.instances[0]["placement"] = copy.deepcopy(data.instances[1]["placement"])
        self.assert_invalid(data)

    def test_unknown_connection_status_kind_and_evidence_rejected(self):
        for field, value in (("status", "assumed"), ("kind", "wire"), ("evidence", "inferred")):
            with self.subTest(field=field):
                data = self.dataset()
                self.edge(data)[field] = value
                self.assert_invalid(data)
