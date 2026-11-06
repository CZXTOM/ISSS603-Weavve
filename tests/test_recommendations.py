"""Synthetic date, cohort and metric-boundary tests; no private outputs."""
from datetime import date, timedelta
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weavve.final.recommendations import (
    annual_windows, build_recommendation_checks, customer_purchase_history,
    initial_purchase_values, initial_segment_checks, matched_followup_cohorts,
    matched_funnel_periods, shift_year, website_cohort,
)


def order(person, oid, when, value=100, **changes):
    row = {
        "person_id": person, "order_id": oid, "order_date": when,
        "net": Decimal(str(value)), "is_purchase": value > 0,
        "is_special_account": False, "is_website": True, "channel_detail": "Own store",
    }
    row.update(changes)
    return row


def funnel(month, sessions=100, orders=10, checkouts=20):
    return {
        "month": month, "geography": "test geography",
        "Sessions": sessions, "Add to Cart": 30,
        "Checkouts Initiated": checkouts, "Orders Placed": orders,
    }


class RecommendationChecksTests(unittest.TestCase):
    def test_customer_scope_and_first_channel_do_not_promote_old_shopee_buyer(self):
        start, end = date(2024, 1, 1), date(2024, 12, 31)
        rows = [
            order("old", "a", start - timedelta(days=1), is_website=False, channel_detail="Shopee"),
            order("old", "b", start),
            order("new", "c", start),
            order("last", "d", end),
            order("future", "e", end + timedelta(days=1)),
            order("special", "f", start, is_special_account=True),
            order("other", "g", start, is_website=False, channel_detail="Lazada"),
            order("nonpositive", "h", start, value=-10),
        ]
        people = customer_purchase_history(rows, end)
        self.assertEqual(set(people), {"old", "new", "last"})
        self.assertEqual(set(website_cohort(people, start, end)), {"new", "last"})
        self.assertEqual(set(website_cohort(people, start, start)), {"new"})

    def test_duplicate_canonical_order_cannot_double_customer_value(self):
        row = order("p", "o", date(2024, 1, 1))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            customer_purchase_history([row, row], date(2024, 12, 31))

    def test_first_calendar_day_is_not_initial_order(self):
        start = date(2024, 1, 1)
        rows = [
            order("later", "a", start, 30), order("later", "b", start, 30),
            order("later", "c", start + timedelta(days=7), 50),
            order("later", "d", start + timedelta(days=8), 500),
            order("same", "e", start, 70), order("same", "f", start, 40),
            order("immature", "g", date(2024, 1, 12), 900),
        ]
        people = customer_purchase_history(rows, date(2024, 1, 15))
        self.assertEqual(initial_purchase_values(people["later"]),
                         {"first_order": 30, "first_calendar_day": 60, "initial_episode": 110})
        result = initial_segment_checks(people, list(people), date(2024, 1, 15))
        self.assertEqual(result["threshold_from_training_episode_net"], 110)
        self.assertEqual(result["excluded_incomplete_episode_people"], 1)
        self.assertEqual(result["qualify_only_after_first_order"], 2)
        self.assertEqual(result["qualify_only_after_first_calendar_day"], 1)

    def test_matched_entries_remove_late_older_people_too(self):
        windows = [(date(2023, 1, 1), date(2023, 12, 31)),
                   (date(2024, 1, 1), date(2024, 12, 31))]
        cutoff = date(2024, 12, 31)
        # Latest mature entry for a 200-day horizon is June 14.
        boundary = cutoff - timedelta(days=200)
        rows = []
        for year in (2023, 2024):
            rows += [order(str(year), "a" + str(year), boundary.replace(year=year), 100),
                     order("late" + str(year), "b" + str(year),
                           boundary.replace(year=year) + timedelta(days=1), 1000)]
        people = customer_purchase_history(rows, cutoff)
        result = matched_followup_cohorts(people, windows, cutoff, 200)
        self.assertEqual([row["people"] for row in result], [1, 1])
        self.assertEqual([row["immature_people"] for row in result], [0, 0])
        self.assertEqual([row["mean_purchase_order_net"] for row in result], [100, 100])

    def test_leap_day_exclusion_and_boundary_mapping_are_explicit(self):
        cutoff = date(2024, 12, 31)
        windows = [(date(2023, 1, 1), date(2023, 12, 31)),
                   (date(2024, 1, 1), cutoff)]
        rows = [order("ordinary", "a", date(2023, 2, 28)),
                order("ordinary2", "b", date(2024, 2, 28)),
                order("leap", "c", date(2024, 2, 29)),
                order("late", "d", date(2023, 3, 1))]
        result = matched_followup_cohorts(customer_purchase_history(rows, cutoff), windows, cutoff, 306)
        self.assertEqual(result[0]["matched_entry_end"], "2023-02-28")
        self.assertEqual(result[1]["matched_entry_end"], "2024-02-29")
        self.assertEqual([row["people"] for row in result], [1, 1])
        self.assertEqual(shift_year(date(2024, 2, 29), -1), date(2023, 2, 28))

    def test_horizon_is_inclusive_and_refunds_use_event_dates(self):
        start, cutoff = date(2024, 1, 1), date(2024, 12, 31)
        rows = [order("p", "a", start, 80),
                order("p", "b", start + timedelta(days=10), 50),
                order("p", "c", start + timedelta(days=11), 700)]
        people = customer_purchase_history(rows, cutoff)
        events = {"p": [(start, 100), (start + timedelta(days=10), 50),
                        (start + timedelta(days=11), -20)]}
        result = matched_followup_cohorts(people, [(start, cutoff)], cutoff, 10, signed_events=events)[0]
        self.assertEqual(result["mean_purchase_order_net"], 130)
        self.assertEqual(result["mean_signed_line_date_net"], 150)

    def test_long_horizon_yields_no_partial_outcomes(self):
        start, cutoff = date(2024, 1, 1), date(2024, 2, 1)
        people = customer_purchase_history([order("p", "a", start)], cutoff)
        result = matched_followup_cohorts(people, [(start, cutoff)], cutoff, 200)[0]
        self.assertEqual(result["people"], 0)
        self.assertIsNone(result["mean_purchase_order_net"])
        self.assertIsNone(result["matched_entry_end"])

    def test_funnel_matches_complete_months_on_both_sides(self):
        rows = [funnel(date(2023, 1, 1)), funnel(date(2024, 1, 1), 80, 4, 10),
                funnel(date(2023, 2, 1), 50000, 1000),
                funnel(date(2024, 2, 1), 50000, 1000)]
        result = matched_funnel_periods(rows, date(2024, 1, 1), date(2024, 2, 15))
        self.assertEqual([row["expected_months"] for row in result["periods"]], [1, 1])
        comparison = result["comparison"]
        self.assertEqual(comparison["order_change"], -6)
        self.assertAlmostEqual(comparison["symmetric_sessions_component"] +
                               comparison["symmetric_conversion_component"], -6)
        self.assertEqual(comparison["holding_current_checkouts_restore_old_finish_extra_orders"], 1)
        self.assertFalse(comparison["is_causal_or_recoverable_effect"])

    def test_missing_funnel_metric_or_month_is_not_zero(self):
        row = funnel(date(2024, 1, 1))
        row["Orders Placed"] = None
        result = matched_funnel_periods([row], date(2024, 1, 1), date(2024, 1, 31))
        self.assertEqual(result["periods"][0]["missing_months"], ["2023-01-01"])
        self.assertEqual(result["periods"][1]["invalid_metrics"][0]["metric"], "Orders Placed")
        self.assertIsNone(result["comparison"])
        self.assertIsNone(result["periods"][1]["totals"])

    def test_funnel_disallows_mixed_geography(self):
        older, newer = funnel(date(2023, 1, 1)), funnel(date(2024, 1, 1))
        newer["geography"] = "different"
        with self.assertRaisesRegex(ValueError, "geography"):
            matched_funnel_periods([older, newer], date(2024, 1, 1), date(2024, 1, 31))

    def test_dataset_output_is_json_safe_and_contains_no_person_records(self):
        cutoff = date(2024, 12, 31)
        purchases = [order("private-person", "private-order", date(2023, 1, 1), 100)]
        lines = [
            {**purchases[0], "line_date": date(2023, 1, 1), "net": Decimal("120")},
            {**purchases[0], "line_date": date(2023, 1, 5), "net": Decimal("-20")},
            {**order("private-person", "negative-order", date(2023, 2, 1), -10),
             "line_date": date(2023, 2, 1)},
        ]

        class Dataset:
            manifest = {"transaction_cutoff": cutoff.isoformat(), "dataset_id": "synthetic"}
            def table(self, name):
                return {"orders": purchases, "order_lines": lines,
                        "website_funnel": [funnel(date(y, m, 1))
                                           for y in (2023, 2024) for m in range(1, 13)]}[name]

        result = build_recommendation_checks(Dataset())
        self.assertEqual(result["annual_cohorts"][1]["mean_signed_line_date_net"], 90)
        encoded = json.dumps(result, allow_nan=False)
        self.assertNotIn("private-person", encoded)
        self.assertNotIn("private-order", encoded)
        self.assertEqual(len(result["annual_cohorts"]), 3)
        self.assertEqual(annual_windows(cutoff, 1), [(date(2024, 1, 1), cutoff)])


if __name__ == "__main__":
    unittest.main()
