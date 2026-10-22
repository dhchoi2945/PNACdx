import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pgcheck.reader import load_export
from pgcheck.synthetic import create_t01
from pgcheck.t01 import check_t01
from pgcheck.validator import validate


class SyntheticTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix=".pgcheck-synthetic-",
                                       dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_fresh_export_passes_independent_validator_and_oracle(self):
        target = create_t01(self.base / "run")
        data = load_export(target)
        self.assertTrue(validate(data).ok, validate(data).as_dict())
        self.assertTrue(check_t01(data).ok, check_t01(data).as_dict())

    def test_existing_directory_is_never_overwritten(self):
        target = self.base / "run"
        target.mkdir()
        sentinel = target / "keep.txt"
        sentinel.write_text("existing", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            create_t01(target)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "existing")
        self.assertEqual(list(target.iterdir()), [sentinel])

    def test_existing_export_is_never_overwritten(self):
        target = create_t01(self.base / "run")
        originals = {file.name: file.read_bytes() for file in target.iterdir()}
        with self.assertRaises(FileExistsError):
            create_t01(target)
        self.assertEqual(originals, {file.name: file.read_bytes() for file in target.iterdir()})

    def test_each_run_has_a_distinct_run_id(self):
        first = load_export(create_t01(self.base / "one"))
        second = load_export(create_t01(self.base / "two"))
        self.assertNotEqual(first.manifest["run_id"], second.manifest["run_id"])

    def test_manifest_does_not_certify_internal_tests(self):
        data = load_export(create_t01(self.base / "run"))
        self.assertEqual(data.manifest["validation_context"], "synthetic")
        self.assertTrue(all(value == "NOT_TESTED" for value in data.manifest["internal_checks"].values()))

    def test_exact_expected_edges_are_hand_authored(self):
        data = load_export(create_t01(self.base / "run"))
        instances = {row["id"]: row["name"] for row in data.instances}
        nets = {row["id"]: row["name"] for row in data.nets}
        actual = {(instances[row["instance_id"]], row["port"], nets[row["net_id"]])
                  for row in data.connections if row["kind"] == "instance_port"}
        expected = {("U_LOAD0", "VDD", "VDD_A"), ("U_LOAD0", "VSS", "VSS_A"),
                    ("U_LOAD0", "EN", "CTRL"), ("U_LOAD1", "VDD", "VDD_B"),
                    ("U_LOAD1", "VSS", "VSS_A"), ("U_LOAD1", "EN", "CTRL")}
        self.assertEqual(actual, expected)

    def test_local_nets_are_separate_for_shared_cell_occurrences(self):
        data = load_export(create_t01(self.base / "run"))
        copies = [row for row in data.nets if row["name"] == "VDD"]
        self.assertEqual(len(copies), 2)
        self.assertEqual(len({row["cell_id"] for row in copies}), 1)
        self.assertEqual(len({row["occurrence_id"] for row in copies}), 2)
        self.assertEqual(len({row["id"] for row in copies}), 2)

    def test_files_are_utf8_without_bom_and_jsonl_is_single_line(self):
        target = create_t01(self.base / "run")
        for file in target.iterdir():
            raw = file.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
            text = raw.decode("utf-8", errors="strict")
            if file.suffix == ".jsonl":
                for line in text.splitlines():
                    self.assertIsInstance(json.loads(line), dict)
        self.assertIn("합성", (target / "manifest.json").read_text(encoding="utf-8"))
