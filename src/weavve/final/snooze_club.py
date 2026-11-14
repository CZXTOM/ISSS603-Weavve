"""Aggregate Snooze Club evidence for the Idea 2 report notebook.

Use the verified shared Dataset interface. Excluded monetary rows can supply
discount-code annotations, but never add sales. Returned results contain no
customer, order or individual voucher identifiers.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal
import math
import re
from statistics import median


REPORT_CUTOFF = date(2026, 8, 28)


def _pct(numerator, denominator):
    return 100 * numerator / denominator if denominator else None


def _codes(lines, sale_only):
    result = defaultdict(set)
    for row in lines:
        if sale_only and row["Order or sales reversal"].strip().casefold() != "order":
            continue
        code = row["Discount code"].strip().upper()
        if code and not row["discount_code_is_date"]:
            result[row["order_id"]].add(code)
    return result


def popup_evidence(orders, kept, excluded):
    """First observed website/Shopee purchase, with mutually exclusive code groups."""
    first = {}
    for row in orders:
        if not (row["is_website"] or row["channel_detail"] == "Shopee"):
            continue
        person = row["person_id"]
        if person not in first or (row["order_date"], row["order_id"]) < (
                first[person]["order_date"], first[person]["order_id"]):
            first[person] = row
    recovered = kept + [r for r in excluded if r["exclusion_reason"] == "repeated_discount_line"]
    lookups = {"recovered_annotations": _codes(recovered, True),
               "kept_lines_only": _codes(kept, False)}
    labels = ("club", "popup", "other_discount_or_code", "no_recorded_discount_or_code")
    result = {}
    for method, lookup in lookups.items():
        windows = {}
        for name, start, end in (
                ("before_popup", date(2023, 8, 28), date(2024, 8, 26)),
                ("after_popup", date(2024, 8, 27), date(2025, 8, 26))):
            cohort = [r for r in first.values() if r["is_website"] and start <= r["order_date"] <= end]
            groups = {label: [] for label in labels}
            total = sum((r["net"] for r in cohort), Decimal(0))
            for row in cohort:
                codes = lookup.get(row["order_id"], set())
                if any(c.startswith("LWC") for c in codes):
                    label = "club"
                elif any(c.startswith(("AL", "WC8ALFR", "WC10ALFR")) for c in codes):
                    label = "popup"
                elif codes or row["discount"] > Decimal("0.005"):
                    label = "other_discount_or_code"
                else:
                    label = "no_recorded_discount_or_code"
                groups[label].append(row)
            windows[name] = {
                "start": start.isoformat(), "end": end.isoformat(), "newcomers": len(cohort),
                "all_newcomer_first_order_net_sales_sgd": float(total),
                "groups": {label: {
                    "people": len(rows), "share_of_newcomers_pct": _pct(len(rows), len(cohort)),
                    "first_order_net_sales_sgd": float(sum((r["net"] for r in rows), Decimal(0))),
                    "share_of_all_newcomer_first_order_net_sales_pct": float(
                        _pct(sum((r["net"] for r in rows), Decimal(0)), total)) if total else None,
                } for label, rows in groups.items()},
            }
        result[method] = windows
    return result


def top_decile_evidence(web, start, end, followup_end):
    spend = defaultdict(Decimal)
    for row in web:
        if start <= row["order_date"] <= end:
            spend[row["person_id"]] += row["net"]
    ranked = sorted(spend, key=lambda person: (-spend[person], person))
    n_top = math.ceil(len(ranked) * .1)
    following = {r["person_id"] for r in web if end < r["order_date"] <= followup_end}
    total = sum(spend.values(), Decimal(0))
    groups = {}
    for label, people in (("top_decile", ranked[:n_top]), ("other_buyers", ranked[n_top:])):
        sales = sum((spend[p] for p in people), Decimal(0))
        returners = len(set(people) & following)
        groups[label] = {
            "people": len(people), "baseline_net_sales_sgd": float(sales),
            "baseline_sales_share_pct": float(_pct(sales, total)) if total else None,
            "mean_annual_net_sales_sgd": float(sales / len(people)) if people else None,
            "next_year_website_returners": returners,
            "next_year_website_return_pct": _pct(returners, len(people)),
        }
    return {"baseline_start": start.isoformat(), "baseline_end": end.isoformat(),
            "followup_start": date(end.year, 9, 1).isoformat(),
            "followup_end": followup_end.isoformat(),
            "full_next_calendar_year_observed": followup_end >= date(end.year + 1, 8, 31),
            "website_buyers": len(ranked), "groups": groups}


def reward_and_cadence_evidence(web, kept, rewards):
    point = [r for r in rewards if r["points"] is not None and r["points"] < 0]
    cash = [r for r in point if re.fullmatch(r"\$(\d+(?:\.\d+)?)\s+off", r["description"].strip(), re.I)]
    rows = []
    for description in sorted({r["description"] for r in cash}):
        selected = [r for r in cash if r["description"] == description]
        used = sum(r["clean_reward_usage_status"] == "used" for r in selected)
        rows.append({"description": description, "selected_codes": len(selected),
                     "used_codes": used, "used_pct": _pct(used, len(selected))})
    by_order = {r["order_id"]: r for r in web}
    linked = set()
    for reward in point:
        if reward["clean_reward_usage_status"] == "used" and reward["clean_order_id"] in by_order:
            linked.add(by_order[reward["clean_order_id"]]["person_id"])
    # Match the prior report's retained sale-code linkage. This is historical
    # evidence of membership, not a validated live member or permission roster.
    point_codes = {r["discount_code"].strip().casefold() for r in point if r["discount_code"].strip()}
    for row in kept:
        order = by_order.get(row["order_id"])
        code = row["Discount code"].strip().casefold()
        if order and row["Order or sales reversal"].strip().casefold() == "order":
            if code.startswith("lwc") or code in point_codes:
                linked.add(order["person_id"])
    history = defaultdict(list)
    active_spend = defaultdict(Decimal)
    start = date(2025, 8, 29)
    for row in web:
        history[row["person_id"]].append(row)
        if row["person_id"] in linked and start <= row["order_date"] <= REPORT_CUTOFF:
            active_spend[row["person_id"]] += row["net"]
    ranked = sorted(active_spend, key=lambda person: (-active_spend[person], person))
    n_top = math.ceil(len(ranked) * .1)
    groups = {}
    for label, people in (("top10", ranked[:n_top]), ("others", ranked[n_top:])):
        personal, pooled = [], []
        for person in people:
            episodes = []
            for order in sorted(history[person], key=lambda r: (r["order_date"], r["order_id"])):
                # Compare with the episode start: never chain adjacent gaps.
                if not episodes or (order["order_date"] - episodes[-1]).days > 7:
                    episodes.append(order["order_date"])
            gaps = [(b - a).days for a, b in zip(episodes, episodes[1:])]
            if gaps:
                personal.append(median(gaps))
                pooled.extend(gaps)
        groups[label] = {"people": len(people), "repeaters": len(personal),
                         "median_personal_median_gap": median(personal) if personal else None,
                         "pooled_median_gap": median(pooled) if pooled else None,
                         "gaps": len(pooled)}
    return {"point_funded_records": len(point), "cash_point_funded_records": len(cash),
            "used_cash_point_funded_records": sum(r["clean_reward_usage_status"] == "used" for r in cash),
            "cash_voucher_records": rows, "active_window": [start.isoformat(), REPORT_CUTOFF.isoformat()],
            "all_website_history_of_latest_active_members": groups}


def voucher_sensitivity(*, redemptions, basket, discount_rate, cap, setup,
                        margins=(.4, .5, .6), additional_orders=(0, 20, 30)):
    """Fixed-redemption illustration; baskets/contribution precede the extra reward."""
    def number(value, name, maximum=None):
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0 or (maximum is not None and value > maximum)):
            raise ValueError(f"Invalid {name}")
        return value
    number(redemptions, "redemptions")
    number(basket, "basket")
    number(discount_rate, "discount_rate", 1)
    number(cap, "cap")
    number(setup, "setup")
    if not float(redemptions).is_integer():
        raise ValueError("Redemptions must be a whole count")
    additional_orders = tuple(additional_orders)
    for count in additional_orders:
        number(count, "additional_orders", redemptions)
        if not float(count).is_integer():
            raise ValueError("Additional orders must be a whole count")
    reward_per_order = min(basket * discount_rate, cap)
    cost = redemptions * reward_per_order + setup
    rows = []
    for margin in margins:
        number(margin, "margin", 1)
        contribution = basket * margin
        threshold = math.ceil(cost / contribution) if contribution else None
        rows.append({"margin": margin, "discount_per_redemption_sgd": reward_per_order,
                     "total_incremental_cost_sgd": cost, "break_even_additional_orders": threshold,
                     "break_even_feasible_within_redemptions": threshold <= redemptions if threshold is not None else False,
                     "net_gain_by_additional_orders": {str(n): n * contribution - cost for n in additional_orders}})
    return rows


def build_evidence(dataset):
    """Load verified canonical tables; freeze report cohorts at the stated cutoff."""
    source_cutoff = date.fromisoformat(dataset.manifest["transaction_cutoff"])
    if source_cutoff < REPORT_CUTOFF:
        raise ValueError("The report requires transactions through 28 August 2026")
    orders = [r for r in dataset.table("orders") if r["is_purchase"]
              and not r["is_special_account"] and r["order_date"] <= REPORT_CUTOFF]
    web = [r for r in orders if r["is_website"]]
    kept = dataset.table("order_lines")
    rewards = dataset.table("loyalty_rewards")
    # Later snapshots would need a point-in-time reward-state reconstruction.
    # Refuse them rather than use future reward status for the report cohort.
    if source_cutoff > REPORT_CUTOFF:
        raise ValueError("Use the report's 28 August 2026 snapshot; later reward state is not point-in-time evidence")
    names = ("orders", "order_lines", "excluded_order_lines", "loyalty_rewards")
    return {
        "dataset_id": dataset.manifest["dataset_id"], "transaction_cutoff": source_cutoff.isoformat(),
        "source_tables": {name: {k: dataset.manifest["tables"][name][k] for k in ("file", "rows", "sha256")} for name in names},
        "popup": popup_evidence(orders, kept, dataset.table("excluded_order_lines")),
        "website_top_deciles": {
            "2023_24": top_decile_evidence(web, date(2023, 9, 1), date(2024, 8, 31), date(2025, 8, 31)),
            "2024_25": top_decile_evidence(web, date(2024, 9, 1), date(2025, 8, 31), REPORT_CUTOFF),
        },
        "rewards_and_cadence": reward_and_cadence_evidence(web, kept, rewards),
    }
