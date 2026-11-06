"""Reproducible recommendation diagnostics over the verified local dataset.

All returned aggregates are private outputs. No original business-team analysis
is claimed to have been rerun. The functions do not clean or mutate source data.
"""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta
import math
from statistics import mean


FUNNEL_METRICS = ("Sessions", "Add to Cart", "Checkouts Initiated", "Orders Placed")


def _day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def shift_year(value, years):
    """Shift a calendar boundary; February 29 maps to February 28."""
    value = _day(value)
    target = value.year + years
    return value.replace(year=target, day=min(value.day, monthrange(target, value.month)[1]))


def annual_windows(cutoff, count=3):
    """Inclusive annual windows ending on the extract's calendar anniversary."""
    cutoff = _day(cutoff)
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValueError("count must be a positive integer")
    return [
        (shift_year(cutoff, -offset - 1) + timedelta(days=1), shift_year(cutoff, -offset))
        for offset in reversed(range(count))
    ]


def _positive_integer(value, name):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _scope(row):
    return not row["is_special_account"] and (row["is_website"] or row["channel_detail"] == "Shopee")


def customer_purchase_history(orders, cutoff):
    """Canonical positive website/Shopee purchases by person, through cutoff.

    A same-day tie is ordered by order_id for reproducibility, not because order
    IDs prove the within-day chronology. The aggregate diagnostics flag ties
    spanning website and Shopee.
    """
    cutoff = _day(cutoff)
    people = defaultdict(list)
    seen = set()
    for row in orders:
        if not row["is_purchase"] or not _scope(row) or _day(row["order_date"]) > cutoff:
            continue
        value = float(row["net"])
        if not math.isfinite(value) or value <= 0:
            raise ValueError("A positive purchase has invalid net")
        if not row["person_id"] or not row["order_id"]:
            raise ValueError("Purchase identity is missing")
        if row["order_id"] in seen:
            raise ValueError("Duplicate canonical order")
        seen.add(row["order_id"])
        people[row["person_id"]].append(row)
    for records in people.values():
        records.sort(key=lambda row: (_day(row["order_date"]), str(row["order_id"])))
    return dict(people)


def website_cohort(people, start, end, *, exclude_leap_day=False):
    """People whose first in-scope purchase is website and in inclusive bounds."""
    start, end = _day(start), _day(end)
    if end < start:
        return []
    return [
        person for person, records in people.items()
        if records[0]["is_website"]
        and start <= _day(records[0]["order_date"]) <= end
        and not (exclude_leap_day and (_day(records[0]["order_date"]).month,
                                       _day(records[0]["order_date"]).day) == (2, 29))
    ]


def initial_purchase_values(records, episode_days=7):
    """Separate initial order, all initial-calendar-day orders, and episode.

    The episode includes both day zero and first-date + episode_days. These
    are order nets as of extraction, including later adjustments to an order.
    """
    _positive_integer(episode_days, "episode_days")
    if not records:
        raise ValueError("Purchase history is empty")
    records = sorted(records, key=lambda row: (_day(row["order_date"]), str(row["order_id"])))
    first = _day(records[0]["order_date"])
    return {
        "first_order": float(records[0]["net"]),
        "first_calendar_day": sum(float(row["net"]) for row in records if _day(row["order_date"]) == first),
        "initial_episode": sum(float(row["net"]) for row in records
                               if _day(row["order_date"]) <= first + timedelta(days=episode_days)),
    }


def _signed_events(lines, cutoff):
    events = defaultdict(list)
    for row in lines:
        if _scope(row) and _day(row["line_date"]) <= cutoff:
            value = float(row["net"])
            if not math.isfinite(value):
                raise ValueError("Signed event has invalid net")
            events[row["person_id"]].append((_day(row["line_date"]), value))
    return dict(events)


def _cohort_summary(people, ids, observation_end, *, followup_days=None, signed_events=None):
    """No incomplete fixed-horizon individual outcome enters a fixed mean."""
    observation_end = _day(observation_end)
    ages = [(observation_end - _day(people[p][0]["order_date"])).days for p in ids]
    mature = [p for p in ids if followup_days is None
              or _day(people[p][0]["order_date"]) + timedelta(days=followup_days) <= observation_end]
    values, events = [], []
    for person in mature:
        start = _day(people[person][0]["order_date"])
        end = observation_end if followup_days is None else start + timedelta(days=followup_days)
        values.append(sum(float(row["net"]) for row in people[person] if _day(row["order_date"]) <= end))
        if signed_events is not None:
            events.append(sum(value for when, value in signed_events.get(person, []) if start <= when <= end))
    return {
        "people": len(ids),
        "mature_people": len(mature),
        "immature_people": len(ids) - len(mature),
        "mean_available_observation_days": mean(ages) if ages else None,
        "mean_observation_days": (followup_days if mature else None)
        if followup_days is not None else (mean(ages) if ages else None),
        "followup_days": followup_days,
        "mean_purchase_order_net": mean(values) if values else None,
        "mean_signed_line_date_net": mean(events) if events else None,
    }


def matched_followup_cohorts(people, windows, cutoff, followup_days=200, *, signed_events=None):
    """Compare identical calendar entry ranges and complete elapsed-day follow-up.

    Latest mature entry = cutoff - followup_days. Apply its calendar boundary
    to every annual window. Exclude February 29 entries in *every* window so a
    leap year's extra entry date does not alter the matched seasonal exposure.
    Boundary shifts clamp February 29 to February 28. Follow-up itself always
    uses elapsed days, including leap days. These are matched early-entry
    subsets, not estimates for each entire annual cohort.
    """
    _positive_integer(followup_days, "followup_days")
    cutoff = _day(cutoff)
    windows = [(_day(start), _day(end)) for start, end in windows]
    if not windows or any(end < start for start, end in windows):
        raise ValueError("Valid annual windows are required")
    latest_start, latest_end = max(windows, key=lambda item: item[0])
    latest_mature_end = min(latest_end, cutoff - timedelta(days=followup_days))
    result = []
    for start, end in windows:
        offset = start.year - latest_start.year
        matched_start = max(start, shift_year(latest_start, offset))
        matched_end = min(end, shift_year(latest_mature_end, offset))
        ids = [] if latest_mature_end < latest_start else website_cohort(
            people, matched_start, matched_end, exclude_leap_day=True)
        # A caller may supply non-annual or future windows. Never hide censoring.
        summary = _cohort_summary(people, ids, cutoff, followup_days=followup_days,
                                  signed_events=signed_events)
        if summary["immature_people"]:
            raise ValueError("Matched window includes people without complete follow-up")
        summary.update({
            "annual_start": start.isoformat(), "annual_end": end.isoformat(),
            "matched_entry_start": matched_start.isoformat(),
            "matched_entry_end": matched_end.isoformat() if latest_mature_end >= latest_start else None,
            "entry_leap_days_excluded": True,
            "is_entire_annual_cohort": False,
        })
        result.append(summary)
    return result


def _quantile(values, probability):
    if not 0 <= probability <= 1 or not math.isfinite(probability):
        raise ValueError("quantile probability must be between zero and one")
    values = sorted(values)
    if not values:
        return None
    index = (len(values) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def initial_segment_checks(people, ids, cutoff, *, episode_days=7, quantile=0.8):
    """Derive a threshold from complete episodes; show date leakage separately."""
    _positive_integer(episode_days, "episode_days")
    cutoff = _day(cutoff)
    complete = [p for p in ids if _day(people[p][0]["order_date"]) + timedelta(days=episode_days) <= cutoff]
    values = {p: initial_purchase_values(people[p], episode_days) for p in complete}
    threshold = _quantile([row["initial_episode"] for row in values.values()], quantile)
    selected = [row for row in values.values() if row["initial_episode"] >= threshold] if threshold is not None else []
    return {
        "training_people": len(complete),
        "excluded_incomplete_episode_people": len(ids) - len(complete),
        "episode_days_after_initial_date_inclusive": episode_days,
        "quantile": quantile,
        "threshold_from_training_episode_net": threshold,
        "selected_people": len(selected),
        "qualify_only_after_first_order": sum(row["first_order"] < threshold for row in selected),
        "qualify_only_after_first_calendar_day": sum(row["first_calendar_day"] < threshold for row in selected),
        "any_additional_episode_order_spend": sum(row["initial_episode"] > row["first_order"] for row in selected),
        "any_later_calendar_day_episode_spend": sum(row["initial_episode"] > row["first_calendar_day"] for row in selected),
        "threshold_is_prospective_validation": False,
        "ties_can_make_selected_share_exceed_target": True,
    }


def _month_sequence(start, end):
    current = start.replace(day=1)
    result = []
    while current <= end:
        result.append(current)
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
    return result


def matched_funnel_periods(rows, latest_start, cutoff):
    """Use exactly the same complete calendar months in adjacent annual periods.

    Missing months/metrics produce an unavailable comparison rather than zeros.
    Both windows must have one consistent geography; the supplied table remains
    all-visitor/all-order funnel data, not a newcomer acquisition funnel.
    """
    latest_start, cutoff = _day(latest_start), _day(cutoff)
    first = latest_start.replace(day=1)
    if first < latest_start:
        first = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    last = cutoff.replace(day=1)
    if cutoff.day != monthrange(cutoff.year, cutoff.month)[1]:
        last = (last - timedelta(days=1)).replace(day=1)
    months = _month_sequence(first, last)
    expected = [[shift_year(month, -1) for month in months], months]
    all_months = set(expected[0] + expected[1])
    lookup = {}
    geographies = set()
    for row in rows:
        month = _day(row["month"]).replace(day=1)
        if month not in all_months:
            continue
        if month in lookup:
            raise ValueError("Duplicate monthly funnel record; select a single geography first")
        lookup[month] = row
        geographies.add(row.get("geography"))
    if len(geographies) > 1:
        raise ValueError("Matched funnel geography differs")
    periods = []
    for group in expected:
        missing = [month.isoformat() for month in group if month not in lookup]
        invalid = []
        totals = {metric: 0.0 for metric in FUNNEL_METRICS}
        for month in group:
            if month not in lookup:
                continue
            for metric in FUNNEL_METRICS:
                value = lookup[month].get(metric)
                if value is None or isinstance(value, bool):
                    invalid.append({"month": month.isoformat(), "metric": metric})
                    continue
                value = float(value)
                if not math.isfinite(value) or value < 0:
                    invalid.append({"month": month.isoformat(), "metric": metric})
                else:
                    totals[metric] += value
        complete = bool(group) and not missing and not invalid
        periods.append({
            "start_month": group[0].isoformat() if group else None,
            "end_month": group[-1].isoformat() if group else None,
            "expected_months": len(group), "missing_months": missing, "invalid_metrics": invalid,
            "complete": complete, "totals": totals if complete else None,
            "orders_per_session": totals["Orders Placed"] / totals["Sessions"]
            if complete and totals["Sessions"] else None,
            "checkout_completion": totals["Orders Placed"] / totals["Checkouts Initiated"]
            if complete and totals["Checkouts Initiated"] else None,
        })
    comparison = None
    older, current = periods
    if all(period["complete"] for period in periods) and all(
            period["orders_per_session"] is not None for period in periods):
        s0, s1 = older["totals"]["Sessions"], current["totals"]["Sessions"]
        r0, r1 = older["orders_per_session"], current["orders_per_session"]
        comparison = {
            "order_change": current["totals"]["Orders Placed"] - older["totals"]["Orders Placed"],
            "symmetric_sessions_component": (s1 - s0) * (r0 + r1) / 2,
            "symmetric_conversion_component": (r1 - r0) * (s0 + s1) / 2,
            "holding_current_checkouts_restore_old_finish_extra_orders":
                current["totals"]["Checkouts Initiated"] * older["checkout_completion"] - current["totals"]["Orders Placed"]
                if older["checkout_completion"] is not None else None,
            "is_causal_or_recoverable_effect": False,
        }
    return {
        "geography": next(iter(geographies)) if geographies else None,
        "periods": periods, "comparison": comparison,
        "scope": "All visitors and orders in monthly funnel; not linked new customers.",
        "partial_cutoff_month_excluded": cutoff.day != monthrange(cutoff.year, cutoff.month)[1],
    }


def build_recommendation_checks(dataset, *, cohort_count=3, followup_days=200,
                                episode_days=7, high_value_quantile=0.8):
    """Return JSON-safe private aggregates from a verified CleanDataset.

    Caller is responsible for loading through load_dataset() with verification
    enabled and keeping this result outside Git. No source-derived identifiers
    or individual records are returned.
    """
    _positive_integer(followup_days, "followup_days")
    cutoff = _day(dataset.manifest["transaction_cutoff"])
    windows = annual_windows(cutoff, cohort_count)
    people = customer_purchase_history(dataset.table("orders"), cutoff)
    signed_events = _signed_events(dataset.table("order_lines"), cutoff)
    annual = []
    training_ids = []
    for index, (start, end) in enumerate(windows):
        ids = website_cohort(people, start, end)
        summary = _cohort_summary(people, ids, end, signed_events=signed_events)
        summary.update({"start": start.isoformat(), "end": end.isoformat(),
                        "same_followup_for_every_person": False})
        annual.append(summary)
        if index < len(windows) - 1:
            training_ids.extend(p for p in ids if _day(people[p][0]["order_date"]) + timedelta(days=365) <= cutoff)
    ambiguous = 0
    for records in people.values():
        first = _day(records[0]["order_date"])
        flags = {bool(row["is_website"]) for row in records if _day(row["order_date"]) == first}
        ambiguous += len(flags) > 1
    segments = initial_segment_checks(people, training_ids, cutoff,
                                      episode_days=episode_days, quantile=high_value_quantile)
    segments["training_scope"] = "Older annual cohorts only, each with at least 365 elapsed days observed."
    return {
        "dataset_id": dataset.manifest["dataset_id"],
        "transaction_cutoff": cutoff.isoformat(),
        "definitions": {
            "customer_scope": "Canonical positive nonspecial website/Shopee purchases; first in-scope purchase must be website.",
            "window_bounds": "Dates inclusive; fixed horizons include day zero through first-date + stated days.",
            "same_day_ties": "Order ID provides deterministic ordering only; first-day cross-channel ties are ambiguous.",
            "purchase_order_net": "Positive-purchase order nets as of extraction, attributed to original order date.",
            "signed_line_date_net": "All retained in-scope signed lines on event dates, including refunds and nonpositive orders.",
            "initial_episode": "Initial date through initial date + episode_days inclusive.",
            "matched_entries": "Identical calendar entry bounds across annual windows; February 29 entries excluded.",
            "quantile": "Linear interpolation, learned from older complete customer-year cohorts; boundary ties retained.",
        },
        "limitations": [
            "New means first observed within website/Shopee data, not proven first lifetime purchase across all platforms.",
            "Supplier person matching is used without independent identity validation.",
            "Profile creation is not verified consent, deliverability, voluntary signup or experiment eligibility.",
            "Historical campaign recipients and issued vouchers are not a current member register.",
            "Order nets include later refund adjustments: date-leakage checks do not validate a live day-one predictor.",
            "Positive-purchase selection excludes nonpositive orders from customer history; signed-line outcomes retain them.",
            "Signed line-date net is recorded sales/refunds, not payment cash flow, contribution margin or profit.",
            "Matched early-entry cohorts do not represent each entire annual cohort; composition may differ.",
            "Funnel decomposition is descriptive and not specific to new visitors or new customers.",
            "No causal uplift, actual margin, operational eligibility, live flow defect or investment return is established.",
        ],
        "same_initial_date_cross_channel_people": ambiguous,
        "annual_cohorts": annual,
        "matched_followup_cohorts": matched_followup_cohorts(
            people, windows, cutoff, followup_days, signed_events=signed_events),
        "initial_purchase_segments": segments,
        "matched_funnel": matched_funnel_periods(dataset.table("website_funnel"), windows[-1][0], cutoff),
    }
