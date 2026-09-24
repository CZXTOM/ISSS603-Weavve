"""Stops a commit that would add a data file or a notebook with outputs left in.

pre-commit passes the staged file names. Exit code 1 blocks the commit.
"""
import json
import sys
from pathlib import Path

BLOCKED = {".csv", ".xlsx", ".xls", ".zip", ".parquet", ".pkl", ".json", ".png", ".jpg", ".jpeg"}
ALLOWED = {".vscode"}
MAX_BYTES = 1_000_000

bad = []
for name in sys.argv[1:]:
    p = Path(name)
    if not p.exists() or any(part in ALLOWED for part in p.parts):
        continue
    if p.suffix.lower() in BLOCKED:
        bad.append(f"{name}: data or image files don't go in this repo")
    elif p.stat().st_size > MAX_BYTES:
        bad.append(f"{name}: over 1 MB, probably data")
    elif p.suffix == ".ipynb":
        nb = json.loads(p.read_text(encoding="utf-8"))
        if any(c.get("outputs") for c in nb.get("cells", []) if c.get("cell_type") == "code"):
            bad.append(f"{name}: notebook still has outputs. Run: nbstripout {name}")

if bad:
    print("Commit blocked:\n  " + "\n  ".join(bad))
    sys.exit(1)
