import io
import json
import subprocess
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from pgcheck.batch import main, run_batch, skill_string
from pgcheck.synthetic import create_t01
from tests.helpers import ExportCase


class BatchTests(ExportCase):
    def setUp(self):
        super().setUp()
        self.output = self.base / "batch-export"
        self.diagnostics = self.base / "batch-diagnostics"
        self.source = self.base / "source"
        module_dir = self.source / "skill"
        module_dir.mkdir(parents=True)
        for name in ("pgcheck_json.il", "pgcheck_export.il"):
            (module_dir / name).write_text("; mock-only source\n", encoding="utf-8")

    def batch(self, **kwargs):
        return run_batch("APPROVED_TEST", "PGC_T01_TOP", "schematic", self.output,
                         self.diagnostics, source_root=self.source, **kwargs)

    def test_skill_string_escapes_quotes_and_backslashes(self):
        self.assertEqual(skill_string('a"b\\c'), '"a\\"b\\\\c"')
        self.assertEqual(skill_string('x") exit(0) ("'), '"x\\") exit(0) (\\""')
        self.assertEqual(skill_string("한국어/λ"), '"한국어/λ"')

    def test_skill_string_rejects_control_bytes(self):
        for code in (*range(32), 127):
            with self.subTest(code=code):
                with self.assertRaises(ValueError):
                    skill_string("before" + chr(code) + "after")

    def test_plan_writes_diagnostics_without_launching_virtuoso(self):
        with patch("pgcheck.batch.shutil.which") as which, patch("pgcheck.batch.subprocess.run") as execute:
            result = self.batch(plan_only=True)
        which.assert_not_called()
        execute.assert_not_called()
        self.assertEqual(result["status"], "NOT_TESTED")
        self.assertEqual(result["internal_acceptance"], "NOT_TESTED")
        self.assertFalse(self.output.exists())
        bootstrap = (self.diagnostics / "bootstrap.il").read_text(encoding="utf-8")
        self.assertIn('pgcExport("APPROVED_TEST" "PGC_T01_TOP" "schematic"', bootstrap)
        self.assertIn("pgcheck_export.il", bootstrap)
        self.assertEqual(json.loads((self.diagnostics / "batch-result.json").read_text(encoding="utf-8")), result)

    def test_unavailable_executable_is_blocked_with_local_diagnostic(self):
        with patch("pgcheck.batch.shutil.which", return_value=None), patch("pgcheck.batch.subprocess.run") as execute:
            result = self.batch()
        execute.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("unavailable", result["reason"])
        self.assertTrue((self.diagnostics / "batch-result.json").is_file())

    def test_nonzero_without_manifest_is_blocked(self):
        with patch("pgcheck.batch.shutil.which", return_value="/mock/virtuoso"), \
                patch("pgcheck.batch.subprocess.run", return_value=SimpleNamespace(returncode=13)) as execute:
            result = self.batch(timeout=42)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["returncode"], 13)
        self.assertEqual(execute.call_args.kwargs["timeout"], 42)
        self.assertFalse(execute.call_args.kwargs["check"])
        self.assertEqual(execute.call_args.kwargs["stderr"], subprocess.STDOUT)
        self.assertFalse("shell" in execute.call_args.kwargs)
        self.assertTrue((self.diagnostics / "process.log").is_file())

    def test_nonzero_even_with_valid_manifest_is_fail(self):
        def failed_process(*args, **kwargs):
            create_t01(self.output)
            return SimpleNamespace(returncode=1)

        with patch("pgcheck.batch.shutil.which", return_value="/mock/virtuoso"), \
                patch("pgcheck.batch.subprocess.run", side_effect=failed_process):
            result = self.batch()
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["internal_acceptance"], "NOT_TESTED")

    def test_zero_exit_without_export_is_fail(self):
        with patch("pgcheck.batch.shutil.which", return_value="/mock/virtuoso"), \
                patch("pgcheck.batch.subprocess.run", return_value=SimpleNamespace(returncode=0)):
            result = self.batch()
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("manifest.json", result["reason"])

    def test_zero_exit_with_synthetic_fixture_validates_without_internal_acceptance(self):
        def successful_process(*args, **kwargs):
            create_t01(self.output)
            return SimpleNamespace(returncode=0)

        with patch("pgcheck.batch.shutil.which", return_value="/mock/virtuoso"), \
                patch("pgcheck.batch.subprocess.run", side_effect=successful_process):
            result = self.batch()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["validation"]["status"], "PASS")
        self.assertEqual(result["internal_acceptance"], "NOT_TESTED")
        self.assertEqual(json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))["validation_context"],
                         "synthetic")

    def test_malformed_export_despite_zero_exit_is_fail(self):
        def malformed_process(*args, **kwargs):
            create_t01(self.output)
            (self.output / "connections.jsonl").write_text("{\n", encoding="utf-8")
            return SimpleNamespace(returncode=0)

        with patch("pgcheck.batch.shutil.which", return_value="/mock/virtuoso"), \
                patch("pgcheck.batch.subprocess.run", side_effect=malformed_process):
            result = self.batch()
        self.assertEqual(result["status"], "FAIL")

    def test_timeout_and_launch_error_are_structured(self):
        errors = [(subprocess.TimeoutExpired(["mock-virtuoso"], 1), "BLOCKED"),
                  (OSError("mock launch failure"), "FAIL")]
        for index, (error, status) in enumerate(errors):
            with self.subTest(error=type(error).__name__):
                self.diagnostics = self.base / f"diagnostics-{index}"
                with patch("pgcheck.batch.shutil.which", return_value="/mock/virtuoso"), \
                        patch("pgcheck.batch.subprocess.run", side_effect=error):
                    result = self.batch()
                self.assertEqual(result["status"], status)
                self.assertTrue((self.diagnostics / "batch-result.json").is_file())

    def test_existing_export_and_diagnostics_are_not_overwritten(self):
        with patch("pgcheck.batch.subprocess.run") as execute:
            self.output.mkdir()
            (self.output / "keep").write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                self.batch()
            self.assertFalse(self.diagnostics.exists())
            self.assertEqual((self.output / "keep").read_text(encoding="utf-8"), "existing")
            self.output = self.base / "other-export"
            self.diagnostics.mkdir()
            (self.diagnostics / "keep").write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                self.batch()
            self.assertEqual((self.diagnostics / "keep").read_text(encoding="utf-8"), "existing")
        execute.assert_not_called()

    def test_missing_parent_or_source_rejected_before_diagnostics_creation(self):
        self.output = self.base / "missing-parent" / "export"
        with self.assertRaises(FileNotFoundError):
            self.batch(plan_only=True)
        self.assertFalse(self.diagnostics.exists())
        self.output = self.base / "new-export"
        (self.source / "skill" / "pgcheck_export.il").unlink()
        with self.assertRaises(FileNotFoundError):
            self.batch(plan_only=True)
        self.assertFalse(self.diagnostics.exists())

    def test_bad_timeout_or_control_arguments_rejected_before_mutation(self):
        for timeout in (0, -1):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                self.batch(timeout=timeout)
        with self.assertRaises(ValueError):
            run_batch("bad\nlibrary", "top", "schematic", self.output, self.diagnostics,
                      source_root=self.source, plan_only=True)
        self.assertFalse(self.diagnostics.exists())
        self.assertFalse(self.output.exists())

    def test_nonfinite_timeout_is_rejected_before_any_mutation(self):
        with patch("pgcheck.batch.shutil.which") as which, patch("pgcheck.batch.subprocess.run") as execute:
            for timeout in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                    self.batch(timeout=timeout)
        which.assert_not_called()
        execute.assert_not_called()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.diagnostics.exists())

    def test_overlapping_export_and_diagnostics_paths_are_rejected(self):
        cases = [
            (self.base / "same", self.base / "same"),
            (self.base / "out-parent", self.base / "out-parent" / "diagnostics"),
            (self.base / "diag-parent" / "export", self.base / "diag-parent"),
            (self.base / "canonical", self.base / "unused" / ".." / "canonical"),
        ]
        with patch("pgcheck.batch.shutil.which") as which, patch("pgcheck.batch.subprocess.run") as execute:
            for output, diagnostics in cases:
                with self.subTest(output=output, diagnostics=diagnostics), self.assertRaises(ValueError):
                    run_batch("TEST", "top", "schematic", output, diagnostics,
                              source_root=self.source, plan_only=True)
                self.assertFalse(output.exists())
                self.assertFalse(diagnostics.exists())
        which.assert_not_called()
        execute.assert_not_called()

    def test_main_maps_each_report_status_to_exit_code(self):
        arguments = ["--library", "TEST", "--output", str(self.output),
                     "--diagnostics", str(self.diagnostics)]
        for status, expected_code in (("PASS", 0), ("FAIL", 1), ("BLOCKED", 2), ("NOT_TESTED", 2)):
            with self.subTest(status=status):
                stdout = io.StringIO()
                with patch("pgcheck.batch.run_batch", return_value={"status": status}), redirect_stdout(stdout):
                    code = main(arguments)
                self.assertEqual(code, expected_code)
                self.assertEqual(json.loads(stdout.getvalue())["status"], status)

    def test_main_reports_local_errors_without_stack_trace(self):
        stdout = io.StringIO()
        with patch("pgcheck.batch.run_batch", side_effect=ValueError("invalid argument")), redirect_stdout(stdout):
            code = main(["--library", "TEST", "--output", str(self.output),
                         "--diagnostics", str(self.diagnostics)])
        self.assertEqual(code, 1)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["reason"], "invalid argument")
