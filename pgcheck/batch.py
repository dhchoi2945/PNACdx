"""Attempt the same exporter under Virtuoso; keep diagnostic files on site."""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path

from .reader import ExportReadError, load_export
from .validator import validate


def skill_string(value: str) -> str:
    """Quote a SKILL string without allowing injected forms or control bytes."""
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Batch arguments must not contain control characters")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def run_batch(library: str, cell: str, view: str, output_dir: str | Path,
              diagnostics_dir: str | Path, *, executable: str = "virtuoso",
              timeout: float = 300, source_root: str | Path | None = None,
              plan_only: bool = False) -> dict:
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    output = Path(output_dir).absolute()
    diagnostics = Path(diagnostics_dir).absolute()
    source = Path(source_root or Path(__file__).resolve().parents[1])
    resolved_output, resolved_diagnostics = output.resolve(), diagnostics.resolve()
    if (resolved_output == resolved_diagnostics or resolved_output in resolved_diagnostics.parents
            or resolved_diagnostics in resolved_output.parents):
        raise ValueError("Export and diagnostics directories must be separate, non-overlapping paths")
    if output.exists():
        raise FileExistsError(f"Export output already exists: {output}")
    if not output.parent.is_dir():
        raise FileNotFoundError(f"Create the approved output parent first: {output.parent}")
    # Validate strings before creating any diagnostics directory.
    values = [skill_string(str(value)) for value in (library, cell, view, output)]
    modules = [source / "skill" / name for name in ("pgcheck_json.il", "pgcheck_export.il")]
    if not all(path.is_file() for path in modules):
        raise FileNotFoundError("Required SKILL exporter modules are missing")
    diagnostics.mkdir(exist_ok=False)
    bootstrap = diagnostics / "bootstrap.il"
    forms = [f"unless(errset(load({skill_string(path.as_posix())}) t) exit(1))" for path in modules]
    forms.extend([
        f"pgcBatchResult=errset(pgcExport({' '.join(values)}) t)",
        "if(pgcBatchResult && car(pgcBatchResult) then exit(0) else exit(1))",
    ])
    bootstrap.write_text("\n".join(forms) + "\n", encoding="utf-8")
    command = [executable, "-nograph", "-restore", str(bootstrap),
               "-log", str(diagnostics / "CDS.log")]
    result = {"status": "NOT_TESTED", "command": command, "timeout_seconds": timeout,
              "output": str(output), "internal_acceptance": "NOT_TESTED"}
    if plan_only:
        result["reason"] = "Plan only; Virtuoso was not launched"
    elif shutil.which(executable) is None:
        result.update(status="BLOCKED", reason="Virtuoso executable unavailable on PATH")
    else:
        try:
            with (diagnostics / "process.log").open("xb") as log:
                process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                         timeout=timeout, check=False)
            result["returncode"] = process.returncode
            if process.returncode != 0:
                result.update(status="FAIL" if (output / "manifest.json").exists() else "BLOCKED",
                              reason="Virtuoso returned nonzero; inspect local logs")
            else:
                report = validate(load_export(output))
                result.update(status=report.status, validation=report.as_dict())
        except subprocess.TimeoutExpired:
            result.update(status="BLOCKED", reason="Virtuoso timed out; inspect process/session state locally")
        except (OSError, ExportReadError) as exc:
            result.update(status="FAIL", reason=str(exc))
    with (diagnostics / "batch-result.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=True, indent=2)
        stream.write("\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PGCHECK local Virtuoso batch attempt")
    parser.add_argument("--library", required=True)
    parser.add_argument("--cell", default="PGC_T01_TOP")
    parser.add_argument("--view", default="schematic")
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostics", required=True)
    parser.add_argument("--virtuoso", default="virtuoso")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_batch(args.library, args.cell, args.view, args.output, args.diagnostics,
                           executable=args.virtuoso, timeout=args.timeout, plan_only=args.plan)
    except (OSError, ValueError) as exc:
        result = {"status": "FAIL", "reason": str(exc)}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2, "NOT_TESTED": 2}[result["status"]]
