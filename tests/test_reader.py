import json
from unittest.mock import patch

from pgcheck.reader import ExportReadError, load_export
from tests.helpers import ExportCase


class ReaderTests(ExportCase):
    def test_reads_all_required_streams(self):
        data = load_export(self.export)
        self.assertEqual(data.manifest["validation_context"], "synthetic")
        self.assertEqual([len(data.cells), len(data.instances), len(data.nets),
                          len(data.connections), len(data.unresolved)], [2, 3, 10, 16, 0])

    def test_utf8_and_escaped_strings_round_trip(self):
        data = load_export(self.export)
        self.assertIn('quote="', data.manifest["notes"])
        self.assertIn("backslash=\\", data.manifest["notes"])
        self.assertIn("newline=\n", data.manifest["notes"])
        self.assertIn("tab=\t", data.manifest["notes"])
        self.assertIn("합성", data.manifest["notes"])
        self.assertIn("진단", data.cells[0]["db_id"])

    def test_missing_export_directory(self):
        with self.assertRaises(ExportReadError):
            load_export(self.base / "missing")

    def test_all_six_files_are_required(self):
        for name in ("manifest.json", "cells.jsonl", "instances.jsonl", "nets.jsonl",
                     "connections.jsonl", "unresolved.jsonl"):
            with self.subTest(name=name):
                path = self.export / name
                original = path.read_bytes()
                path.unlink()
                with self.assertRaises(ExportReadError):
                    load_export(self.export)
                path.write_bytes(original)

    def test_invalid_utf8_is_rejected(self):
        for name in ("manifest.json", "cells.jsonl"):
            with self.subTest(name=name):
                path = self.export / name
                original = path.read_bytes()
                path.write_bytes(b'{"bad":"\xff"}\n')
                with self.assertRaises(ExportReadError):
                    load_export(self.export)
                path.write_bytes(original)

    def test_bom_is_rejected(self):
        for name in ("manifest.json", "cells.jsonl"):
            with self.subTest(name=name):
                path = self.export / name
                original = path.read_bytes()
                path.write_bytes(b"\xef\xbb\xbf" + original)
                with self.assertRaises(ExportReadError):
                    load_export(self.export)
                path.write_bytes(original)

    def test_duplicate_keys_rejected_at_any_depth(self):
        bad_documents = ['{"id":"a","id":"b"}\n', '{"nested":{"x":1,"x":2}}\n']
        for name in ("manifest.json", "cells.jsonl"):
            path = self.export / name
            original = path.read_bytes()
            for content in bad_documents:
                with self.subTest(name=name, content=content):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(ExportReadError):
                        load_export(self.export)
            path.write_bytes(original)

    def test_nonfinite_numbers_rejected(self):
        path = self.export / "cells.jsonl"
        original = path.read_bytes()
        for value in ("NaN", "Infinity", "-Infinity", "1e999"):
            with self.subTest(value=value):
                path.write_text('{"number":' + value + '}\n', encoding="utf-8")
                with self.assertRaises(ExportReadError):
                    load_export(self.export)
        path.write_bytes(original)

    def test_lone_unicode_surrogate_escape_is_rejected(self):
        for name in ("manifest.json", "cells.jsonl"):
            path = self.export / name
            original = path.read_bytes()
            for escape in (r"\ud800", r"\udfff"):
                with self.subTest(name=name, escape=escape):
                    path.write_text('{"value":"' + escape + '"}\n', encoding="utf-8")
                    with self.assertRaises(ExportReadError):
                        load_export(self.export)
            path.write_bytes(original)

    def test_valid_unicode_surrogate_pair_is_accepted(self):
        path = self.export / "cells.jsonl"
        path.write_text(r'{"value":"\ud83d\ude00"}' + "\n", encoding="utf-8")
        self.assertEqual(load_export(self.export).cells[0]["value"], "😀")

    def test_parser_recursion_limit_is_reported_as_read_error(self):
        # Python versions have different JSON nesting limits.
        with patch("pgcheck.reader.json.loads", side_effect=RecursionError("nesting limit")):
            with self.assertRaises(ExportReadError):
                load_export(self.export)

    def test_jsonl_lines_must_be_objects(self):
        path = self.export / "cells.jsonl"
        for content in ("[]\n", "null\n", "42\n", '"string"\n'):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ExportReadError):
                    load_export(self.export)

    def test_manifest_must_be_object(self):
        (self.export / "manifest.json").write_text("[]", encoding="utf-8")
        with self.assertRaises(ExportReadError):
            load_export(self.export)

    def test_malformed_json_and_blank_lines_rejected(self):
        path = self.export / "cells.jsonl"
        for content in ('{"id":\n', '{} {}\n', '{}\n\n', '{}\n  \n', '{"a":1,}\n'):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ExportReadError):
                    load_export(self.export)

    def test_truncated_manifest_rejected(self):
        (self.export / "manifest.json").write_text('{"status":', encoding="utf-8")
        with self.assertRaises(ExportReadError):
            load_export(self.export)

    def test_schema_fields_are_left_to_validator(self):
        (self.export / "cells.jsonl").write_text('{}\n', encoding="utf-8")
        self.assertEqual(load_export(self.export).cells, [{}])

    def test_additional_diagnostic_fields_are_preserved(self):
        self.mutate_file("manifest.json", lambda row: row.update(site_debug={"label": "한국어"}))
        self.assertEqual(load_export(self.export).manifest["site_debug"], {"label": "한국어"})

    def test_empty_unresolved_stream_is_valid(self):
        self.assertEqual((self.export / "unresolved.jsonl").read_bytes(), b"")
        self.assertEqual(load_export(self.export).unresolved, [])
