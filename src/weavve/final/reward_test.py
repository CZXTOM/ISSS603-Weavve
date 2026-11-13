"""Conditional economics for one fixed-roster earned-reward reminder test.

The model values purchases before the tested reward and subtracts its incremental
redemption cost once. It is not an analysis of net sales already after that reward.
No company inputs, audience counts or effect assumptions are supplied by default.
"""
from __future__ import annotations

import math


def _number(value, name, minimum=0, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{name} is outside its permitted range")
    return float(value)


def evaluate_reward_test(config):
    """Evaluate named private 90-day scenarios for a fixed eligible roster.

    Purchase rate is the probability of at least one purchase. One tested reward
    can be redeemed at most once per person in the window. Contribution per
    purchaser represents all their purchases in that window before this reward.
    All other variable costs must already be included in that contribution or
    explicitly entered as incremental per-treated-person operating costs.
    Contact and operating inputs are differences from business as usual; matched
    message timing does not justify charging the full email cost to one arm.
    """
    required = {
        "label", "eligible_people", "treatment_fraction", "baseline_purchase_rate",
        "baseline_reward_redemption_rate", "contribution_per_purchaser_before_tested_reward",
        "tested_reward_cost_per_redemption", "contact_cost_per_treated_person",
        "additional_operations_cost_per_treated_person", "setup_cost", "scenarios",
        "notes", "unpriced_costs",
    }
    if not isinstance(config, dict) or set(config) != required:
        raise ValueError("Reward-test inputs must match the documented private schema")
    if not isinstance(config["label"], str) or not config["label"].strip():
        raise ValueError("Supply a descriptive scenario label")
    for field in ("notes", "unpriced_costs"):
        if not isinstance(config[field], list) or not all(isinstance(x, str) for x in config[field]):
            raise ValueError(f"{field} must be a list of strings")
    eligible = _number(config["eligible_people"], "eligible_people", minimum=1)
    if not eligible.is_integer():
        raise ValueError("eligible_people must be a whole-person count")
    allocation = _number(config["treatment_fraction"], "treatment_fraction", maximum=1)
    if not 0 < allocation < 1:
        raise ValueError("A controlled test requires both treatment and control")
    treated = math.floor(eligible * allocation)
    if treated < 1 or eligible - treated < 1:
        raise ValueError("The roster must allocate at least one person to each arm")
    p0 = _number(config["baseline_purchase_rate"], "baseline_purchase_rate", maximum=1)
    q0 = _number(config["baseline_reward_redemption_rate"], "baseline_reward_redemption_rate", maximum=p0)
    contribution = _number(config["contribution_per_purchaser_before_tested_reward"], "contribution_per_purchaser_before_tested_reward")
    reward = _number(config["tested_reward_cost_per_redemption"], "tested_reward_cost_per_redemption")
    contact = _number(config["contact_cost_per_treated_person"], "contact_cost_per_treated_person")
    operations = _number(config["additional_operations_cost_per_treated_person"], "additional_operations_cost_per_treated_person")
    setup = _number(config["setup_cost"], "setup_cost")
    cases = config["scenarios"]
    if not isinstance(cases, dict) or not cases:
        raise ValueError("Supply named adverse, zero-purchase-lift and benefit scenarios")
    results = []
    for label, case in cases.items():
        if not isinstance(label, str) or not label.strip() or not isinstance(case, dict) or set(case) != {"purchase_rate", "reward_redemption_rate"}:
            raise ValueError("Each named scenario requires purchase_rate and reward_redemption_rate only")
        p1 = _number(case["purchase_rate"], "purchase_rate", maximum=1)
        q1 = _number(case["reward_redemption_rate"], "reward_redemption_rate", maximum=p1)
        incremental_reward_cost = (q1 - q0) * reward
        before_fixed = (p1 - p0) * contribution - incremental_reward_cost - contact - operations
        threshold = (incremental_reward_cost + contact + operations + setup / treated) / contribution if contribution else None
        results.append({
            "label": label,
            "purchase_rate": p1, "reward_redemption_rate": q1,
            "purchase_rate_difference": p1 - p0,
            "incremental_redemption_cost_per_treated_person": incremental_reward_cost,
            "incremental_contribution_per_treated_person_before_setup": before_fixed,
            "trial_incremental_contribution_after_setup": treated * before_fixed - setup,
            "break_even_purchase_rate_difference_given_entered_redemptions": threshold,
        })
    if not any(row["purchase_rate_difference"] == 0 for row in results):
        raise ValueError("Include a zero-purchase-lift case with its own redemption assumption")
    if not any(row["purchase_rate_difference"] < 0 for row in results):
        raise ValueError("Include an adverse purchase-response case")
    return {
        "label": config["label"], "status": "conditional arithmetic, not observed trial results",
        "horizon_days": 90, "eligible_people": int(eligible),
        "treated_people": treated, "control_people": int(eligible) - treated,
        "assumptions": config, "scenarios": results,
        "limitations": [
            "A current eligible roster, programme status, unused reward validity and permission remain external prerequisites.",
            "These are one-off 90-day fixed-roster trial scenarios; no annual recurrence or live launch is implied.",
            "More redemptions with zero purchase uplift can reduce contribution through subsidy.",
            "Contribution inputs are before the tested reward; do not subtract it again from net sales already after it.",
            "The contribution-per-purchaser assumption may fail if treatment changes basket size, frequency or costs.",
            "Break-even purchase uplift is conditional on the entered redemption response, not a universal threshold.",
            "Listed unpriced costs are excluded rather than established as zero.",
            "This model does not establish statistical precision or identify which individual purchase is incremental.",
        ],
    }


def evaluate_post_purchase_test(config):
    """Use the fixed-roster model for one content-only post-purchase test.

    The same purchase/contribution accounting applies, with no tested reward.
    Explicit zero reward fields prevent a content test from hiding an incentive.
    """
    if not isinstance(config, dict):
        raise ValueError("Supply private post-purchase planning inputs")
    if config.get("baseline_reward_redemption_rate") != 0 or config.get("tested_reward_cost_per_redemption") != 0:
        raise ValueError("A content-only test requires zero tested reward rates and cost")
    if not isinstance(config.get("scenarios"), dict) or any(
            case.get("reward_redemption_rate") != 0 for case in config["scenarios"].values() if isinstance(case, dict)):
        raise ValueError("A content-only test cannot include reward redemptions")
    result = evaluate_reward_test(config)
    result["proposal"] = "One relevant post-purchase message, no added incentive"
    result["limitations"] = [
        "Historical profile linkage and risk-set counts are not current permission or a verified launch roster.",
        "Entered purchase lifts and marginal-buyer contribution remain assumptions, not measured treatment effects.",
        "Observed returner value need not equal induced-buyer value; test value/cost and audience coverage sensitivities.",
        "This is a one-off 90-day fixed-roster planning case, not recurring annual or rollout profit.",
        "Contact and operating costs are increments over current communications; excluded costs are not established as zero.",
        "No reward is introduced; evaluate realised person-level contribution if baskets, purchase frequency or costs change.",
    ]
    return result
