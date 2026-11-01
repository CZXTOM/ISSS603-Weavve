"""Turns the check results into the numbers the final report quotes, written as the report prints them.

quotes() rebuilds each quoted number from the check results. compare() looks for each one in the report's Word
file, which stays in data/ with the Weavve files. The repo is public, so the code never holds the report's
numbers.

Profit is extra net sales times the margin, minus any discount cost. The margin is the two thirds implied by
Weavve's 1.5 floor on return on ad spend (report Section 7.3).
"""

import math
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

MARGIN = 1 / 1.5

# Recommendation 2's two plan rules. Every other input is rebuilt from Weavve's files by snooze_plan().
PLAN_RULES = {
    "signup_points": 150,  # part 3 raises sign-up points from 50 to 150
    "extra_off_first_order": 0.02,  # the club code takes 10% off a first order, against 8% for the pop-up
}


def snooze_plan(TC, V2):
    """Recommendation 2's inputs: Weavve's own rates and reward rule, plus the two plan rules."""
    reward = TC["smallest_reward"]
    # With 150 sign-up points and 1 point per $1, a first order of $100 reaches the smallest reward
    assert reward["points"] - PLAN_RULES["signup_points"] == 100
    return {
        **PLAN_RULES,
        "join_with_part_2": TC["club_code_first_order"]["2023_h2"]["club_code_pct"] / 100,  # first full half year
        "ready_with_part_3": V2["snooze_inputs"]["first_order_100_plus_pct"] / 100,  # first orders of $100+
        "back_gain": TC["reward_ready_return_gap"]["gap"] / 100,  # members against non-members, $200+ first order
        "rewards_used": TC["reward_ready_second_order"]["any_points_voucher_pct"] / 100,  # second orders with a voucher
        "reward_value": reward["value"],
        "reward_points": reward["points"],
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

    # Section 7. Recommendation 1 (our version): the sign-up route, counting only sign-ups who first buy 1 to 90 days
    # after signing up
    sign = F["new_signups_website_order_within_90_days"]
    sign_all_now = sign["2026"]["pct"] / 100
    sign_now, sign_2024, sign_2023 = (sign[y]["later_pct"] / 100 for y in ("2026", "2024", "2023"))
    sign_plan = (sign_now + sign_2024) / 2
    signups_year = F["reach_2026"]["new_signups_a_year"]
    gain_lo, gain_hi = Y1["2024_website"] - Y1["2024_Shopee"], Y1["2025_website"] - Y1["2025_Shopee"]
    extra_sign = signups_year * (sign_plan - sign_now)
    sales_sign = (extra_sign * gain_lo, extra_sign * gain_hi)
    q["7.3 Sign-up buying, all against later"] = (
        f"{100 * sign_all_now:.1f}% bought on the website within 90 days, but only {100 * sign_now:.1f}% bought after"
    )
    q["7.3 Later buying, today to planned"] = f"from {100 * sign_now:.1f}% to {100 * sign_plan:.1f}% of new sign-ups"
    q["7.3 Later buying in 2023"] = f"The rate was {100 * sign_2023:.1f}% in 2023"
    q["Table 15 sign-ups a year"] = f"{signups_year:,} new sign-ups"
    q["Table 15 extra buyers, sign-up route"] = f"About {extra_sign:,.0f}"
    q["Table 15 sales, sign-up route"] = k_range(sales_sign)
    q["Table 15 profit, sign-up route"] = k_range([profit(v) for v in sales_sign])
    q["7.3 Profit per point of later buying"] = (
        f"{k(signups_year * 0.01 * gain_lo * MARGIN)} to "
        f"{k(signups_year * 0.01 * gain_hi * MARGIN)} of profit"
    )
    n_emails, n_half = n_per_group(sign_now, sign_2024), n_per_group(sign_now, sign_plan)
    months_emails = 2 * n_emails / (signups_year / 12)
    q["Table 16 test C size"] = f"{n_emails:,} sign-ups per side, about {months_emails:.0f} months"
    q["7.4 Months to confirm a half-way lift"] = f"would take about {2 * n_half / (signups_year / 12):.0f} months"
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
    q["Table 18 pop-up code on first orders, 2026"] = (
        f"{TC['first_order_codes_27apr_28aug_2026']['popup_pct']}% of new website customers used a pop-up code"
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

    plan_snz = snooze_plan(TC, V2)

    def snooze(join_rate):
        members_now, members = new * join_now, new * join_rate
        ready_now_n, ready = members_now * ready_now, members * plan_snz["ready_with_part_3"]
        back = (ready - ready_now_n) * plan_snz["back_gain"]
        return {
            "members_now": members_now,
            "members": members,
            "ready_now": ready_now_n,
            "ready": ready,
            "back": back,
            "sales": back * per_returner,
            "cost": (members - members_now) * plan_snz["extra_off_first_order"] * first
            + (ready - ready_now_n) * plan_snz["rewards_used"] * plan_snz["reward_value"],
        }

    b, up = snooze(plan_snz["join_with_part_2"]), snooze(join_2024)
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
    gap = TC["reward_ready_return_gap"]
    q["11 Return gap behind Recommendation 2"] = (
        f"back {gap['gap']:.1f} points more often. That is the gap"
    )
    q["11 Return gap range"] = f"range runs from {gap['ci95'][0]:.1f} to {gap['ci95'][1]:.1f} points"

    # Sections 6.2, 6.4, 8.1 to 8.3 and 10.5: numbers added for Final v1
    sc, src = V1["search_clicks_janjul"], F["new_signups_by_source"]
    y1, y2 = src["sep2024_aug2025"], src["sep2025_aug2026"]
    q["6.2 Google search clicks"] = (
        f"rose from {sc['2024']['clicks'] / 1000:.1f}k to {sc['2025']['clicks'] / 1000:.1f}k"
    )
    q["6.2 Product search clicks"] = f"held at about {round(sc['2025']['product'], -2):,.0f}"
    q["6.2 Other search clicks"] = f"rose from {sc['2024']['other']:,} to {sc['2025']['other']:,}"
    q["6.2 Facebook and Instagram sign-ups"] = (
        f"fell from {y1['facebook_instagram']:,} to {y2['facebook_instagram']:,}"
    )
    q["6.2 Google ad link sign-ups"] = (
        f"Google ad links fell from {y1['google_ad_link']} to {y2['google_ad_link']}"
    )
    disc = TC["back_within_a_year_by_first_discount"]
    q["6.4 Return by first-order discount"] = (
        f"were {disc['discount']['pct']}% against {disc['full_price']['pct']}%"
    )
    q["6.4 Returners back within 90 days"] = (
        f"{TC['returners_back_within_90_days_pct']:.0f}% do so within 90 days"
    )
    q["Table 17 club code, 2024"] = (
        f"{TC['club_code_first_order']['2024_27apr_28aug']['club_code_pct']}% in the"
    )
    mr = TC["members_reward"]
    q["Table 17 members who earn and use a reward"] = (
        f"{mr['earn_smallest_reward_pct']}% earn the smallest reward but only {mr['ever_used_points_voucher_pct']}% ever use"
    )
    bk = TC["back_within_a_year_after_7_days"]
    q["8.1 Members back within a year"] = (
        f"{bk['members_200_plus']['pct']}%, against {bk['all_non_members_200_plus']['pct']}% for non-members"
    )
    ce = TC["file_e_codes_redeemed"]
    q["Table 18 sign-up codes used, 2026"] = (
        f"{ce['club_signup_2026_redeemed']} of the {ce['club_signup_2026_released']} sign-up codes"
    )
    rw = TC["smallest_reward"]
    q["Table 18 smallest reward"] = f"The smallest reward, ${rw['value']} off, costs {rw['points']} points"
    q["Table 18 weekend orders"] = (
        f"{TC['weekend_share_of_website_orders']['2026']:.0f}% of website orders come on"
    )
    need = rw["points"] - plan_snz["signup_points"]
    q["Table 19 part 3 reward"] = f"reaches the {rw['points']}-point, ${rw['value']} reward"
    q["Table 19 part 3 first orders"] = (
        f"{100 * plan_snz['ready_with_part_3']:.0f}% of first orders are ${need}"
    )
    q["Table 21 test A size"] = (
        f"{n_per_group(join_now, plan_snz['join_with_part_2'])} new buyers per side"
    )
    q["10.5 Google search clicks rose"] = (
        f"Google search clicks rose {100 * (sc['2025']['clicks'] / sc['2024']['clicks'] - 1):.0f}%"
    )
    q["Table 22 sign-up measure now"] = f"{100 * sign_now:.1f}%, sign-ups January to May 2026"
    q["Table 22 sign-up measure target"] = f"{100 * sign_plan:.1f}%, half way back to 2024"

    # Coverage additions: every computed number in Part B that the sections above do not already quote
    earlier = [L5[y]["sales_from_earlier_buyers"] for y in ("2023", "2024", "2025")]
    q["Figure 5 sales from earlier buyers"] = f"between {k(min(earlier))} and {k(max(earlier))} a year"
    t11, base = V1["product_t11_groups"], V1["product_t11_base"]
    q["6.3 Several kinds, more than average"] = f"spent {t11['several_kinds']['index'] - 100}% more"
    q["6.3 Table 11 caption, average"] = f"Index 100 is the average of {money(base['avg_2y_sales'])}"
    q["6.3 Table 11 caption, people in groups"] = (
        f"hold {base['people'] - t11['unclassified']['people']:,} of {base['people']:,} people"
    )
    q["6.3 Table 11 caption, unclassified"] = f"The other {t11['unclassified']['people']} bought"
    for g, v in t11.items():
        if g == "unclassified":
            continue
        q[f"Table 11 {g}, people"] = f"{v['people']:,}"
        q[f"Table 11 {g}, sales"] = money(v["sales_2y"])
        q[f"Table 11 {g}, index"] = str(v["index"])
    q["Table 14 several kinds"] = f"worth {t11['several_kinds']['index'] - 100}% more over two years"
    sq = F["new_signups_by_quarter"]
    late = [v["pct"] for qq, v in sq.items() if qq >= "2025 Q2"]
    q["Figure 6 recent level"] = f"to about {sum(late) / len(late):.0f}%"
    q["Figure 6 starting level"] = f"The share fell from {sq['2024 Q1']['pct']:.0f}%"
    q["7.3 Each extra buyer adds"] = f"adds {money(gain_lo)} to {money(gain_hi)}"
    q["Table 19 club offer in early 2024"] = f"{100 * join_2024:.1f}% of new buyers used it"
    q["Table 20 new website customers"] = f"{new:,}"
    q["Table 20 join rate with part 2"] = f"{100 * plan_snz['join_with_part_2']:.1f}% with part 2"
    q["Table 20 reward in reach with part 3"] = f"{100 * plan_snz['ready_with_part_3']:.1f}% with part 3"
    q["Table 20 sales per returner"] = f"{money(per_returner)} for each"
    q["8.4 Early-2024 join rate"] = f"early-2024 rate of {100 * join_2024:.1f}%"
    q["Table 21 test A target"] = f"Joining rises toward {100 * plan_snz['join_with_part_2']:.1f}%"
    q["Table 22 join target"] = f"{100 * plan_snz['join_with_part_2']:.1f}%"
    q["Table 22 reward-ready target"] = f"{100 * plan_snz['ready_with_part_3']:.1f}%"
    q["Table 22 join now"] = f"{100 * join_now:.1f}%, the year to 28 August 2026"
    q["Table 22 reward-ready now"] = f"{100 * ready_now:.1f}%"
    q["Table 22 return now"] = f"{L4['2025']['active_y1_pct_after_7_days']}%, 2025 starters"
    q["Table 22 return target"] = f"{L4['2024']['active_y1_pct_after_7_days']}%, the 2024 level"
    q["Table 20 return gain"] = f"{100 * plan_snz['back_gain']:.1f} points more often"
    before = sum(sq[x]["signups"] for x in ("2024 Q1", "2024 Q2", "2024 Q3")) / 3
    after = sum(sq[x]["signups"] for x in ("2025 Q1", "2025 Q2", "2025 Q3", "2025 Q4")) / 4
    q["11 Sign-ups before and after Alia"] = (
        f"about {round(before, -1):,.0f} and {round(after, -1):,.0f} a quarter"
    )
    co = [L5[y]["sales_all"] - L5[y]["sales_ex_company_osco"] for y in ("2024", "2025")]
    q["11 Company and Osco accounts"] = f"bought about {k(co[0])} to {k(co[1])} a"

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
        bph, fph = kwd[("buy bed sheets singapore", "PHRASE")], kwd[("fitted sheet", "PHRASE")]
        q["Table 26 round 1, phrase keyword"] = f"earned {bph['clicks']} clicks from {bph['impressions']:,} views"
        q["Table 26 round 2, phrase fitted sheet"] = f"earned {fph['clicks']} clicks from {fph['impressions']:,} views"
        pph = kwd[("pillowcase", "PHRASE")]
        tbs = kwd[("tencel bed sheets", "EXACT")]
        q["10.2 tencel bed sheets clicks"] = f"Some of its {tbs['clicks']} clicks"
        q["Table 26 round 3, phrase pillowcase"] = f"earned {pph['clicks']} click from {pph['impressions']} views"
        groups = {g["name"]: g for g in ads["ad_groups"]}
        for name in ("1 TENCEL", "2 Cotton", "3 Buy in Singapore", "4 Fitted and single", "5 Pillowcases"):
            g = groups[name]
            q[f"Table 25 {name}, views"] = f"{g['impressions']:,}"
            q[f"Table 25 {name}, clicks"] = str(g["clicks"])
            q[f"Table 25 {name}, click rate"] = f"{100 * g['clicks'] / g['impressions']:.1f}%"
            q[f"Table 25 {name}, cost per click"] = f"S${g['cost'] / g['clicks']:.2f}"
        q["Table 25 all, cost per click"] = f"S${C['cost'] / C['clicks']:.2f}"
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
