"""Recorded cart-to-order diagnostics and explicitly conditional planning.

The supplied funnel records aggregate events, not linked unique cart exposures.
These calculations do not infer a recoverable effect, a profit forecast or power
for a customer experiment. Returned real-data aggregates must remain private.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
import math

from .recommendations import annual_windows, matched_funnel_periods


def _day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


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


def _money(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Nonfinite canonical money")
    return result


def website_value_reference(orders, lines, start_month, end_month):
    """Same-calendar-month website ledger reference, geography unverified.

    Positive purchase-order mean and signed order/event totals retain distinct
    boundaries. Order net is as of extract, including later refund adjustments.
    None of these values is contribution, cash flow or a Singapore-linked AOV.
    """
    if start_month is None or end_month is None:
        return {"status": "unavailable_no_complete_months", "purchase_order_net_reference": None,
                "geography_matches_funnel": False}
    start, last = _day(start_month), _day(end_month)
    end = last.replace(day=monthrange(last.year, last.month)[1])
    selected = []
    seen = set()
    for row in orders:
        if not row["is_website"] or row["is_special_account"] or not start <= _day(row["order_date"]) <= end:
            continue
        if row["order_id"] in seen:
            raise ValueError("Duplicate canonical website order")
        seen.add(row["order_id"])
        selected.append(row)
    positive = [row for row in selected if row["is_purchase"]]
    if any(_money(row["net"]) <= 0 for row in positive):
        raise ValueError("A positive purchase has nonpositive net")
    purchase_net = sum(_money(row["net"]) for row in positive)
    event_lines = [row for row in lines if row["is_website"] and not row["is_special_account"]
                   and start <= _day(row["line_date"]) <= end]
    return {
        "status": "descriptive_unlinked_website_reference",
        "start_date": start.isoformat(), "end_date_inclusive": end.isoformat(),
        "positive_purchase_orders": len(positive), "purchase_order_net_total": purchase_net,
        "purchase_order_net_reference": purchase_net / len(positive) if positive else None,
        "signed_website_order_count": len(selected),
        "signed_website_order_net_total": sum(_money(row["net"]) for row in selected),
        "signed_website_line_date_net_total": sum(_money(row["net"]) for row in event_lines),
        "geography_matches_funnel": False,
        "scope": "Nonspecial canonical website ledger; order/customer geography is not established.",
    }


def build_cart_completion_results(dataset):
    """Compare identical complete months and preserve event/ledger scope limits."""
    cutoff = _day(dataset.manifest["transaction_cutoff"])
    start = annual_windows(cutoff, 1)[0][0]
    funnel = matched_funnel_periods(dataset.table("website_funnel"), start, cutoff)
    orders, lines = dataset.table("orders"), dataset.table("order_lines")
    periods = []
    for label, period in zip(("previous", "current"), funnel["periods"]):
        totals = period["totals"]
        carts = totals["Add to Cart"] if totals is not None else None
        placed = totals["Orders Placed"] if totals is not None else None
        ratio = placed / carts if carts else None
        periods.append({
            "label": label, "start_month": period["start_month"], "end_month": period["end_month"],
            "complete_months": period["expected_months"], "complete": period["complete"],
            "recorded_add_to_cart": carts, "orders_placed": placed,
            "orders_per_recorded_add_to_cart": ratio,
            "ledger_reference": website_value_reference(orders, lines, period["start_month"], period["end_month"]),
        })
    previous, current = periods
    available = previous["orders_per_recorded_add_to_cart"] is not None and current["orders_per_recorded_add_to_cart"] is not None
    difference = current["orders_per_recorded_add_to_cart"] - previous["orders_per_recorded_add_to_cart"] if available else None
    headroom = (current["recorded_add_to_cart"] * previous["orders_per_recorded_add_to_cart"]
                - current["orders_placed"]) if available else None
    label = (f"{current['start_month']} through {current['end_month']}: "
             f"{current['complete_months']} complete months") if current["start_month"] else "No complete planning period"
    return {
        "dataset_id": dataset.manifest["dataset_id"], "transaction_cutoff": cutoff.isoformat(),
        "planning_period_label": label,
        "periods": periods,
        "cart_ratio_gap": difference,
        "holding_current_recorded_carts_restore_old_ratio_extra_orders": headroom,
        "matched_funnel": funnel,
        "definitions": {
            "cart_metric": "Aggregate recorded Add to Cart metric; unique cart/session/person interpretation is unverified.",
            "cart_ratio": "Total recorded Orders Placed divided by total recorded Add to Cart in matched complete months, not a mean of monthly ratios.",
            "headroom": "Arithmetic scenario holding current recorded cart metric fixed and replacing its orders/cart ratio with the prior ratio.",
            "ledger_reference": "Positive canonical website purchase-order mean for the same calendar months; geography/linkage differs from Singapore funnel.",
        },
        "limitations": [
            "An aggregate orders/cart ratio is not a verified unique-cart conversion probability or a customer experiment baseline.",
            "Stage totals do not identify linked users, cross-device sessions, event duplication or attribution changes.",
            "Historical headroom is descriptive and is not a causal or recoverable intervention effect.",
            "Funnel geography is Singapore-only in the supplied source; the website-ledger reference has unverified geography and order linkage.",
            "Order net includes retrospective refund adjustments; signed event-date net is a separate timing boundary.",
            "Neither recorded net sales nor the reference mean establishes marginal order value, contribution or profit.",
            "No annualisation, treatment effect, unique experiment exposure count or trial power is inferred.",
        ],
    }


def evaluate_cart_scenarios(config):
    """Conditional planning for a named period; no automatic annual extrapolation.

    The observed cart metric is a planning scale only. It must not be reused as
    independent unique experiment exposures. Signed order changes also change
    per-order variable costs, while the entered fixed cost applies in every case.
    """
    required = {"observed_recorded_carts", "baseline_ratio", "purchase_order_net_reference",
                "marginal_value_factor", "assumed_contribution_rate", "fixed_incremental_cost",
                "variable_cost_per_extra_order", "cases", "planning_period_label"}
    if not isinstance(config, dict) or set(config) != required:
        raise ValueError("Cart scenario keys must match the documented private schema")
    if not isinstance(config["planning_period_label"], str) or not config["planning_period_label"].strip():
        raise ValueError("planning_period_label must describe the period explicitly")
    carts = _number(config["observed_recorded_carts"], "observed_recorded_carts", minimum=0)
    if carts == 0:
        raise ValueError("observed_recorded_carts must be positive")
    baseline = _number(config["baseline_ratio"], "baseline_ratio", minimum=0)
    reference = _number(config["purchase_order_net_reference"], "purchase_order_net_reference", minimum=0)
    factor = _number(config["marginal_value_factor"], "marginal_value_factor", minimum=0, maximum=1)
    rate = _number(config["assumed_contribution_rate"], "assumed_contribution_rate", minimum=0, maximum=1)
    fixed = _number(config["fixed_incremental_cost"], "fixed_incremental_cost", minimum=0)
    variable = _number(config["variable_cost_per_extra_order"], "variable_cost_per_extra_order", minimum=0)
    cases = config["cases"]
    if not isinstance(cases, dict) or not cases:
        raise ValueError("cases must contain named adverse, zero and positive changes")
    changes = []
    for name, case in cases.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Each case needs a nonempty label")
        if isinstance(case, dict):
            if set(case) != {"rate_change"}:
                raise ValueError("Each case object must contain only rate_change")
            case = case["rate_change"]
        changes.append((name, _number(case, "rate_change")))
    if not any(delta < 0 for _, delta in changes) or not any(delta == 0 for _, delta in changes) or not any(delta > 0 for _, delta in changes):
        raise ValueError("Include adverse, zero and positive rate-change cases")
    unit = reference * factor * rate - variable
    rows = []
    for name, delta in changes:
        if baseline + delta < 0:
            raise ValueError("An assumed target orders/cart ratio cannot be negative")
        extra = carts * delta
        rows.append({
            "label": name, "rate_change": delta, "target_recorded_orders_cart_ratio": baseline + delta,
            "extra_orders": extra, "incremental_net_sales": extra * reference * factor,
            "variable_order_cost_change": extra * variable,
            "contribution_after_entered_costs": extra * unit - fixed,
        })
    return {
        "status": "conditional planning arithmetic, not a forecast or causal estimate",
        "planning_period_label": config["planning_period_label"], "assumptions": config,
        "assumed_unit_contribution_after_extra_order_cost": unit,
        "break_even_rate_change": fixed / (carts * unit) if unit > 0 else None,
        "break_even_extra_orders": fixed / unit if unit > 0 else None,
        "positive_unit_contribution": unit > 0,
        "cases": rows,
        "limitations": [
            "All uplift, marginal-value, contribution-rate and cost inputs are assumptions requiring verification.",
            "The recorded cart metric is not a count of independent unique carts, customers or experiment assignments.",
            "The reference order value is not geography-matched or causally linked to the funnel orders.",
            "Negative order changes also reduce entered variable order costs; fixed costs still apply in the adverse and zero cases.",
            "Excluded costs remain excluded; the output is not complete net profit unless the entered cost boundary is complete.",
            "The stated planning period is retained without automatic annualisation or repeated-quarter assumptions.",
            "This calculation does not establish trial power, a feasible treatment effect or operational readiness.",
        ],
    }
