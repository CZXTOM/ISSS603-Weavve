"""Idea 1, every number on the final deck slides 3, 4 and 5, in one run.
Sheet starters = newcomers whose first order had sheets (whole bed, sheet set, sheet separates).

Years run Sep to Aug and are named by the year they end in:
  2024 = Sep 2023 to Aug 2024, 2025 = Sep 2024 to Aug 2025, 2026 = Sep 2025 to Aug 2026.
A newcomer is a person whose first ever purchase was on the website.
Margin 60% is assumed (Weavve gave none). Meta cost per new customer $100 to $300 is from Weavve's case deck.
Set-up costs $1,000 (emails) and $500 (whole-bed photos) are estimates.

Needs idea1_v8.py in the same folder. Reads ~/Desktop/Weavve_Clean_Data (or SRC_DIR).
Writes ~/Desktop/idea1_slide_numbers.csv (or OUT_CSV).
Run:  python idea1_slide_numbers.py
"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_CSV = os.environ.get("OUT_CSV", os.path.expanduser("~/Desktop/idea1_slide_numbers.csv"))

# Shared analysis: loads the data, builds newcomers (nw), repeat orders (rep), first baskets, Meta payback (F4d),
# whole-bed share by welcome code (F4e) and second-order timing and contents (F5a, F5b)
exec(open(os.path.join(HERE, "idea1_v8.py")).read().split("# ================= Sizing")[0])

rows = []
def put(slide, item, value, note=""):
    rows.append({"slide": slide, "item": item, "value": value, "note": note})

YEARS = {"2025": ("2024-08-29", "2025-08-28"), "2026": ("2025-08-29", "2026-08-28")}
SHEETS = ["Whole bed", "Sheet set only", "Sheet separates only"]   # first order had sheets
on_list_ids = J[~J.excluded_account].person_id.dropna().unique()
nw["on_list"] = nw.index.isin(on_list_ids)
nw["sf"] = nw.entry.isin(SHEETS)
nw["b6"] = nw.index.isin(rep[rep.age < 182].person_id)

# ---------- Slide 3, left: email list, split by first order, via search ----------
for y, (a, b) in YEARS.items():
    d = nw[(nw.order_date >= a) & (nw.order_date <= b)]
    lst = d[d.on_list]
    put(3, f"Email list newcomers {y}", len(lst), f"{100 * len(lst) / len(d):.0f}% of {len(d)} newcomers")
    put(3, f"Sheet starters {y}", int(lst.sf.sum()))
    put(3, f"Others {y}", int((~lst.sf).sum()))
    put(3, f"Via search {y}", int((d.src == "Search").sum()))

# ---------- Slide 3, right: sheet starters, the group to keep ----------
a, b = YEARS["2026"]
l26 = nw[(nw.order_date >= a) & (nw.order_date <= b) & nw.on_list]
put(3, "Share of 2026 email-list newcomers who start with sheets %", round(100 * l26.sf.mean(), 1))
mix1 = 100 * l26.entry.value_counts(normalize=True)
for kk in ["Sheet set only", "Sheet separates only", "Whole bed", "Bedding only", "Bath, kitchen or other"]:
    put(3, f"2026 first order, {kk} %", round(mix1.get(kk, 0), 1))
c = nw[(nw.order_date >= "2022-08-29") & (nw.order_date <= "2024-08-28")]
spend2 = x[x.age < 730].groupby("person_id").net.sum()
for g_, nm in [(True, "sheet starter"), (False, "others")]:
    put(3, f"2-year spend per newcomer, {nm} $", round(spend2.reindex(c[c.sf == g_].index).mean()), "Sep 2022 to Aug 2024 starters")
for y, (a, b) in YEARS.items():
    d = nw[(nw.order_date >= a) & (nw.order_date <= b) & nw.on_list & (nw.follow >= 182)]
    for g_, nm in [(True, "sheet starters"), (False, "others")]:
        put(3, f"Back within 6 months {y}, {nm} %", round(100 * d[d.sf == g_].b6.mean(), 1), f"{int((d.sf == g_).sum())} with 6 months to watch")
sr = r2[r2.person_id.isin(c[c.sf].index) & r2.cats.apply(lambda s: isinstance(s, set))]
put(3, "Sheet starters who come back, second order includes sheets %",
    round(100 * sr.cats.apply(lambda s: "1. Bedsheets" in s).mean(), 1), f"{len(sr)} returners, 2 years")
for kk, cat_ in [("bedding", "2. Bedding"), ("bath", "3. Bath")]:
    put(3, f"Sheet starters who come back, second order includes {kk} %", round(100 * sr.cats.apply(lambda s: cat_ in s).mean(), 1))

# ---------- Slide 4, left: when sheet starters' second orders come ----------
ss = sec.reindex(c[c.sf].index).dropna()
put(4, "Second orders, day 8 to 18 %", round(100 * (ss <= 18).mean(), 1), f"{len(ss)} sheet-starter returners, Sep 2022 to Aug 2024")
put(4, "Second orders, day 18 to 1 year %", round(100 * ((ss > 18) & (ss < 365)).mean(), 1))
put(4, "Second orders, after 1 year %", round(100 * (ss >= 365).mean(), 1))
for lab, lo, hi in [("Under 1 month", 7, 30), ("1 to 6 months", 30, 180), ("6 to 12 months", 180, 365), ("1 to 2 years", 365, 730)]:
    put(4, f"Second orders, {lab} %", round(100 * ((ss > lo) & (ss <= hi)).mean(), 1))
put(4, "Second orders after 1 month %", round(100 * (ss > 30).mean(), 1))

# ---------- Slide 4, right: Meta profit and whole-bed share ----------
for cpa in [100, 200, 300]:
    for nm in ["Whole bed", "Other"]:
        put(4, f"First-order profit after ${cpa} Meta cost, {nm}", round(V[nm]["first"] * M - cpa), "60% margin, newcomers Sep 2024 to Aug 2025")
for y, w in [("2024", "W1"), ("2025", "W2"), ("2026", "W3")]:
    d = nw[nw.w == w]
    put(4, f"Whole-bed first orders {y}, welcome code %", round(100 * d[d.welcome].wb.mean(), 1), f"{int(d.welcome.sum())} people")
    put(4, f"Whole-bed first orders {y}, others %", round(100 * d[~d.welcome].wb.mean(), 1), f"{int((~d.welcome).sum())} people")

# ---------- Slide 5: the prize, 2026 back to 2025 levels ----------
L5 = nw[(nw.w == "W2") & nw.on_list & nw.sf]; L6 = nw[(nw.w == "W3") & nw.on_list & nw.sf]
r6_25 = 100 * L5[L5.follow >= 182].b6.mean(); r6_26 = 100 * L6[L6.follow >= 182].b6.mean()
r12_25 = 100 * L5[L5.follow >= 365].back1.mean(); ratio = r12_25 / r6_25
ret = nw[nw.w.isin(["W1", "W2"]) & nw.back1 & nw.sf].index
val1 = rep[rep.person_id.isin(ret) & (rep.age < 365)].groupby("person_id").net.sum().mean()
x1 = len(L6) * (r6_25 - r6_26) * ratio / 100
gp1 = x1 * val1 * M
put(5, "Opp 1 people reached", len(L6), "2026 email-list sheet starters")
put(5, "Opp 1 come back 6 months, 2025 vs 2026 %", f"{r6_25:.1f} vs {r6_26:.1f}")
put(5, "Opp 1 year factor, 1-year / 6-month rate in 2025", round(ratio, 2), f"{r12_25:.1f} / {r6_25:.1f}")
put(5, "Opp 1 extra people back", round(x1, 1))
put(5, "Opp 1 repeat spend per sheet-starter returner, year one $", round(val1))
put(5, "Opp 1 gross profit $", round(gp1), "% active")

b2w = nw[(nw.w == "W2") & nw.wb]
add_item = k[k.order_id.isin(b2w.order_id) & (k.category == "2. Bedding")].groupby("order_id").net.sum().mean()
shrink = R["F3c premium Sep 2022-Aug 2024"]["same-size extra 2yr after-spend"] / R["F3c premium Sep 2022-Aug 2024"]["raw extra 2yr after-spend"]
per_switch = add_item + ((V["Whole bed"]["y1"] - V["Whole bed"]["first"]) - (V["Other"]["y1"] - V["Other"]["first"])) * shrink
w5 = nw[(nw.w == "W2") & nw.welcome]; w6 = nw[(nw.w == "W3") & nw.welcome]
s5, s6 = 100 * w5.wb.mean(), 100 * w6.wb.mean()
x2 = len(w6) * (s5 - s6) / 100
gp2 = x2 * per_switch * M
put(5, "Opp 2 people reached", len(w6), "2026 welcome-code newcomers")
put(5, "Opp 2 whole-bed share, 2025 vs 2026 %", f"{s5:.1f} vs {s6:.1f}")
put(5, "Opp 2 extra whole-bed first orders", round(x2, 1))
put(5, "Opp 2 value per switch $", round(per_switch), f"bedding added ${add_item:.0f} plus later value")
put(5, "Opp 2 gross profit $", round(gp2), "AOV")

put(5, "Total gross profit $", round(gp1 + gp2))
put(5, "After $1,500 set-up $", round(gp1 + gp2 - 1500))
put(5, "Back for every $1 of set-up", round((gp1 + gp2) / 1500, 2))

out = pd.DataFrame(rows)
pd.set_option("display.max_colwidth", 70)
for s, part in out.groupby("slide"):
    print(f"\n=== Slide {s}\n" + part[["item", "value", "note"]].to_string(index=False))
out.to_csv(OUT_CSV, index=False)
print("\nsaved", OUT_CSV)
