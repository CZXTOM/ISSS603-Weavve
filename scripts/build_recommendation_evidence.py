"""Build private evidence for corrected Idea 1 and the cart-completion proposal."""
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
from weavve.final.idea1 import build_idea1_results
from weavve.final.reward_test import evaluate_reward_test, evaluate_post_purchase_test
from weavve.final.cart_completion import build_cart_completion_results, evaluate_cart_scenarios
from weavve.private_outputs import write_private_json
from weavve.paths import OUT


def _read_private_json(path):
    raw = Path(path).expanduser().read_bytes()
    return json.loads(raw.decode("utf-8-sig")), sha256(raw).hexdigest()


def build_evidence(dataset=None, *, welcome_codes_path=None, reward_scenario_path=None,
                   post_purchase_scenario_path=None, cart_scenario_path=None, ads_dir=None):
    dataset = dataset if dataset is not None else load_dataset()
    codes = None
    inputs = {}
    if welcome_codes_path:
        codes, digest = _read_private_json(welcome_codes_path)
        if not isinstance(codes, list) or not all(isinstance(code, str) and code.strip() for code in codes):
            raise ValueError("Private welcome codes must be a list of nonempty exact code strings")
        inputs["welcome_codes_sha256"] = digest
    reward = None
    if reward_scenario_path:
        settings, digest = _read_private_json(reward_scenario_path)
        reward = evaluate_reward_test(settings)
        inputs["reward_scenario_sha256"] = digest
    post_purchase = None
    if post_purchase_scenario_path:
        settings, digest = _read_private_json(post_purchase_scenario_path)
        post_purchase = evaluate_post_purchase_test(settings)
        inputs["post_purchase_scenario_sha256"] = digest
    cart_planning = None
    if cart_scenario_path:
        settings, digest = _read_private_json(cart_scenario_path)
        cart_planning = evaluate_cart_scenarios(settings)
        inputs["cart_scenario_sha256"] = digest
    ads = None
    if ads_dir:
        from weavve.final.ads_results import build_ads_results
        folder = Path(ads_dir).expanduser()
        data, digest = _read_private_json(folder / "ads_monitor_api_data.json")
        inputs["ads_data_sha256"] = digest
        optional = {}
        for key, filename in (("log", "ads_monitor_api_log.json"), ("plan", "ads_monitor_plan.json")):
            if (folder / filename).exists():
                optional[key], inputs[f"ads_{key}_sha256"] = _read_private_json(folder / filename)
        ads = build_ads_results(data, **optional)
    inventory = ["src/weavve/final/idea1.py", "src/weavve/final/reward_test.py",
                 "src/weavve/final/cart_completion.py",
                 "src/weavve/private_outputs.py", "scripts/build_recommendation_evidence.py"]
    if ads_dir:
        inventory.append("src/weavve/final/ads_results.py")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return {
        "schema_version": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "checkout_commit": commit.stdout.strip() if commit.returncode == 0 else None,
        "analysis_code_sha256": {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in inventory},
        "private_input_sha256": inputs,
        "idea1": build_idea1_results(dataset, welcome_codes=codes),
        "idea1_planning_scenarios": post_purchase,
        "idea2": {
            "proposal": "Consistent delivery information and a controlled cart-summary test at unchanged prices",
            "diagnostics": build_cart_completion_results(dataset),
            "planning_scenarios": cart_planning,
            "status": "proposed; no store change or causal effect measured",
            "missing_launch_inputs": [
                "Approved delivery policy, current cart behaviour and theme capability",
                "Unique cart/visitor measurement and stable pre-treatment assignment",
                "Actual contribution costs and an agreed loss/decision threshold",
                "Named operator, test schedule and outcome/refund-linkage plan",
            ],
        },
        "deferred_reward_option": {
            "proposal": "Clearer explanation of an existing valid earned reward in the same member-message slot",
            "comparator": "Current verified member communication with comparable contact timing and reward terms",
            "status": "proposed; no live allocation or effect measured",
            "eligibility": "Current permission, deliverability, valid unused reward and no competing trial/flow",
            "planning_scenarios": reward,
            "missing_launch_inputs": [
                "Current person-level membership, reward validity and permission roster",
                "Verified current programme status and business-as-usual message contrast",
                "Actual incremental contribution costs and an agreed loss/decision threshold",
                "Named operator, assignment registry, schedule and outcome-linkage plan",
            ],
        },
        "ads": ads,
        "limitations": [
            "Historical diagnostics are not causal effects or live experiment readiness.",
            "No company financial inputs or effects are assumed by default.",
            "Absent optional evidence is reported as not evaluated, not replaced by fabricated values.",
            "All generated figures, private inputs and executed notebooks stay outside Git.",
        ],
    }


def write_evidence(report, out_dir=None):
    folder = out_dir if out_dir is not None else OUT / "recommendation_evidence" / report["idea1"]["dataset_id"]
    return write_private_json(report, folder, "recommendation_evidence.json")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--welcome-codes", type=Path, help="private JSON list of exact approved code identifiers")
    parser.add_argument("--reward-scenario", type=Path, help="private fixed-roster reward-test assumptions JSON")
    parser.add_argument("--idea1-scenario", type=Path, help="private fixed-roster content-test assumptions JSON")
    parser.add_argument("--cart-scenario", "--idea2-scenario", dest="cart_scenario", type=Path,
                        help="private fixed-period cart-completion planning assumptions JSON")
    parser.add_argument("--ads-dir", type=Path, help="private dated snapshots using the documented filenames")
    args = parser.parse_args(argv)
    try:
        report = build_evidence(welcome_codes_path=args.welcome_codes,
                                reward_scenario_path=args.reward_scenario,
                                post_purchase_scenario_path=args.idea1_scenario,
                                cart_scenario_path=args.cart_scenario,
                                ads_dir=args.ads_dir)
        destination = write_evidence(report, args.out_dir)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Evidence build failed: {exc}\n")
    print(f"Private evidence written to {destination}")
    print("No campaign, member offer or live experiment has been launched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
