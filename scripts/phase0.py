"""Independent unit tests followed by local evidence collection."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pgcheck.cli import main

test = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                      cwd=ROOT, check=False)
if test.returncode:
    raise SystemExit(1)
raise SystemExit(main(["phase0", *sys.argv[1:]]))
