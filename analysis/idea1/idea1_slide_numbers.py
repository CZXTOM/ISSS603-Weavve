"""Print the location of private slide evidence from the shared dataset.

All calculations live in importable package functions. The private output holds
claim IDs, definitions and values; no source-code prefix is executed or parsed.
Run with the options in docs/recommendation_evidence.md.
"""
from pathlib import Path
import runpy

if __name__ == "__main__":
    script = Path(__file__).resolve().parents[2] / "scripts" / "build_recommendation_evidence.py"
    runpy.run_path(str(script), run_name="__main__")
