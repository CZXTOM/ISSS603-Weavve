"""Idea 2, size of the prize for the VIP voucher test, final report section 7.7 and slide 8.

Top 10% = website buyers ranked by website net sales in one Weavve year.
Years run Sep to Aug and are named by the year they end in, so 2025 = Sep 2024 to Aug 2025.
A returner is a top 10% buyer who bought on the website again in the next year.

The voucher is one 10% offer capped at $20, assumed used by every VIP who comes back.
Margin 50% and set-up $500 are planning assumptions. Weavve gave no margin.
The lifts 4.3 and 7.2 points come from the team's Snooze Club analysis, report source [17].
They are not proven, so a no-lift case and the break-even are shown too.

Reads ~/Desktop/Weavve_Clean_Data (or SRC_DIR).
Run:  python idea2_size.py
"""
import os
import pandas as pd

DIR = os.environ.get("SRC_DIR", os.path.expanduser("~/Desktop/Weavve_Clean_Data"))
MARGIN, VOUCHER, SETUP = 0.50, 20, 500
LIFTS = {"No lift": 0.0, "Middle case": 0.043, "High case": 0.072}

O = pd.read_excel(os.path.join(DIR, "C_Orders_clean.xlsx"), sheet_name="orders")
W = O[O.in_customer_scope & O.is_purchase & (O.channel_detail == "Own store")].copy()
W["wy"] = W.order_date.dt.year + (W.order_date.dt.month >= 9)


def cohort(y):
    cur = W[W.wy == y].groupby("person_id").net.sum().sort_values(ascending=False)
    n = round(len(cur) * 0.10)
    top = cur.iloc[:n]
    ret = W[(W.wy == y + 1) & W.person_id.isin(top.index)].groupby("person_id").net.sum()
    print(f"Top 10% of Sep {y - 1} to Aug {y}: {n} buyers, ${top.sum():,.0f} = {top.sum() / cur.sum():.1%} of website sales")
    print(f"  back on the website the next year: {len(ret)} = {len(ret) / n:.1%}, spend per returner ${ret.mean():,.0f}")
    return n, len(ret) / n, ret.mean()


cohort(2024)                               # slide 7 return figure, 21.4%
n, base, spend = cohort(2025)              # latest cohort used for the size of the prize, 193 buyers

value = spend * MARGIN                     # gross profit from one extra VIP coming back
print(f"\nSize of the prize, {n} VIPs, base return {base:.1%}, ${spend:,.0f} x {MARGIN:.0%} = ${value:,.1f} per extra returner")
for name, lift in LIFTS.items():
    extra = n * lift
    cost = n * (base + lift) * VOUCHER + SETUP
    profit = extra * value - cost
    print(f"  {name:<12} +{lift * 100:.1f} points, {extra:4.1f} more VIPs back, profit {'-' if profit < 0 else '+'}${abs(profit):,.0f} a year")
be = (n * base * VOUCHER + SETUP) / (value - VOUCHER)
print(f"  Break-even   {be:.1f} more VIPs back, a lift of {be / n * 100:.1f} points")
