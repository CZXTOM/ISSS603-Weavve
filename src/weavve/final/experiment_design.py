"""Conditional planning arithmetic, never estimated effects or launch approval.

Inputs belong in a private assumptions file. These functions do not infer costs,
eligibility, treatment effects or exposure from historical associations.
"""
from __future__ import annotations

import math
from statistics import NormalDist


def _number(value, name, *, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return value


def sample_per_arm(baseline, target, *, alpha=0.05, power=0.8):
    """Approximate fixed-sample, two-sided, equal-allocation binary endpoint.

    This is not power for the contribution endpoint, sequential monitoring,
    cluster randomisation or subgroup analyses. Equal rates have no finite N.
    """
    baseline = _number(baseline, "baseline", minimum=0, maximum=1)
    target = _number(target, "target", minimum=0, maximum=1)
    alpha = _number(alpha, "alpha", minimum=0, maximum=1)
    power = _number(power, "power", minimum=0, maximum=1)
    if not 0 < baseline < 1 or not 0 < target < 1:
        raise ValueError("rates must be strictly between zero and one")
    if not 0 < alpha < 1 or not 0.5 < power < 1:
        raise ValueError("require 0 < alpha < 1 and 0.5 < power < 1")
    if target == baseline:
        return None
    average = (baseline + target) / 2
    z_alpha = NormalDist().inv_cdf(1 - alpha / 2)
    z_power = NormalDist().inv_cdf(power)
    numerator = (z_alpha * math.sqrt(2 * average * (1 - average))
                 + z_power * math.sqrt(baseline * (1 - baseline) + target * (1 - target))) ** 2
    return math.ceil(numerator / (target - baseline) ** 2)


def rollout_exposure(schedule):
    """Annual treatment exposure assuming uniform eligible-person arrivals."""
    if not isinstance(schedule, list) or not schedule:
        raise ValueError("rollout must be a nonempty list of months/fraction objects")
    months = weighted = 0.0
    for period in schedule:
        if not isinstance(period, dict) or set(period) != {"months", "fraction"}:
            raise ValueError("each rollout period requires only months and fraction")
        length = _number(period["months"], "months", minimum=0, maximum=12)
        fraction = _number(period["fraction"], "fraction", minimum=0, maximum=1)
        if length == 0:
            raise ValueError("rollout months must be positive")
        months += length
        weighted += length * fraction
    if not math.isclose(months, 12, abs_tol=1e-9):
        raise ValueError("rollout must cover exactly twelve months")
    return weighted / months


def evaluate_scenario(config):
    """Evaluate explicit private assumptions; retain zero/adverse cases.

    Value is net sales over the specified mature-buyer horizon. The supplied
    contribution margin must include the costs assigned to that boundary.
    Additional per-treated-person costs capture subsidy/leakage not already
    included in net sales or margin; setup/running costs apply once per year.
    """
    required = {
        "label", "annual_eligible", "baseline_rate", "target_rates",
        "mature_buyer_net_sales", "value_horizon_days", "contribution_margin",
        "setup_cost", "annual_operating_cost", "additional_cost_per_treated_person",
        "rollout", "outcome_days", "unpriced_costs", "notes",
    }
    allowed = required | {"alpha", "power"}
    if not isinstance(config, dict) or required - set(config) or set(config) - allowed:
        raise ValueError("scenario keys must match the documented private schema")
    if not isinstance(config["label"], str) or not config["label"].strip():
        raise ValueError("label must describe the conditional scenario")
    for key in ("notes", "unpriced_costs"):
        if not isinstance(config[key], list) or not all(isinstance(v, str) for v in config[key]):
            raise ValueError(f"{key} must be a list of strings")
    annual = _number(config["annual_eligible"], "annual_eligible", minimum=0)
    if annual <= 0:
        raise ValueError("annual_eligible must be positive; verify the roster separately")
    baseline = _number(config["baseline_rate"], "baseline_rate", minimum=0, maximum=1)
    value = _number(config["mature_buyer_net_sales"], "mature_buyer_net_sales", minimum=0)
    margin = _number(config["contribution_margin"], "contribution_margin", minimum=0, maximum=1)
    setup = _number(config["setup_cost"], "setup_cost", minimum=0)
    running = _number(config["annual_operating_cost"], "annual_operating_cost", minimum=0)
    per_person = _number(config["additional_cost_per_treated_person"], "additional_cost_per_treated_person", minimum=0)
    followup = _number(config["outcome_days"], "outcome_days", minimum=1)
    value_days = _number(config["value_horizon_days"], "value_horizon_days", minimum=1)
    exposure = rollout_exposure(config["rollout"])
    targets = config["target_rates"]
    if not isinstance(targets, dict) or not targets:
        raise ValueError("target_rates requires named adverse, zero and benefit scenarios")
    rates = [_number(rate, "target rate", minimum=0, maximum=1) for rate in targets.values()]
    if not any(rate == baseline for rate in rates) or not any(rate < baseline for rate in rates):
        raise ValueError("include both a zero-lift and an adverse scenario")
    rows = []
    for label, target in targets.items():
        if not isinstance(label, str) or not label.strip():
            raise ValueError("target labels must be nonempty strings")
        target = float(target)
        n = sample_per_arm(baseline, target, alpha=config.get("alpha", 0.05), power=config.get("power", 0.8))
        buyers = annual * (target - baseline)
        contribution = buyers * value * margin - annual * per_person
        recruitment_days = (2 * n / annual) * 365.25 if n is not None else None
        rows.append({
            "label": label, "target_rate": target, "rate_difference": target - baseline,
            "additional_buyers_full_exposure": buyers,
            "mature_cohort_contribution_full_exposure_after_costs": contribution - setup - running,
            "mature_cohort_contribution_rollout_exposure_after_costs": contribution * exposure - setup - running,
            "approximate_binary_endpoint_n_per_arm": n,
            "equal_allocation_recruitment_months": recruitment_days / (365.25 / 12) if recruitment_days is not None else None,
            "equal_allocation_last_outcome_matures_months": (recruitment_days + followup) / (365.25 / 12) if recruitment_days is not None else None,
        })
    return {
        "label": config["label"], "status": "conditional arithmetic, not an effect estimate",
        "assumptions": config, "annual_treatment_exposure": exposure,
        "value_horizon_days": value_days, "scenarios": rows,
        "limitations": [
            "Eligible audience, effect, marginal-buyer value and costs are unverified inputs.",
            "These mature-cohort figures are not launch-calendar-year realised profit or cash flow.",
            "Binary-endpoint sample size does not establish power for incremental contribution.",
            "Recruitment assumes constant arrivals and 50:50 allocation throughout; it does not follow the rollout allocation.",
            "Arrival-based recruitment months do not apply to an existing-member roster already available at launch.",
            "Changing allocation or repeated monitoring requires a separately specified analysis plan.",
            "No quarterly repetition, immediate rollout or ad-spend decision follows from these scenarios.",
            "Costs listed as unpriced are excluded, not assumed to be economically zero.",
        ],
    }
