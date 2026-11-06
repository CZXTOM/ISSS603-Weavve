"""Rebuild recommendation checks into private local outputs, never the repo."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from weavve.clean import load_dataset
from weavve.final.experiment_design import evaluate_scenario
from weavve.final.recommendations import build_recommendation_checks
from weavve.paths import OUT
from weavve.private_outputs import private_output_directory, write_private_json


def build_report(dataset=None, scenario_path=None):
    dataset = dataset if dataset is not None else load_dataset()
    code_files = ["src/weavve/final/recommendations.py", "src/weavve/final/experiment_design.py",
                  "src/weavve/private_outputs.py",
                  "scripts/check_recommendations.py"]
    inventory = {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in code_files}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "analysis_code_sha256": inventory,
        "checkout_commit": commit.stdout.strip() if commit.returncode == 0 else None,
        "evidence_status": "historical diagnostic checks; no live experiment or causal effect established",
        "checks": build_recommendation_checks(dataset),
        "planning_scenario": None,
    }
    if scenario_path:
        raw = Path(scenario_path).expanduser().read_bytes()
        scenario = json.loads(raw.decode("utf-8-sig"))
        report["planning_scenario"] = evaluate_scenario(scenario)
        report["planning_scenario_sha256"] = sha256(raw).hexdigest()
    return report


def write_report(report, out_dir=None):
    dataset_id = report["checks"]["dataset_id"]
    folder = out_dir if out_dir is not None else OUT / "recommendation_checks" / dataset_id
    return write_private_json(report, folder, "recommendation_checks.json")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, help="private explicit assumptions JSON; omitted means no economics forecast")
    parser.add_argument("--out-dir", type=Path, help="private destination outside every Git checkout")
    args = parser.parse_args(argv)
    scenario = args.scenario or os.environ.get("WEAVVE_RECOMMENDATION_SCENARIO")
    try:
        report = build_report(scenario_path=scenario)
        destination = write_report(report, args.out_dir)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Recommendation checks failed: {exc}\n")
    print(f"Private recommendation checks written to {destination}")
    print("Historical diagnostics and conditional scenarios do not establish live readiness or causal effects.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
