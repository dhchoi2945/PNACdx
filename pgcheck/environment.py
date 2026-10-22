"""Local environment diagnostics. No network or design data collection."""
from __future__ import annotations

import locale
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path


def inspect_environment(directory: str | Path = ".") -> dict:
    root = Path(directory)
    writable = False
    error = None
    try:
        with tempfile.TemporaryFile(dir=root):
            writable = True
    except OSError as exc:
        error = str(exc)
    python_ok = sys.version_info >= (3, 10)
    executable = shutil.which("virtuoso")
    return {
        "status": "PASS" if python_ok and writable else "FAIL",
        "python_version": platform.python_version(), "python_supported": python_ok,
        "platform": platform.system(), "machine": platform.machine(),
        "output_writable": writable, "write_error": error,
        "preferred_encoding": locale.getpreferredencoding(False),
        "locale": {key: os.environ.get(key) for key in ("LC_ALL", "LC_CTYPE", "LANG")},
        "virtuoso_on_path": executable is not None,
        "virtuoso_runtime": "NOT_TESTED",
        "api_probe": "NOT_TESTED", "ciw": "NOT_TESTED", "batch": "NOT_TESTED",
        "note": "Local Python checks only. Run pgcProbe inside the approved Virtuoso session.",
    }
