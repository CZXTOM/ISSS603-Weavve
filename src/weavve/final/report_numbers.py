"""Turns the check results into the numbers the final report quotes, written as the report prints them.

quotes() rebuilds each quoted number from the check results. compare() looks for each one in the report's Word
file, which stays in data/ with the Weavve files. The repo is public, so the code never holds the report's
numbers.

Profit is extra net sales times the margin, minus any discount cost. The margin is the two thirds implied by
Weavve's 1.5 floor on return on ad spend (report Section 7.3).
"""

import json
import math
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from weavve.paths import DATA

MARGIN = 1 / 1.5

# The business team's Snooze Club plan [17]. Its four measured inputs are the team's own figures, so they stay in
# data/ with the Weavve files (team_snooze_plan.json) and the repo holds none of them. The last two are rules of
# the plan itself.
TEAM_PLAN = DATA / "team_snooze_plan.json"
SNOOZE_PLAN = {
    **(json.loads(TEAM_PLAN.read_text(encoding="utf-8")) if TEAM_PLAN.exists() else {}),
    "extra_off_first_order": 0.02,  # the club code takes 10% off the first order, against 8% for the pop-up
    "reward_value": 12,  # the smallest reward, $12 off
}


def money(v):
    return f"${v:,.0f}"


def k(v):
    return f"${v / 1000:,.0f}k"


def k_range(pair):
    return f"{k(pair[0])} to {k(pair[1])}"


def pct(v, dp=1):
    return f"{v:.{dp}f}%"


def tens(v):
    return money(round(v / 10) * 10)


def profit(sales, cost=0.0):
    return sales * MARGIN - cost


def n_per_group(p1, p2, za=1.959964, zb=0.841621):
    """People per group for a two-proportion test at 80% power and a 5% level, by the class formula."""
    pbar = (p1 + p2) / 2
    num = za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return math.ceil(num**2 / (p2 - p1) ** 2)


def funnel_sums(monthly, year, months):
    rows = [r for r in monthly if r["month"][:4] == str(year) and int(r["month"][5:7]) in months]
    return {key: sum(r[key] for r in rows) for key in ("Sessions", "Add to Cart", "Orders Placed")}


def quotes(R, ads=None, log=None, plan=None):
    """Each number the report quotes that the checks can rebuild, written as the report prints it.

    R holds the check results with text keys, as after a JSON round trip.
    """
    V1, V2, TC, F, monthly = R["recs"], R["inputs"], R["team"], R["rec1"], R["funnel"]
    q = {}

    # Section 6. What we found
    L5, L4, L2 = (
        V1["online_store"]["lens5"],
        V1["online_store"]["lens4"],
        V1["online_store"]["lens2_2024_2025"],
    )
    kept = [L5[y]["kept_from_last_year_pct"] for y in ("2021", "2022", "2023", "2024", "2025")]
    q["6.1 Earlier buyers bring back, of last year"] = f"only {min(kept):.0f}% to {max(kept):.0f}%"
    q["6.1 New buyers in the top tenth, 2025"] = (
        f"{V1['online_store']['lens1_2025']['deciles'][0]['new_pct']}% were new that year"
    )
    q["6.1 New website buyers, 2024"] = f"Weavve won {L5['2024']['new_buyers']:,} new website buyers in 2024"
    q["6.1 New website buyers, 2025, and needed"] = (
        f"it won {L5['2025']['new_buyers']:,} against about "
        f"{L5['2025']['needed_to_stand_still']:,} needed"
    )
    s24, s25 = L5["2024"]["sales_ex_company_osco"], L5["2025"]["sales_ex_company_osco"]
    q["6.1 Website sales fell, 2025"] = (
        f"Website sales fell {100 * (1 - s25 / s24):.0f}% that year, from {k(s24)} to {k(s25)}"
    )
    q["6.1 Buyers lost and gained, 2024 to 2025"] = (
        f"lost {L2['y0_only']['customers']:,} buyers who did not come back and gained "
        f"only {L2['y1_only']['customers']:,}"
    )
    q["6.1 First-year value of starters"] = (
        f"were worth {money(L4['2025']['y1_sales_per_member'])} each in their first year, "
        f"against {money(L4['2024']['y1_sales_per_member'])}"
    )
    q["6.1 Starters, 2025 against 2024"] = f"{L4['2025']['cohort']:,} against {L4['2024']['cohort']:,}"

    NC, DEPTH = V2["newcomers_janaug"], V2["discount_depth_janaug_pct"]
    q["6.2 Newcomers, January to August 2026"] = (
        f"about {round(NC['2026']['newcomers'], -1):,} people made a first purchase"
    )
    for y in ("2023", "2024", "2025", "2026"):
        q[f"Table 10 newcomers {y}"] = f"{NC[y]['newcomers']:,}"
        q[f"Table 10 started on the website {y}"] = pct(100 * NC[y]["started_website"] / NC[y]["newcomers"])
        q[f"Table 10 Shopee discount depth {y}"] = pct(DEPTH[f"Shopee_{y}"])
        q[f"Table 10 website discount depth {y}"] = pct(DEPTH[f"website_{y}"])
    q["6.2 Shopee discount with a seller label"] = (
        f"Over {min(V2['shopee_discount_with_seller_label_pct'].values()):.1f}% of it"
    )
    Y1 = V1["year1_value_per_newcomer"]
    q["6.2 First-year value by starting channel"] = (
        f"A website starter brings {money(Y1['2024_website'])} in the first year, "
        f"against {money(Y1['2025_Shopee'])} to {money(Y1['2024_Shopee'])}"
    )
    q["6.2 Bought on both channels"] = (
        f"Only {V1['both_channels']['both_pct_of_either']}% of website or Shopee buyers"
    )
    base90 = [v["within_90_days_pct"] for v in V2["shopee_starters_later_website_order"].values()]
    q["6.2 Shopee starters with a website order in 90 days"] = (
        f"Only {min(base90):.1f}% to {max(base90):.1f}% of Shopee starters"
    )
    ja = list(range(1, 9))
    f24, f25, f26 = (funnel_sums(monthly, y, ja) for y in (2024, 2025, 2026))
    c0, c1 = f24["Orders Placed"] / f24["Sessions"], f25["Orders Placed"] / f25["Sessions"]
    effect = (f25["Sessions"] - f24["Sessions"]) * (c0 + c1) / 2
    q["6.2 Visits fell"] = f"Visits fell {100 * (1 - f26['Sessions'] / f24['Sessions']):.0f}%"
    q["6.2 Fall in orders explained by visits"] = (
        f"Fewer visits explain " f"{100 * effect / (f25['Orders Placed'] - f24['Orders Placed']):.0f}%"
    )
    mj25, mj26 = funnel_sums(monthly, 2025, [5, 6]), funnel_sums(monthly, 2026, [5, 6])
    q["Table 12 visits in May and June 2026"] = (
        f"were {100 * (mj26['Sessions'] / mj25['Sessions'] - 1):.0f}% above"
    )
    q["Table 12 add-to-cart rate"] = (
        f"fell from {100 * mj25['Add to Cart'] / mj25['Sessions']:.1f}% to "
        f"{100 * mj26['Add to Cart'] / mj26['Sessions']:.1f}%"
    )
    q["6.4 Back within a year, 2025 starters"] = (
        f"Only {L4['2025']['active_y1_pct_after_7_days']}% of the January to August 2025"
    )
    q["6.4 Back within a year, 2024 starters"] = (
        f"down from {L4['2024']['active_y1_pct_after_7_days']}% for the 2024 starters"
    )
    clicks = V1["email_click_rate_pct"]
    q["6.4 Email clicks"] = f"{clicks['2024']:.2f}% in 2024 to {clicks['2026']:.2f}% in 2026"
    klav = V1["j_source_klaviyo_signup_new_website_buyers"]["jan_aug"]
    q["Table 13 buyers from the sign-up forms"] = f"fell from {klav['2024']} to {klav['2026']}"

    # Section 7. Recommendation 1 (our version)
    sign = F["new_signups_website_order_within_90_days"]
    sign_now, sign_2024 = sign["2026"]["pct"] / 100, sign["2024"]["pct"] / 100
    sign_plan = (sign_now + sign_2024) / 2
    signups_year, starters_year = (
        F["reach_2026"]["new_signups_a_year"],
        F["reach_2026"]["shopee_starters_a_year"],
    )
    p_base = sum(base90) / len(base90) / 100
    movers = F["shopee_starters_year1_value"]
    lo, hi = (
        F["mover_gain_year1"]["against_shopee_only_repeat"]["mean"],
        F["mover_gain_year1"]["against_no_repeat"]["mean"],
    )
    gain_lo, gain_hi = Y1["2024_website"] - Y1["2024_Shopee"], Y1["2025_website"] - Y1["2025_Shopee"]
    extra_sign, extra_card = signups_year * (sign_plan - sign_now), starters_year * (0.025 - p_base)
    sales_sign, sales_card = (extra_sign * gain_lo, extra_sign * gain_hi), (extra_card * lo, extra_card * hi)
    shopee_month = V2["shopee_purchases_janaug_2026"] / (7 + 28 / 31)
    parcels_year = shopee_month * 12
    per_parcel = profit(sales_card[0]) / parcels_year
    q["7.3 Sign-up buying, today to planned"] = (
        f"from {100 * sign_now:.1f}% to {100 * sign_plan:.1f}% of new sign-ups"
    )
    q["7.3 Movers spent"] = (
        f"The {movers['website_order_within_90_days']['people']} Shopee buyers who moved on their own spent "
        f"{money(movers['website_order_within_90_days']['mean'])}"
    )
    q["7.3 Others spent"] = (
        f"spent {money(movers['shopee_only_repeat_within_90_days']['mean'])}, and those who did not spent "
        f"{money(movers['no_repeat_within_90_days']['mean'])}"
    )
    q["7.3 Each moved buyer adds"] = f"each moved buyer adds {money(lo)} to {money(hi)}"
    q["Table 15 sign-ups a year"] = f"{signups_year:,} new sign-ups"
    q["Table 15 new Shopee buyers a year"] = f"{starters_year:,} new Shopee buyers"
    q["Table 15 extra buyers, sign-up route"] = f"About {extra_sign:,.0f}"
    q["Table 15 extra buyers, parcel card"] = f"About {extra_card:,.0f}"
    q["Table 15 sales, sign-up route"] = k_range(sales_sign)
    q["Table 15 profit, sign-up route"] = k_range([profit(v) for v in sales_sign])
    q["Table 15 sales, parcel card"] = k_range(sales_card)
    q["Table 15 profit, parcel card"] = k_range([profit(v) for v in sales_card])
    q["Table 15 card pays if it costs under"] = f"${per_parcel:.2f} a parcel"
    q["7.3 Shopee parcels a year"] = f"about {round(parcels_year, -2):,.0f} a year"
    q["7.3 Profit per point of sign-up buying"] = (
        f"{k(signups_year * 0.01 * gain_lo * MARGIN)} to "
        f"{k(signups_year * 0.01 * gain_hi * MARGIN)} of profit"
    )
    n_sign, n_card, n_emails = (
        n_per_group(sign_now, sign_plan),
        n_per_group(p_base, 0.025),
        n_per_group(sign_plan, sign_2024),
    )
    months_emails = 2 * n_emails / (signups_year / 12)
    q["Table 16 test A size"] = (
        f"{n_sign:,} sign-ups per side, about {2 * n_sign / (signups_year / 12):.0f} months"
    )
    q["Table 16 test C size"] = (
        f"{n_card:,} parcels per group, about {2 * n_card / shopee_month:.0f} months at "
        f"{shopee_month:.0f} Shopee purchases a month"
    )
    q["Table 16 test D size"] = f"{n_emails:,} sign-ups per side, about {months_emails:.0f} months"
    q["9 Welcome-email test months"] = f"Months 4 to {3 + math.ceil(months_emails)}"

    # Sections 7.3 and 11. The margin: what Weavve's ad account counts as a conversion
    conv = V2["ad_conversions"]
    q["7.3 Value of one ad conversion"] = (
        f"values the average conversion at {money(conv['value_per_conversion'])}, "
        f"less than one average website order of {money(conv['website_mean_order_since_2019'])}"
    )
    q["11 Ad conversions per click"] = (
        f"counts {conv['non_brand_conversions_per_click_pct']:.1f}% of clicks "
        "on keywords without the Weavve name as conversions, "
        f"against {conv['site_orders_per_session_pct']:.1f}% of website visits ending in an order"
    )

    # Section 8. Recommendation 2: the team's Snooze Club numbers we rebuilt, and the projection
    joins = TC["club_joins_a_month"].values()
    q["Table 17 joins a month"] = f"About {min(joins):.0f} to {max(joins):.0f} people join a month"
    cm = TC["member_email_click_rate_pct"]
    q["Table 17 member email clicks"] = f"{cm['2023']:.2f}% in 2023 to {cm['2026']:.2f}% in 2026"
    rep = TC["two_year_repeats"]
    q["Table 17 repeat orders"] = (
        f"{rep['members']['repeat_orders_per_returner']:.2f} more times in two years, against "
        f"{rep['non_members']['repeat_orders_per_returner']:.2f}"
    )
    q["Table 17 extra spend per repeat order"] = (
        f"Members spend ${TC['two_year_gaps']['net_per_repeat_order']['gap']:.0f} more"
    )
    cost = TC["club_cost_share_of_website_net_sales_pct"]
    q["Table 17 club cost, every year"] = (
        f"under {math.floor(max(v['club'] for v in cost.values())) + 1}% of website sales"
    )
    q["Table 17 club cost, 2026"] = f"and {cost['2026']['club']}% in 2026"
    c10 = TC["back_within_a_year_after_7_days"]
    q["8.1 Other 10% codes"] = (
        f"came back at {c10['weavve10off_200_plus']['pct']}% and {c10['whwa10oi_200_plus']['pct']}%"
    )
    e = TC["file_e_codes_redeemed"]
    q["Table 18 codes redeemed in 2025"] = (
        f"redeemed {e['alia_2025']} of its codes and {e['club_signup_2025']} of the club's"
    )
    v = TC["vouchers_never_used_pct"]
    q["Table 18 vouchers never used"] = (
        f"never used {v['2025']['never_used_pct']:.0f}% of the vouchers they made in 2025, "
        f"against {v['2023']['never_used_pct']:.0f}% in 2023"
    )
    snz = V2["snooze_inputs"]
    new, join_now, ready_now, first = (
        snz["new_website_customers"],
        snz["club_code_on_first_order_pct"] / 100,
        snz["first_order_200_plus_pct"] / 100,
        snz["first_order_mean"],
    )
    join_2024, per_returner = (
        TC["club_code_first_order"]["2024_h1"]["club_code_pct"] / 100,
        TC["year1_repeat_sales_per_returner"],
    )

    def snooze(join_rate):
        members_now, members = new * join_now, new * join_rate
        ready_now_n, ready = members_now * ready_now, members * SNOOZE_PLAN["ready_with_part_3"]
        back = (ready - ready_now_n) * SNOOZE_PLAN["back_gain"]
        return {
            "members_now": members_now,
            "members": members,
            "ready_now": ready_now_n,
            "ready": ready,
            "back": back,
            "sales": back * per_returner,
            "cost": (members - members_now) * SNOOZE_PLAN["extra_off_first_order"] * first
            + (ready - ready_now_n) * SNOOZE_PLAN["rewards_used"] * SNOOZE_PLAN["reward_value"],
        }

    b, up = snooze(SNOOZE_PLAN["join_with_part_2"]), snooze(join_2024)
    per1000 = {key: b[key] * 1000 / new for key in ("sales", "cost")}
    q["Table 20 join rate today"] = f"Join the club: {100 * join_now:.1f}% today"
    q["Table 20 reward in reach today"] = f"Members with a reward in reach: {100 * ready_now:.1f}% today"
    q["Table 20 members today"] = f"{b['members_now']:.0f}"
    q["Table 20 members with part 2"] = f"{b['members']:.0f}"
    q["Table 20 in reach today"] = f"{b['ready_now']:.1f}"
    q["Table 20 in reach with part 3"] = f"{b['ready']:.1f}"
    q["Table 20 extra members back"] = f"{b['back']:.1f}"
    q["Table 20 profit formula"] = f"{money(b['sales'])} × 2/3 − {money(b['cost'])}"
    q["Table 20 profit at two thirds"] = f"About {tens(profit(b['sales'], b['cost']))}"
    q["8.4 Upside if joining returns to its 2024 rate"] = (
        f"or about {tens(profit(up['sales'], up['cost']))} if joining returns"
    )
    q["8.4 Break-even range"] = (
        f"breaks even at a margin of {100 * b['cost'] / b['sales']:.0f}% "
        f"to {100 * up['cost'] / up['sales']:.0f}%"
    )
    q["8.4 Each 1,000 extra website buyers"] = (
        f"adds about {tens(profit(per1000['sales'], per1000['cost']))} more"
    )
    q["Table 22 sign-up measure now"] = f"{100 * sign_now:.1f}%, sign-ups January to May 2026"
    q["Table 22 sign-up measure target"] = f"{100 * sign_plan:.1f}%, half way back to 2024"

    # Section 10. Paid search, from the campaign snapshot when it is in the data folder
    if ads and log and plan:
        C = ads["campaign"]
        kw = ads["keywords"]
        ex = [x for x in kw if x["match"] == "EXACT"]
        ph = [x for x in kw if x["match"] == "PHRASE"]
        rated = [x for x in kw if x["qs"] is not None]

        def period(a, z):
            rows = [r for r in ads["daily"] if a <= r["date"] <= z]
            views, clicks_ = sum(r["impressions"] for r in rows), sum(r["clicks"] for r in rows)
            return views, clicks_, 100 * clicks_ / views, views / len(rows)

        first9, r1, r2, r3, last9 = (
            period("2026-10-13", "2026-10-21"),
            period("2026-10-19", "2026-10-21"),
            period("2026-10-22", "2026-10-23"),
            period("2026-10-24", "2026-10-30"),
            period("2026-10-22", "2026-10-30"),
        )
        rewrites = [e for e in log if e.get("lever") == "Rewrite"]
        new_lines = {(e["group"][0], e["new_text"]) for e in rewrites}
        kwd = {(x["text"], x["match"]): x for x in kw}
        q["10 Campaign totals"] = (
            f"{C['clicks']} clicks from {C['impressions']:,} views, a "
            f"{100 * C['clicks'] / C['impressions']:.1f}% click rate, for S${C['cost']:.2f}"
        )
        q["10 Weavve's past click rate"] = f"below Weavve's past {plan['baseline']['ctr']}%"
        q["10 Exact-match click rate"] = (
            "Exact-match keywords ran at "
            f"{100 * sum(x['clicks'] for x in ex) / sum(x['impressions'] for x in ex):.1f}%"
        )
        q["10 Phrase-match click rate"] = (
            f"for reach ran at {100 * sum(x['clicks'] for x in ph) / sum(x['impressions'] for x in ph):.1f}%"
        )
        q["10.3 First nine days, click rate"] = f"earned a {first9[2]:.1f}% click rate"
        q["10.3 First nine days, views a day"] = f"Its {first9[3]:.0f} views a day"
        q["10.3 Last nine days"] = f"about {last9[3]:.0f} views a day at a {last9[2]:.1f}% click rate"
        q["10.3 Expected click rate below average"] = (
            f"below average on {sum(x['exp_ctr'] == 'BELOW_AVERAGE' for x in rated)} of the "
            f"{len(rated)} rated keywords"
        )
        q["10.3 Landing page below average"] = (
            f"below average on {sum(x['landing'] == 'BELOW_AVERAGE' for x in rated)} of them"
        )
        q["10.3 Views lost"] = (
            f"lost {C['lost_rank']:.0f}% of possible views to low ad rank "
            f"and {C['lost_budget']:.0f}% to budget"
        )
        wb, cs = kwd[("where to buy bed sheets singapore", "EXACT")], kwd[("cotton bed sheet set", "EXACT")]
        q["10.3 where to buy bed sheets singapore"] = (
            f"earned {100 * wb['clicks'] / wb['impressions']:.1f}% against"
        )
        q["10.3 cotton bed sheet set"] = f"and earned {100 * cs['clicks'] / cs['impressions']:.1f}%"
        nv = sum(a["impressions"] for a in ads["assets"] if (a["ad_group"][0], a["text"]) in new_lines)
        nc = sum(a["clicks"] for a in ads["assets"] if (a["ad_group"][0], a["text"]) in new_lines)
        q["Table 26 round 1, click rate"] = f"The click rate held at {r1[2]:.1f}%"
        q["Table 26 round 1, new headlines"] = (
            f"new headlines {nv:,} times against {sum(e['before']['impressions'] for e in rewrites)} "
            f"for the old ones, and they earned {nc} clicks"
        )
        q["Table 26 round 2"] = (
            f"from about {r1[3]:.0f} to about {r2[3]:.0f}, and the click rate fell to {r2[2]:.1f}%"
        )
        q["Table 26 round 3"] = f"The click rate stayed at {r3[2]:.1f}%"
    return q


STRAIGHT = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u00a0": " "})
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _words(element):
    return "".join(t.text or "" for t in element.iter(W + "t")).translate(STRAIGHT)


def report_text(path):
    """The report's text from its Word file, in full and table by table, keyed by table number."""
    with ZipFile(path) as z:
        body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
    lines, tables, caption = [], {}, None
    for element in body:
        if element.tag == W + "p":
            lines.append(_words(element))
            m = re.match(r"Table (\d+)\.", lines[-1])
            caption = int(m.group(1)) if m else caption
        elif element.tag == W + "tbl":
            cells = "\n".join(_words(p) for p in element.iter(W + "p"))
            lines.append(cells)
            if caption is not None:
                tables[caption], caption = cells, None
    return {"all": "\n".join(lines), "tables": tables}


def _printed(fragment, text):
    """True if the text prints the fragment whole, so 14 does not match 2014, 14.5 or $1,140."""
    return (
        re.search(r"(?<![\w.,$])" + re.escape(fragment.translate(STRAIGHT)) + r"(?!\w|[.,]\d)", text)
        is not None
    )


def compare(q, report):
    """Quotes that the report does not print word for word.

    A quote named after a table is looked for in that table only.
    """
    missing = {}
    for key, fragment in q.items():
        m = re.match(r"Table (\d+) ", key)
        text = report["tables"].get(int(m.group(1)), "") if m else report["all"]
        if not _printed(fragment, text):
            missing[key] = fragment
    return missing
