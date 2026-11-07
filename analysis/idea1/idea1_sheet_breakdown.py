"""Idea 1, sheet starters broken down by what exactly they bought.
Item, fabric range, colour and size come from File D, joined to File C lines by SKU.
Needs idea1_v8.py in the same folder. Reads ~/Desktop/Weavve_Clean_Data (or SRC_DIR)."""
import os
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(HERE, "idea1_v8.py")).read().split("# ================= Sizing")[0])

D = pd.read_excel(os.path.join(DIR, "D_Products_clean.xlsx"))
ids = J[~J.excluded_account].person_id.dropna().unique(); nw["on_list"] = nw.index.isin(ids)
SHEETS = ["Whole bed", "Sheet set only", "Sheet separates only"]
nw["sf"] = nw.entry.isin(SHEETS)
nw["b6"] = nw.index.isin(rep[rep.age < 182].person_id)

# ---------- Step 1. item, fabric, colour and size for every bed line ----------
def item(r):
    pt, t3 = r.product_type, r.tier_3_category
    if r.category == "1. Bedsheets":
        if pt == "Set":
            return {"Classic Set": "Classic set", "Fitted Sheet Set": "Fitted sheet set", "Deluxe Set": "Deluxe set",
                    "Duvet Cover Set": "Duvet cover set"}.get(t3, "Other set")
        return {"Fitted Sheet": "Fitted sheet", "Duvet Cover": "Duvet cover", "Flat Sheet": "Flat sheet", "pillow case": "Pillow or bolster cases",
                "bolster": "Pillow or bolster cases", "Cot sheet": "Cot sheet"}.get(pt, "Other sheets")
    if r.category == "2. Bedding":
        return {"quilt": "Weighted blanket", "duvet": "Duvet insert", "Mattress Protectors": "Mattress protector", "pillow": "Pillow",
                "Blankets": "Waffle blanket"}.get(pt, "Other bedding")
    return None
def fabric(s):
    s = str(s)
    return "Signature TENCEL" if "STC" in s or "Scene Shang" in s else "Everyday TENCEL" if "ETC" in s else "Cotton" if "Cotton" in s or "CT" in s else None
bl = L[(L.sale_or_refund == "order") & ~L.order_level_row & L.category.isin(["1. Bedsheets", "2. Bedding"])].merge(
    D[["sku", "tier_3_category", "option_1", "option_2"]], on="sku", how="left")
bl["item"] = bl.apply(item, axis=1)
bl["fabric"] = np.where(bl.category == "1. Bedsheets", bl.sub_category.map(fabric), None)
bl["colour"] = bl.option_2.where(bl.category == "1. Bedsheets")
bl["size"] = bl.option_1.where(bl.category == "1. Bedsheets")
t = bl.groupby(["category", "item"]).net.agg(["size", "sum"]); t["share of category sales %"] = 100 * t["sum"] / t.groupby(level=0)["sum"].transform("sum")
show("S1 items, all orders", t.sort_values("sum", ascending=False).round(1))
print("S1 sheet lines with fabric known %", round(100 * bl[bl.category == "1. Bedsheets"].fabric.notna().mean(), 1),
      "colour known %", round(100 * bl[bl.category == "1. Bedsheets"].colour.notna().mean(), 1))

# ---------- Step 2. what sheet starters bought first ----------
fo = bl[bl.order_id.isin(nw.order_id)]
fi = fo.groupby("order_id").item.agg(set)
SETS = {"Classic set", "Fitted sheet set", "Deluxe set", "Duvet cover set", "Other set"}
def first_group(s):
    if not isinstance(s, set): return None
    if s & SETS: return "Sheet set"
    if "Fitted sheet" in s: return "Fitted sheet, no set"
    if "Duvet cover" in s: return "Duvet cover, no set"
    if "Pillow or bolster cases" in s: return "Pillow or bolster cases only"
    return "Flat or cot sheet"
nw["sg"] = nw.order_id.map(fi).map(first_group).where(nw.sf)
nw["set_type"] = nw.order_id.map(fi).map(lambda s: next((x for x in ["Deluxe set", "Classic set", "Fitted sheet set", "Duvet cover set", "Other set"] if isinstance(s, set) and x in s), None)).where(nw.sg == "Sheet set")
ff = fo[fo.category == "1. Bedsheets"].groupby("order_id").fabric.agg(lambda s: s.dropna().mode().iat[0] if s.notna().any() else None)
nw["fab"] = nw.order_id.map(ff).where(nw.sf)

c = nw[(nw.order_date >= "2022-08-29") & (nw.order_date <= "2024-08-28")].copy()
spend2 = x[x.age < 730].groupby("person_id").net.sum(); c["s2"] = spend2.reindex(c.index)
l26 = nw[(nw.w == "W3") & nw.on_list & nw.sf]
def prof(col):
    g = c[c.sf].groupby(col).agg(people=("s2", "size"), first=("net", "mean"), two_year=("s2", "mean"), back2=("back2", "mean"),
                                 whole_bed=("wb", "mean"))
    g[["back2", "whole_bed"]] *= 100
    g["share of sheet starters %"] = 100 * g.people / c.sf.sum()
    g["share of 2026 sheet starters %"] = 100 * l26[col].value_counts(normalize=True)
    return g.sort_values("people", ascending=False).round(1)
show("S2 first sheet item, sheet starters Sep 2022-Aug 2024", prof("sg"))
show("S2b set type, sheet-set starters", prof("set_type"))
show("S2c fabric range, sheet starters", prof("fab"))

# ---------- Step 4. who is slipping: back within 6 months, 2025 vs 2026 ----------
rows = []
for col in ["sg", "fab"]:
    for g_ in nw[col].dropna().unique():
        for y, w in [("2025", "W2"), ("2026", "W3")]:
            d = nw[(nw.w == w) & nw.on_list & (nw.follow >= 182) & (nw[col] == g_)]
            rows.append({"split": col, "group": g_, "year": y, "n": len(d), "back": int(d.b6.sum()), "back %": round(100 * d.b6.mean(), 1) if len(d) else np.nan})
t = pd.DataFrame(rows).pivot_table(index=["split", "group"], columns="year", values=["n", "back", "back %"])
show("S4 back within 6 months by group", t)

# ---------- Step 5. what the second order holds ----------
r2s = r2[r2.person_id.isin(c[c.sf].index) & r2.cats.apply(lambda s: isinstance(s, set))].copy()   # same 778 base as slide 3
so = bl[bl.order_id.isin(r2s.order_id)]
si = so.groupby("order_id").item.agg(set); r2s["items2"] = r2s.order_id.map(si).apply(lambda s: s if isinstance(s, set) else set())
r2s["sg"] = r2s.person_id.map(c.sg); r2s["fab1"] = r2s.person_id.map(c.fab)
allitems = ["Classic set", "Fitted sheet set", "Deluxe set", "Duvet cover set", "Fitted sheet", "Duvet cover", "Pillow or bolster cases", "Flat sheet",
            "Weighted blanket", "Duvet insert", "Mattress protector", "Pillow", "Waffle blanket"]
rows = {}
for g_, d in [("All sheet starters", r2s)] + list(r2s.groupby("sg")):
    rr = {"returners": len(d)}
    rr["any sheet set"] = 100 * d.items2.apply(lambda s: bool(s & SETS)).mean()
    for it in allitems: rr[it] = 100 * d.items2.apply(lambda s: it in s).mean()
    rr["any bedding"] = 100 * d.items2.apply(lambda s: bool(s & {"Weighted blanket", "Duvet insert", "Mattress protector", "Pillow", "Waffle blanket"})).mean()
    rows[g_] = rr
show("S5 second order items, sheet starters who came back within 2 years, % of returners", pd.DataFrame(rows).round(1))
# same first item group again, same fabric, same colour, same size
p1 = fo[(fo.category == "1. Bedsheets") & fo.person_id.isin(r2s.person_id)]
p2 = so[so.category == "1. Bedsheets"]
def same(col):
    a = p1.dropna(subset=[col]).groupby("person_id")[col].agg(set); b = p2.dropna(subset=[col]).groupby("person_id")[col].agg(set)
    both = a.index.intersection(b.index)
    return len(both), round(100 * np.mean([bool(a[i] & b[i]) for i in both]), 1)
print("S5b repeat sheet buyers with same fabric / colour / size as first order (n, %):",
      {k_: same(k_) for k_ in ["fabric", "colour", "size"]})
fa = r2s.items2.apply(lambda s: bool(s & SETS))
print("S5c second order has a set, by first group:", r2s.assign(st=fa).groupby("sg").st.mean().mul(100).round(1).to_dict())
f1i = fo[fo.category == "1. Bedsheets"].groupby("person_id").item.agg(set)
r2s["same_item"] = [bool(f1i.get(p_, set()) & s_) for p_, s_ in zip(r2s.person_id, r2s.items2)]
print("S5d second order repeats an item type from the first order %, by first group:", r2s.groupby("sg").same_item.mean().mul(100).round(1).to_dict(), "all", round(100*r2s.same_item.mean(),1))
print("S5e second order: set buyers buy set again %", round(100*r2s[r2s.sg=="Sheet set"].items2.apply(lambda s: bool(s & SETS)).mean(),1),
      "| separates buyers move up to a set %", round(100*r2s[r2s.sg!="Sheet set"].items2.apply(lambda s: bool(s & SETS)).mean(),1), "n", int((r2s.sg!="Sheet set").sum()))

# ---------- Step 6. timing by group ----------
cs = c[c.sf].copy(); cs["sec"] = sec.reindex(cs.index)
t = cs.dropna(subset=["sec"]).groupby("sg").sec.agg(returners="size", median_day="median", after_month=lambda s: 100 * (s > 30).mean(),
                                                     day19_364=lambda s: 100 * ((s > 18) & (s < 365)).mean())
show("S6 second-order timing by first group", t.round(1))

# ---------- Step 7. whole-bed first orders, which bedding with which sheets ----------
wbo = fo[fo.order_id.isin(c[c.wb].order_id)]
bi = wbo[wbo.category == "2. Bedding"].groupby("order_id").item.agg(set)
si_ = wbo[wbo.category == "1. Bedsheets"].groupby("order_id").item.agg(set).map(first_group)
w = pd.DataFrame({"bedding": bi, "sheets": si_})
print("S7 whole-bed first orders", len(w))
print("S7 bedding item share %", {it: round(100 * w.bedding.apply(lambda s: isinstance(s, set) and it in s).mean(), 1)
                                   for it in ["Weighted blanket", "Duvet insert", "Mattress protector", "Pillow", "Waffle blanket"]})
print("S7 sheet part %", (100 * w.sheets.value_counts(normalize=True)).round(1).to_dict())
# bedding added later by sheet-only starters, which item
lb = bl.merge(x[["order_id", "person_id", "age"]], on="order_id", how="inner", suffixes=("", "_x"))
later = lb[(lb.age > 7) & (lb.age < 730) & (lb.category == "2. Bedding") & lb.person_id_x.isin(c[c.sf & ~c.wb].index)]
print("S7b sheet-only starters who bought bedding within 2 years", later.person_id_x.nunique(), "of", int((c.sf & ~c.wb).sum()),
      (100 * later.drop_duplicates(["person_id_x", "item"]).item.value_counts() / later.person_id_x.nunique()).round(1).to_dict())
# 2026 whole-bed by welcome code: bedding item
w26 = fo[fo.order_id.isin(nw[(nw.w.isin(["W2", "W3"])) & nw.wb].order_id) & (fo.category == "2. Bedding")].groupby("order_id").item.agg(set)
print("S7c whole-bed first orders 2025-2026 bedding item %", {it: round(100 * w26.apply(lambda s: it in s).mean(), 1)
                                                              for it in ["Weighted blanket", "Duvet insert", "Mattress protector", "Pillow"]}, len(w26))

# ---------- checks for the separates finding ----------
import math
nw["sep"] = nw.sg.isin(["Fitted sheet, no set", "Duvet cover, no set", "Pillow or bolster cases only", "Flat or cot sheet"])
def z(x1, n1, x2, n2):
    p = (x1 + x2) / (n1 + n2); se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)); zz = (x1 / n1 - x2 / n2) / se
    return round(zz, 2), round(math.erfc(abs(zz) / math.sqrt(2)), 4)
for nm_, mask in [("separates", nw.sep), ("sets", nw.sg == "Sheet set")]:
    a = nw[(nw.w == "W2") & nw.on_list & (nw.follow >= 182) & mask]; b = nw[(nw.w == "W3") & nw.on_list & (nw.follow >= 182) & mask]
    a2 = a[a.order_date.dt.month.isin([9, 10, 11, 12, 1, 2])]
    print("CHK", nm_, "2025", len(a), int(a.b6.sum()), round(100 * a.b6.mean(), 1), "| 2025 Sep-Feb", len(a2), int(a2.b6.sum()), round(100 * a2.b6.mean(), 1),
          "| 2026", len(b), int(b.b6.sum()), round(100 * b.b6.mean(), 1), "| z,p", z(a.b6.sum(), len(a), b.b6.sum(), len(b)))
    w1 = nw[(nw.w == "W1") & nw.on_list & mask]; print("CHK", nm_, "2024", len(w1), round(100 * w1.b6.mean(), 1))
# share of 2026 list sheet starters who are separates, and their reach
L6 = nw[(nw.w == "W3") & nw.on_list & nw.sf]
print("CHK 2026 list sheet starters", len(L6), "separates", int(L6.sep.sum()), "sets", int((L6.sg == "Sheet set").sum()))
for y in ["W1", "W2", "W3"]:
    d = nw[(nw.w == y) & nw.on_list & nw.sf]; print("CHK mix", y, len(d), (100 * d.sg.value_counts(normalize=True)).round(1).to_dict())
# value per returner by group, year one repeat sales, 2024 and 2025 starters
ret = nw[nw.w.isin(["W1", "W2"]) & nw.back1 & nw.sf]
v = rep[rep.person_id.isin(ret.index) & (rep.age < 365)].groupby("person_id").net.sum()
print("CHK val1 sets", round(v.reindex(ret[ret.sg == "Sheet set"].index).mean(), 1), "separates", round(v.reindex(ret[ret.sep].index).mean(), 1), "n", int(ret.sep.sum()))
r12 = nw[(nw.w == "W2") & nw.on_list & nw.sep & (nw.follow >= 365)]
print("CHK separates 2025 back in a year", round(100 * r12.back1.mean(), 1))
