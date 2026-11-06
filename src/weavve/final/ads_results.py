"""Aggregate a private saved ads snapshot without embedding campaign inputs.

No account access, keyword strings, campaign identifiers or destination URLs are
returned. A successful reconciliation is descriptive evidence, not a causal test.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
import math


METRICS = ("impressions", "clicks", "cost")


def _day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("Ads dates must be ISO calendar dates")
    return date.fromisoformat(value)


def _number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite nonnegative number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{field} must be a finite nonnegative number")
    if field in ("impressions", "clicks") and not result.is_integer():
        raise ValueError(f"{field} must be a whole count")
    return int(result) if field in ("impressions", "clicks") else result


def _rows(value, name):
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"{name} must be a list of records")
    return value


def _totals(rows):
    if rows is None:
        return None
    result = {"row_count": len(rows)}
    missing = {}
    for metric in METRICS:
        absent = sum(row.get(metric) is None for row in rows)
        missing[metric] = absent
        values = [_number(row[metric], metric) for row in rows if row.get(metric) is not None]
        result[metric] = sum(values) if not absent else None
    result["missing_metric_counts"] = missing
    result["ctr_pct"] = (100 * result["clicks"] / result["impressions"]
                         if result["impressions"] and result["clicks"] is not None else None)
    return result


def _comparison(left, right):
    if left is None or right is None:
        return None
    return {metric: None if left[metric] is None or right[metric] is None else
            math.isclose(left[metric], right[metric], rel_tol=1e-9, abs_tol=1e-6)
            for metric in METRICS}


def _diagnostics(keywords):
    if keywords is None:
        return {"available": False}
    texts = set()
    missing_texts = 0
    scored = []
    for row in keywords:
        text = row.get("text")
        if isinstance(text, str) and text.strip():
            texts.add(text.strip().casefold())
        else:
            missing_texts += 1
        score = row.get("qs")
        if score is None:
            continue
        score = _number(score, "quality score")
        if not score.is_integer() or not 1 <= score <= 10:
            raise ValueError("A present quality score must be an integer from one to ten")
        scored.append((row, int(score)))
    landing = Counter(str(row.get("landing")).upper() for row, _ in scored
                      if row.get("landing") is not None)
    known_landing = sum(landing.values())
    return {
        "available": True,
        "criterion_count": len(keywords), "distinct_keyword_text_count": len(texts),
        "missing_keyword_text_count": missing_texts,
        "scored_criterion_count": len(scored), "unscored_criterion_count": len(keywords) - len(scored),
        "landing_experience_counts": dict(landing),
        "landing_known_scored_count": known_landing,
        "landing_missing_scored_count": len(scored) - known_landing,
        "landing_below_average_count": landing.get("BELOW_AVERAGE", 0),
        "quality_score_counts": dict(Counter(str(score) for _, score in scored)),
        "unit": "keyword/match-type criterion, not distinct destination page",
        "keyword_text_count_rule": "Trimmed, case-insensitive exact text; no close-variant inference.",
    }


def _phase_results(daily, start, end, log, missing_days):
    if log is None:
        return [], "unavailable: no change log supplied", None
    log = _rows(log, "change log")
    dates = Counter()
    invalid = outside = 0
    for row in log:
        try:
            when = _day(row.get("date"))
        except (ValueError, TypeError):
            invalid += 1
            continue
        if start <= when <= end:
            dates[when] += 1
        else:
            outside += 1
    coverage = {"record_count": len(log), "invalid_date_count": invalid,
                "outside_range_count": outside,
                "supplied_log_completeness_verified": False,
                "changes_by_date": [{"date": when.isoformat(), "count": count}
                                    for when, count in sorted(dates.items())]}
    if invalid or missing_days or daily is None:
        return [], "unavailable: incomplete dated daily or change-log evidence", coverage
    phases = []
    phase_start = start
    boundaries = sorted(set(dates) | {end})
    for phase_end in boundaries:
        if phase_start > phase_end:
            continue
        rows = [row for row in daily if phase_start <= _day(row["date"]) <= phase_end]
        totals = _totals(rows)
        days = (phase_end - phase_start).days + 1
        totals.update({
            "start_inclusive": phase_start.isoformat(), "end_inclusive": phase_end.isoformat(),
            "calendar_days": days,
            "impressions_per_day": totals["impressions"] / days if totals["impressions"] is not None else None,
            "clicks_per_day": totals["clicks"] / days if totals["clicks"] is not None else None,
            "recorded_changes_on_end_date": dates.get(phase_end, 0),
            "is_causal_effect": False,
        })
        phases.append(totals)
        phase_start = phase_end + timedelta(days=1)
    return phases, "descriptive phases from supplied log; log completeness unverified", coverage


def build_ads_results(data, log=None, plan=None):
    """Return JSON-safe aggregates from the documented private monitor schema.

    Expected keys: range=[start,end], campaign, daily, ad_groups and keywords.
    Missing optional arrays remain unavailable. Daily rows require unique ISO
    dates and nonnegative metrics. No missing day is silently treated as zero.
    """
    if not isinstance(data, dict):
        raise ValueError("Ads snapshot must be an object")
    daily = _rows(data.get("daily"), "daily")
    groups = _rows(data.get("ad_groups"), "ad_groups")
    keywords = _rows(data.get("keywords"), "keywords")
    raw_range = data.get("range")
    inferred_range = raw_range is None
    if raw_range is None:
        if not daily:
            raise ValueError("Supply a date range or dated daily records")
        raw_range = [min(_day(row["date"]) for row in daily), max(_day(row["date"]) for row in daily)]
    if not isinstance(raw_range, (list, tuple)) or len(raw_range) != 2:
        raise ValueError("Ads range requires exactly a start and end date")
    start, end = map(_day, raw_range)
    if end < start:
        raise ValueError("Ads range end precedes start")
    present = set()
    for row in daily or []:
        when = _day(row.get("date"))
        if not start <= when <= end or when in present:
            raise ValueError("Daily records must have unique dates inside the stated range")
        present.add(when)
    expected = {start + timedelta(days=n) for n in range((end - start).days + 1)}
    missing_days = sorted(expected - present)
    campaign = data.get("campaign")
    if campaign is not None and not isinstance(campaign, dict):
        raise ValueError("campaign must be an object")
    campaign_totals = _totals([campaign]) if campaign is not None else None
    daily_totals, group_totals, keyword_totals = map(_totals, (daily, groups, keywords))
    diagnostics = _diagnostics(keywords)
    phases, phase_status, log_coverage = _phase_results(daily, start, end, log, missing_days)
    rank_loss = campaign.get("lost_rank") if campaign is not None else None
    if rank_loss is not None:
        rank_loss = _number(rank_loss, "rank-loss percentage")
        if rank_loss > 100:
            raise ValueError("Rank-loss percentage must be on a zero-to-one-hundred scale")
    plan_summary = {"available": plan is not None}
    if plan is not None:
        if not isinstance(plan, dict):
            raise ValueError("plan must be an object")
        planned_groups = _rows(plan.get("groups"), "planned groups")
        dropped = _rows(plan.get("dropped"), "dropped entries")
        plan_summary.update({
            "group_count": len(planned_groups) if planned_groups is not None else None,
            "keyword_entry_count": sum(len(row.get("keywords", [])) for row in planned_groups) if planned_groups is not None else None,
            "distinct_destination_url_count": len({row["url"] for row in planned_groups if row.get("url")}) if planned_groups is not None else None,
            "dropped_entry_count": len(dropped) if dropped is not None else None,
        })
    errors = data.get("errors") or []
    status = "descriptive_saved_snapshot" if not errors else "snapshot_has_reported_errors"
    claims = []
    if campaign_totals is not None:
        for claim_id, metric, unit in (("ADS_IMPRESSIONS", "impressions", "count"),
                                       ("ADS_CLICKS", "clicks", "count"),
                                       ("ADS_COST", "cost", "account currency"),
                                       ("ADS_CTR", "ctr_pct", "percent")):
            claims.append({"claim_id": claim_id, "value": campaign_totals[metric], "unit": unit,
                           "range": [start.isoformat(), end.isoformat()], "evidence_status": status,
                           "is_causal_effect": False})
    if diagnostics["available"]:
        for claim_id, key in (("ADS_SCORED_CRITERIA", "scored_criterion_count"),
                              ("ADS_LP_BELOW_AVERAGE", "landing_below_average_count")):
            claims.append({"claim_id": claim_id, "value": diagnostics[key], "unit": diagnostics["unit"],
                           "denominator": diagnostics["scored_criterion_count"], "evidence_status": status,
                           "is_causal_effect": False})
    return {
        "range": [start.isoformat(), end.isoformat()], "range_inferred_from_daily": inferred_range,
        "generated_at": data.get("generated_at"), "account_timezone": data.get("account_tz"),
        "evidence_status": status, "campaign_totals": campaign_totals,
        "daily_totals": daily_totals, "group_totals": group_totals, "keyword_totals": keyword_totals,
        "ad_groups": [{"group_index": index, **_totals([row])} for index, row in enumerate(groups or [], 1)],
        "keyword_diagnostics": diagnostics, "plan_summary": plan_summary,
        "rank_loss": {"percent": rank_loss, "scope": "Estimated eligible Search impressions lost due to rank; not all searches or people."},
        "coverage": {"expected_daily_records": len(expected), "observed_daily_records": len(present),
                     "missing_dates": [when.isoformat() for when in missing_days],
                     "source_error_count": len(errors)},
        "reconciliation": {"daily_vs_campaign": _comparison(daily_totals, campaign_totals),
                           "groups_vs_campaign": _comparison(group_totals, campaign_totals),
                           "keywords_vs_campaign": _comparison(keyword_totals, campaign_totals)},
        "phases": phases, "phase_evidence_status": phase_status, "change_log_coverage": log_coverage,
        "phase_convention": "Whole-day phases include the change date in the previous phase; intraday exposure is mixed.",
        "deconfliction_status": "Unverified: no complete counterpart keyword/query replay is supplied by this interface.",
        "claims": claims,
        "limitations": [
            "Saved snapshot, not a fresh account pull or an experiment result.",
            "Before/after phases can combine settings, auction and traffic changes; no isolated causal effect is estimated.",
            "Quality and landing-page ratings are keyword/match-type diagnostics, not a count of distinct pages.",
            "Missing days and metrics remain explicit; totals with incomplete coverage need qualification.",
            "Source currencies are not inferred; cost is in the account currency.",
            "Clicks, CTR and serving rates do not establish incremental customer contribution.",
        ],
    }
