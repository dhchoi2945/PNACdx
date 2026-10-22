import unittest
import json
from pathlib import Path

from pgcheck.schema import SCHEMAS, arr, obj, schema_errors


class SchemaTests(unittest.TestCase):
    def errors(self, value, schema):
        return list(schema_errors(value, schema, "root"))

    def test_object_helper_requires_each_property_by_default(self):
        schema = obj({"name": {"type": "string"}, "count": {"type": "integer"}})
        self.assertEqual(schema["required"], ["name", "count"])
        self.assertEqual(self.errors({"name": "x", "count": 2}, schema), [])
        self.assertEqual(self.errors({"name": "x"}, schema)[0][0], "root.count")

    def test_explicit_optional_properties(self):
        schema = obj({"name": {"type": "string"}}, required=[])
        self.assertEqual(self.errors({}, schema), [])

    def test_array_helper_and_nested_diagnostic_paths(self):
        schema = obj({"rows": arr(obj({"id": {"type": "string", "minLength": 1}}))})
        self.assertEqual(self.errors({"rows": [{"id": ""}]}, schema)[0][0], "root.rows[0].id")

    def test_exact_json_types_reject_boolean_numeric_aliases(self):
        for kind, wrong in (("integer", True), ("number", False), ("array", {}),
                            ("object", []), ("string", 1), ("null", "null")):
            with self.subTest(kind=kind):
                self.assertTrue(self.errors(wrong, {"type": kind}))

    def test_nullable_records_do_not_require_child_properties(self):
        self.assertEqual(self.errors(None, SCHEMAS["instances"]["properties"]["selected"]), [])
        self.assertEqual(self.errors(None, SCHEMAS["instances"]["properties"]["placement"]), [])

    def test_nonfinite_numbers_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                self.assertTrue(self.errors(value, {"type": "number"}))
        self.assertEqual(self.errors(-1.25, {"type": "number"}), [])

    def test_minimum_and_empty_strings(self):
        self.assertTrue(self.errors(-1, {"type": "integer", "minimum": 0}))
        self.assertEqual(self.errors(0, {"type": "integer", "minimum": 0}), [])
        self.assertTrue(self.errors("", {"type": "string", "minLength": 1}))

    def test_const_enum_and_additional_diagnostics(self):
        self.assertTrue(self.errors("other", {"const": "1.0"}))
        self.assertTrue(self.errors("other", {"enum": ["connected", "unconnected"]}))
        self.assertEqual(self.errors({"extra": {"site": "local"}}, obj({}, required=[])), [])

    def test_each_required_stream_has_a_schema(self):
        self.assertEqual(set(SCHEMAS),
                         {"manifest", "cells", "instances", "nets", "connections", "unresolved"})

    def test_emitted_json_schemas_match_the_runtime_contract(self):
        root = Path(__file__).resolve().parents[1] / "schema"
        self.assertEqual({path.name for path in root.glob("*.schema.json")},
                         {name + ".schema.json" for name in SCHEMAS})
        for name, schema in SCHEMAS.items():
            with self.subTest(name=name):
                emitted = json.loads((root / (name + ".schema.json")).read_text(encoding="utf-8"))
                self.assertEqual(emitted.pop("$schema"), "https://json-schema.org/draft/2020-12/schema")
                self.assertEqual(emitted, schema)
