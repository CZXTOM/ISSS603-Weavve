"""Synthetic checks of report scope, code recovery and incentive accounting."""
from datetime import date, timedelta
from decimal import Decimal
import unittest

from weavve.final.snooze_club import (
    popup_evidence, reward_and_cadence_evidence, top_decile_evidence,
    voucher_sensitivity,
)


def order(person, key, day, net=100, website=True):
    return {"person_id": person, "order_id": key, "order_date": day,
            "net": Decimal(net), "discount": Decimal(0), "is_website": website,
            "channel_detail": "Own store" if website else "Shopee"}


def line(key, code, reason=None):
    row = {"order_id": key, "Discount code": code, "discount_code_is_date": False,
           "Order or sales reversal": "order"}
    if reason:
        row["exclusion_reason"] = reason
    return row


class SnoozeClubTests(unittest.TestCase):
    def test_recovered_metadata_changes_route_without_adding_sales(self):
        orders = [order("a", "one", date(2024, 9, 1))]
        kept = [line("one", "")]
        excluded = [line("one", "AL-EXAMPLE", "repeated_discount_line"),
                    line("one", "LWC-EXAMPLE", "cancelled")]
        result = popup_evidence(orders, kept, excluded)
        primary = result["recovered_annotations"]["after_popup"]
        sensitivity = result["kept_lines_only"]["after_popup"]
        self.assertEqual(primary["newcomers"], 1)
        self.assertEqual(primary["all_newcomer_first_order_net_sales_sgd"], 100)
        self.assertEqual(primary["groups"]["popup"]["people"], 1)
        self.assertEqual(primary["groups"]["club"]["people"], 0)
        self.assertEqual(sensitivity["groups"]["popup"]["people"], 0)

    def test_earlier_shopee_purchase_excludes_website_newcomer(self):
        orders = [order("a", "web", date(2024, 9, 2)),
                  order("a", "shop", date(2024, 9, 1), website=False)]
        result = popup_evidence(orders, [], [])
        self.assertEqual(result["recovered_annotations"]["after_popup"]["newcomers"], 0)

    def test_club_precedence_and_unreadable_date_codes(self):
        orders = [order("a", "one", date(2024, 9, 1)),
                  order("b", "two", date(2024, 9, 2))]
        unreadable = line("two", "AL-EXAMPLE")
        unreadable["discount_code_is_date"] = True
        result = popup_evidence(orders, [line("one", "AL-EXAMPLE"),
                                       line("one", "LWC-EXAMPLE"), unreadable], [])
        groups = result["recovered_annotations"]["after_popup"]["groups"]
        self.assertEqual(groups["club"]["people"], 1)
        self.assertEqual(groups["popup"]["people"], 0)
        self.assertEqual(groups["no_recorded_discount_or_code"]["people"], 1)

    def test_partial_followup_does_not_become_a_full_year(self):
        rows = [order(str(i), f"base-{i}", date(2024, 10, 1), 200 - i) for i in range(11)]
        rows += [order("0", "return", date(2026, 8, 28)),
                 order("1", "outside", date(2026, 8, 31))]
        result = top_decile_evidence(rows, date(2024, 9, 1), date(2025, 8, 31), date(2026, 8, 28))
        self.assertEqual(result["groups"]["top_decile"]["people"], 2)
        self.assertEqual(result["groups"]["top_decile"]["next_year_website_returners"], 1)
        self.assertFalse(result["full_next_calendar_year_observed"])

    def test_purchase_occasions_use_start_date_instead_of_chaining(self):
        start = date(2025, 9, 1)
        rows = [order("a", str(i), start + timedelta(days=gap)) for i, gap in enumerate((0, 7, 14))]
        result = reward_and_cadence_evidence(rows, [line("0", "LWC-EXAMPLE")], [])
        top = result["all_website_history_of_latest_active_members"]["top10"]
        self.assertEqual(top["median_personal_median_gap"], 14)
        self.assertEqual(top["repeaters"], 1)

    def test_zero_lift_pays_all_vouchers_and_cap_limits_cost(self):
        result = voucher_sensitivity(redemptions=10, basket=100, discount_rate=.5,
                                     cap=12, setup=30, margins=(.6,), additional_orders=(0, 3))[0]
        self.assertEqual(result["net_gain_by_additional_orders"]["0"], -150)
        self.assertEqual(result["net_gain_by_additional_orders"]["3"], 30)
        self.assertEqual(result["break_even_additional_orders"], 3)

    def test_impossible_incremental_orders_are_rejected(self):
        with self.assertRaises(ValueError):
            voucher_sensitivity(redemptions=2, basket=100, discount_rate=.1,
                                cap=20, setup=0, additional_orders=(3,))


if __name__ == "__main__":
    unittest.main()
