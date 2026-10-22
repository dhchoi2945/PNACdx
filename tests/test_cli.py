import json
import os
import subprocess
import sys
from pathlib import Path

from tests.helpers import ExportCase


class CLITests(ExportCase):
    def run_cli(self, *arguments):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        process = subprocess.run(
            [sys.executable, "-m", "pgcheck", *map(str, arguments)],
            cwd=Path(__file__).resolve().parents[1], env=env,
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertNotIn("Traceback", process.stderr + process.stdout)
        try:
            result = json.loads(process.stdout)
        except json.JSONDecodeError:
            self.fail(f"CLI must emit JSON; exit={process.returncode}, stdout={process.stdout!r}, "
                      f"stderr={process.stderr!r}")
        return process, result

    def test_validate_and_t01_success(self):
        process, result = self.run_cli("validate", self.export, "--t01")
        self.assertEqual(process.returncode, 0, result)
        self.assertEqual(result["status"], "PASS")

    def test_validation_report_written_locally(self):
        report = self.base / "report.json"
        process, result = self.run_cli("validate", self.export, "--t01", "--report", report)
        self.assertEqual(process.returncode, 0, result)
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"], "PASS")

    def test_existing_validation_report_is_not_overwritten(self):
        report = self.base / "existing-report.json"
        report.write_text('{"existing":"evidence"}', encoding="utf-8")
        process, result = self.run_cli("validate", self.export, "--report", report)
        self.assertEqual(process.returncode, 1, result)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(report.read_text(encoding="utf-8"), '{"existing":"evidence"}')

    def test_bad_reference_returns_fail(self):
        path = self.export / "connections.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        rows[0]["net_id"] = "missing"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        process, result = self.run_cli("validate", self.export)
        self.assertEqual(process.returncode, 1, result)
        self.assertEqual(result["status"], "FAIL")

    def test_read_failure_is_structured_without_traceback(self):
        (self.export / "manifest.json").write_text("{", encoding="utf-8")
        process, result = self.run_cli("validate", self.export)
        self.assertEqual(process.returncode, 1, result)
        self.assertEqual(result["status"], "FAIL")

    def test_synthetic_command_creates_fresh_fixture(self):
        target = self.base / "cli-export"
        process, result = self.run_cli("synthetic", target)
        self.assertEqual(process.returncode, 0, result)
        self.assertEqual(result["status"], "PASS")
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["validation_context"], "synthetic")

    def test_synthetic_command_rejects_existing_output(self):
        originals = {file.name: file.read_bytes() for file in self.export.iterdir()}
        process, result = self.run_cli("synthetic", self.export)
        self.assertEqual(process.returncode, 1, result)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(originals, {file.name: file.read_bytes() for file in self.export.iterdir()})

    def test_environment_probe_emits_local_report(self):
        target = self.base / "environment.json"
        process, result = self.run_cli("env", "--output", target)
        self.assertIn(process.returncode, (0, 1, 2), result)
        self.assertIn(result["status"], ("PASS", "FAIL", "BLOCKED", "NOT_TESTED"))
        self.assertIsInstance(json.loads(target.read_text(encoding="utf-8")), dict)

    def test_phase0_without_internal_export_remains_blocked(self):
        process, result = self.run_cli("phase0")
        self.assertEqual(process.returncode, 2, result)
        self.assertEqual(result["status"], "BLOCKED")

    def test_phase0_synthetic_export_never_certifies_internal_acceptance(self):
        target = self.base / "phase0.json"
        process, result = self.run_cli("phase0", "--export", self.export, "--t01", "--report", target)
        self.assertEqual(process.returncode, 2, result)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["status"], "BLOCKED")
