"""Synthetic source fixtures: no private source rows or report targets are embedded."""
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
from io import BytesIO
import unittest

import openpyxl

from weavve.clean_search import _gsc, _metric_column, build_search_tables
from weavve.clean_support import build_support_tables


@dataclass
class MemoryFile:
    name: str
    data: bytes

    @property
    def relative_path(self):
        return self.name

    @property
    def sha256(self):
        return sha256(self.data).hexdigest()

    def read_bytes(self):
        return self.data


class MemoryCatalog:
    def __init__(self, groups):
        self.groups = groups

    def files(self, code):
        return self.groups.get(code, [])


def book(name, sheets):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        for row in rows:
            ws.append(row)
    data = BytesIO()
    wb.save(data)
    wb.close()
    return MemoryFile(name, data.getvalue())


def gsc(name, periods, primary, *, country="Singapore", query_value=3, extra_filters=None):
    filters = [["Filter", "Value"], ["Search type", "Web"], ["Date", primary]]
    if country is not None:
        filters.append(["Country", country])
    if extra_filters:
        filters += extra_filters
    head = ["Country"] + [f"{p} Clicks" for p in periods] + [f"{p} Impressions" for p in periods]
    queries = ["Top queries"] + [f"{p} Clicks" for p in periods] + [f"{p} Impressions" for p in periods]
    return book(name, {"Filters": filters, "Countries": [head, ["Singapore"] + [10]*len(periods) + [100]*len(periods)],
                       "Queries": [queries, ["synthetic query"] + [query_value]*len(periods) + [20]*len(periods)]})


class GscSelectionTests(unittest.TestCase):
    def test_named_month_year_headers_map_without_position_assumptions(self):
        periods = [(date(2025, 4, 1), date(2025, 4, 30)), (date(2025, 5, 1), date(2025, 5, 31))]
        headers = ["Top queries", "May 2025 Clicks", "Apr 2025 Clicks"]
        self.assertEqual(_metric_column(headers, periods[0], "clicks", periods), 2)
        self.assertEqual(_metric_column(headers, periods[1], "clicks", periods), 1)

    def test_prefers_primary_not_filename_order(self):
        january = "1/1/25 - 1/31/25"
        february = "2/1/25 - 2/28/25"
        primary = gsc("z_primary.xlsx", [january], "Jan 1, 2025-Jan 31, 2025", query_value=4)
        secondary = gsc("a_later.xlsx", [february, january], "Feb 1, 2025-Feb 28, 2025", query_value=7)
        tables, _ = _gsc(MemoryCatalog({"A": [secondary, primary]}), date(2025, 3, 1))
        jan = next(r for r in tables["gsc_months"] if r["month"] == date(2025, 1, 1))
        self.assertEqual(jan["source_file"], "z_primary.xlsx")
        self.assertEqual(jan["query_clicks_sum"], 4)

    def test_partial_primary_uses_full_previous_month(self):
        partial = gsc("partial.xlsx", ["6/1/25 - 6/29/25"], "Jun 1, 2025-Jun 29, 2025")
        later = gsc("later.xlsx", ["7/1/25 - 7/31/25", "6/1/25 - 6/30/25"], "Jul 1, 2025-Jul 31, 2025")
        tables, _ = _gsc(MemoryCatalog({"A": [partial, later]}), date(2025, 8, 1))
        june = next(r for r in tables["gsc_months"] if r["month"] == date(2025, 6, 1))
        self.assertEqual(june["reason"], "selected_previous_month_fallback")
        self.assertTrue(any("not_full_calendar_month" in r["reason"] for r in tables["gsc_month_candidates"]))

    def test_scope_date_and_comparison_errors_stay_visible(self):
        no_country = gsc("no_country.xlsx", ["1/1/25 - 1/31/25"], "Jan 1, 2025-Jan 31, 2025", country=None)
        future = gsc("future.xlsx", ["2/1/25 - 2/28/25", "1/1/25 - 1/31/25"], "Jan 1, 2025-Jan 31, 2025")
        wrong_year = gsc("wrong_year.xlsx", ["4/1/25 - 4/30/25", "3/1/24 - 3/31/24"], "Apr 1, 2025-Apr 30, 2025")
        mismatch = gsc("mismatch.xlsx", ["5/1/25 - 5/31/25"], "Jun 1, 2025-Jun 30, 2025")
        tables, _ = _gsc(MemoryCatalog({"A": [no_country, future, wrong_year, mismatch]}), date(2025, 8, 1))
        self.assertNotIn(date(2025, 2, 1), {r["month"] for r in tables["gsc_months"]})
        self.assertNotIn(date(2024, 3, 1), {r["month"] for r in tables["gsc_months"]})
        reasons = [r["reason"] for r in tables["gsc_month_candidates"]]
        self.assertTrue(any("missing_explicit_singapore_filter" in r for r in reasons))
        self.assertTrue(any("filter_date_not_matched_to_header" in r for r in reasons))
        self.assertGreater(len(tables["gsc_raw_rows"]), 0)

    def test_later_pasted_filter_does_not_overwrite_canonical_block(self):
        source = gsc("pasted.xlsx", ["6/1/25 - 6/30/25"], "Jun 1, 2025-Jun 30, 2025",
                     extra_filters=[[], ["Filter", "Value"], ["Date", "Mar 1, 2024-Mar 31, 2024"]])
        tables, warnings = _gsc(MemoryCatalog({"A": [source]}), date(2025, 7, 1))
        self.assertEqual(len(tables["gsc_months"]), 1)
        self.assertTrue(tables["gsc_months"][0]["has_extra_filter_block"])
        self.assertTrue(any("extra Filters" in w for w in warnings))

    def test_missing_query_metric_remains_unknown(self):
        source = gsc("missing_value.xlsx", ["1/1/25 - 1/31/25"], "Jan 1, 2025-Jan 31, 2025", query_value=None)
        tables, _ = _gsc(MemoryCatalog({"A": [source]}), date(2025, 2, 1))
        self.assertIsNone(tables["gsc_queries"][0]["clicks"])
        self.assertIsNone(tables["gsc_months"][0]["query_clicks_sum"])

    def test_partial_query_metrics_keep_observed_sum_and_unknown_reasons_separate(self):
        jan, dec = "1/1/25 - 1/31/25", "12/1/24 - 12/31/24"
        source = book("mixed.xlsx", {
            "Filters": [["Filter", "Value"], ["Search type", "Web"], ["Date", "Jan 1, 2025-Jan 31, 2025"], ["Country", "Singapore"]],
            "Countries": [["Country", f"{jan} Clicks", f"{dec} Clicks"], ["Singapore", 10, 20]],
            "Queries": [["Top queries", f"{jan} Clicks", f"{dec} Clicks"],
                        ["observed example", 5, 3], ["comparison example", None, 2],
                        ["no metric example", None, None], ["invalid example", "unknown", 1]],
        })
        tables, _ = _gsc(MemoryCatalog({"A": [source]}), date(2025, 2, 1))
        month = next(r for r in tables["gsc_months"] if r["month"] == date(2025, 1, 1))
        self.assertEqual(month["query_rows"], 4)
        self.assertEqual(month["observed_query_rows"], 1)
        self.assertEqual(month["missing_query_rows"], 3)
        self.assertEqual(month["observed_query_clicks_sum"], 5)
        self.assertEqual(month["observed_query_click_coverage"], .5)
        self.assertEqual(month["query_rows_without_any_period_metrics"], 1)
        self.assertEqual(month["unparseable_query_click_rows"], 1)
        self.assertIsNone(month["query_clicks_sum"])
        rows = {r["query"]: r for r in tables["gsc_queries"] if r["month"] == date(2025, 1, 1)}
        self.assertEqual(rows["comparison example"]["query_clicks_status"], "missing_blank")
        self.assertTrue(rows["comparison example"]["has_any_period_numeric_metric"])
        self.assertFalse(rows["no metric example"]["has_any_period_numeric_metric"])
        self.assertEqual(rows["invalid example"]["query_clicks_status"], "unparseable")

    def test_conflicting_filters_within_canonical_block_are_rejected(self):
        source = gsc("conflicting_filters.xlsx", ["1/1/25 - 1/31/25"], "Jan 1, 2025-Jan 31, 2025",
                     extra_filters=[["Country", "Elsewhere"]])
        tables, _ = _gsc(MemoryCatalog({"A": [source]}), date(2025, 2, 1))
        self.assertEqual(tables["gsc_months"], [])
        self.assertIn("ambiguous_or_unrecognized_filter_scope", tables["gsc_month_candidates"][0]["reason"])

    def test_conflicting_equal_priority_exports_are_not_arbitrarily_chosen(self):
        a = gsc("a.xlsx", ["1/1/25 - 1/31/25"], "Jan 1, 2025-Jan 31, 2025", query_value=2)
        b = gsc("b.xlsx", ["1/1/25 - 1/31/25"], "Jan 1, 2025-Jan 31, 2025", query_value=5)
        tables, warnings = _gsc(MemoryCatalog({"A": [a, b]}), date(2025, 2, 1))
        self.assertEqual(tables["gsc_months"], [])
        self.assertTrue(any("conflicting" in w for w in warnings))

    def test_identical_named_copies_do_not_duplicate_selected_queries(self):
        a = gsc("a.xlsx", ["1/1/25 - 1/31/25"], "Jan 1, 2025-Jan 31, 2025")
        b = MemoryFile("b.xlsx", a.data)
        tables, _ = _gsc(MemoryCatalog({"A": [a, b]}), date(2025, 2, 1))
        self.assertEqual(len(tables["gsc_months"]), 1)
        self.assertEqual(len(tables["gsc_queries"]), 1)


class OtherSourceTests(unittest.TestCase):
    def test_red_flag_uses_keyword_fill_and_source_legend_when_text_disagrees(self):
        from openpyxl.styles import PatternFill
        source = book("12.synthetic.xlsx", {
            "Search keyword report All time ": [["Keyword", "Match type", "Impr.", "Clicks"], ["[sample sheets]", "Exact match", 4, 1]],
            "Negative Keyword report ": [["Negative keyword"], ["[unwanted]"], ["+unwanted"]],
            "Filtered": [["Keyword", "KW List tier colour"], ["[sample sheets]", "A different tier"]],
            "Categories": [[None, "Do not retarget for Google Ads"]],
        })
        wb = openpyxl.load_workbook(BytesIO(source.data))
        # The unusual color proves that the code reads the legend, not a hardcoded red RGB.
        fill = PatternFill("solid", fgColor="FF123456")
        wb["Categories"]["B1"].fill = fill
        wb["Filtered"]["A2"].fill = fill
        output = BytesIO()
        wb.save(output)
        wb.close()
        source.data = output.getvalue()
        result = build_search_tables(MemoryCatalog({"A": [], "B": [], "12": [source]}), date(2025, 3, 1))
        self.assertTrue(result["tables"]["ads_keywords"][0]["historical_red_list_flag"])
        tier = result["tables"]["ads_keyword_tiers"][0]
        self.assertTrue(tier["historical_tier_label_conflict"])
        self.assertEqual(tier["historical_red_list_evidence"], "keyword_cell_fill_matches_source_legend")
        self.assertEqual({r["clean_keyword"] for r in result["tables"]["ads_negatives"]}, {"unwanted", "+unwanted"})

    def test_semrush_dates_and_red_list_remain_separate(self):
        ads = book("12.synthetic.xlsx", {
            "Search keyword report All time ": [["Keyword", "Match type", "Impr.", "Clicks"], ["[sample sheets]", "Exact match", 4, 1]],
            "Negative Keyword report ": [["Negative keyword"], ["[unwanted]"]],
            "Filtered": [["Keyword", "KW List tier colour"], ["[sample sheets]", "Do not retarget for Google Ads"]],
            "Categories": [[None, "Do not retarget for Google Ads"]],
        })
        csv_file = MemoryFile("Organic KWs - Feb 2025.csv", b"Keyword,Timestamp,Position,Search Volume,Position Type\nexample,2025-01-15,1,10,AI overview\n")
        result = build_search_tables(MemoryCatalog({"A": [], "B": [csv_file], "12": [ads]}), date(2025, 3, 1))
        row = result["tables"]["semrush_keywords"][0]
        self.assertTrue(row["is_stale_observation"])
        self.assertEqual(row["visibility_class"], "serp_feature")
        self.assertEqual(row["Position"], "1")
        self.assertTrue(result["tables"]["ads_keywords"][0]["historical_red_list_flag"])

    def test_support_preserves_snapshots_and_full_month_boundaries(self):
        groups = {
            "G": [book("G.xlsx", {"Person map": [["Customer ID", "person_id"], ["c1", "p1"]], "Order channel": [["Order ID", "channel_detail"], ["o1", "Shopee"]]})],
            "D": [book("D.xlsx", {"Products": [["Code"], ["sku1"]]})],
            "I": [book("I.xlsx", {"Clearance SKUs": [["SKU Code"], ["sku2"]]})],
            "E": [book("E.xlsx", {"Full Discounts Report": [["Name", "Times Used In Total"], ["CODE", 0]], "FirstWelcome Order Discount by ": [["Group"], ["synthetic"]]})],
            "F": [book("F.xlsx", {"Redemptions": [["date", "times_used", "order_id"], [datetime(2025, 1, 1), 0, None]]})],
            "J": [book("J.xlsx", {"Subscribers": [["person_id", "Profile Created On", "Initial Source"], ["p1", datetime(2025, 2, 10), "google"]]})],
            "K": [book("K.xlsx", {"Campaigns": [["Send Date", "Total Recipients", "Unique Clicks", "Unique Opens", "Click Rate"], [datetime(2025, 2, 20), 20, 2, 6, .2]]})],
            "L": [book("L.xlsx", {"Funnel": [["Conversion Funnel", "Singapore Only"], [], [None, "Source", datetime(2025, 1, 1), datetime(2025, 2, 1)], ["Sessions", "Shopify", 100, 100], ["Orders Placed", "Shopify", 2, 3]]})],
        }
        result = build_support_tables(MemoryCatalog(groups), date(2025, 2, 15))
        tables = result["tables"]
        self.assertEqual([r["in_transaction_complete_month_window"] for r in tables["website_funnel"]], [True, False])
        self.assertFalse(tables["email_campaigns"][0]["in_transaction_window"])
        self.assertEqual(tables["email_campaigns"][0]["clean_unique_click_rate"], .1)
        self.assertEqual(tables["email_campaigns"][0]["Click Rate"], .2)
        self.assertEqual(tables["loyalty_rewards"][0]["clean_reward_usage_status"], "issued_unused")
        self.assertEqual(tables["subscribers"][0]["clean_initial_source_label"], "google")
        self.assertNotIn("paid", tables["subscribers"][0])


if __name__ == "__main__":
    unittest.main()
