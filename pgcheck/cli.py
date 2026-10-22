"""Offline command-line entry points. All results stay on the local machine."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .environment import inspect_environment
from .reader import ExportReadError, load_export
from .t01 import check_t01
from .validator import validate


def _write_result(result: dict, report_path: str | None) -> None:
    text = json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False)
    if report_path:
        # Evidence and previous reports are never silently replaced.
        with Path(report_path).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text + "\n")
    print(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pgcheck", description="PGCHECK Phase 0 offline tools")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("validate", help="Validate an export without modifying it")
    check.add_argument("directory")
    check.add_argument("--t01", action="store_true")
    check.add_argument("--report")
    synth = sub.add_parser("synthetic", help="Create hand-authored synthetic T01 data")
    synth.add_argument("output_dir")
    env = sub.add_parser("env", help="Inspect local Python and PATH")
    env.add_argument("--output", dest="report")
    phase = sub.add_parser("phase0", help="Collect automatic checks and pending internal gates")
    phase.add_argument("--export", dest="directory")
    phase.add_argument("--t01", action="store_true")
    phase.add_argument("--report")
    args = parser.parse_args(argv)
    result: dict
    exit_code = 0
    try:
        if args.command == "synthetic":
            from .synthetic import create_t01
            path = create_t01(args.output_dir)
            result = {"status": "PASS", "validation_context": "synthetic", "output": str(path),
                      "internal_acceptance": "NOT_TESTED"}
        elif args.command == "env":
            result = inspect_environment()
            exit_code = 0 if result["status"] == "PASS" else 1
        elif args.command == "validate":
            data = load_export(args.directory)
            result = (check_t01(data) if args.t01 else validate(data)).as_dict()
            result["validation_context"] = data.manifest.get("validation_context")
            result["internal_acceptance"] = "NOT_TESTED"
            exit_code = 0 if result["status"] == "PASS" else 1
        else:
            checks = {key: "NOT_TESTED" for key in (
                "t01_safe_creation", "collision_prevention", "ciw_execution",
                "occurrence_separation", "different_vdd", "shared_gnd", "signal_port",
                "parent_child_ports", "jsonl_parse", "referential_integrity", "batch_attempt",
                "placement", "user_approval")}
            result = {"status": "BLOCKED", "checks": checks,
                      "note": "Internal generator/CIW evidence and user approval must be recorded on site."}
            if args.directory:
                data = load_export(args.directory)
                integrity = validate(data)
                oracle = check_t01(data) if args.t01 else None
                checks["jsonl_parse"] = "PASS"
                checks["referential_integrity"] = integrity.status
                if oracle:
                    for key in ("occurrence_separation", "different_vdd", "shared_gnd",
                                "signal_port", "parent_child_ports"):
                        checks[key] = oracle.status
                    result["t01"] = oracle.as_dict()
                result["validation"] = integrity.as_dict()
                result["validation_context"] = data.manifest["validation_context"]
                if not integrity.ok or (oracle and not oracle.ok):
                    result["status"] = "FAIL"
            exit_code = 1 if result["status"] == "FAIL" else 2
        _write_result(result, getattr(args, "report", None))
    except (ExportReadError, OSError, ValueError) as exc:
        # Full details are local stdout; no uploads, emails or telemetry.
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=True))
        return 1
    return exit_code
