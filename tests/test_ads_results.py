"""Synthetic ads arithmetic and evidence-boundary checks."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weavve.final.ads_results import build_ads_results


def fixture():
    daily = [{"date": f"2030-02-0{day}", "impressions": impressions,
              "clicks": clicks, "cost": cost}
             for day, impressions, clicks, cost in [(1, 10, 2, 1), (2, 90, 3, 2),
                                                   (3, 20, 4, 3), (4, 80, 1, 4)]]
    return {"range": ["2030-02-01", "2030-02-04"], "account_tz": "Synthetic/Zone",
            "campaign": {"id": "DO-NOT-COPY", "name": "DO-NOT-COPY", "impressions": 200,
                         "clicks": 10, "cost": 10, "lost_rank": 25},
            "daily": daily,
            "ad_groups": [{"name": "DO-NOT-COPY", "impressions": 200, "clicks": 10, "cost": 10}],
            "keywords": [
                {"text": "SYNTHETIC-QUERY", "match": "EXACT", "qs": 3, "landing": "BELOW_AVERAGE", "impressions": 100, "clicks": 8, "cost": 6},
                {"text": "synthetic-query", "match": "PHRASE", "qs": 7, "landing": "AVERAGE", "impressions": 50, "clicks": 2, "cost": 2},
                {"text": "OTHER-SYNTHETIC", "match": "EXACT", "qs": None, "landing": None, "impressions": 50, "clicks": 0, "cost": 2},
            ], "errors": []}


class AdsResultsTests(unittest.TestCase):
    def test_weighted_ctr_reconciles_and_raw_labels_are_not_returned(self):
        result = build_ads_results(fixture())
        self.assertEqual(result["campaign_totals"]["ctr_pct"], 5)
        self.assertEqual(result["daily_totals"]["ctr_pct"], 5)
        self.assertTrue(all(result["reconciliation"]["daily_vs_campaign"].values()))
        self.assertNotIn("DO-NOT-COPY", json.dumps(result))
        self.assertNotIn("SYNTHETIC-QUERY", json.dumps(result))

    def test_diagnostics_count_criteria_not_destination_pages(self):
        result = build_ads_results(fixture())
        diagnostic = result["keyword_diagnostics"]
        self.assertEqual(diagnostic["criterion_count"], 3)
        self.assertEqual(diagnostic["distinct_keyword_text_count"], 2)
        self.assertEqual(diagnostic["scored_criterion_count"], 2)
        self.assertEqual(diagnostic["unscored_criterion_count"], 1)
        self.assertEqual(diagnostic["landing_below_average_count"], 1)
        self.assertIn("not distinct destination", diagnostic["unit"])

    def test_phase_boundaries_include_change_date_in_previous_phase(self):
        log = [{"date": "2030-02-02", "id": "private"}, {"date": "2030-02-02"},
               {"date": "2030-02-03"}]
        result = build_ads_results(fixture(), log)
        self.assertEqual([(p["start_inclusive"], p["end_inclusive"]) for p in result["phases"]],
                         [("2030-02-01", "2030-02-02"), ("2030-02-03", "2030-02-03"),
                          ("2030-02-04", "2030-02-04")])
        self.assertEqual([p["calendar_days"] for p in result["phases"]], [2, 1, 1])
        self.assertEqual(result["phases"][0]["clicks_per_day"], 2.5)
        self.assertFalse(result["change_log_coverage"]["supplied_log_completeness_verified"])

    def test_missing_day_prevents_phase_comparison(self):
        data = fixture()
        data["daily"].pop(1)
        result = build_ads_results(data, [{"date": "2030-02-02"}])
        self.assertEqual(result["coverage"]["missing_dates"], ["2030-02-02"])
        self.assertEqual(result["phases"], [])
        self.assertFalse(result["reconciliation"]["daily_vs_campaign"]["impressions"])

    def test_zero_impressions_has_undefined_ctr(self):
        data = {"range": ["2030-01-01", "2030-01-01"],
                "campaign": {"impressions": 0, "clicks": 0, "cost": 0},
                "daily": [{"date": "2030-01-01", "impressions": 0, "clicks": 0, "cost": 0}]}
        result = build_ads_results(data, [])
        self.assertIsNone(result["campaign_totals"]["ctr_pct"])
        self.assertIsNone(result["phases"][0]["ctr_pct"])
        self.assertFalse(result["keyword_diagnostics"]["available"])

    def test_missing_metric_is_unknown_not_zero(self):
        data = fixture()
        del data["daily"][0]["clicks"]
        result = build_ads_results(data)
        self.assertIsNone(result["daily_totals"]["clicks"])
        self.assertIsNone(result["daily_totals"]["ctr_pct"])
        self.assertEqual(result["daily_totals"]["missing_metric_counts"]["clicks"], 1)

    def test_duplicate_or_outside_dates_and_invalid_metrics_fail(self):
        for mutation in ("duplicate", "outside", "negative", "nan"):
            with self.subTest(mutation=mutation):
                data = fixture()
                if mutation == "duplicate": data["daily"][1]["date"] = data["daily"][0]["date"]
                elif mutation == "outside": data["daily"][0]["date"] = "2029-01-01"
                elif mutation == "negative": data["daily"][0]["cost"] = -1
                else: data["daily"][0]["cost"] = float("nan")
                with self.assertRaises(ValueError):
                    build_ads_results(data)

    def test_missing_landing_rating_has_visible_coverage(self):
        data = fixture()
        data["keywords"][0]["landing"] = None
        diagnostic = build_ads_results(data)["keyword_diagnostics"]
        self.assertEqual(diagnostic["landing_missing_scored_count"], 1)
        self.assertEqual(diagnostic["scored_criterion_count"], 2)

    def test_plan_returns_counts_without_destination_or_keyword_content(self):
        plan = {"groups": [{"url": "https://private.invalid/hidden", "keywords": ["private"]}],
                "dropped": [{"text": "private"}]}
        result = build_ads_results(fixture(), plan=plan)
        self.assertEqual(result["plan_summary"]["distinct_destination_url_count"], 1)
        self.assertEqual(result["plan_summary"]["keyword_entry_count"], 1)
        self.assertNotIn("private.invalid", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
