"""Rebuilds the findings in Section 6 of the final report from Files C, D, G, J and K.

weavve.final.data reads the files and checks each one against the report's copy. The checks apply the Part A
rules. They leave out cancelled orders and repeated discount lines, and they keep refunds with their order.
Orders with zero or negative net sales do not count as purchases.

Run it through notebooks/05_final_report.ipynb.
"""

from collections import defaultdict
from datetime import date, timedelta

from weavve.final.data import order_view, rows, text, money, day

COMPANY, OSCO = "P000034", "P013881"
CUTOFF = date(2026, 8, 28)
results = {}


def is_web(o, scope):
    return (
        ("Online Store" in o["original_channels"])
        if scope == "online_store"
        else (o["channel"] == "Own store")
    )


def jan_aug(d):
    return d.month <= 8 and not (d.month == 8 and d.day > 28)


orders = order_view(drop_cancelled=True, drop_repeated=True, positive_only=True)
# Signed net including all non-repeated rows, for sales totals that keep zero-net orders out of purchase
# counts only.
all_orders = order_view(drop_cancelled=True, drop_repeated=True, positive_only=False)

for scope in ("online_store", "own_store"):
    web = [o for o in orders if is_web(o, scope)]
    web_all = [o for o in all_orders if is_web(o, scope)]
    people = defaultdict(list)
    for o in web:
        if o["person"] in (COMPANY, OSCO):
            continue
        people[o["person"]].append(o)
    first = {p: min(x["date"] for x in os) for p, os in people.items()}
    r = {}

    # Lens 5: website sales by year, new buyers, kept and share from new
    sales = defaultdict(float)
    sales_ex_company = defaultdict(float)
    for o in web_all:
        sales[o["date"].year] += o["net"]
        if o["person"] not in (COMPANY, OSCO):
            sales_ex_company[o["date"].year] += o["net"]
    new_by_year = defaultdict(int)
    for p, d in first.items():
        new_by_year[d.year] += 1
    from_new = defaultdict(float)
    from_old = defaultdict(float)
    for p, os in people.items():
        for o in os:
            (from_new if o["date"].year == first[p].year else from_old)[o["date"].year] += o["net"]
    lens5 = {}
    for y in range(2021, 2026):
        kept = from_old[y] / sales_ex_company[y - 1] if sales_ex_company[y - 1] else None
        leak = sales_ex_company[y - 1] - from_old[y]
        per_new = from_new[y] / new_by_year[y] if new_by_year[y] else None
        lens5[y] = {
            "sales_all": round(sales[y]),
            "sales_ex_company_osco": round(sales_ex_company[y]),
            "new_buyers": new_by_year[y],
            "kept_from_last_year_pct": round(100 * kept, 1) if kept else None,
            "share_from_new_pct": round(100 * from_new[y] / sales_ex_company[y], 1),
            "sales_from_new_buyers": round(from_new[y]),
            "sales_from_earlier_buyers": round(from_old[y]),
            "leak": round(leak),
            "in_year_sales_per_new_buyer": round(per_new, 1) if per_new else None,
            "needed_to_stand_still": round(leak / per_new) if per_new else None,
        }
    r["lens5"] = lens5

    # Lens 2: 2024 vs 2025, and Jan-Aug 2025 vs 2026
    def split(y0, y1, window=None):
        def yr(o, y):
            return o["date"].year == y and (window is None or window(o["date"]))

        b0 = {p for p, os in people.items() if any(yr(o, y0) for o in os)}
        b1 = {p for p, os in people.items() if any(yr(o, y1) for o in os)}
        out = {}
        for name, grp, y in (
            ("y0_only", b0 - b1, y0),
            ("both_y0", b0 & b1, y0),
            ("both_y1", b0 & b1, y1),
            ("y1_only", b1 - b0, y1),
        ):
            os = [o for p in grp for o in people[p] if yr(o, y)]
            n = len(grp)
            out[name] = {
                "customers": n,
                "orders_each": round(len(os) / n, 2) if n else None,
                "aov": round(sum(o["net"] for o in os) / len(os)) if os else None,
                "sales": round(sum(o["net"] for o in os)),
            }
        return out

    r["lens2_2024_2025"] = split(2024, 2025)
    r["lens2_janaug_2025_2026"] = split(2025, 2026, jan_aug)
    new25 = sum(1 for p, d in first.items() if d.year == 2025)
    r["lens2_new_share_of_2025_only"] = round(100 * new25 / r["lens2_2024_2025"]["y1_only"]["customers"], 1)

    # Lens 1: 2025 deciles by 2025 website sales
    b25 = sorted(
        (
            (sum(o["net"] for o in os if o["date"].year == 2025), p)
            for p, os in people.items()
            if any(o["date"].year == 2025 for o in os)
        ),
        reverse=True,
    )
    n = len(b25)
    tot = sum(s for s, _ in b25)
    deciles = []
    size = n // 10
    for k in range(10):
        grp = b25[k * size : (k + 1) * size] if k < 9 else b25[9 * size :]
        os = [o for _, p in grp for o in people[p] if o["date"].year == 2025]
        deciles.append(
            {
                "decile": k + 1,
                "people": len(grp),
                "share_pct": round(100 * sum(s for s, _ in grp) / tot, 1),
                "orders_each": round(len(os) / len(grp), 2),
                "aov": round(sum(o["net"] for o in os) / len(os)),
                "new_pct": round(100 * sum(first[p].year == 2025 for _, p in grp) / len(grp)),
            }
        )
    r["lens1_2025"] = {
        "people": n,
        "new_pct_all": round(100 * sum(first[p].year == 2025 for _, p in b25) / n, 1),
        "deciles": deciles,
    }

    # Lens 4: Jan to 28 Aug first-purchase cohorts, year-1 activity
    lens4 = {}
    for y in (2022, 2023, 2024, 2025):
        coh = [p for p, d in first.items() if d.year == y and jan_aug(d)]

        def back(p, gap_min):
            d0 = first[p]
            return any(
                d0 + timedelta(days=gap_min) <= o["date"] <= d0 + timedelta(days=365) and o["date"] > d0
                for o in people[p]
            )

        def yr1(p):
            d0 = first[p]
            return [o for o in people[p] if o["date"] <= d0 + timedelta(days=365)]

        def yr2(p):
            d0 = first[p]
            return [o for o in people[p] if o["date"] <= d0 + timedelta(days=730)]

        active_any = sum(back(p, 1) for p in coh)
        active_7 = sum(back(p, 8) for p in coh)
        returners = [p for p in coh if back(p, 1)]
        rep_orders = [o for p in returners for o in yr1(p) if o["date"] > first[p]]
        first_orders = [min(people[p], key=lambda o: (o["date"], o["order"])) for p in coh]
        y1_sales = sum(o["net"] for p in coh for o in yr1(p))
        mature2 = all(first[p] + timedelta(days=730) <= CUTOFF for p in coh)
        lens4[y] = {
            "cohort": len(coh),
            "active_y1_pct_any_later_day": round(100 * active_any / len(coh), 1),
            "active_y1_pct_after_7_days": round(100 * active_7 / len(coh), 1),
            "repeat_orders_per_returner": round(len(rep_orders) / len(returners), 2) if returners else None,
            "first_order_mean": round(sum(o["net"] for o in first_orders) / len(coh)),
            "y1_sales_per_member": round(y1_sales / len(coh)),
            "y2_sales_per_member": (
                round(sum(o["net"] for p in coh for o in yr2(p)) / len(coh)) if mature2 else None
            ),
        }
    r["lens4"] = lens4
    results[scope] = r

# Step 1b and Step 2: first-ever purchase across website and Shopee, by person, Jan to 28 Aug
people_all = defaultdict(list)
for o in orders:
    if o["person"] in (COMPANY, OSCO):
        continue
    people_all[o["person"]].append(o)
newcomers = {}
for scope in ("online_store", "own_store"):
    out = {}
    for y in (2023, 2024, 2025, 2026):
        web = shp = 0
        for p, os in people_all.items():
            cand = [o for o in os if is_web(o, scope) or o["channel"] == "Shopee"]
            if not cand:
                continue
            f = min(cand, key=lambda o: (o["date"], o["order"]))
            if f["date"].year != y or not jan_aug(f["date"]):
                continue
            if f["channel"] == "Shopee" and not is_web(f, scope):
                shp += 1
            else:
                web += 1
        out[y] = {
            "newcomers": web + shp,
            "started_website": web,
            "started_shopee": shp,
            "shopee_share_pct": round(100 * shp / (web + shp), 1),
        }
    newcomers[scope] = out
results["step1b_newcomers_janaug"] = newcomers


# Discount depth: discounts / (net + discounts), Jan to 28 Aug 2026, by channel, on non-repeated sale rows
def depth(window):
    acc = defaultdict(lambda: [0.0, 0.0])
    for o in orders:
        if not window(o["date"]):
            continue
        ch = "website" if "Online Store" in o["original_channels"] else o["channel"]
        for r in o["rows"]:
            if text(r["Order or sales reversal"]) != "order":
                continue
            acc[ch][0] += float(-money(r["Discounts"]))
            acc[ch][1] += float(money(r["Net sales"]) - money(r["Discounts"]))
    return {ch: round(100 * d / g, 1) for ch, (d, g) in acc.items() if g > 0}


results["discount_depth_2026_janaug"] = depth(lambda d: d.year == 2026 and jan_aug(d))
results["discount_depth_2026_27apr_28aug"] = depth(
    lambda d: d.year == 2026 and date(2026, 4, 27) <= d <= CUTOFF
)

# Orders Jan to 28 Aug by channel, 2024 and 2026 (purchases)
cnt = defaultdict(int)
for o in orders:
    if o["date"].year in (2024, 2026) and jan_aug(o["date"]):
        ch = "website" if "Online Store" in o["original_channels"] else o["channel"]
        cnt[(ch, o["date"].year)] += 1
results["orders_janaug"] = {f"{c}_{y}": n for (c, y), n in sorted(cnt.items())}
for ch in ("website", "Shopee"):
    a, b = cnt[(ch, 2024)], cnt[(ch, 2026)]
    results["orders_janaug"][f"{ch}_change_pct"] = round(100 * (b / a - 1), 1) if a else None

# Share of website or Shopee buyers who bought on both
web_p = {
    o["person"]
    for o in orders
    if "Online Store" in o["original_channels"] and o["person"] not in (COMPANY, OSCO)
}
shp_p = {o["person"] for o in orders if o["channel"] == "Shopee" and o["person"] not in (COMPANY, OSCO)}
results["both_channels"] = {
    "website_people": len(web_p),
    "shopee_people": len(shp_p),
    "both": len(web_p & shp_p),
    "both_pct_of_either": round(100 * len(web_p & shp_p) / len(web_p | shp_p), 1),
}

# Website first-order discount, Jan to 28 Aug cohorts
fo = {}
for y in (2023, 2024, 2025, 2026):
    d_sum = g_sum = 0.0
    seen = set()
    for o in sorted(
        (
            o
            for o in orders
            if "Online Store" in o["original_channels"] and o["person"] not in (COMPANY, OSCO)
        ),
        key=lambda o: (o["date"], o["order"]),
    ):
        if o["person"] in seen:
            continue
        seen.add(o["person"])
        if o["date"].year == y and jan_aug(o["date"]):
            for r in o["rows"]:
                if text(r["Order or sales reversal"]) == "order":
                    d_sum += float(-money(r["Discounts"]))
                    g_sum += float(money(r["Net sales"]) - money(r["Discounts"]))
    fo[y] = round(100 * d_sum / g_sum, 1)
results["first_website_order_discount_pct_janaug"] = fo

# Product T11 base: first website purchase Jan 2023 to Aug 2024, 2-year website sales per person
web_people = defaultdict(list)
for o in orders:
    if "Online Store" in o["original_channels"] and o["person"] not in (COMPANY, OSCO):
        web_people[o["person"]].append(o)
base = []
for p, os in web_people.items():
    d0 = min(o["date"] for o in os)
    if date(2023, 1, 1) <= d0 <= date(2024, 8, 31):
        base.append(sum(o["net"] for o in os if o["date"] <= d0 + timedelta(days=730)))
results["product_t11_base"] = {"people": len(base), "avg_2y_sales": round(sum(base) / len(base))}

D = {text(r["Code"]): r for r in rows("D")}
unknown_first = 0
for p, os in web_people.items():
    f = min(os, key=lambda o: (o["date"], o["order"]))
    if date(2023, 1, 1) <= f["date"] <= date(2024, 8, 31):
        skus = {
            text(r["Product variant SKU at time of sale"])
            for r in f["rows"]
            if text(r["Order or sales reversal"]) == "order" and text(r["Line item ID"]) not in ("", "0")
        } - {""}
        unknown_first += int(not any(s in D for s in skus))
results["product_t11_base"]["first_order_products_missing_from_D"] = unknown_first

# Year-1 value per newcomer by start channel, Jan to 28 Aug cohorts. Shopee lines after 26 Aug 2025 are
# divided by 1.09 to take out GST.
val = defaultdict(lambda: [0, 0.0])
for p, os in people_all.items():
    cand = [o for o in os if "Online Store" in o["original_channels"] or o["channel"] == "Shopee"]
    if not cand:
        continue
    f = min(cand, key=lambda o: (o["date"], o["order"]))
    if f["date"].year not in (2023, 2024, 2025) or not jan_aug(f["date"]):
        continue
    start = "website" if "Online Store" in f["original_channels"] else "Shopee"
    v = val[f'{f["date"].year}_{start}']
    v[0] += 1
    v[1] += sum(
        o["net"] / (1.09 if o["channel"] == "Shopee" and o["date"] >= date(2025, 8, 26) else 1.0)
        for o in cand
        if o["date"] <= f["date"] + timedelta(days=365)
    )
results["year1_value_per_newcomer"] = {k: round(s / n) for k, (n, s) in sorted(val.items())}

# Email clicks, File K: campaigns sent to 20 or more people, unique clicks over recipients, cut at 28 Aug 2026
from weavve.final.data import num

clicks = defaultdict(lambda: [0.0, 0.0])
for r in rows("K"):
    d, n, c = day(r["Send Date"]), num(r["Total Recipients"]), num(r["Unique Clicks"])
    if d and n is not None and n >= 20 and d <= CUTOFF:
        clicks[d.year][0] += c or 0
        clicks[d.year][1] += n
results["email_click_rate_pct"] = {y: round(100 * c / n, 3) for y, (c, n) in sorted(clicks.items())}

# File J initial sources for new website buyers, by year of first website purchase (full year and Jan to 28
# Aug)
src = defaultdict(set)
for r in rows("J", "Subscribers"):
    if text(r["person_id"]):
        src[text(r["person_id"])].add(text(r["Initial Source"]))
for label, test in (
    ("klaviyo_signup", lambda s: "Klaviyo" in s),
    ("wedding_vow", lambda s: "theweddingvowsg.com" in s),
):
    full, ja = defaultdict(int), defaultdict(int)
    for p, os in web_people.items():
        d0 = min(o["date"] for o in os)
        if test(src.get(p, set())):
            full[d0.year] += 1
            ja[d0.year] += int(jan_aug(d0))
    results[f"j_source_{label}_new_website_buyers"] = {
        "full_year": dict(sorted(full.items())),
        "jan_aug": dict(sorted(ja.items())),
    }
