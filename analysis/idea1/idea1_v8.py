"""Compatibility entry point for corrected shared-data Idea 1 evidence.

Set WEAVVE_DATA and WEAVVE_OUT as in README. This entry point uses the verified
shared dataset; it does not read independently cleaned Excel workbooks. Optional
private settings are documented in docs/recommendation_evidence.md.
"""
from pathlib import Path
import runpy

if __name__ == "__main__":
    script = Path(__file__).resolve().parents[2] / "scripts" / "build_recommendation_evidence.py"
    runpy.run_path(str(script), run_name="__main__")
