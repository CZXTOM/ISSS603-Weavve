"""Recompute existing analysis formulas from the verified shared cleaned dataset.

Run through notebook 05. Observational comparisons and scenario assumptions
remain distinct from causal evidence or validation of a report.
"""

import math
import re
import statistics
from collections import defaultdict
from datetime import date, timedelta

from weavve.final.data import order_view, rows, text, money, day

COMPANY, OSCO = "P000034", "P013881"
CUTOFF = date(2026, 8, 28)
res = {}
orders = order_view(drop_cancelled=True, drop_repeated=True, positive_only=True)


def is_web(o):
    return "Online Store" in o["original_channels"]


def codes(o):
    return {text(r["Discount code"]).upper() for r in o["rows"] if text(r["Discount code"])}


def pct(a, b):
    return round(100 * a / b, 1) if b else None


people = defaultdict(list)
for o in orders:
    if o["person"] not in (COMPANY, OSCO) and (is_web(o) or o["channel"] == "Shopee"):
        people[o["person"]].append(o)
first = {p: min(os, key=lambda o: (o["date"], o["order"])) for p, os in people.items()}
starters = {p: f for p, f in first.items() if is_web(f)}  # website starters, as in the team's count
club = {p for p, f in starters.items() if any(c.startswith("LWC") for c in codes(f))}


def share_club(lo, hi):
    coh = [p for p, f in starters.items() if lo <= f["date"] <= hi]
    return {"people": len(coh), "club_code_pct": pct(sum(p in club for p in coh), len(coh))}


# Table 17 and Table 19: club sign-up code on the first website order
res["club_code_first_order"] = {
    "2024_27apr_28aug": share_club(date(2024, 4, 27), date(2024, 8, 28)),
    "2026_27apr_28aug": share_club(date(2026, 4, 27), date(2026, 8, 28)),
    "2023_h2": share_club(date(2023, 7, 1), date(2023, 12, 31)),
    "2024_h1": share_club(date(2024, 1, 1), date(2024, 6, 30)),
}

# Section 8.1 and Table 17: website starters 27 Apr 2023 to 26 Aug 2024, repeats counted after the first 7
# days
win = {p: f for p, f in starters.items() if date(2023, 4, 27) <= f["date"] <= date(2024, 8, 26)}
ten_codes = {"WEAVVE10OFF": "weavve10off", "WHWA10OI": "whwa10oi"}
back = defaultdict(lambda: [0, 0])
two_year = defaultdict(lambda: [0, 0, 0.0, 0])  # returners, repeat orders, repeat net sales, people
per_returner, per_order = defaultdict(list), defaultdict(list)
y1_repeat = [0, 0.0]
for p, f in win.items():
    c = codes(f)
    group = "members" if p in club else next((v for k, v in ten_codes.items() if k in c), "non_members")
    band = "200_plus" if f["net"] >= 200 else "under_200"
    rep1 = [
        o for o in people[p] if f["date"] + timedelta(days=7) < o["date"] <= f["date"] + timedelta(days=365)
    ]
    rep2 = [
        o for o in people[p] if f["date"] + timedelta(days=7) < o["date"] <= f["date"] + timedelta(days=730)
    ]
    for key in (f"{group}_{band}", f"{group}_all") + (
        () if group == "members" else (f"all_non_members_{band}",)
    ):
        back[key][0] += 1
        back[key][1] += int(bool(rep1))
    if rep1:
        y1_repeat[0] += 1
        y1_repeat[1] += sum(o["net"] for o in rep1)
    m = "members" if p in club else "non_members"
    t = two_year[m]
    t[3] += 1
    if rep2:
        t[0] += 1
        t[1] += len(rep2)
        t[2] += sum(o["net"] for o in rep2)
        per_returner[m].append(len(rep2))
        per_order[m] += [o["net"] for o in rep2]


def gap_ci(a, b):
    """Difference in means, members minus non-members, with a 95% interval (Welch)."""
    d = statistics.fmean(a) - statistics.fmean(b)
    se = math.sqrt(statistics.variance(a) / len(a) + statistics.variance(b) / len(b))
    return {"gap": round(d, 2), "ci95": [round(d - 1.96 * se, 2), round(d + 1.96 * se, 2)]}


res["back_within_a_year_after_7_days"] = {
    k: {"people": n, "pct": pct(b, n)} for k, (n, b) in sorted(back.items())
}


def share_gap(a, b):
    """Difference in shares, a minus b, in points, with a 95% interval."""
    (na, ba), (nb, bb) = a, b
    pa, pb = ba / na, bb / nb
    se = math.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)
    return {"gap": round(100 * (pa - pb), 1), "ci95": [round(100 * (pa - pb - 1.96 * se), 1), round(100 * (pa - pb + 1.96 * se), 1)]}


# Section 11: the return gain Recommendation 2 is sized on, members against non-members with a first order of
# $200 or more, and whether it could be chance
res["reward_ready_return_gap"] = share_gap(back["members_200_plus"], back["all_non_members_200_plus"])

# Section 6.4: one-year return by the discount on the first website order, same starters and window. Members used
# the club sign-up code. "Discount" is any other code or price reduction. The rest paid full price.
by_disc = defaultdict(lambda: [0, 0])
for p, f in win.items():
    g = "members" if p in club else "discount" if codes(f) or f["discount"] > 0.005 else "full_price"
    by_disc[g][0] += 1
    by_disc[g][1] += int(any(f["date"] + timedelta(days=7) < o["date"] <= f["date"] + timedelta(days=365) for o in people[p]))
res["back_within_a_year_by_first_discount"] = {g: {"people": n, "pct": pct(b, n)} for g, (n, b) in sorted(by_disc.items())}
res["discount_against_full_price_gap"] = share_gap(by_disc["discount"], by_disc["full_price"])

# Section 6.4: of website starters (January 2023 to 28 August 2024) who bought again within two years, the share
# whose first repeat came within 90 days. Repeats count after the first 7 days.
returned = within_90 = 0
for p, f in starters.items():
    if not date(2023, 1, 1) <= f["date"] <= date(2024, 8, 28):
        continue
    later = sorted(o["date"] for o in people[p] if f["date"] + timedelta(days=7) < o["date"] <= f["date"] + timedelta(days=730))
    if later:
        returned += 1
        within_90 += int(later[0] <= f["date"] + timedelta(days=90))
res["returners_back_within_90_days_pct"] = pct(within_90, returned)
res["two_year_repeats"] = {
    k: {"returners": r, "repeat_orders_per_returner": round(n / r, 2), "net_per_repeat_order": round(s / n)}
    for k, (r, n, s, _) in two_year.items()
}
res["two_year_gaps"] = {
    "repeat_orders_per_returner": gap_ci(per_returner["members"], per_returner["non_members"]),
    "net_per_repeat_order": gap_ci(per_order["members"], per_order["non_members"]),
}
res["year1_repeat_sales_per_returner"] = round(y1_repeat[1] / y1_repeat[0])

# Table 18: pop-up codes on first website orders in 2026, using Weavve's own code groups in File E
group_of = {
    text(r["Code Name"]).upper(): text(r["Group"])
    for r in rows("E", "Discount Detail by Code")
    if text(r["Code Name"])
}
popup = {"Alia", "Welcome8Alia", "Welcome10Alia"}
coh26 = [f for f in starters.values() if date(2026, 1, 1) <= f["date"] <= CUTOFF]
res["popup_code_first_order_2026"] = {
    "people": len(coh26),
    "popup_code_pct": pct(sum(any(group_of.get(c) in popup for c in codes(f)) for f in coh26), len(coh26)),
    "club_code_pct": pct(sum(any(c.startswith("LWC") for c in codes(f)) for f in coh26), len(coh26)),
}

# Table 18: share of new website customers, 27 April to 28 August 2026, whose first order used a pop-up code (codes
# starting AL, and the WC8ALFR and WC10ALFR codes the pop-up emails an hour later) or the club sign-up code (LWC)
coh = [f for f in starters.values() if date(2026, 4, 27) <= f["date"] <= CUTOFF]
res["first_order_codes_27apr_28aug_2026"] = {
    "people": len(coh),
    "popup_pct": pct(sum(any(c.startswith(("AL", "WC8ALFR", "WC10ALFR")) for c in codes(f)) for f in coh), len(coh)),
    "club_pct": pct(sum(any(c.startswith("LWC") for c in codes(f)) for f in coh), len(coh)),
}

# Table 18: pop-up against club sign-up codes, from Weavve's own code report in File E
by_year = {(text(r["Group"]), int(r["Year"])): r for r in rows("E", "Discount by Year") if r["Year"]}
res["file_e_codes_redeemed"] = {
    "alia_first_issued": min(text(r["First Issued"])[:10] for (g, _), r in by_year.items() if g == "Alia"),
    "alia_2025": int(by_year[("Alia", 2025)]["Codes Redeemed"]),
    "club_signup_2025": int(by_year[("Loyaltywelcome", 2025)]["Codes Redeemed"]),
    "club_signup_2026_redeemed": int(by_year[("Loyaltywelcome", 2026)]["Codes Redeemed"]),
    "club_signup_2026_released": int(by_year[("Loyaltywelcome", 2026)]["Codes Released"]),
}

# Table 18: weekend share of website orders
wk = defaultdict(lambda: [0, 0])
for o in orders:
    if is_web(o) and o["date"].year in (2025, 2026) and o["date"] <= CUTOFF:
        wk[o["date"].year][0] += 1
        wk[o["date"].year][1] += int(o["date"].weekday() >= 5)
res["weekend_share_of_website_orders"] = {y: pct(b, n) for y, (n, b) in sorted(wk.items())}

# Table 18: vouchers members made by swapping points (WHLP money off, WHFP free product), never used, by year
# made. Birthday (BDAY) and referral codes are issued automatically, so they are not vouchers a member made.
F = rows("F", "Redemptions")
points_codes = {
    text(r["discount_code"]).upper()
    for r in F
    if text(r["discount_code"]).upper().startswith(("WHLP", "WHFP"))
}
smallest_codes = {
    text(r["discount_code"]).upper()
    for r in F
    if text(r["discount_code"]).upper().startswith("WHLP") and r["points"] == -250
}
# Section 8: the smallest money-off reward members can swap points for, with its points and value (File F)
money_off = [
    (-int(r["points"]), int(re.search(r"\$(\d+)", text(r["description"])).group(1)))
    for r in F
    if text(r["discount_code"]).upper().startswith("WHLP") and r["points"] and re.search(r"\$\d+", text(r["description"]))
]
res["smallest_reward"] = dict(zip(("points", "value"), min(money_off)))
made = defaultdict(lambda: [0, 0])
for r in F:
    d = day(r["date"])
    if d and d <= CUTOFF and text(r["discount_code"]).upper() in points_codes:
        made[d.year][0] += 1
        made[d.year][1] += int(not (r["times_used"] or 0))
res["vouchers_never_used_pct"] = {
    y: {"made": n, "never_used_pct": pct(u, n)} for y, (n, u) in sorted(made.items())
}

# Table 17: members who joined with their first order (club code), 26 Apr 2023 to 28 Aug 2026. In the data
# period the smallest reward was 250 points, sign-up gave 50 and each $1 earned 1 point, so earning it takes
# $200 of website sales.
members = [p for p in club]
web_orders = {p: [o for o in people[p] if is_web(o)] for p in members}
earned = [p for p in members if sum(o["net"] for o in web_orders[p]) >= 200]
used = [p for p in members if any(codes(o) & points_codes for o in web_orders[p])]
res["members_reward"] = {
    "members": len(members),
    "earn_smallest_reward_pct": pct(len(earned), len(members)),
    "ever_used_points_voucher_pct": pct(len(used), len(members)),
}

# Table 20 input: reward-ready members (first order $200 or more) whose second website order used a points
# voucher
ready = [p for p in members if starters[p]["net"] >= 200]
second = {
    p: sorted(
        (o for o in web_orders[p] if o["date"] > starters[p]["date"]), key=lambda o: (o["date"], o["order"])
    )
    for p in ready
}
with_second = [p for p in ready if second[p]]
res["reward_ready_second_order"] = {
    "reward_ready_members": len(ready),
    "with_second_website_order": len(with_second),
    "any_points_voucher_pct": pct(
        sum(bool(codes(second[p][0]) & points_codes) for p in with_second), len(with_second)
    ),
    "smallest_reward_pct": pct(
        sum(bool(codes(second[p][0]) & smallest_codes) for p in with_second), len(with_second)
    ),
}

# Table 17: club cost as a share of website net sales, by year (2026 to 28 Aug). Club discounts are the
# sign-up code and points vouchers. Birthday codes are shown apart.
cost = defaultdict(lambda: [0.0, 0.0, 0.0])
for o in orders:
    if not is_web(o) or o["person"] in (COMPANY, OSCO) or o["date"] > CUTOFF or o["date"].year < 2023:
        continue
    c = cost[o["date"].year]
    c[0] += o["net"]
    for r in o["rows"]:
        code, disc = text(r["Discount code"]).upper(), float(-money(r["Discounts"]))
        if code.startswith("LWC") or code in points_codes:
            c[1] += disc
        elif code.startswith("BDAY"):
            c[2] += disc
res["club_cost_share_of_website_net_sales_pct"] = {
    y: {"club": pct(a, n), "birthday": pct(b, n)} for y, (n, a, b) in sorted(cost.items())
}

# Table 17: joins a month, from the club sign-up codes Weavve released (File E)
months = {
    2023: (date(2023, 12, 31) - date(2023, 4, 26)).days / 30.44,
    2024: 12,
    2025: 12,
    2026: (date(2026, 8, 4) - date(2026, 1, 1)).days / 30.44,
}
res["club_joins_a_month"] = {
    y: round(int(by_year[("Loyaltywelcome", y)]["Codes Released"]) / m, 1) for y, m in months.items()
}


# Table 17: emails to loyalty members (File K lists), campaigns with 20 or more recipients
def member_list(name):
    n = name.lower()
    return ("loyal" in n or "member" in n) and not any(
        w in n for w in ("no loyalty", "non-loya", "not member", "not a member")
    )


sends, clicks = defaultdict(float), defaultdict(lambda: [0.0, 0.0])
for r in rows("K"):
    d, n, c = day(r["Send Date"]), r["Total Recipients"], r["Unique Clicks"]
    if d and d <= CUTOFF and n and n >= 20 and member_list(text(r["List"])):
        sends[d] += n
        clicks[d.year][0] += c or 0
        clicks[d.year][1] += n
res["member_email_click_rate_pct"] = {y: round(100 * c / n, 2) for y, (c, n) in sorted(clicks.items())}
res["member_emails_per_send_day"] = {
    y: {"days": len(v), "min": round(min(v)), "max": round(max(v))}
    for y in sorted({d.year for d in sends})
    for v in [[t for d, t in sends.items() if d.year == y]]
}
