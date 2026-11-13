"""Synthetic recorded-event, accounting and scenario-boundary checks."""
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weavve.final.cart_completion import (
    build_cart_completion_results, evaluate_cart_scenarios, website_value_reference,
)


def funnel(month, carts, orders):
    return {"month": month, "Sessions": carts * 10, "Add to Cart": carts,
            "Checkouts Initiated": carts, "Orders Placed": orders, "geography": "Singapore Only"}


def order(oid, when, net, **changes):
    row = {"order_id": oid, "order_date": when, "net": Decimal(str(net)),
           "is_purchase": net > 0, "is_website": True, "is_special_account": False}
    row.update(changes)
    return row


def config():
    return {"observed_recorded_carts": 1000, "baseline_ratio": .2,
            "purchase_order_net_reference": 100, "marginal_value_factor": .5,
            "assumed_contribution_rate": .6, "fixed_incremental_cost": 100,
            "variable_cost_per_extra_order": 5,
            "cases": {"adverse": -.01, "zero": 0, "positive": .02},
            "planning_period_label": "Synthetic two-month planning period"}


class CartCompletionTests(unittest.TestCase):
    def test_calendar_period_is_inclusive_and_money_boundaries_are_separate(self):
        orders = [order("first", date(2024, 9, 1), 80), order("last", date(2024, 10, 31), 120),
                  order("refund", date(2024, 10, 1), -20), order("zero", date(2024, 10, 2), 0),
                  order("before", date(2024, 8, 31), 999), order("after", date(2024, 11, 1), 999),
                  order("special", date(2024, 9, 1), 999, is_special_account=True),
                  order("marketplace", date(2024, 9, 1), 999, is_website=False)]
        lines = [{**orders[0], "line_date": date(2024, 9, 1), "net": Decimal("100")},
                 {**orders[0], "line_date": date(2024, 11, 1), "net": Decimal("-20")},
                 {**orders[2], "line_date": date(2024, 10, 31)}]
        result = website_value_reference(orders, lines, "2024-09-01", "2024-10-01")
        self.assertEqual(result["positive_purchase_orders"], 2)
        self.assertEqual(result["purchase_order_net_reference"], 100)
        self.assertEqual(result["signed_website_order_count"], 4)
        self.assertEqual(result["signed_website_order_net_total"], 180)
        self.assertEqual(result["signed_website_line_date_net_total"], 80)
        self.assertFalse(result["geography_matches_funnel"])

    def test_ratios_use_total_counts_and_only_matched_complete_months(self):
        rows = [funnel(date(2023, 9, 1), 10, 10), funnel(date(2023, 10, 1), 90, 9),
                funnel(date(2024, 9, 1), 20, 2), funnel(date(2024, 10, 1), 80, 8),
                funnel(date(2024, 11, 1), 9999, 9999)]
        # A cutoff on November 15 excludes that partial month in both periods.
        class Dataset:
            manifest = {"dataset_id": "synthetic", "transaction_cutoff": "2024-11-15"}
            def table(self, name):
                return {"website_funnel": rows, "orders": [], "order_lines": []}[name]
        # The annual window begins mid-November, so December-August must also
        # be supplied; use zero cart/order events in those common complete months.
        for year, months in ((2022, [12]), (2023, range(1, 9)),
                             (2023, [12]), (2024, range(1, 9))):
            rows.extend(funnel(date(year, month, 1), 0, 0) for month in months)
        result = build_cart_completion_results(Dataset())
        old, current = result["periods"]
        self.assertEqual(old["orders_per_recorded_add_to_cart"], .19)
        self.assertEqual(current["orders_per_recorded_add_to_cart"], .1)
        self.assertAlmostEqual(result["cart_ratio_gap"], -.09)
        self.assertAlmostEqual(result["holding_current_recorded_carts_restore_old_ratio_extra_orders"], 9)
        self.assertIn("not a verified unique-cart", result["limitations"][0])
        self.assertFalse(current["ledger_reference"]["geography_matches_funnel"])

    def test_zero_and_adverse_cases_retain_fixed_cost_and_signed_variable_savings(self):
        result = evaluate_cart_scenarios(config())
        rows = {row["label"]: row for row in result["cases"]}
        self.assertEqual(result["assumed_unit_contribution_after_extra_order_cost"], 25)
        self.assertEqual(rows["zero"]["contribution_after_entered_costs"], -100)
        self.assertEqual(rows["adverse"]["extra_orders"], -10)
        self.assertEqual(rows["adverse"]["variable_order_cost_change"], -50)
        self.assertEqual(rows["adverse"]["contribution_after_entered_costs"], -350)
        self.assertEqual(rows["positive"]["contribution_after_entered_costs"], 400)
        self.assertEqual(result["break_even_extra_orders"], 4)
        self.assertEqual(result["break_even_rate_change"], .004)
        self.assertEqual(result["planning_period_label"], config()["planning_period_label"])
        json.dumps(result, allow_nan=False)

    def test_missing_downside_or_unprofitable_unit_is_not_hidden(self):
        bad = config()
        bad["cases"] = {"zero": 0, "benefit": .01}
        with self.assertRaises(ValueError):
            evaluate_cart_scenarios(bad)
        bad = config()
        bad["variable_cost_per_extra_order"] = 30
        result = evaluate_cart_scenarios(bad)
        self.assertFalse(result["positive_unit_contribution"])
        self.assertIsNone(result["break_even_extra_orders"])
        self.assertIsNone(result["break_even_rate_change"])

    def test_event_ratio_is_not_capped_as_a_probability(self):
        data = config()
        data["baseline_ratio"] = 1.2
        data["cases"] = {"adverse": {"rate_change": -.01}, "zero": {"rate_change": 0},
                         "positive": {"rate_change": .01}}
        self.assertAlmostEqual(evaluate_cart_scenarios(data)["cases"][-1]["target_recorded_orders_cart_ratio"], 1.21)

    def test_invalid_assumptions_and_duplicate_orders_fail(self):
        for key, value in (("observed_recorded_carts", 0), ("baseline_ratio", float("nan")),
                           ("marginal_value_factor", 1.1), ("fixed_incremental_cost", True)):
            data = config()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                evaluate_cart_scenarios(data)
        row = order("duplicate", date(2024, 9, 1), 10)
        with self.assertRaises(ValueError):
            website_value_reference([row, row], [], "2024-09-01", "2024-09-01")


if __name__ == "__main__":
    unittest.main()
