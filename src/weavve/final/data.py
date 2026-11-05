"""Compatibility views over the single verified local cleaned dataset.

The current analysis scripts never clean raw sources themselves. Original source
columns are retained in support tables; legacy transaction row money is adapted
from canonical corrected fields, without applying tax adjustments a second time.
"""
import math
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache

from weavve.clean import load_dataset

SOURCES = {}


@lru_cache(None)
def dataset():
    result = load_dataset()
    for source in result.manifest["contract"]["sources"]:
        SOURCES[source["file"]] = {"source": source["source"], "sha256": source["sha256"]}
    return result


def text(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def num(v):
    if v is None or isinstance(v, bool) or not text(v):
        return None
    try:
        n = float(text(v).replace(",", ""))
    except (ValueError, TypeError):
        return None
    return n if math.isfinite(n) else None


def money(v):
    return Decimal(text(v) or "0")


def day(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if not text(v):
        return None
    try:
        return datetime.fromisoformat(text(v).replace("Z", "+00:00")).date()
    except ValueError:
        return None


TABLES = {
    ("C", None): "order_lines",
    ("C", "Order  Transaction-Level"): "order_lines",
    ("D", None): "products",
    ("G", "Person map"): "g_person_map",
    ("G", "Order channel"): "g_order_channels",
    ("I", None): "clearance_skus",
    ("E", None): "discounts",
    ("E", "Full Discounts Report"): "discounts",
    ("E", "Discount Detail by Code"): "discount_detail_by_code",
    ("E", "Discount by Year"): "discount_by_year",
    ("E", "FirstWelcome Order Discount by "): "discount_summary",
    ("E", "Alia by Discount Depth"): "discount_alia_depth",
    ("F", None): "loyalty_rewards",
    ("F", "Redemptions"): "loyalty_rewards",
    ("J", None): "subscribers",
    ("J", "Subscribers"): "subscribers",
    ("K", None): "email_campaigns",
    ("12", None): "ads_keywords",
    ("12", "Search keyword report All time "): "ads_keywords",
}


@lru_cache(None)
def rows(code, sheet=None):
    try:
        name = TABLES[(code, sheet)]
    except KeyError:
        raise ValueError(f"No shared table mapping for {code}/{sheet}; add an explicit mapping.") from None
    return dataset().table(name)


@lru_cache(None)
def order_view(records=None, *, drop_cancelled=True, drop_repeated=True, positive_only=True):
    """One canonical order, keeping the historical analysis interface explicit."""
    if records is not None or not drop_cancelled or not drop_repeated:
        raise ValueError("Current analyses require canonical cleaned orders; raw comparisons belong in historical notebooks.")
    grouped = defaultdict(list)
    for line in dataset().table("order_lines"):
        adapted = dict(line)
        adapted["Net sales"] = line["net"]
        adapted["Discounts"] = -line["discount"]
        grouped[line["order_id"]].append(adapted)
    result = []
    for order in dataset().table("orders"):
        if positive_only and not order["is_purchase"]:
            continue
        kept = grouped[order["order_id"]]
        result.append({
            "order": order["order_id"], "customer": order["customer_id"],
            "person": order["person_id"], "channel": order["channel_detail"],
            "original_channels": order["original_channels"], "date": order["order_date"],
            "net": float(order["net"]), "discount": float(order["discount"]),
            "cancelled": False,
            "has_negative_discount": any(line["discount"] > 0 for line in kept),
            "rows": kept,
        })
    return result


def funnel_monthly():
    """All supplied monthly observations; each keeps its complete-window flag."""
    return dataset().table("website_funnel")


@lru_cache(None)
def search_console():
    """Selected full-month Singapore exports with top-query coverage retained."""
    queries = defaultdict(dict)
    query_rows = defaultdict(list)
    for row in dataset().table("gsc_queries"):
        # Some source labels repeat as an observed row followed by a blank row.
        # Preserve both rows, without letting the blank erase known evidence.
        month, query, clicks = row["month"], row["query"], row["clicks"]
        query_rows[month].append({"query": query, "clicks": clicks})
        if clicks is not None and queries[month].get(query) is not None:
            raise ValueError("Multiple observed GSC rows share a month/query label; resolve their grain before aggregation.")
        if query not in queries[month] or clicks is not None:
            queries[month][query] = clicks
    result = {}
    for row in dataset().table("gsc_months"):
        month = row["month"]
        result[(month.year, month.month)] = {
            "clicks": row["clicks"], "queries": queries[month],
            "query_rows": query_rows[month],
            "query_click_coverage": row["query_click_coverage"],
            "source_file": row["source_file"],
        }
    return result
