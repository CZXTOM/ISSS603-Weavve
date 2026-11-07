"""Idea 1, the numbers behind the final report section 6, Tables 10 to 18, in one run.

Sheet starters = newcomers whose first order had sheets (whole bed, sheet set, sheet separates).
Years run Sep to Aug and are named by the year they end in:
  2024 = Sep 2023 to Aug 2024, 2025 = Sep 2024 to Aug 2025, 2026 = Sep 2025 to Aug 2026.
A newcomer is a person whose first ever purchase, on the website or Shopee, was on the website.
A second order must come more than 7 days after the first.
Margin 60% is assumed (Weavve gave none). Set-up costs $1,000 (emails) and $500 (whole-bed photos) are estimates.

Table 12 and the second-order detail in 6.2 (item, fabric, colour, size) come from idea1_sheet_breakdown.py.
Figures 7 to 11 come from idea1_report_figures.py.

Needs idea1_v8.py and idea1_slide_numbers.py in the same folder.
Reads ~/Desktop/Weavve_Clean_Data (or SRC_DIR).
Writes ~/Desktop/idea1_report_numbers.csv (or REPORT_CSV).
Run:  python idea1_report_numbers.py
"""
import os
import math
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_CSV = os.environ.get("REPORT_CSV", os.path.expanduser("~/Desktop/idea1_report_numbers.csv"))

# Shared set-up from the slide script: newcomers (nw), repeat orders (rep), the Sep 2022 to Aug 2024
# cohort (c), first-order lines with item and fabric (fo), later lines (lb), File D (D), V and R from idea1_v8.py
exec(open(os.path.join(HERE, "idea1_slide_numbers.py")).read().split("sec_g = sec.reindex")[0])

out = []
def put(table, item, value):
    out.append({"table": table, "item": item, "value": value})
    print(f"{table:<10} {item:<70} {value}")

def pct(s):
    return round(100 * s.mean(), 1)

print("\n================ Idea 1 report numbers ================\n")

# ---------- Table 10. Website newcomers by year ----------
for w, name in [("W1", "2024"), ("W2", "2025"), ("W3", "2026")]:
    d = nw[nw.w == w]
    put("Table 10", f"{name} newcomers", len(d))
    put("Table 10", f"{name} average first order $", round(d.net.mean(), 2))
    put("Table 10", f"{name} share on the email list %", pct(d.on_list))
    if w != "W3":   # 2026 newcomers cannot yet be followed for a full year
        put("Table 10", f"{name} back within a year %", pct(d.back1))
        put("Table 10", f"{name} year-one sales per newcomer $", round(d.y1.mean(), 2))

# ---------- Table 11. Newcomers by first order ----------
spend2 = x[x.age < 730].groupby("person_id").net.sum()   # every order in the first two years, first order included
cc = c.copy()
cc["s2"] = spend2.reindex(cc.index)
l26 = nw[(nw.w == "W3") & nw.on_list]
groups = [(g, cc.entry == g, l26.entry == g) for g in cc.entry.unique()]
groups += [("Sheet starters", cc.sf, l26.sf), ("Other newcomers", ~cc.sf, ~l26.sf)]
for g, m, m26 in groups:
    s = cc[m]
    put("Table 11", f"{g}, share of 2026 list newcomers %", round(100 * m26.mean(), 1))
    put("Table 11", f"{g}, people Sep 2022 to Aug 2024", len(s))
    put("Table 11", f"{g}, first order $", round(s.net.mean(), 1))
    put("Table 11", f"{g}, two-year sales per person $", round(s.s2.mean(), 1))
    put("Table 11", f"{g}, back within two years %", pct(s.back2))

# Sheet set types and fabrics, 6.2 text
D2 = D[["sku", "tier_3_category"]]
set_type = fo[fo.item == "Set"].merge(D2, on="sku", how="left").groupby("order_id").tier_3_category \
    .agg(lambda z: z.dropna().iloc[0] if z.notna().any() else "Other")
ss = cc[cc.sg == "Sheet set"]
t = ss.order_id.map(set_type).fillna("Other")
for k_, v_ in (100 * t.value_counts(normalize=True)).round(1).items():
    put("6.2 text", f"set starters by set type, {k_} %", v_)
for k_, v_ in (100 * ss.assign(t=t).groupby("t").back2.mean()).round(1).items():
    put("6.2 text", f"set starters back within two years, {k_} %", v_)
ss26 = l26[l26.entry == "Sheet set only"]
fab = fo[(fo.item == "Set") & fo.order_id.isin(ss26.order_id)].groupby("order_id").fabric \
    .agg(lambda z: "/".join(sorted(set(z.dropna()))) or "unknown")
for k_ in ["Signature TENCEL", "Everyday TENCEL", "Cotton"]:
    put("6.2 text", f"2026 list newcomers whose first set included {k_} %", round(100 * fab.str.contains(k_).sum() / len(l26), 1))

# ---------- Table 13. When sheet starters' second orders came ----------
gap = sec.reindex(cc[cc.sf].index).dropna()
gap = gap[gap < 730]
put("Table 13", "sheet starters back within two years", len(gap))
put("Table 13", "second orders on day 8 to 18 %", pct(gap <= 18))
put("Table 13", "second orders on day 19 to 364 %", pct((gap > 18) & (gap < 365)))
put("Table 13", "second orders on day 365 or later %", pct(gap >= 365))
put("Table 13", "median day of the second order", gap.median())

# ---------- Table 14. First order by what it held ----------
for w, name in [("W2", "2025"), ("W3", "2026")]:
    d = nw[nw.w == w]
    put("Table 14", f"{name} first order, whole bed $", round(d[d.wb].net.mean(), 2))
    put("Table 14", f"{name} first order, sheets only $", round(d[d.entry.isin(["Sheet set only", "Sheet separates only"])].net.mean(), 2))
    put("Table 14", f"{name} first order, any other $", round(d[~d.wb].net.mean(), 2))
f5e = R["F5e sheet-only starters buying bedding within 6 months"]["buy bedding within 6 months %"]
put("Table 14", "sheet-only starters buying bedding within 6 months, 2025 %", f5e["W2"])
put("Table 14", "sheet-only starters buying bedding within 6 months, 2026 Sep to Feb %", f5e["W3 Sep-Feb"])

# ---------- Table 15. Whole-bed share with and without a welcome code ----------
for w, name in [("W1", "2024"), ("W2", "2025"), ("W3", "2026")]:
    d = nw[nw.w == w]
    put("Table 15", f"{name} whole-bed share, welcome code %", pct(d[d.welcome].wb))
    put("Table 15", f"{name} whole-bed share, no welcome code %", pct(d[~d.welcome].wb))

# ---------- Table 17. What Idea 1 is worth a year ----------
L5 = nw[(nw.w == "W2") & nw.on_list & nw.sf]
L6 = nw[(nw.w == "W3") & nw.on_list & nw.sf]
a5, a6, a5y = L5[L5.follow >= 182], L6[L6.follow >= 182], L5[L5.follow >= 365]
r6_25, r6_26, r12_25 = 100 * a5.b6.mean(), 100 * a6.b6.mean(), 100 * a5y.back1.mean()
ret = nw[nw.w.isin(["W1", "W2"]) & nw.back1 & nw.sf].index
val1 = rep[rep.person_id.isin(ret) & (rep.age < 365)].groupby("person_id").net.sum()
x1 = len(L6) * (r6_25 - r6_26) / 100 * (r12_25 / r6_25)
put("Table 17", "Opp 1, 2026 sheet starters on the list a year", len(L6))
put("Table 17", "Opp 1, back within 6 months, 2025 %", round(r6_25, 2))
put("Table 17", "Opp 1, back within 6 months, 2026 %", round(r6_26, 2))
put("Table 17", "Opp 1, gap in points", round(r6_25 - r6_26, 2))
put("Table 17", "Opp 1, six months to a year, 2025 back within a year %", round(r12_25, 2))
put("Table 17", "Opp 1, six months to a year ratio", round(r12_25 / r6_25, 3))
put("Table 17", "Opp 1, extra people back a year", round(x1, 1))
put("Table 17", "Opp 1, sales per extra person, returners in 2024 and 2025", len(val1))
put("Table 17", "Opp 1, sales per extra person $", round(val1.mean(), 1))
put("Table 17", "Opp 1, extra sales a year $", round(x1 * val1.mean()))
put("Table 17", "Opp 1, gross profit at 60% $", round(x1 * val1.mean() * M))

w5, w6 = nw[(nw.w == "W2") & nw.welcome], nw[(nw.w == "W3") & nw.welcome]
gap2 = w5.wb.mean() - w6.wb.mean()
x2 = len(w6) * gap2
b2w = nw[(nw.w == "W2") & nw.wb]
add_item = k[k.order_id.isin(b2w.order_id) & (k.category == "2. Bedding")].groupby("order_id").net.sum().mean()
shrink = R["F3c premium Sep 2022-Aug 2024"]["same-size extra 2yr after-spend"] / R["F3c premium Sep 2022-Aug 2024"]["raw extra 2yr after-spend"]
later = (V["Whole bed"]["y1"] - V["Whole bed"]["first"] - (V["Other"]["y1"] - V["Other"]["first"])) * shrink
per_switch = add_item + later
put("Table 17", "Opp 2, 2026 welcome-code newcomers", len(w6))
put("Table 17", "Opp 2, whole-bed share gap, 2025 minus 2026, points", round(100 * gap2, 2))
put("Table 17", "Opp 2, extra whole-bed first orders a year", round(x2, 1))
put("Table 17", "Opp 2, bedding added to the first order $", round(add_item, 1))
put("Table 17", "Opp 2, later sales kept after same-size check $", round(later, 1))
put("Table 17", "Opp 2, value per switch $", round(per_switch, 1))
put("Table 17", "Opp 2, extra sales a year $", round(x2 * per_switch))
put("Table 17", "Opp 2, gross profit at 60% $", round(x2 * per_switch * M))

base = nw[nw.w == "W3"]
put("Table 17", "Lens 5, all 2026 newcomers", len(base))
put("Table 17", "Lens 5, points more back, Opp 1", round(100 * x1 / len(base), 1))
put("Table 17", "Lens 5, sales per newcomer, Opp 2 $", round(x2 * per_switch / len(base), 1))
for m_ in [0.5, 0.6, 0.7]:
    tot = (x1 * val1.mean() + x2 * per_switch) * m_
    put("Table 17", f"total gross profit at {int(m_ * 100)}% margin $", round(tot))
    put("Table 17", f"total after $1,500 set-up at {int(m_ * 100)}% margin $", round(tot - 1500))

def p_two_props(a, b):
    p = (a.sum() + b.sum()) / (len(a) + len(b))
    z = (a.mean() - b.mean()) / math.sqrt(p * (1 - p) * (1 / len(a) + 1 / len(b)))
    return round(math.erfc(abs(z) / math.sqrt(2)), 2)

put("6.8 limits", "p-value, back within 6 months, 2025 vs 2026 sheet starters", p_two_props(a5.b6, a6.b6))
put("6.8 limits", "p-value, whole-bed share, 2025 vs 2026 welcome-code newcomers", p_two_props(w5.wb, w6.wb))
put("Table 18", "break-even, Opp 1 extra returners a year for $1,000 set-up", round(1000 / (val1.mean() * M), 1))
put("Table 18", "break-even, Opp 2 extra whole-bed orders a year for $500 set-up", round(500 / (per_switch * M), 1))

# ---------- Table 18. Test sizes, two proportions, 80% power, 5% two-sided ----------
def n_per_group(p1, p2):
    pb = (p1 + p2) / 2
    za, zb = 1.96, 0.8416
    return math.ceil((za * math.sqrt(2 * pb * (1 - pb)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 / (p1 - p2) ** 2)

def smallest_lift(n1, n2, p1):
    for d in range(1, 400):
        p2 = p1 + d / 1000
        pb = (n1 * p1 + n2 * p2) / (n1 + n2)
        se0 = math.sqrt(pb * (1 - pb) * (1 / n1 + 1 / n2))
        se1 = math.sqrt(p1 * (1 - p1) / n2 + p2 * (1 - p2) / n1)
        if (p2 - p1 - 1.96 * se0) / se1 >= 0.8416:
            return round(100 * (p2 - p1), 1)

put("Table 18", "Test A, people per group to see 13.4% vs 16.3%", n_per_group(round(r6_26, 1) / 100, round(r6_25, 1) / 100))
put("Table 18", "Test A, smallest lift seen with one year split 50/50, points", smallest_lift(len(L6) // 2, len(L6) - len(L6) // 2, r6_26 / 100))
put("Table 18", "Test A, smallest lift seen with two years split 50/50, points", smallest_lift(len(L6), len(L6), r6_26 / 100))
put("Table 18", "Test B, people per group to see 7.9% vs 9.5%", n_per_group(round(100 * w6.wb.mean(), 1) / 100, round(100 * w5.wb.mean(), 1) / 100))

pd.DataFrame(out).to_csv(REPORT_CSV, index=False)
print(f"\nsaved {len(out)} numbers to {REPORT_CSV}")
