import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pgcheck.environment import inspect_environment


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix=".pgcheck-environment-",
                                       dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_reports_only_local_python_success(self):
        with patch("pgcheck.environment.shutil.which", return_value=None):
            report = inspect_environment(self.base)
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["output_writable"])
        self.assertTrue(report["python_supported"])
        self.assertFalse(report["virtuoso_on_path"])
        self.assertEqual(list(self.base.iterdir()), [])
        self.assertIsInstance(json.loads(json.dumps(report)), dict)

    def test_virtuoso_executable_presence_never_certifies_runtime(self):
        with patch("pgcheck.environment.shutil.which", return_value="/approved/bin/virtuoso"):
            report = inspect_environment(str(self.base))
        self.assertTrue(report["virtuoso_on_path"])
        for key in ("virtuoso_runtime", "api_probe", "ciw", "batch"):
            self.assertEqual(report[key], "NOT_TESTED")

    def test_missing_output_directory_records_failure_without_creating_it(self):
        missing = self.base / "does-not-exist"
        report = inspect_environment(missing)
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["output_writable"])
        self.assertTrue(report["write_error"])
        self.assertFalse(missing.exists())

    def test_unsupported_python_records_failure(self):
        with patch("pgcheck.environment.sys.version_info", (3, 9, 0)):
            report = inspect_environment(self.base)
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["python_supported"])

    def test_locale_report_is_limited_to_relevant_keys(self):
        with patch.dict("pgcheck.environment.os.environ",
                        {"LC_ALL": "C.UTF-8", "SECRET_TOKEN": "do-not-record"}, clear=True):
            report = inspect_environment(self.base)
        self.assertEqual(set(report["locale"]), {"LC_ALL", "LC_CTYPE", "LANG"})
        self.assertEqual(report["locale"]["LC_ALL"], "C.UTF-8")
        self.assertNotIn("do-not-record", json.dumps(report))
