"""Idea 1 v8. Website newcomers: fewer arrive, so win more from each one, at the first order and at the second order.
Every number for the rebuilt Idea 1, analysis and sizing in one script.
Windows: W1 29 Aug 2023-28 Aug 2024, W2 29 Aug 2024-28 Aug 2025, W3 29 Aug 2025-28 Aug 2026 (labelled Sep to Aug).
New website customer = a person whose first purchase on the website or Shopee was on the website.
Margin 60% is assumed (Weavve gave none). Meta cost per new customer $100-300 is from Weavve's case deck.
Reads ~/Desktop/Weavve_Clean_Data (or SRC_DIR). Writes ~/Desktop/idea1_v8_numbers.json (or OUT)."""
import os, json, numpy as np, pandas as pd
DIR = os.environ.get("SRC_DIR", os.path.expanduser("~/Desktop/Weavve_Clean_Data"))
OUT = os.environ.get("OUT", os.path.expanduser("~/Desktop/idea1_v8_numbers.json"))
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
M = 0.60
R = {}
def show(name, obj):
    print(f"\n=== {name}\n{obj.to_string() if hasattr(obj, 'to_string') else obj}")
    R[name] = json.loads(obj.to_json()) if hasattr(obj, "to_json") else obj

W = {"W1": ("2023-08-29", "2024-08-28"), "W2": ("2024-08-29", "2025-08-28"), "W3": ("2025-08-29", "2026-08-28")}
END = pd.Timestamp("2026-08-28")
def win(d):
    out = pd.Series(np.nan, index=d.index, dtype=object)
    for k, (a, b) in W.items(): out[(d >= a) & (d <= b)] = k
    return out

O = pd.read_excel(os.path.join(DIR, "C_Orders_clean.xlsx"), sheet_name="orders")
L = pd.read_excel(os.path.join(DIR, "C_Orders_clean.xlsx"), sheet_name="lines")
J = pd.read_excel(os.path.join(DIR, "J_Subscribers_clean.xlsx"), sheet_name="subscribers")
O = O[O.in_customer_scope & O.is_purchase & (O.order_date <= END)].sort_values(["order_date", "order_id"])
first = O.groupby("person_id").head(1).set_index("person_id")
nw = first[first.channel_detail == "Own store"].copy()
nw["w"] = win(nw.order_date)
x = O.merge(nw[["order_date"]].rename(columns={"order_date": "d0"}), left_on="person_id", right_index=True)
x["age"] = (x.order_date - x.d0).dt.days
rep = x[x.age > 7]                        # repeat orders: more than 7 days after the first, so split or same-week top-up orders do not count
nw["follow"] = (END - nw.order_date).dt.days
nw["y1"] = x[x.age < 365].groupby("person_id").net.sum()
nw["after1"] = rep[rep.age < 365].groupby("person_id").net.sum().reindex(nw.index).fillna(0)
nw["after2"] = rep[rep.age < 730].groupby("person_id").net.sum().reindex(nw.index).fillna(0)
nw["back1"] = nw.index.isin(rep[rep.age < 365].person_id)
nw["back2"] = nw.index.isin(rep[rep.age < 730].person_id)

# first-order basket
fl = L[L.order_id.isin(nw.order_id) & (L.sale_or_refund == "order") & ~L.order_level_row]
k = fl[fl.category.notna() & (fl.category != "Unknown")]
cats = nw.order_id.map(k.groupby("order_id").category.agg(set))
ptyp = nw.order_id.map(k.groupby("order_id").product_type.agg(set))
has = lambda s, c: isinstance(s, set) and c in s
bs, bd = cats.apply(lambda s: has(s, "1. Bedsheets")), cats.apply(lambda s: has(s, "2. Bedding"))
st = ptyp.apply(lambda s: has(s, "Set"))
nw["entry"] = np.select([bs & bd, bs & st, bs, bd, cats.apply(lambda s: isinstance(s, set))],
                        ["Whole bed", "Sheet set only", "Sheet separates only", "Bedding only", "Bath, kitchen or other"], "Product not known")
nw["wb"] = nw.entry == "Whole bed"

# sign-up source, exact names
src = J.dropna(subset=["person_id"]).sort_values("profile_created_on").groupby("person_id").initial_source.first().fillna("").str.lower().str.strip()
G = {"google.com": "Search", "google.com.sg": "Search", "bing.com": "Search", "duckduckgo.com": "Search", "yahoo.com": "Search",
     "search.yahoo.com": "Search", "google": "Search", "g": "Search",
     "facebook": "Facebook tag, most likely Meta ads",
     "l.instagram.com": "Instagram and Facebook links", "instagram": "Instagram and Facebook links", "ig": "Instagram and Facebook links",
     "m.facebook.com": "Instagram and Facebook links", "l.facebook.com": "Instagram and Facebook links",
     "klaviyo": "Email sign-up forms", "bitespeed": "Email sign-up forms", "(direct)": "Direct", "weavvehome.com": "Direct"}
nw["src"] = src.reindex(nw.index).map(lambda s: G.get(s, "Other") if isinstance(s, str) and s != "" else "No sign-up record")

# ================= F1 cohort size and quality, class Lens 4 =================
# (a) yearly cohorts with a full year of follow-up
rows = []
for w in ["W1", "W2"]:
    c = nw[nw.w == w]; r1 = rep[rep.person_id.isin(c.index) & (rep.age < 365)]
    rows.append({"cohort": w, "size": len(c), "first order": c.net.mean(), "% back in year one": 100 * c.back1.mean(),
                 "repeat orders per returner": len(r1) / c.back1.sum(), "repeat order value": r1.net.mean(),
                 "year-one value per customer": c.y1.mean(), "year-one total": c.y1.sum()})
show("F1a yearly cohorts, Lens 4", pd.DataFrame(rows).set_index("cohort").round(2))
# (b) same-season cohorts as in the Lens 4 class example: first website purchase Sep to Nov, followed 182 days
rows = []
for y in [2023, 2024, 2025]:
    c = nw[(nw.order_date >= f"{y}-09-01") & (nw.order_date <= f"{y}-11-30")]
    r = rep[rep.person_id.isin(c.index) & (rep.age < 182)]
    v = x[x.person_id.isin(c.index) & (x.age < 182)].groupby("person_id").net.sum()
    rows.append({"cohort": f"Sep-Nov {y}", "size": len(c), "first order": c.net.mean(),
                 "% back within 6 months": 100 * c.index.isin(r.person_id).mean(), "6-month value per customer": v.reindex(c.index).fillna(0).mean(),
                 "6-month total": v.sum()})
show("F1b same-season cohorts, 6 months", pd.DataFrame(rows).set_index("cohort").round(2))
t = nw.dropna(subset=["w"]).groupby("w").agg(new=("net", "size"), first=("net", "mean"))
show("F1 new website customers by year", t.round(1))

# ================= F1c where the lost newcomers first came from =================
s = pd.crosstab(nw.src, nw.w).drop(columns=[], errors="ignore")
s["W2 to W3"] = s.W3 - s.W2; s["share of W2-W3 drop %"] = 100 * s["W2 to W3"] / (s.W3.sum() - s.W2.sum())
show("F1c newcomers by first source", s.sort_values("W2 to W3").round(1))

# ================= F2 Table 8.5, website customers W2 =================
web = O[O.channel_detail == "Own store"]
w2o = web[win(web.order_date) == "W2"]
l2 = L[L.order_id.isin(w2o.order_id) & (L.sale_or_refund == "order") & ~L.order_level_row & L.category.notna() & (L.category != "Unknown")].copy()
l2["person_id"] = l2.order_id.map(w2o.set_index("order_id").person_id)
cat = l2.category.str.replace(r"^\d\. ", "", regex=True); l2["cat"] = np.where(cat.isin(["Bedsheets", "Bedding", "Bath", "Kitchen"]), cat, "Other")
cc = l2.groupby("person_id").cat.agg(set); ns = cc.map(len)
sp = l2.groupby("person_id").net.sum(); spc = l2.groupby(["person_id", "cat"]).net.sum()
rows = []
for c in ["Bedsheets", "Bedding", "Bath", "Kitchen", "Other"]:
    b = cc[cc.map(lambda z: c in z)].index; oth = [q for q in ["Bedsheets", "Bedding", "Bath", "Kitchen", "Other"] if q != c]
    also = {q: cc[b].map(lambda z: q in z).mean() for q in oth}; tp = max(also, key=also.get)
    rows.append({"category": c, "buyers": len(b), "% sole buyers": 100 * (ns[b] == 1).mean(), "categories per buyer": ns[b].mean(),
                 "share of website sales %": 100 * l2.loc[l2.cat == c, "net"].sum() / l2.net.sum(),
                 "share of its buyers' spend %": 100 * spc.xs(c, level="cat").reindex(b).sum() / sp[b].sum(),
                 "most common other category": tp, "% also buying it": 100 * also[tp]})
show("F2 Table 8.5, website W2", pd.DataFrame(rows).set_index("category").round(1))

# ================= F3 whole-bed first order, raw and adjusted =================
c2 = nw[(nw.order_date >= "2022-08-29") & (nw.order_date <= "2024-08-28")].copy()
base = c2.after2.mean()
e = c2.groupby("entry").agg(people=("net", "size"), first_order=("net", "mean"), after_2yr=("after2", "mean"), back_2yr=("back2", "mean"))
e["share %"] = 100 * e.people / len(c2); e["after-spend index"] = 100 * e.after_2yr / base; e["back_2yr"] *= 100
show("F3a first basket, cohort Sep 2022-Aug 2024, raw", e.sort_values("after-spend index", ascending=False).round(1))
rng = np.random.default_rng(1); wbv, allv = c2.loc[c2.wb, "after2"].values, c2.after2.values
boot = [100 * rng.choice(wbv, len(wbv)).mean() / rng.choice(allv, len(allv)).mean() for _ in range(2000)]
R["F3 index 95% range"] = [round(float(np.percentile(boot, 2.5)), 0), round(float(np.percentile(boot, 97.5)), 0)]
print("F3 whole-bed index 95% range", R["F3 index 95% range"])
# adjusted: compare whole bed with other first orders of the SAME size band, then weight by whole-bed people per band
bands = [0, 150, 250, 400, 1e9]; lab = ["under $150", "$150-250", "$250-400", "$400+"]
def adjusted(c):
    c = c.copy(); c["band"] = pd.cut(c.net, bands, labels=lab, right=False)
    g = c.groupby(["band", "wb"], observed=True).agg(n=("net", "size"), after=("after2", "mean"), back=("back2", "mean")).unstack("wb")
    g = g.dropna(); wts = g[("n", True)] / g[("n", True)].sum()
    return g, float(((g[("after", True)] - g[("after", False)]) * wts).sum()), float(100 * ((g[("back", True)] - g[("back", False)]) * wts).sum())
for lab_, a, b in [("Sep 2022-Aug 2024", "2022-08-29", "2024-08-28"), ("check Sep 2020-Aug 2022", "2020-08-29", "2022-08-28")]:
    cc_ = nw[(nw.order_date >= a) & (nw.order_date <= b)]
    g, d_after, d_back = adjusted(cc_)
    raw_after = cc_[cc_.wb].after2.mean() - cc_[~cc_.wb].after2.mean(); raw_back = 100 * (cc_[cc_.wb].back2.mean() - cc_[~cc_.wb].back2.mean())
    show(f"F3b by first-order size, {lab_}", g.round(2))
    R[f"F3c premium {lab_}"] = {"raw extra 2yr after-spend": round(raw_after, 1), "same-size extra 2yr after-spend": round(d_after, 1),
                                "raw extra % back 2yr": round(raw_back, 1), "same-size extra % back 2yr": round(d_back, 1)}
    print(R[f"F3c premium {lab_}"])
bed = k[k.order_id.isin(c2[c2.wb].order_id) & (k.category == "2. Bedding")].groupby("order_id").product_type.agg(set)
R["F3d bedding item in whole-bed first orders %"] = {t: round(100 * bed.map(lambda z: t in z).mean(), 1) for t in ["Mattress Protectors", "duvet", "quilt", "pillow", "Duvet Cover"]}
print("F3d", R["F3d bedding item in whole-bed first orders %"])
pen = nw.dropna(subset=["w"]).groupby("w").wb.agg(["sum", "mean"]); pen["mean"] *= 100
show("F3e whole-bed share of new website customers by year", pen.round(1))

# ================= F4 when do newcomers buy the whole bed, and does it pay back Meta =================
xx = nw[(nw.order_date >= "2022-08-29") & (nw.order_date <= "2026-08-28")].copy()
cd = xx.discount_campaigns.fillna("").astype(str).str.upper()
sale = cd.str.contains(r"SALE|1111|11$|12$|CNY|RAYA|MIDYR|HOHOHO|JOLLY|BFCM|HOLIDAY|JUNE|JULY|77|XMAS|BLACK")
welcome = cd.str.contains("ONE-OFF|WEAVVE10OFF|WEAVVE8OFF|IG10OFF|WELCOME")
xx["code"] = np.select([cd == "", welcome, sale], ["No code", "Welcome or one-off code", "Seasonal sale code"], "Other code")
t = xx.groupby("code").agg(people=("wb", "size"), whole_bed=("wb", "mean"), first_order=("net", "mean")); t["whole_bed"] *= 100
show("F4a whole-bed share by first-order code, Sep 2022-Aug 2026", t.round(1))
t = xx.assign(y=xx.order_date.dt.year).pivot_table(index="code", columns="y", values="wb", aggfunc="mean").mul(100)
show("F4b whole-bed share by code and calendar year", t.round(1))
t = nw.dropna(subset=["w"]).groupby("src").agg(people=("wb", "size"), whole_bed=("wb", "mean"), first_order=("net", "mean")); t["whole_bed"] *= 100
show("F4c whole-bed share and first order by source, W1-W3", t.round(1))
# Lens 5 year-one value per new customer = first order + % back x repeat orders per returner x repeat order value, W2 cohort
b = nw[nw.w == "W2"]
def y1v(g):
    r = rep[rep.person_id.isin(g.index) & (rep.age < 365)]
    return {"n": len(g), "first": g.net.mean(), "back": g.back1.mean(), "ro": len(r) / max(g.back1.sum(), 1), "ra": r.net.mean(),
            "y1": g.net.mean() + g.back1.mean() * len(r) / max(g.back1.sum(), 1) * r.net.mean()}
V = {"All": y1v(b), "Whole bed": y1v(b[b.wb]), "Other": y1v(b[~b.wb])}
show("Lens 5 base, W2 cohort", pd.DataFrame(V).T.round(3))
pay = []
for cpa in [100, 200, 300]:
    for nm in ["Whole bed", "Other"]:
        pay.append({"Meta cost per new customer": cpa, "first order": nm, "first-order revenue / cost": V[nm]["first"] / cpa,
                    "first-order gross profit minus cost": V[nm]["first"] * M - cpa, "year-one gross profit minus cost": V[nm]["y1"] * M - cpa})
show("F4d Meta payback, 60% margin", pd.DataFrame(pay).round(2))

cdw = nw.discount_campaigns.fillna("").astype(str).str.upper()
nw["welcome"] = cdw.str.contains("ONE-OFF|WEAVVE10OFF|WEAVVE8OFF|IG10OFF|WELCOME")
t = nw.dropna(subset=["w"]).groupby(["w", "welcome"]).wb.agg(["size", "mean"]).unstack("welcome"); t[("mean", True)] *= 100; t[("mean", False)] *= 100
show("F4e whole-bed share, welcome-code newcomers vs others", t.round(1))
be = {cpa: 100 * (cpa / M - V["Other"]["y1"]) / (V["Whole bed"]["y1"] - V["Other"]["y1"]) for cpa in [100, 150, 200, 300]}
R["F4f whole-bed share Meta newcomers need for year-one gross profit to cover the Meta cost %"] = {k_: round(max(v_, 0), 1) for k_, v_ in be.items()}
print("F4f break-even whole-bed share", R["F4f whole-bed share Meta newcomers need for year-one gross profit to cover the Meta cost %"])

# ================= F5 the second order: when, what, and is it slipping =================
la = L[(L.sale_or_refund == "order") & ~L.order_level_row & L.order_id.isin(O.order_id) & L.category.notna() & (L.category != "Unknown")].copy()
c = nw[(nw.order_date >= "2022-08-29") & (nw.order_date <= "2024-08-28")]
sec = rep.groupby("person_id").age.min().reindex(c.index).dropna(); sec = sec[sec < 730]
R["F5a second order timing, cohort Sep 2022-Aug 2024"] = {"back within 2 years %": round(100 * len(sec) / len(c), 1), "median days": float(sec.median()),
    "share of second orders by days %": {str(kk_): round(vv, 1) for kk_, vv in (100 * pd.cut(sec, [7, 30, 60, 90, 180, 365, 730]).value_counts(normalize=True).sort_index()).items()}}
print("F5a", R["F5a second order timing, cohort Sep 2022-Aug 2024"])
r2 = rep[rep.person_id.isin(c.index) & (rep.age < 730)].groupby("person_id").head(1)
c2cats = la[la.order_id.isin(r2.order_id)].groupby("order_id").category.agg(set); r2 = r2.assign(cats=r2.order_id.map(c2cats), first=r2.person_id.map(c.entry))
r2["sheets"] = r2.cats.apply(lambda s: has(s, "1. Bedsheets")); r2["bedding"] = r2.cats.apply(lambda s: has(s, "2. Bedding"))
t = r2.groupby("first").agg(returners=("net", "size"), second_order=("net", "mean"), has_sheets=("sheets", "mean"), has_bedding=("bedding", "mean"), on_website=("channel_detail", lambda s: (s == "Own store").mean()))
t[["has_sheets", "has_bedding", "on_website"]] *= 100
show("F5b what the second order holds, by first basket", t.round(1))
rows = []
for nm_, a, b_ in [("W1", "2023-08-29", "2024-08-28"), ("W2", "2024-08-29", "2025-08-28"), ("W3 Sep-Feb", "2025-08-29", "2026-02-28")]:
    cc_ = nw[(nw.order_date >= a) & (nw.order_date <= b_)]; rr = rep[rep.person_id.isin(cc_.index) & (rep.age < 180)].groupby("person_id").head(1)
    rows.append({"cohort": nm_, "newcomers": len(cc_), "back within 6 months %": 100 * len(rr) / len(cc_),
                 "on website %": 100 * (rr.channel_detail == "Own store").sum() / len(cc_), "on Shopee %": 100 * (rr.channel_detail != "Own store").sum() / len(cc_)})
show("F5c back within 6 months, any channel", pd.DataFrame(rows).set_index("cohort").round(1))
# later bedding buying among sheet-only starters (File K email counts are not used: list names changed between years)
lb = la.merge(nw[["order_date"]].rename(columns={"order_date": "d0"}), left_on=la.order_id.map(O.set_index("order_id").person_id), right_index=True)
lb["person_id"] = la.order_id.map(O.set_index("order_id").person_id); lb["age"] = (lb.order_date - lb.d0).dt.days
bed_later = set(lb[(lb.age > 7) & (lb.age < 180) & (lb.category == "2. Bedding")].person_id)
rows = []
for nm_, a, b_ in [("W1", "2023-08-29", "2024-08-28"), ("W2", "2024-08-29", "2025-08-28"), ("W3 Sep-Feb", "2025-08-29", "2026-02-28")]:
    so = nw[(nw.order_date >= a) & (nw.order_date <= b_) & nw.entry.isin(["Sheet set only", "Sheet separates only"])]
    rows.append({"cohort": nm_, "sheet-only starters": len(so), "buy bedding within 6 months %": 100 * so.index.isin(bed_later).mean()})
show("F5e sheet-only starters buying bedding within 6 months", pd.DataFrame(rows).set_index("cohort").round(1))

# ================= Ideas checked and moved out, with their evidence =================
# checkout: orders per cart flat
F = pd.read_excel(os.path.join(DIR, "L_Website_Funnel_clean.xlsx"))
mo = F.assign(opc=F.orders_placed / F.add_to_cart)
R["Out, checkout, orders per cart monthly average %"] = {"W2": round(100 * mo[(mo.month >= "2024-09-01") & (mo.month <= "2025-08-01")].opc.mean(), 1),
                                                         "W3": round(100 * mo[(mo.month >= "2025-09-01") & (mo.month <= "2026-08-01")].opc.mean(), 1)}
# sign-up route: share of newcomers who signed up first and bought later held steady
sd = J.dropna(subset=["person_id"]).sort_values("profile_created_on").groupby("person_id").profile_created_on.first().dt.normalize()
gap = (nw.order_date.dt.normalize() - sd.reindex(nw.index)).dt.days
R["Out, sign-up route, newcomers who signed up first and bought later"] = {w_: [int(((nw.w == w_) & (gap >= 1)).sum()), round(100 * ((nw.w == w_) & (gap >= 1)).sum() / (nw.w == w_).sum(), 1)] for w_ in ["W1", "W2", "W3"]}
print("Out checks", R["Out, checkout, orders per cart monthly average %"], R["Out, sign-up route, newcomers who signed up first and bought later"])

# ================= Sizing =================
END = pd.Timestamp("2026-08-28")
N3 = int((nw.w == "W3").sum())
gap_s = (int((nw.w == "W2").sum()) - N3) * V["All"]["y1"]
rows = []
def add(idea, case, lever, sales, cost, basis, kpi):
    rows.append({"idea": idea, "case": case, "lever": lever, "sales": round(sales), "gross profit": round(sales * M),
                 "after cost": round(sales * M - cost), "uplift based on": basis, "KPI": kpi})
# R1 timed follow-up emails. Reach in year one = a year of newcomers + the backlog of recent newcomers (60 to 240 days, not yet back) at launch
bk = nw[(nw.order_date >= END - pd.Timedelta(days=240)) & (nw.order_date <= END - pd.Timedelta(days=60))]
backlog = len(bk) - bk.index.isin(rep.person_id).sum()
reach = N3 + backlog
# value of one extra returner = what returners spend in repeat orders over two years, newcomers of Sep 2022 to Aug 2024
c22 = nw[(nw.order_date >= "2022-08-29") & (nw.order_date <= "2024-08-28")].index
r1p = rep[rep.person_id.isin(c22) & (rep.age < 365)].person_id.unique()
val2 = rep[rep.person_id.isin(r1p) & (rep.age < 730)].groupby("person_id").net.sum().mean()
val1 = rep[rep.person_id.isin(r1p) & (rep.age < 365)].groupby("person_id").net.sum().mean()
R["R1 reach and value"] = {"newcomers a year": N3, "backlog at launch": int(backlog), "reach in year one": int(reach),
                           "repeat spend per returner, year one": round(val1, 1), "repeat spend per returner, two years": round(val2, 1)}
print("R1", R["R1 reach and value"])
earlier = {}
for nm_, a, b_ in [("2021/22", "2021-08-29", "2022-08-28"), ("2022/23", "2022-08-29", "2023-08-28"), ("W1", "2023-08-29", "2024-08-28"), ("W2", "2024-08-29", "2025-08-28")]:
    earlier[nm_] = round(100 * nw[(nw.order_date >= a) & (nw.order_date <= b_)].back1.mean(), 1)
R["% back in year one by cohort"] = earlier
b1, b2 = earlier["W1"], 100 * V["All"]["back"]
be_r1 = 100 * 1000 / M / (reach * val2)
R["R1 break-even lift pts"] = round(be_r1, 2)
for case, pts, basis in [("Low", be_r1, "break-even, just pays its $1,000 cost"), ("Middle", 1.0, "one more returner per 100 newcomers"),
                         ("High", (b1 - b2) / 2, f"half way back to W1's {b1:.1f}%, about the 2022/23 level of {earlier['2022/23']}%")]:
    add("R1 timed follow-up emails", case, "% active", reach * pts / 100 * val2, 1000,
        f"{reach} people reached, back within a year +{pts:.2f} pts, {basis}, two-year repeat spend ${val2:.0f}", "% back within 12 months, flow group vs control")
R["R1 cost per extra returner, middle"] = round(1000 / (reach * 0.01), 1)
# R2 whole bed at the welcome offer
wc = nw[(nw.w == "W3") & nw.welcome]; wc_share = 100 * wc.wb.mean()
lvl = {w_: 100 * nw[(nw.w == w_) & nw.welcome].wb.mean() for w_ in ["W1", "W2"]}; all3 = 100 * nw[nw.w == "W3"].wb.mean()
b2w = nw[(nw.w == "W2") & nw.wb]; add_item = k[k.order_id.isin(b2w.order_id) & (k.category == "2. Bedding")].groupby("order_id").net.sum().mean()
shrink = R["F3c premium Sep 2022-Aug 2024"]["same-size extra 2yr after-spend"] / R["F3c premium Sep 2022-Aug 2024"]["raw extra 2yr after-spend"]
later = ((V["Whole bed"]["y1"] - V["Whole bed"]["first"]) - (V["Other"]["y1"] - V["Other"]["first"])) * shrink
per_switch = add_item + later
R["R2 value per switch"] = {"bedding added": round(add_item, 1), "later value kept": round(later, 1), "per switch": round(per_switch, 1)}
for case, tgt, basis in [("Low", lvl["W2"], "back to their W2 level"), ("Middle", lvl["W1"], "back to their W1 level, when they matched other newcomers"),
                         ("High", all3, "up to the W3 average of all newcomers")]:
    add("R2 whole bed at the welcome offer", case, "AOV first order", len(wc) * max(tgt - wc_share, 0) / 100 * per_switch, 500,
        f"{len(wc)} welcome-code newcomers, whole-bed share {wc_share:.1f}% to {tgt:.1f}%, {basis}", "whole-bed share of welcome-code first orders, new vs current welcome email")
be_r2 = 100 * 500 / M / (len(wc) * per_switch); R["R2 break-even lift pts"] = round(be_r2, 2)
T = pd.DataFrame(rows); show("Size table", T.set_index(["idea", "case"]))
tot = T.groupby("case")[["sales", "gross profit", "after cost"]].sum(); tot["share of gross-profit gap %"] = 100 * tot["gross profit"] / (gap_s * M)
tot["gross profit per $1 of cost"] = tot["gross profit"] / 1500
show("Total", tot.round(2)); R["gap"] = {"new customers": int((nw.w == "W2").sum()) - N3, "sales": round(gap_s), "gross profit": round(gap_s * M)}
R["newcomer pool, W3 year-one sales"] = round(N3 * V["All"]["y1"]); print(R["gap"], "pool", R["newcomer pool, W3 year-one sales"], "R1 cost per extra returner", R["R1 cost per extra returner, middle"])
for m_ in [0.4, 0.5, 0.6]: print(f"margin {m_:.0%}: middle gross profit ${tot.loc['Middle', 'sales'] * m_:,.0f}")
from math import erf, sqrt
Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))
def n_per_arm(p1, p2): return int(np.ceil((1.96 + 0.8416) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p2 - p1) ** 2))
def read(p1, p2, n):
    se = sqrt(p1 * (1 - p1) / n + p2 * (1 - p2) / n); z = (p2 - p1) / se
    return round(Phi(z), 2), round(Phi(z - 1.96), 2)
R["test"] = {"R1 people per group to prove +1 pt": n_per_arm(b2 / 100, b2 / 100 + .01), "R2 per group to prove the middle": n_per_arm(wc_share / 100, lvl["W1"] / 100),
             "R1 50/50 over two years, right direction and power at +1 pt": read(b2 / 100, b2 / 100 + .01, reach),
             "decision rule": "keep each move unless the control group does better or unsubscribes rise; break-even R1 +%.2f pts, R2 +%.2f pts" % (be_r1, be_r2)}
print("test", R["test"])
json.dump(R, open(OUT, "w"), default=float, indent=1); print("saved", OUT)
