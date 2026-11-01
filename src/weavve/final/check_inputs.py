"""Checks the Part B inputs that check_recs.py does not cover.

It uses the same Part A rules and hash-checked files as check_recs.py.

Run it through notebooks/05_final_report.ipynb.
"""

from collections import defaultdict
from datetime import date, timedelta

from weavve.final.data import funnel_monthly, money, num, order_view, rows, text

COMPANY, OSCO = "P000034", "P013881"
CUTOFF = date(2026, 8, 28)
res = {}
orders = order_view(drop_cancelled=True, drop_repeated=True, positive_only=True)


def jan_aug(d):
    return d.month <= 8 and not (d.month == 8 and d.day > 28)


def is_web(o):
    return "Online Store" in o["original_channels"]


def chan(o):
    return "website" if is_web(o) else o["channel"]


# 1. Discount depth by channel, January to 28 August, and who sets the Shopee discount
seller = ("price match", "match shopee price", "voucher from seller", "bundle deal")
depth = defaultdict(lambda: [0.0, 0.0, 0.0])
for o in orders:
    if not jan_aug(o["date"]) or o["date"].year not in (2023, 2024, 2025, 2026):
        continue
    for r in o["rows"]:
        if text(r["Order or sales reversal"]) != "order":
            continue
        disc = float(-money(r["Discounts"]))
        acc = depth[(chan(o), o["date"].year)]
        acc[0] += disc
        acc[1] += float(money(r["Net sales"])) + disc
        if disc and any(s in text(r["Discount name"]).lower() for s in seller):
            acc[2] += disc
res["discount_depth_janaug_pct"] = {
    f"{c}_{y}": round(100 * d / g, 1)
    for (c, y), (d, g, s) in sorted(depth.items())
    if c in ("website", "Shopee") and g
}
res["shopee_discount_with_seller_label_pct"] = {
    y: round(100 * depth[("Shopee", y)][2] / depth[("Shopee", y)][0], 1) for y in (2024, 2025, 2026)
}

# 2. People: first-ever purchase across the website and Shopee
people = defaultdict(list)
for o in orders:
    if o["person"] in (COMPANY, OSCO):
        continue
    if is_web(o) or o["channel"] == "Shopee":
        people[o["person"]].append(o)
first = {p: min(os, key=lambda o: (o["date"], o["order"])) for p, os in people.items()}

# 3. Baseline for the parcel-card test: Shopee starters who place a website order later
base = defaultdict(lambda: [0, 0, 0])
for p, f in first.items():
    if f["channel"] != "Shopee" or is_web(f) or f["date"].year not in (2023, 2024, 2025):
        continue
    if f["date"] + timedelta(days=365) > CUTOFF:
        continue
    web_dates = [o["date"] for o in people[p] if is_web(o) and o["date"] > f["date"]]
    b = base[f["date"].year]
    b[0] += 1
    b[1] += int(any(d <= f["date"] + timedelta(days=90) for d in web_dates))
    b[2] += int(any(d <= f["date"] + timedelta(days=365) for d in web_dates))
res["shopee_starters_later_website_order"] = {
    y: {
        "people": n,
        "within_90_days_pct": round(100 * a / n, 2),
        "within_365_days_pct": round(100 * b / n, 2),
    }
    for y, (n, a, b) in sorted(base.items())
}
shopee_orders_2026 = sum(
    1 for o in orders if o["channel"] == "Shopee" and o["date"].year == 2026 and jan_aug(o["date"])
)
res["shopee_purchases_janaug_2026"] = shopee_orders_2026

# 4. Snooze Club sizing inputs: new website customers 29 Aug 2025 to 28 Aug 2026
win = [f for f in first.values() if is_web(f) and date(2025, 8, 29) <= f["date"] <= CUTOFF]
n = len(win)


def codes(o):
    return {text(r["Discount code"]).upper() for r in o["rows"] if text(r["Discount code"])}


res["snooze_inputs"] = {
    "new_website_customers": n,
    "club_code_on_first_order_pct": round(
        100 * sum(any(c.startswith("LWC") for c in codes(f)) for f in win) / n, 1
    ),
    "first_order_200_plus_pct": round(100 * sum(f["net"] >= 200 for f in win) / n, 1),
    "first_order_80_plus_pct": round(100 * sum(f["net"] >= 80 for f in win) / n, 1),
    "first_order_100_plus_pct": round(100 * sum(f["net"] >= 100 for f in win) / n, 1),
    "first_order_mean": round(sum(f["net"] for f in win) / n),
}

# 5. Member comparison behind the club's lift in return (first website order 27 Apr 2023 to 26 Aug 2024)
grp = defaultdict(lambda: [0, 0])
for p, f in first.items():
    if not is_web(f) or not (date(2023, 4, 27) <= f["date"] <= date(2024, 8, 26)):
        continue
    member = any(c.startswith("LWC") for c in codes(f))
    big = f["net"] >= 200
    back = any(f["date"] < o["date"] <= f["date"] + timedelta(days=365) for o in people[p])
    for key in (("all", member), ("200_plus" if big else "under_200", member)):
        g = grp[key]
        g[0] += 1
        g[1] += int(back)
res["member_return_within_1_year"] = {
    f'{k}_{"members" if m else "non_members"}': {"people": a, "back_pct": round(100 * b / a, 1)}
    for (k, m), (a, b) in sorted(grp.items())
}

# 6. Newcomers by start channel and their year-1 value, January to 28 August cohorts
nc = defaultdict(lambda: [0, 0])
for p, f in first.items():
    if jan_aug(f["date"]) and f["date"].year in (2023, 2024, 2025, 2026):
        nc[f["date"].year][0] += 1
        nc[f["date"].year][1] += int(is_web(f))
res["newcomers_janaug"] = {
    y: {"newcomers": a, "started_website": b, "website_share_pct": round(100 * b / a, 1)}
    for y, (a, b) in sorted(nc.items())
}

# 7. What Weavve's ad account counts as a conversion, for the margin in Section 7.3 and the limits in
# Section 11 (File 12, all time). Searches for the Weavve name convert far more often, so the click comparison
# leaves them out.
ad_rows = rows("12", "Search keyword report All time ")


def ad_totals(keep):
    kept = [r for r in ad_rows if keep(r)]
    return {k: sum(num(r[k]) or 0 for r in kept) for k in ("Clicks", "Conversions", "Conv. value")}


def brand(r):
    return "weavve" in (text(r["Keyword"]) + text(r["Campaign"])).lower()


all_ads, other_ads = ad_totals(lambda r: True), ad_totals(lambda r: not brand(r))
web_orders = [
    o["net"] for o in orders if is_web(o) and o["person"] not in (COMPANY, OSCO) and o["date"].year >= 2019
]
funnel = funnel_monthly()
res["ad_conversions"] = {
    "value_per_conversion": round(all_ads["Conv. value"] / all_ads["Conversions"], 2),
    "non_brand_conversions_per_click_pct": round(100 * other_ads["Conversions"] / other_ads["Clicks"], 1),
    "non_brand_value_per_conversion": round(other_ads["Conv. value"] / other_ads["Conversions"], 2),
    "website_mean_order_since_2019": round(sum(web_orders) / len(web_orders), 2),
    "site_orders_per_session_pct": round(
        100 * sum(r["Orders Placed"] for r in funnel) / sum(r["Sessions"] for r in funnel), 1
    ),
}
