"""Rebuilds our Recommendation 1 findings for the comparison with the business team's version.

The checks answer three questions.

1. What is the first-year value of Shopee starters who place a website order within 90 days? The check
   compares them with starters who buy again only on Shopee and with starters who do not buy again within 90
   days. This replaces the assumption that a moved buyer spends like a website starter.
2. How many new email sign-ups join each year, and what share place a website order within 90 days? A new
   sign-up is a File J profile of someone who had not bought before. This share is the baseline for the
   welcome-flow test.
3. How many people would the parcel card and the welcome flow reach in 2026?

It uses the same verified cleaned dataset and first-year definition as check_recs.py.
Profile creation is a proxy, not evidence of voluntary signup or marketing consent.
Group differences are observational, not causal treatment effects.

Run it through notebooks/05_final_report.ipynb.
"""

import math
import statistics
from collections import defaultdict
from datetime import date, timedelta

from weavve.final.data import order_view, rows, text, day

COMPANY, OSCO = "P000034", "P013881"
CUTOFF = date(2026, 8, 28)
res = {}
orders = order_view(drop_cancelled=True, drop_repeated=True, positive_only=True)


def is_web(o):
    return "Online Store" in o["original_channels"]


def net(o):
    # Already corrected at line level in the shared dataset.
    return o["net"]


people = defaultdict(list)
for o in orders:
    if o["person"] not in (COMPANY, OSCO) and (is_web(o) or o["channel"] == "Shopee"):
        people[o["person"]].append(o)
first = {p: min(os, key=lambda o: (o["date"], o["order"])) for p, os in people.items()}


def summary(values):
    n, mean = len(values), statistics.fmean(values)
    sd = statistics.stdev(values) if n > 1 else 0.0
    return {
        "people": n,
        "mean": round(mean),
        "median": round(statistics.median(values)),
        "sd": round(sd),
        "ci95": [round(mean - 1.96 * sd / math.sqrt(n)), round(mean + 1.96 * sd / math.sqrt(n))],
    }


def gap(a, b):
    diff = statistics.fmean(a) - statistics.fmean(b)
    se = math.sqrt(statistics.variance(a) / len(a) + statistics.variance(b) / len(b))
    return {"mean": round(diff), "ci95": [round(diff - 1.96 * se), round(diff + 1.96 * se)]}


# 1. Shopee starters with a full first year in the data: first purchase 1 Jan 2023 to 28 Aug 2025
groups = defaultdict(list)
for p, f in first.items():
    if is_web(f) or f["date"].year not in (2023, 2024, 2025) or f["date"] + timedelta(days=365) > CUTOFF:
        continue
    later = [o for o in people[p] if f["date"] < o["date"] <= f["date"] + timedelta(days=90)]
    if any(is_web(o) for o in later):
        g = "website_order_within_90_days"
    elif later:
        g = "shopee_only_repeat_within_90_days"
    else:
        g = "no_repeat_within_90_days"
    groups[g].append(sum(net(o) for o in people[p] if o["date"] <= f["date"] + timedelta(days=365)))
movers = groups["website_order_within_90_days"]
res["shopee_starters_year1_value"] = {g: summary(v) for g, v in sorted(groups.items())}
res["mover_gain_year1"] = {
    "against_shopee_only_repeat": gap(movers, groups["shopee_only_repeat_within_90_days"]),
    "against_no_repeat": gap(movers, groups["no_repeat_within_90_days"]),
}

# 2. New email sign-ups: File J profiles created 2023 onward by people with no earlier website or Shopee
# purchase
web_dates = defaultdict(list)
for p, os in people.items():
    web_dates[p] = [o["date"] for o in os if is_web(o)]
signups, quarters = defaultdict(lambda: [0, 0, 0]), defaultdict(lambda: [0, 0])
reach_2026 = 0
for r in rows("J", "Subscribers"):
    d = day(r["Profile Created On"])
    p = text(r["person_id"])
    if not d or d.year < 2023 or (p and p in first and first[p]["date"] < d):
        continue
    if d.year == 2026 and d <= CUTOFF:
        reach_2026 += 1
    if d + timedelta(days=90) > CUTOFF:
        continue
    dates = web_dates.get(p, []) if p else []
    bought = int(any(d <= x <= d + timedelta(days=90) for x in dates))
    # Bought later: no website order on the day of sign-up, then one within 90 days. Most buyers sign up on the
    # day they buy, to get the pop-up code, so welcome emails can only reach the later buyers.
    later = int(bought and d not in dates)
    for s in (signups[d.year], quarters[f"{d.year} Q{(d.month - 1) // 3 + 1}"]):
        s[0] += 1
        s[1] += bought
    signups[d.year][2] += later
res["new_signups_website_order_within_90_days"] = {
    y: {
        "signups": n,
        "bought": b,
        "pct": round(100 * b / n, 1),
        "bought_later": lt,
        "later_pct": round(100 * lt / n, 1),
        "window": "profiles created 1 Jan to 30 May 2026" if y == 2026 else "full year",
    }
    for y, (n, b, lt) in sorted(signups.items())
}
# Section 6.2: new sign-ups by where they came from (File J Initial Source), September to August. Facebook and
# Instagram are counted together. "google" on its own is a tagged ad link. Other Google sources are search.
def source(s):
    s = s.lower()
    if "facebook" in s or "instagram" in s or s in ("ig", "fb", "igshopping"):
        return "facebook_instagram"
    if s == "google":
        return "google_ad_link"
    return "other"


by_source = defaultdict(lambda: defaultdict(int))
for r in rows("J", "Subscribers"):
    d = day(r["Profile Created On"])
    p = text(r["person_id"])
    if not d or d < date(2024, 9, 1) or d > CUTOFF or (p and p in first and first[p]["date"] < d):
        continue
    year = "sep2024_aug2025" if d < date(2025, 9, 1) else "sep2025_aug2026"
    by_source[year][source(text(r["Initial Source"]))] += 1
res["new_signups_by_source"] = {y: dict(v) for y, v in sorted(by_source.items())}

# When the rate fell, to set against the sign-up reward failure in late 2025
res["new_signups_by_quarter"] = {
    q: {"signups": n, "pct": round(100 * b / n, 1)} for q, (n, b) in sorted(quarters.items()) if q >= "2024"
}

# 3. Reach a year in 2026: new sign-ups 1 Jan to 28 Aug, and Shopee starters 1 Jan to 28 Aug, both scaled to a
# year
days_2026 = (CUTOFF - date(2026, 1, 1)).days + 1
shopee_starters_2026 = sum(
    1 for f in first.values() if not is_web(f) and f["date"].year == 2026 and f["date"] <= CUTOFF
)
res["reach_2026"] = {
    "new_signups_janaug": reach_2026,
    "new_signups_a_year": round(reach_2026 * 365 / days_2026),
    "shopee_starters_janaug": shopee_starters_2026,
    "shopee_starters_a_year": round(shopee_starters_2026 * 365 / days_2026),
}
