"""Idea 1 evidence from the single verified dataset; returned aggregates stay private.

This analysis preserves descriptive first-basket and repeat-purchase questions.
It supplies no default margin, acquisition cost, causal uplift or profit forecast.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from hashlib import sha256
import json
import math
import re
from statistics import mean

from .recommendations import annual_windows, customer_purchase_history, shift_year, website_cohort


def _day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _money(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Nonfinite amount in verified table")
    return result


def _average(values):
    return mean(values) if values else None


def _pct(numerator, denominator):
    return 100 * numerator / denominator if denominator else None


def product_index(products):
    """Exact SKU attributes; conflicting duplicates must be adjudicated upstream."""
    result = {}
    for row in products:
        sku = str(row.get("clean_sku") or "").strip()
        if not sku:
            continue
        category = re.sub(r"^\d+\.\s*", "", str(row.get("Category") or "").strip())
        kind = str(row.get("Product Types") or "").strip().casefold()
        attributes = (category, kind)
        if sku in result and result[sku] != attributes:
            raise ValueError("Conflicting exact-SKU product attributes")
        result[sku] = attributes
    return result


def basket_features(lines, products):
    """Known sale-line attributes of one order, without treating unknown as absent."""
    categories, sheet_types = set(), set()
    unknown = relevant = 0
    for row in lines:
        if str(row.get("Order or sales reversal") or "").strip().casefold() != "order" or row["is_order_level"]:
            continue
        relevant += 1
        attributes = products.get(str(row.get("sku") or "").strip())
        if not attributes or attributes[0] in {"", "Unknown", "Unassigned"}:
            unknown += 1
            continue
        category, kind = attributes
        categories.add(category)
        if category == "Bedsheets" and kind:
            sheet_types.add(kind)
    sheets, bedding = "Bedsheets" in categories, "Bedding" in categories
    if sheets and bedding:
        entry = "Sheets plus bedding"
    elif sheets and "set" in sheet_types:
        entry = "Sheet set without bedding"
    elif sheets:
        entry = "Sheet separates without bedding"
    elif bedding:
        entry = "Bedding without known sheets"
    elif categories:
        entry = "Other known products"
    else:
        entry = "Product unknown"
    if "set" in sheet_types:
        subtype = "Set present"
    elif sheet_types == {"fitted sheet"}:
        subtype = "Fitted sheet only"
    elif sheet_types == {"duvet cover"}:
        subtype = "Duvet cover only"
    elif sheet_types == {"pillow case"}:
        subtype = "Pillowcases only"
    elif sheets:
        subtype = "Mixed or other sheets"
    else:
        subtype = None
    return {"entry_type": entry, "sheet_starter": sheets, "sheets_plus_bedding": sheets and bedding,
            "sheet_subtype": subtype, "categories": categories,
            "has_known_category": bool(categories), "sale_product_lines": relevant,
            "unknown_product_lines": unknown}


def classify_codes(lines, welcome_codes):
    """Match private exact code identifiers, never campaign names or guessed dates.

    Codes are stripped/case-folded. Date-typed or explicitly flagged date codes
    remain unresolved. A recognised exact match can coexist with another unknown
    annotation, so uncertainty coverage is reported independently.
    """
    supplied = welcome_codes is not None
    accepted = set()
    if supplied:
        if isinstance(welcome_codes, (str, bytes)):
            raise ValueError("welcome_codes must be an iterable of exact identifiers")
        for value in welcome_codes:
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Exact welcome codes must be nonempty strings")
            accepted.add(value.strip().casefold())
    codes, unknown = set(), False
    for row in lines:
        if str(row.get("Order or sales reversal") or "").strip().casefold() != "order":
            continue
        value = row.get("Discount code")
        if row.get("discount_code_is_date") or isinstance(value, (date, datetime)):
            unknown = True
        elif value is None or value == "":
            continue
        elif isinstance(value, str):
            if value.strip():
                codes.add(value.strip().casefold())
        else:
            unknown = True
    if not supplied:
        group = "Not evaluated: no exact welcome-code specification"
    elif codes & accepted:
        group = "Exact welcome-code match"
    elif unknown:
        group = "Unresolved code"
    elif codes:
        group = "Other recorded code"
    else:
        group = "No recorded code"
    return {"group": group, "has_recorded_string_code": bool(codes), "has_unresolved_code": unknown}


def outcome_summary(people, ids, cutoff, horizon_days, episode_days=7, *, signed_events=None):
    """Complete fixed-day outcomes on [initial date, initial date + horizon).

    Orders through episode day seven retain their value. A separate behavioural
    repeat flag requires age > episode_days. Order nets are retrospective as of
    extraction; signed line-date net supplies the distinct event-date boundary.
    """
    _integer(horizon_days, "horizon_days")
    _integer(episode_days, "episode_days")
    cutoff = _day(cutoff)
    mature = [p for p in ids if _day(people[p][0]["order_date"]) + timedelta(days=horizon_days - 1) <= cutoff]
    values, signed, first_values, episode_values, repeat_values, early_extra = [], [], [], [], [], []
    repeat_counts, all_counts = [], []
    for person in mature:
        start = _day(people[person][0]["order_date"])
        selected = [row for row in people[person] if 0 <= (_day(row["order_date"]) - start).days < horizon_days]
        episode = [row for row in selected if (_day(row["order_date"]) - start).days <= episode_days]
        repeat = [row for row in selected if (_day(row["order_date"]) - start).days > episode_days]
        first = _money(people[person][0]["net"])
        ep_value = sum(_money(row["net"]) for row in episode)
        values.append(sum(_money(row["net"]) for row in selected))
        first_values.append(first)
        episode_values.append(ep_value)
        early_extra.append(ep_value - first)
        repeat_values.append(sum(_money(row["net"]) for row in repeat))
        repeat_counts.append(len(repeat))
        all_counts.append(len(selected))
        if signed_events is not None:
            signed.append(sum(value for when, value in signed_events.get(person, [])
                              if 0 <= (when - start).days < horizon_days))
    returners = sum(count > 0 for count in repeat_counts)
    repeaters_spend = [value for value, count in zip(repeat_values, repeat_counts) if count]
    total_repeat_orders = sum(repeat_counts)
    return {
        "entry_people": len(ids), "people": len(mature), "immature_people": len(ids) - len(mature),
        "horizon_days": horizon_days, "endpoint": "initial date inclusive; initial date + horizon exclusive",
        "returners": returners, "repeat_rate_pct": _pct(returners, len(mature)),
        "mean_first_order_net": _average(first_values),
        "mean_initial_episode_net": _average(episode_values),
        "mean_additional_day0_to_episode_net": _average(early_extra),
        "mean_post_episode_purchase_net": _average(repeat_values),
        "mean_purchase_order_net": _average(values),
        "mean_signed_line_date_net": _average(signed),
        "mean_purchase_order_count": _average(all_counts),
        "repeat_orders": total_repeat_orders,
        "repeat_orders_per_returner": total_repeat_orders / returners if returners else None,
        "mean_repeat_order_net": sum(repeat_values) / total_repeat_orders if total_repeat_orders else None,
        "mean_returner_post_episode_net": _average(repeaters_spend),
        "episode_plus_repeat_identity_gap": sum(values) - sum(episode_values) - sum(repeat_values),
    }


def _mix(ids, features, field):
    counts = Counter(features[p][field] for p in ids)
    return [{"name": name, "count": count, "share_pct": _pct(count, len(ids))}
            for name, count in sorted(counts.items(), key=lambda item: str(item[0]))]


def _profile_summary(ids, features, linked, dated_before):
    selected = [p for p in ids if p in linked]
    sheet = sum(features[p]["sheet_starter"] for p in selected)
    return {"people": len(selected), "share_of_cohort_pct": _pct(len(selected), len(ids)),
            "sheet_starters": sheet, "sheet_starter_share_pct": _pct(sheet, len(selected)),
            "dated_profile_on_or_before_initial_date_people": sum(p in dated_before for p in selected),
            "basket_mix": _mix(selected, features, "entry_type"),
            "is_verified_marketable_audience": False}


def matched_cohort_evidence(people, windows, cutoff, features, linked, horizon_days=182,
                            episode_days=7, *, signed_events=None):
    """Match entry month/day intervals as well as outcome duration across years."""
    _integer(horizon_days, "horizon_days")
    cutoff = _day(cutoff)
    latest_start, latest_end = windows[-1]
    mature_end = min(latest_end, cutoff - timedelta(days=horizon_days - 1))
    rows = []
    for start, end in windows:
        offset = start.year - latest_start.year
        matched_start = max(start, shift_year(latest_start, offset))
        matched_end = min(end, shift_year(mature_end, offset))
        ids = [] if mature_end < latest_start else website_cohort(people, matched_start, matched_end, exclude_leap_day=True)
        sheet = [p for p in ids if features[p]["sheet_starter"]]
        profile_sheet = [p for p in sheet if p in linked]
        row = {"annual_start": start.isoformat(), "annual_end": end.isoformat(),
               "entry_start": matched_start.isoformat(),
               "entry_end": matched_end.isoformat() if mature_end >= latest_start else None,
               "leap_day_entries_excluded": True, "is_entire_annual_cohort": False}
        for key, selected in (("all", ids), ("sheet_starters", sheet), ("profile_linked_sheet_starters", profile_sheet)):
            row[key] = outcome_summary(people, selected, cutoff, horizon_days, episode_days, signed_events=signed_events)
            if row[key]["immature_people"]:
                raise ValueError("A matched entry window contains an immature outcome")
        rows.append(row)
    return rows


def pilot_risk_set_evidence(people, windows, cutoff, features, profile_dates, *,
                           assignment_day=60, outcome_days=90, episode_days=7,
                           signed_events=None):
    """Historical baseline for one early post-purchase content experiment.

    Candidate entry seasons match across cohorts. Eligibility at assignment
    excludes post-episode purchases before that date, without conditioning on
    purchases after assignment. This reconstructs an observed historical risk
    set, not a verified marketable roster or a causal treatment effect.
    """
    _integer(assignment_day, "assignment_day")
    _integer(outcome_days, "outcome_days")
    _integer(episode_days, "episode_days")
    if assignment_day <= episode_days:
        raise ValueError("assignment_day must follow the initial episode")
    cutoff = _day(cutoff)
    latest_start, latest_end = windows[-1]
    end_age = assignment_day + outcome_days
    latest_mature = min(latest_end, cutoff - timedelta(days=end_age - 1))
    cohorts = []

    def summary(ids):
        values, signed, counts = [], [], []
        for person in ids:
            first = _day(people[person][0]["order_date"])
            purchases = [row for row in people[person]
                         if assignment_day <= (_day(row["order_date"]) - first).days < end_age]
            values.append(sum(_money(row["net"]) for row in purchases))
            counts.append(len(purchases))
            if signed_events is not None:
                signed.append(sum(value for when, value in signed_events.get(person, [])
                                  if assignment_day <= (when - first).days < end_age))
        buyers = sum(n > 0 for n in counts)
        return {"people": len(ids), "buyers": buyers, "purchase_rate_pct": _pct(buyers, len(ids)),
                "purchase_orders": sum(counts), "mean_purchase_orders": _average(counts),
                "mean_window_purchase_order_net": _average(values),
                "mean_window_signed_line_date_net": _average(signed),
                "mean_purchase_net_per_buyer": _average([value for value, n in zip(values, counts) if n]),
                "mean_signed_line_date_net_per_buyer":
                    _average([value for value, n in zip(signed, counts) if n]) if signed_events is not None else None,
                "is_verified_marketable_audience": False}

    for start, end in windows:
        offset = start.year - latest_start.year
        entry_start = max(start, shift_year(latest_start, offset))
        entry_end = min(end, shift_year(latest_mature, offset))
        candidates = [] if latest_mature < latest_start else [
            p for p in website_cohort(people, entry_start, entry_end, exclude_leap_day=True)
            if features[p]["sheet_starter"]]
        eligible = []
        for person in candidates:
            first = _day(people[person][0]["order_date"])
            if first + timedelta(days=end_age - 1) > cutoff:
                raise ValueError("Pilot matched entry has incomplete outcome follow-up")
            if not any(episode_days < (_day(row["order_date"]) - first).days < assignment_day
                       for row in people[person]):
                eligible.append(person)
        profile_linked = [p for p in eligible if p in profile_dates and
                          _day(profile_dates[p]) <= _day(people[p][0]["order_date"]) + timedelta(days=assignment_day)]
        cohorts.append({
            "entry_start": entry_start.isoformat(),
            "entry_end": entry_end.isoformat() if latest_mature >= latest_start else None,
            "sheet_starter_candidates": len(candidates),
            "excluded_previous_post_episode_purchase": len(candidates) - len(eligible),
            "all_risk_eligible": summary(eligible),
            "profile_linked_by_assignment": summary(profile_linked),
        })
    return {"assignment_day": assignment_day, "outcome_days": outcome_days,
            "outcome_age_start_inclusive": assignment_day, "outcome_age_end_exclusive": end_age,
            "post_episode_purchase_exclusion_age_start_inclusive": episode_days + 1,
            "post_episode_purchase_exclusion_age_end_exclusive": assignment_day,
            "parameters_are_optimal_timing_evidence": False,
            "cohorts": cohorts,
            "limitations": [
                "Day-based reconstruction has no within-day event ordering; same-date profile creation is not proven to precede assignment time.",
                "A supplied dated profile does not establish consent, delivery, suppression, current membership or live eligibility.",
                "Eligibility uses canonical positive order net as of extract; later refunds can affect retrospective purchase classification.",
                "Per-buyer spend is selected observed-buyer value, not estimated value of an induced purchaser.",
                "Recorded signed net sales/refunds are not contribution; treatment, product and operating costs remain separate inputs.",
                "This conditional post-purchase baseline differs from a first-purchase-to-six-month return rate.",
            ]}


def _historical_repeat_evidence(people, ids, cutoff, features, order_baskets, episode_days, signed_events):
    horizon = 730
    mature = [p for p in ids if _day(people[p][0]["order_date"]) + timedelta(days=horizon - 1) <= cutoff]
    sheet = [p for p in mature if features[p]["sheet_starter"]]
    other = [p for p in mature if not features[p]["sheet_starter"]]
    seconds = []
    subtype = []
    for name in sorted({features[p]["sheet_subtype"] for p in sheet}):
        subset = [p for p in sheet if features[p]["sheet_subtype"] == name]
        summary = outcome_summary(people, subset, cutoff, horizon, episode_days, signed_events=signed_events)
        subtype.append({"name": name, **summary})
    for person in sheet:
        start = _day(people[person][0]["order_date"])
        orders = [row for row in people[person] if episode_days < (_day(row["order_date"]) - start).days < horizon]
        if orders:
            second = orders[0]
            seconds.append({"age": (_day(second["order_date"]) - start).days,
                            "basket": order_baskets[second["order_id"]]})
    known = [record for record in seconds if record["basket"]["has_known_category"]]
    categories = sorted({category for record in known for category in record["basket"]["categories"]})
    category_counts = {category: sum(category in r["basket"]["categories"] for r in known) for category in categories}
    timings = [record["age"] for record in seconds]
    bins = [(f"Day {episode_days + 1} to 18", episode_days + 1, 19),
            ("Day 19 to 364", 19, 365), ("Day 365 to 729", 365, 730)]
    # The display split is meaningful only for the specified seven-day episode.
    timing = {"people_with_post_episode_repeat": len(seconds), "initial_sheet_starters": len(sheet),
              "horizon_days": horizon, "conditional_on_returning": True,
              "bins": [{"label": label, "lower_day_inclusive": low, "upper_day_exclusive": high,
                        "count": sum(low <= age < high for age in timings),
                        "share_pct": _pct(sum(low <= age < high for age in timings), len(timings))}
                       for label, low, high in bins] if episode_days == 7 else [],
              "after_day18_share_pct": _pct(sum(age > 18 for age in timings), len(timings))}
    return {"people": len(mature), "excluded_incomplete_people": len(ids) - len(mature),
            "horizon_days": horizon,
            "sheet_starters": outcome_summary(people, sheet, cutoff, horizon, episode_days, signed_events=signed_events),
            "others_including_product_unknown": outcome_summary(people, other, cutoff, horizon, episode_days, signed_events=signed_events),
            "initial_sheet_subtype_repeat": subtype,
            "second_basket": {"all_sheet_starter_returners": len(seconds), "category_known_returners": len(known),
                              "category_unknown_returners": len(seconds) - len(known),
                              "returners_with_any_unknown_product_lines": sum(r["basket"]["unknown_product_lines"] > 0 for r in seconds),
                              "category_counts": category_counts,
                              "category_shares_pct": {c: _pct(n, len(known)) for c, n in category_counts.items()},
                              "category_percentages_can_overlap": True},
            "repeat_timing": timing}


def build_idea1_results(dataset, *, horizon_days=182, episode_days=7, cohort_count=3, welcome_codes=None,
                       assignment_day=60, pilot_outcome_days=90):
    """Build private aggregate evidence; caller loads the verified shared dataset.

    Optional welcome_codes is a private explicit list of exact code identifiers.
    Without it, welcome-code comparisons are unavailable, not assumed to be zero.
    """
    _integer(horizon_days, "horizon_days")
    _integer(episode_days, "episode_days")
    _integer(cohort_count, "cohort_count")
    if horizon_days <= episode_days + 1:
        raise ValueError("horizon_days must leave time beyond the initial episode")
    cutoff = _day(dataset.manifest["transaction_cutoff"])
    windows = annual_windows(cutoff, cohort_count)
    orders = dataset.table("orders")
    lines = dataset.table("order_lines")
    products = product_index(dataset.table("products"))
    people = customer_purchase_history(orders, cutoff)
    by_order = defaultdict(list)
    signed_events = defaultdict(list)
    for row in lines:
        by_order[row["order_id"]].append(row)
        if not row["is_special_account"] and (row["is_website"] or row["channel_detail"] == "Shopee") and _day(row["line_date"]) <= cutoff:
            signed_events[row["person_id"]].append((_day(row["line_date"]), _money(row["net"])))
    order_baskets = {row["order_id"]: basket_features(by_order[row["order_id"]], products)
                     for records in people.values() for row in records}
    features = {p: order_baskets[records[0]["order_id"]] for p, records in people.items()}
    linked, dated_before, profile_dates = set(), set(), {}
    for row in dataset.table("subscribers"):
        person = row.get("clean_person_id")
        if not person:
            continue
        linked.add(person)
        created = row.get("clean_profile_created_date")
        if created:
            created = _day(created)
            profile_dates[person] = min(profile_dates.get(person, created), created)
        if created and person in people and _day(created) <= _day(people[person][0]["order_date"]):
            dated_before.add(person)
    if welcome_codes is not None:
        welcome_codes = list(welcome_codes) if not isinstance(welcome_codes, (str, bytes)) else welcome_codes
        classify_codes([], welcome_codes)  # Validate once, even for an empty dataset.
    annual, welcome = [], []
    for start, end in windows:
        ids = website_cohort(people, start, end)
        profile = _profile_summary(ids, features, linked, dated_before)
        row = {"entry_start": start.isoformat(), "entry_end": end.isoformat(), "people": len(ids),
               "profile_linked": profile, "basket_mix": _mix(ids, features, "entry_type"),
               "people_with_unknown_first_product_lines": sum(features[p]["unknown_product_lines"] > 0 for p in ids),
               "complete365day_outcomes_subset": outcome_summary(people, ids, cutoff, 365, episode_days, signed_events=signed_events)}
        annual.append(row)
        codes = {p: classify_codes(by_order[people[p][0]["order_id"]], welcome_codes) for p in ids}
        group_rows = []
        for name in sorted({value["group"] for value in codes.values()}):
            selected = [p for p in ids if codes[p]["group"] == name]
            n_both = sum(features[p]["sheets_plus_bedding"] for p in selected)
            group_rows.append({"name": name, "people": len(selected), "sheets_plus_bedding_people": n_both,
                               "sheets_plus_bedding_share_pct": _pct(n_both, len(selected))})
        welcome.append({"entry_start": start.isoformat(), "entry_end": end.isoformat(),
                        "people": len(ids), "status": "evaluated_exact_codes" if welcome_codes is not None else "not_evaluated",
                        "people_with_recorded_string_code": sum(v["has_recorded_string_code"] for v in codes.values()),
                        "people_with_unresolved_code": sum(v["has_unresolved_code"] for v in codes.values()),
                        "groups": group_rows})
    matched = matched_cohort_evidence(people, windows, cutoff, features, linked, horizon_days,
                                      episode_days, signed_events=signed_events)
    pilot = pilot_risk_set_evidence(people, windows, cutoff, features, profile_dates,
                                    assignment_day=assignment_day, outcome_days=pilot_outcome_days,
                                    episode_days=episode_days, signed_events=signed_events)
    history_start, history_end = shift_year(cutoff, -4) + timedelta(days=1), shift_year(cutoff, -2)
    historical_ids = website_cohort(people, history_start, history_end)
    history = _historical_repeat_evidence(people, historical_ids, cutoff, features, order_baskets, episode_days, signed_events)
    history.update({"entry_start": history_start.isoformat(), "entry_end": history_end.isoformat()})
    ambiguous = sum(len({bool(row["is_website"]) for row in records
                         if _day(row["order_date"]) == _day(records[0]["order_date"])}) > 1
                    for records in people.values())
    claims = []

    def add(claim_id, metric, value, unit, population, *, numerator=None, denominator=None,
            start=None, end=None, horizon=None, status="descriptive_shared_dataset"):
        claims.append({"claim_id": claim_id, "metric": metric, "value": value, "unit": unit,
                       "population": population, "entry_start": start, "entry_end": end,
                       "horizon_days": horizon, "numerator": numerator, "denominator": denominator,
                       "evidence_status": status, "is_causal_effect": False})

    latest = annual[-1]
    p = latest["profile_linked"]
    add("I1_PROFILE_LINKED_SHEET_SHARE_LATEST", "First order contains known sheets", p["sheet_starter_share_pct"], "percent",
        "Website newcomers linked to a supplied profile at extract; not verified marketing eligibility",
        numerator=p["sheet_starters"], denominator=p["people"], start=latest["entry_start"], end=latest["entry_end"])
    add("I1_FIRST_ORDER_MIX_LATEST", "First-order category mix", p["basket_mix"], "table",
        "Profile-linked website newcomers", denominator=p["people"], start=latest["entry_start"], end=latest["entry_end"])
    for label, index in (("LATEST", -1), ("PRIOR", -2)):
        if len(matched) < abs(index):
            continue
        row = matched[index]
        summary = row["profile_linked_sheet_starters"]
        add(f"I1_MATCHED_REPEAT_RATE_{label}", "Post-episode repeat within fixed matched horizon", summary["repeat_rate_pct"], "percent",
            "Matched seasonal website entrants with known sheets and a supplied profile link; not a reachable launch roster",
            numerator=summary["returners"], denominator=summary["people"], start=row["entry_start"], end=row["entry_end"], horizon=horizon_days)
    for category, key in (("Bedsheets", "SHEETS"), ("Bedding", "BEDDING")):
        n = history["second_basket"]["category_counts"].get(category, 0)
        d = history["second_basket"]["category_known_returners"]
        add(f"I1_RETURNERS_{key}_SHARE_2Y", f"First post-episode repeat includes {category}", _pct(n, d), "percent",
            "Historical sheet starters who returned and whose second basket has a known category",
            numerator=n, denominator=d, start=history_start.isoformat(), end=history_end.isoformat(), horizon=730)
    add("I1_TWO_YEAR_SHEET_VALUE", "Mean fixed-horizon purchase-order net", history["sheet_starters"]["mean_purchase_order_net"], "currency",
        "Historical sheet starters with complete follow-up; first purchase included",
        denominator=history["sheet_starters"]["people"], start=history_start.isoformat(), end=history_end.isoformat(), horizon=730)
    add("I1_TIMING_AFTER_DAY18_SHARE", "Post-episode repeats occurring after day 18", history["repeat_timing"]["after_day18_share_pct"], "percent",
        "Historical sheet-starter returners, conditional on returning within fixed horizon",
        numerator=sum(b["count"] for b in history["repeat_timing"]["bins"] if b["lower_day_inclusive"] > 18),
        denominator=history["repeat_timing"]["people_with_post_episode_repeat"], start=history_start.isoformat(), end=history_end.isoformat(), horizon=730)
    if len(annual) > 1:
        prior = annual[-2]
        summary = prior["complete365day_outcomes_subset"]
        add("I1_VALUE_365_ALL_PRIOR", "Mean complete 365-day purchase-order net, all orders retained", summary["mean_purchase_order_net"], "currency",
            "Prior annual website-entry cohort with complete 365-day follow-up",
            denominator=summary["people"], start=prior["entry_start"], end=prior["entry_end"], horizon=365)
    for label, index in (("LATEST", -1), ("PRIOR", -2)):
        if len(pilot["cohorts"]) < abs(index):
            continue
        row = pilot["cohorts"][index]
        summary = row["profile_linked_by_assignment"]
        population = ("Matched seasonal sheet starters without an earlier post-episode purchase, "
                      "linked to a dated supplied profile by the assignment calendar day; not verified marketing eligibility")
        add(f"I1_PILOT_BUYER_RATE_{label}", "Purchase rate in the fixed post-assignment window", summary["purchase_rate_pct"], "percent",
            population, numerator=summary["buyers"], denominator=summary["people"],
            start=row["entry_start"], end=row["entry_end"], horizon=pilot_outcome_days)
        add(f"I1_PILOT_OBSERVED_BUYER_VALUE_{label}", "Recorded purchase-order net per observed post-assignment buyer", summary["mean_purchase_net_per_buyer"], "currency",
            population + "; conditional on subsequently buying", denominator=summary["buyers"],
            start=row["entry_start"], end=row["entry_end"], horizon=pilot_outcome_days)
    code_fingerprint = None if welcome_codes is None else sha256(json.dumps(sorted({v.strip().casefold() for v in welcome_codes})).encode()).hexdigest()
    return {
        "dataset_id": dataset.manifest["dataset_id"], "transaction_cutoff": cutoff.isoformat(),
        "parameters": {"horizon_days": horizon_days, "episode_days": episode_days, "cohort_count": cohort_count,
                       "assignment_day": assignment_day, "pilot_outcome_days": pilot_outcome_days,
                       "exact_welcome_codes_supplied": welcome_codes is not None, "welcome_code_set_sha256": code_fingerprint},
        "definitions": {
            "newcomer": "First observed positive nonspecial website/Shopee purchase is website, using canonical is_website; not first lifetime purchase across all channels.",
            "first_order_ties": "Same-date order IDs provide deterministic ordering, not within-day chronology.",
            "basket": "Known category/product-type attributes joined by exact SKU on retained non-order-level sale lines of the first individual order; unknown coverage retained.",
            "sheet_starter": "First individual order includes a known Bedsheets category; may also contain bedding or other items.",
            "profile_linked": "Person appears in the supplied profile extract; not consent, deliverability, an active subscriber or historical eligibility.",
            "repeat": "First qualifying purchase more than episode_days after initial date; early orders still retain all monetary value.",
            "fixed_horizon": "Initial date inclusive through initial date + horizon exclusive; mature when last included date is observed.",
            "matched_entries": "Same month/day entry interval across years; latest mature entry cap applied to every cohort; February 29 entries excluded.",
            "purchase_order_net": "Canonical positive purchase order net as of extract; includes later refund adjustments attributed to original order date.",
            "signed_line_date_net": "All retained scoped signed lines in the actual event-date window, including nonpositive orders/refunds; not cash or contribution.",
            "welcome_code": "Optional private exact string identifier list; strip and case-fold only. No campaign-name attribution or reconstruction of date-typed codes.",
        },
        "limitations": [
            "Descriptive subgroup differences and timing do not estimate intervention effects or optimal contact dates.",
            "Historical profile linkage does not identify a current reachable experiment population.",
            "Known basket attributes can be partial; category-known repeat shares exclude entirely unknown baskets and may overlap.",
            "First-order net can change after the decision date through refunds; this is not prospective predictor validation.",
            "Matched early-entry cohorts are seasonal subsets, not the full latest annual cohort.",
            "No actual margin, cost, campaign attribution, operational flow gap or annual profit is inferred.",
            "No bootstrap interval is supplied; a subgroup/population ratio needs joint customer resampling if uncertainty is later estimated.",
        ],
        "same_initial_date_cross_channel_people": ambiguous,
        "annual_cohorts": annual, "matched_cohorts": matched,
        "pilot_risk_set": pilot,
        "historical_two_year": history, "repeat_timing": history["repeat_timing"],
        "welcome_code_comparison": welcome, "claims": claims,
    }
