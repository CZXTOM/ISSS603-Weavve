"""Synthetic Idea 1 boundary checks; no private records or result fixtures."""
from datetime import date, timedelta
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weavve.final.idea1 import (
    basket_features, build_idea1_results, classify_codes, matched_cohort_evidence,
    outcome_summary, pilot_risk_set_evidence, product_index,
)
from weavve.final.recommendations import customer_purchase_history


def order(person, oid, when, amount=100, **changes):
    row = {"person_id": person, "order_id": oid, "order_date": when,
           "net": Decimal(str(amount)), "is_purchase": amount > 0,
           "is_special_account": False, "is_website": True, "channel_detail": "Own store"}
    row.update(changes)
    return row


def line(purchase, sku="SYNTHETIC-SHEET", **changes):
    row = {**purchase, "line_date": purchase["order_date"], "sku": sku,
           "Order or sales reversal": "order", "is_order_level": False,
           "Discount code": "", "Discount name": "", "discount_code_is_date": False}
    row.update(changes)
    return row


def product(sku="SYNTHETIC-SHEET", category="1. Bedsheets", kind="Set"):
    return {"clean_sku": sku, "Category": category, "Product Types": kind}


class Dataset:
    def __init__(self, orders, lines, products, subscribers=None, cutoff=date(2026, 1, 31)):
        self.manifest = {"dataset_id": "synthetic", "transaction_cutoff": cutoff.isoformat()}
        self.tables = {"orders": orders, "order_lines": lines, "products": products,
                       "subscribers": subscribers or []}

    def table(self, name):
        return self.tables[name]


class Idea1Tests(unittest.TestCase):
    def test_all_early_orders_retain_value_even_when_not_behavioural_returns(self):
        first = date(2024, 1, 1)
        offsets = [(0, 100), (0, 50), (2, 25), (7, 40), (8, 80), (364, 10), (365, 999)]
        rows = [order("p", f"o{i}", first + timedelta(days=age), amount)
                for i, (age, amount) in enumerate(offsets)]
        people = customer_purchase_history(rows, date(2025, 12, 31))
        result = outcome_summary(people, ["p"], date(2025, 12, 31), 365)
        self.assertEqual(result["mean_purchase_order_net"], 305)
        self.assertEqual(result["mean_first_order_net"], 100)
        self.assertEqual(result["mean_initial_episode_net"], 215)
        self.assertEqual(result["mean_additional_day0_to_episode_net"], 115)
        self.assertEqual(result["mean_post_episode_purchase_net"], 90)
        self.assertEqual(result["repeat_orders"], 2)
        self.assertEqual(result["episode_plus_repeat_identity_gap"], 0)

    def test_exclusive_horizon_maturity_includes_the_last_observed_day(self):
        cutoff, horizon = date(2024, 12, 31), 182
        boundary = cutoff - timedelta(days=horizon - 1)
        rows = [order("mature", "a", boundary), order("late", "b", boundary + timedelta(days=1)),
                order("mature", "c", cutoff, 30)]
        people = customer_purchase_history(rows, cutoff)
        result = outcome_summary(people, list(people), cutoff, horizon)
        self.assertEqual(result["people"], 1)
        self.assertEqual(result["immature_people"], 1)
        self.assertEqual(result["mean_purchase_order_net"], 130)

    def test_matched_entries_filter_late_entrants_from_both_years(self):
        cutoff, horizon = date(2024, 12, 31), 182
        boundary = cutoff - timedelta(days=horizon - 1)
        rows, features = [], {}
        for year in (2023, 2024):
            for offset, label in ((0, "early"), (1, "late")):
                person = f"{year}-{label}"
                rows.append(order(person, person, boundary.replace(year=year) + timedelta(days=offset)))
                features[person] = {"sheet_starter": True}
        people = customer_purchase_history(rows, cutoff)
        windows = [(date(2023, 1, 1), date(2023, 12, 31)), (date(2024, 1, 1), cutoff)]
        result = matched_cohort_evidence(people, windows, cutoff, features, set(people), horizon)
        self.assertEqual([row["all"]["people"] for row in result], [1, 1])
        self.assertEqual([row["all"]["immature_people"] for row in result], [0, 0])

    def test_refunds_follow_event_dates_in_the_signed_outcome(self):
        first, cutoff = date(2024, 1, 1), date(2025, 12, 31)
        people = customer_purchase_history([order("p", "a", first, 80)], cutoff)
        events = {"p": [(first, 120), (first + timedelta(days=20), -10),
                        (first + timedelta(days=365), -30)]}
        result = outcome_summary(people, ["p"], cutoff, 365, signed_events=events)
        self.assertEqual(result["mean_purchase_order_net"], 80)
        self.assertEqual(result["mean_signed_line_date_net"], 110)

    def test_unknown_products_and_order_level_rows_are_not_invented_categories(self):
        initial = order("p", "a", date(2024, 1, 1))
        products = product_index([product(), product("SYNTHETIC-BEDDING", "2. Bedding", "duvet")])
        result = basket_features([line(initial), line(initial, "MISSING-SKU"),
                                  line(initial, "SYNTHETIC-BEDDING", is_order_level=True)], products)
        self.assertTrue(result["sheet_starter"])
        self.assertFalse(result["sheets_plus_bedding"])
        self.assertEqual(result["unknown_product_lines"], 1)
        unknown = basket_features([line(initial, "MISSING-SKU")], products)
        self.assertEqual(unknown["entry_type"], "Product unknown")
        self.assertFalse(unknown["has_known_category"])

    def test_conflicting_sku_attributes_fail_instead_of_picking_a_product(self):
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            product_index([product(), product(category="2. Bedding")])

    def test_codes_use_exact_identifiers_and_never_campaign_names(self):
        initial = order("p", "a", date(2024, 1, 1))
        accepted = ["SYNTHETIC-WELCOME"]
        self.assertEqual(classify_codes([line(initial, **{"Discount code": " synthetic-welcome "})], accepted)["group"], "Exact welcome-code match")
        self.assertEqual(classify_codes([line(initial, **{"Discount code": "PREFIX-SYNTHETIC-WELCOME", "Discount name": "SYNTHETIC-WELCOME"})], accepted)["group"], "Other recorded code")
        self.assertEqual(classify_codes([line(initial, **{"Discount name": "SYNTHETIC-WELCOME"})], accepted)["group"], "No recorded code")
        unresolved = classify_codes([line(initial, **{"Discount code": "2024-01-01", "discount_code_is_date": True})], accepted)
        self.assertEqual(unresolved["group"], "Unresolved code")
        self.assertTrue(unresolved["has_unresolved_code"])
        self.assertEqual(classify_codes([], None)["group"], "Not evaluated: no exact welcome-code specification")
        with self.assertRaises(ValueError):
            classify_codes([], "SYNTHETIC-WELCOME")

    def test_canonical_website_flag_is_used_not_generic_own_store_label(self):
        cutoff = date(2026, 1, 31)
        rows = [order("draft", "d", date(2025, 1, 1), is_website=False),
                order("old-marketplace", "m", date(2024, 1, 1), is_website=False, channel_detail="Shopee"),
                order("old-marketplace", "w", date(2025, 1, 1)),
                order("special", "s", date(2025, 1, 1), is_special_account=True),
                order("new", "n", date(2025, 8, 1))]
        result = build_idea1_results(Dataset(rows, [line(o) for o in rows], [product()], cutoff=cutoff))
        self.assertEqual(result["annual_cohorts"][-1]["people"], 1)

    def test_profile_linkage_is_not_contemporaneous_or_marketing_eligibility(self):
        first = order("SYNTHETIC-PERSON", "SYNTHETIC-ORDER", date(2025, 8, 1))
        profile = {"clean_person_id": first["person_id"], "clean_profile_created_date": date(2025, 9, 1)}
        result = build_idea1_results(Dataset([first], [line(first)], [product()], [profile]))
        proxy = result["annual_cohorts"][-1]["profile_linked"]
        self.assertEqual(proxy["people"], 1)
        self.assertEqual(proxy["dated_profile_on_or_before_initial_date_people"], 0)
        self.assertFalse(proxy["is_verified_marketable_audience"])
        self.assertEqual(result["welcome_code_comparison"][-1]["status"], "not_evaluated")
        encoded = json.dumps(result, allow_nan=False)
        self.assertNotIn(first["person_id"], encoded)
        self.assertNotIn(first["order_id"], encoded)
        self.assertEqual(len({c["claim_id"] for c in result["claims"]}), len(result["claims"]))

    def test_unknown_second_basket_is_reported_outside_the_known_denominator(self):
        initial = order("p", "a", date(2023, 1, 1))
        repeat = order("p", "b", date(2023, 1, 10), 50)
        result = build_idea1_results(Dataset([initial, repeat], [line(initial), line(repeat, "UNKNOWN")], [product()]))
        basket = result["historical_two_year"]["second_basket"]
        self.assertEqual(basket["all_sheet_starter_returners"], 1)
        self.assertEqual(basket["category_known_returners"], 0)
        self.assertEqual(basket["category_unknown_returners"], 1)
        claims = {c["claim_id"]: c for c in result["claims"]}
        self.assertIsNone(claims["I1_RETURNERS_SHEETS_SHARE_2Y"]["value"])

    def test_same_day_cross_channel_tie_is_flagged_without_claiming_chronology(self):
        first = date(2025, 8, 1)
        rows = [order("p", "a", first), order("p", "b", first, is_website=False, channel_detail="Shopee")]
        result = build_idea1_results(Dataset(rows, [line(row) for row in rows], [product()]))
        self.assertEqual(result["same_initial_date_cross_channel_people"], 1)
        self.assertIn("not within-day chronology", result["definitions"]["first_order_ties"])

    def test_no_data_yields_null_rates_not_fabricated_zero_performance(self):
        result = build_idea1_results(Dataset([], [], []))
        self.assertIsNone(result["annual_cohorts"][-1]["profile_linked"]["sheet_starter_share_pct"])
        self.assertIsNone(result["matched_cohorts"][-1]["all"]["repeat_rate_pct"])
        json.dumps(result, allow_nan=False)

    def test_invalid_parameters_and_duplicate_orders_fail(self):
        with self.assertRaises(ValueError):
            build_idea1_results(Dataset([], [], []), horizon_days=7)
        initial = order("p", "a", date(2023, 1, 1))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            build_idea1_results(Dataset([initial, initial], [line(initial)], [product()]))

    def test_pilot_risk_set_uses_only_preassignment_purchases_for_eligibility(self):
        first, cutoff = date(2024, 1, 1), date(2024, 12, 31)
        rows = [order(p, p + "-first", first) for p in ("topup", "pre", "at", "none")]
        rows += [order("topup", "topup-extra", first + timedelta(days=7), 20),
                 order("pre", "pre-repeat", first + timedelta(days=59), 30),
                 order("at", "at-repeat", first + timedelta(days=60), 40)]
        people = customer_purchase_history(rows, cutoff)
        features = {p: {"sheet_starter": True} for p in people}
        profiles = {"topup": first + timedelta(days=60), "at": first + timedelta(days=61)}
        result = pilot_risk_set_evidence(people, [(first, cutoff)], cutoff, features, profiles)
        cohort = result["cohorts"][0]
        self.assertEqual(cohort["sheet_starter_candidates"], 4)
        self.assertEqual(cohort["excluded_previous_post_episode_purchase"], 1)
        self.assertEqual(cohort["all_risk_eligible"]["people"], 3)
        self.assertEqual(cohort["all_risk_eligible"]["buyers"], 1)
        self.assertEqual(cohort["profile_linked_by_assignment"]["people"], 1)
        self.assertEqual(cohort["profile_linked_by_assignment"]["buyers"], 0)

    def test_pilot_outcome_excludes_age150_and_applies_latest_season_cap_to_both_years(self):
        cutoff = date(2024, 12, 31)
        latest_boundary = cutoff - timedelta(days=149)
        windows = [(date(2023, 1, 1), date(2023, 12, 31)), (date(2024, 1, 1), cutoff)]
        rows, features = [], {}
        for year in (2023, 2024):
            first = latest_boundary.replace(year=year)
            person, late = f"p-{year}", f"late-{year}"
            rows += [order(person, person + "-first", first),
                     order(person, person + "-end", first + timedelta(days=149), 50),
                     order(late, late + "-first", first + timedelta(days=1))]
            if year == 2023:
                rows.append(order(person, person + "-excluded", first + timedelta(days=150), 900))
            features[person] = features[late] = {"sheet_starter": True}
        people = customer_purchase_history(rows, cutoff)
        result = pilot_risk_set_evidence(people, windows, cutoff, features, {})
        self.assertEqual([r["sheet_starter_candidates"] for r in result["cohorts"]], [1, 1])
        self.assertEqual([r["all_risk_eligible"]["mean_window_purchase_order_net"] for r in result["cohorts"]], [50, 50])


if __name__ == "__main__":
    unittest.main()
