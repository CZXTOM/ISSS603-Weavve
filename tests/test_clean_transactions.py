"""Synthetic business-rule tests. No private source data or report values."""

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weavve.clean_transactions import clean_transactions


def line(order="o1", customer="c1", item="l1", **changes):
    row = {
        "Order ID": order, "Customer ID": customer, "Line item ID": item,
        "Order or sales reversal": "order", "Is canceled order": False,
        "Day": datetime(2025, 8, 1), "Order sales channel": "Online Store",
        "Product variant SKU at time of sale": "sku1", "Quantity ordered": 1,
        "Net sales": 100, "Total sales": 109, "Discounts": -10, "Orders": 1,
        "Refund ID": None, "Discount name": "offer-a", "Discount code": "A",
        "Unrelated raw column": "preserve me",
    }
    row.update(changes)
    return row


def run(rows, *, people=None, channels=None, products=None, clearance=None, **options):
    if people is None:
        people = [{"Customer ID": c, "person_id": "person-" + str(c)} for c in sorted({r["Customer ID"] for r in rows})]
    if channels is None:
        channels = [{"Order ID": o, "channel_detail": "Own store"} for o in sorted({r["Order ID"] for r in rows})]
    products = [{"Code": "sku1"}] if products is None else products
    return clean_transactions(rows, people, channels, products, clearance or [], **options)


class CleanTransactionsTests(unittest.TestCase):
    def test_stacked_discount_removed_but_signed_refund_kept(self):
        sale = line()
        stacked = line(**{"Discount name": "offer-b", "Discount code": "B"})
        refund = line(**{
            "Order or sales reversal": "reversal", "Day": date(2025, 9, 2),
            "Quantity ordered": -1, "Net sales": -25, "Total sales": -27.25,
            "Discounts": 2.5, "Orders": 0, "Refund ID": "refund-1",
        })
        source = [sale, stacked, refund]
        before = deepcopy(source)
        result = run(source)
        self.assertEqual(source, before)
        self.assertEqual(result["checks"]["repeated_discount_rows"], 1)
        order = result["tables"]["orders"][0]
        self.assertEqual(order["net"], Decimal("75"))
        self.assertEqual(order["discount"], Decimal("7.5"))
        self.assertEqual(order["order_date"], date(2025, 8, 1))
        refund_line = result["tables"]["order_lines"][1]
        self.assertEqual(refund_line["line_date"], date(2025, 9, 2))
        self.assertEqual(refund_line["order_date"], order["order_date"])
        self.assertEqual(refund_line["Unrelated raw column"], "preserve me")
        excluded = result["tables"]["excluded_order_lines"][0]
        self.assertEqual(excluded["exclusion_reason"], "repeated_discount_line")
        self.assertEqual(excluded["duplicate_of_source_row"], 2)
        self.assertEqual(excluded["source_row"], 3)
        self.assertTrue(result["checks"]["rows_reconcile"])
        self.assertTrue(result["checks"]["raw_net_reconciles"])

    def test_cancellation_removes_whole_order_before_duplicate_rule(self):
        result = run([line(), line(**{"Is canceled order": "True", "Discount name": "other"})])
        self.assertEqual(result["tables"]["orders"], [])
        self.assertEqual(result["tables"]["order_lines"], [])
        self.assertEqual(result["checks"]["cancelled_rows"], 2)
        self.assertEqual(result["checks"]["cancelled_orders"], 1)
        self.assertEqual(result["checks"]["repeated_discount_rows"], 0)
        self.assertTrue(all(x["exclusion_reason"] == "cancelled_order" for x in result["tables"]["excluded_order_lines"]))

    def test_tax_rule_uses_line_date_and_preserves_january_exception(self):
        market = "Easy Shopee, TikTok & Lazada"
        rows = [
            line("o1", **{"Order sales channel": market, "Day": date(2025, 8, 25), "Net sales": 109, "Total sales": 109}),
            line("o2", **{"Order sales channel": market, "Day": date(2025, 8, 26), "Net sales": 109, "Total sales": 109, "Discounts": -10.9}),
            line("o3", **{"Order sales channel": market, "Day": date(2026, 1, 10), "Net sales": 100, "Total sales": 109}),
            line("o4", **{"Day": date(2026, 2, 1), "Net sales": 109, "Total sales": 109}),
        ]
        result = run(rows)
        byid = {r["order_id"]: r for r in result["tables"]["order_lines"]}
        self.assertEqual([byid[o]["gst_adjusted"] for o in ["o1", "o2", "o3", "o4"]], [False, True, False, False])
        self.assertEqual(byid["o2"]["net"], Decimal("100"))
        self.assertEqual(byid["o2"]["discount"], Decimal("10"))
        self.assertEqual(byid["o2"]["Net sales"], 109)
        self.assertEqual(byid["o2"]["Discounts"], -10.9)

    def test_later_refund_gst_and_zero_purchase(self):
        market = "Easy Shopee, TikTok & Lazada"
        rows = [line(**{"Order sales channel": market}), line(**{
            "Order sales channel": market, "Day": date(2026, 1, 20),
            "Order or sales reversal": "reversal", "Net sales": -109, "Total sales": -109,
            "Discounts": 10.9, "Quantity ordered": -1, "Orders": 0, "Refund ID": "r1",
        })]
        result = run(rows)
        order = result["tables"]["orders"][0]
        self.assertEqual(order["net_raw"], Decimal("-9"))
        self.assertEqual(order["net"], Decimal("0"))
        self.assertFalse(order["is_purchase"])
        self.assertFalse(order["customer_analysis_eligible"])
        self.assertTrue(result["tables"]["order_lines"][1]["gst_adjusted"])
        self.assertEqual(order["order_date"], date(2025, 8, 1))

    def test_identical_annotations_and_zero_line_ids_are_not_silently_removed(self):
        rows = [line(), line(), line(item=0), line(item=0, **{"Discount name": "different"})]
        result = run(rows)
        self.assertEqual(result["checks"]["clean_rows"], 4)
        self.assertEqual(result["checks"]["repeated_discount_rows"], 0)
        self.assertEqual(result["checks"]["same_annotation_candidates_retained"], 1)
        self.assertEqual(result["checks"]["order_level_rows"], 2)
        self.assertTrue(result["warnings"])

    def test_separate_refunds_with_different_refund_ids_survive(self):
        refund = {"Order or sales reversal": "reversal", "Net sales": -10, "Total sales": -10.9, "Orders": 0}
        result = run([line(), line(**refund, **{"Refund ID": "r1"}), line(**refund, **{"Refund ID": "r2", "Discount name": "other"})])
        self.assertEqual(result["checks"]["refund_rows"], 2)
        self.assertEqual(result["tables"]["orders"][0]["net"], Decimal("80"))

    def test_same_discount_name_with_different_code_is_stacked_annotation(self):
        result = run([line(), line(**{"Discount code": "B"})])
        self.assertEqual(result["checks"]["repeated_discount_rows"], 1)
        self.assertEqual(result["tables"]["orders"][0]["net"], Decimal("100"))

    def test_excel_date_code_is_flagged_without_reconstruction(self):
        code = datetime(2025, 4, 3)
        result = run([line("date", **{"Discount code": code}), line("text", **{"Discount code": "2025-04-03"})])
        records = {r["order_id"]: r for r in result["tables"]["order_lines"]}
        self.assertTrue(records["date"]["discount_code_is_date"])
        self.assertEqual(records["date"]["Discount code"], code)
        self.assertFalse(records["text"]["discount_code_is_date"])
        self.assertEqual(records["text"]["Discount code"], "2025-04-03")

    def test_unknown_product_and_time_aware_clearance_are_retained(self):
        rules = [{"SKU Code": "sku1", "Remarks (estimated)": "On clearance since Q3 2025"}]
        rows = [line("before", **{"Day": date(2025, 6, 30)}), line("within"), line("after", **{"Day": date(2025, 10, 1)}), line("unknown", **{"Product variant SKU at time of sale": "missing"})]
        result = run(rows, clearance=rules)
        byid = {r["order_id"]: r for r in result["tables"]["order_lines"]}
        self.assertEqual([byid[o]["clearance_timing"] for o in ["before", "within", "after"]], ["before", "within", "after"])
        self.assertFalse(byid["unknown"]["product_match"])
        self.assertFalse(byid["unknown"]["clearance_sku"])
        self.assertEqual(len(result["tables"]["orders"]), 4)

    def test_discontinued_and_unparseable_dates_are_explicit(self):
        result = run([line()], clearance=[{"SKU Code": "sku1", "Remarks (estimated)": "Discontinued since Q4 2024"}])
        self.assertEqual(result["tables"]["order_lines"][0]["clearance_status"], "discontinued")
        result = run([line()], clearance=[{"SKU Code": "sku1", "Remarks (estimated)": "date not supplied"}])
        self.assertEqual(result["tables"]["order_lines"][0]["clearance_timing"], "unknown")
        self.assertTrue(result["warnings"])

    def test_customer_population_flags(self):
        rows = [line("web"), line("shop", "c2", **{"Order sales channel": "Easy Shopee, TikTok & Lazada"}), line("lazada", "c3", **{"Order sales channel": "Easy Shopee, TikTok & Lazada"}), line("special", "c4"), line("pos", "c5", **{"Order sales channel": "POS"})]
        channels = [{"Order ID": o, "channel_detail": c} for o, c in [("web", "Own store"), ("shop", "Shopee"), ("lazada", "Lazada"), ("special", "Own store"), ("pos", "Own store")]]
        result = run(rows, channels=channels, special_person_ids=["person-c4"])
        orders = {r["order_id"]: r for r in result["tables"]["orders"]}
        self.assertTrue(orders["web"]["customer_analysis_eligible"])
        self.assertTrue(orders["shop"]["customer_analysis_eligible"])
        self.assertFalse(orders["lazada"]["customer_analysis_eligible"])
        self.assertFalse(orders["special"]["customer_analysis_eligible"])
        self.assertFalse(orders["pos"]["is_website"])
        self.assertFalse(orders["pos"]["customer_analysis_eligible"])

    def test_strict_mapping_coverage_and_uniqueness(self):
        with self.assertRaisesRegex(ValueError, "missing from person map"):
            run([line()], people=[])
        with self.assertRaisesRegex(ValueError, "missing from channel map"):
            run([line()], channels=[])
        with self.assertRaisesRegex(ValueError, "Duplicate person map"):
            run([line()], people=[{"Customer ID": "c1", "person_id": "p1"}] * 2)
        with self.assertRaisesRegex(ValueError, "Duplicate channel map"):
            run([line()], channels=[{"Order ID": "o1", "channel_detail": "Own store"}] * 2)
        with self.assertRaisesRegex(ValueError, "Duplicate product master"):
            run([line()], products=[{"Code": "sku1"}] * 2)
        with self.assertRaisesRegex(ValueError, "Ambiguous Customer ID"):
            run([line(), line(customer="c2")], people=[{"Customer ID": c, "person_id": "same-person"} for c in ["c1", "c2"]])

    def test_mapping_errors_on_cancelled_orders_are_not_hidden(self):
        with self.assertRaisesRegex(ValueError, "missing from person map"):
            run([line(**{"Is canceled order": True})], people=[])

    def test_excel_row_metadata_determines_duplicate_origin(self):
        first = line(source_row=4)
        second = line(source_row=9, **{"Discount name": "other"})
        a, b = run([second, first]), run([first, second])
        self.assertEqual(a, b)
        self.assertEqual(a["tables"]["excluded_order_lines"][0]["duplicate_of_source_row"], 4)
        with self.assertRaisesRegex(ValueError, "source_row"):
            run([first, first])

    def test_malformed_values_are_not_coerced_to_zero(self):
        for key, value in [("Net sales", None), ("Discounts", "bad"), ("Day", "bad"), ("Is canceled order", "unknown")]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                run([line(**{key: value})])
        with self.assertRaisesRegex(ValueError, "collide"):
            run([line(net=1)])

    def test_refund_only_order_keeps_value_and_warns_on_date(self):
        result = run([line(**{"Order or sales reversal": "reversal", "Net sales": -10, "Total sales": -10.9, "Refund ID": "r1"})])
        self.assertEqual(result["tables"]["orders"][0]["net"], Decimal("-10"))
        self.assertFalse(result["tables"]["orders"][0]["is_purchase"])
        self.assertEqual(result["checks"]["orders_without_sale_line"], 1)
        self.assertTrue(result["warnings"])

    def test_empty_input_is_valid(self):
        result = clean_transactions([], [], [], [], [])
        self.assertTrue(result["checks"]["rows_reconcile"])
        self.assertTrue(result["checks"]["raw_net_reconciles"])
        self.assertEqual(result["tables"]["orders"], [])


if __name__ == "__main__":
    unittest.main()
