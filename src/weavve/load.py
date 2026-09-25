"""Read each Weavve file once and cache it, so later notebooks load in seconds.

Every loader returns the raw table untouched (apart from column types).
Cleaning happens in the notebooks, where each step can be seen and checked.
"""
import glob
import os
import re

import pandas as pd

from .paths import CACHE, ensure_out, path

MARKETPLACE, WEBSITE = "Easy Shopee, TikTok & Lazada", "Online Store"


def _cached(name, build):
    ensure_out()
    f = CACHE / f"{name}.pkl"
    if f.exists():
        return pd.read_pickle(f)
    df = build()
    df.to_pickle(f)
    return df


def orders():
    """File 3, one row per order line (sales, refunds and cancellations mixed)."""
    def build():
        t = pd.read_excel(path("orders"))
        for c in ["Product variant SKU at time of sale", "Discount code", "Discount name", "Discount title"]:
            t[c] = t[c].astype("string")
        t["Is canceled order"] = t["Is canceled order"].astype(bool)
        return t
    return _cached("orders", build)


def skus():
    """File 4, the product list."""
    def build():
        s = pd.read_excel(path("skus"))
        s["Code"] = s["Code"].astype("string")
        return s
    return _cached("skus", build)


def discounts():
    """File 8, every discount code row."""
    return _cached("discounts", lambda: pd.read_excel(path("discounts"), sheet_name="Full Discounts Report"))


def loyalty():
    """File 9.1, loyalty voucher redemptions."""
    return _cached("loyalty", lambda: pd.read_excel(path("loyalty"), sheet_name="Redemptions"))


def semrush():
    """File 2, all monthly Semrush files stacked, month taken from the file name."""
    def build():
        frames = []
        for p in sorted(glob.glob(str(path("semrush") / "*.csv"))):
            m = re.search(r"-\s*([A-Za-z]{3})\s*(\d{4})", os.path.basename(p))
            d = pd.read_csv(p)
            d["month"] = pd.Timestamp(f"{m.group(2)}-{m.group(1)}-01")
            d["source_file"] = os.path.basename(p)
            frames.append(d)
        return pd.concat(frames, ignore_index=True)
    return _cached("semrush", build)


def gsc_workbooks():
    """File 1, the list of Search Console workbooks, skipping Excel lock files."""
    all_books = glob.glob(str(path("gsc") / "*" / "*.xlsx"))
    books = [p for p in all_books if not os.path.basename(p).startswith("~$")]
    return sorted(books), len(all_books) - len(books)


def gsc_site_clicks():
    """Monthly Singapore clicks from each workbook's Countries sheet, one row per (month, workbook)."""
    def build():
        rows = []
        for p in gsc_workbooks()[0]:
            c = pd.read_excel(p, sheet_name="Countries")
            sg = c[c["Country"] == "Singapore"]        # some workbooks are not filtered to Singapore
            row = sg.iloc[0] if len(sg) else c.iloc[0]
            for col in c.columns:
                m = re.match(r"(\d+)/1/(\d+)\s*-\s*\d+/\d+/\d+\s*Clicks", str(col).strip())
                if m:
                    month = pd.Timestamp(f"20{int(m.group(2)) % 100:02d}-{int(m.group(1)):02d}-01")
                    rows.append({"month": month, "workbook": os.path.basename(p), "clicks": int(row[col])})
        return pd.DataFrame(rows)
    return _cached("gsc_site_clicks", build)


def ads():
    """File 12, past Google Ads keyword results."""
    def build():
        a = pd.read_excel(path("ads"), sheet_name="Search keyword report All time ")
        for c in ["Cost", "Clicks", "Impr."]:
            a[c] = pd.to_numeric(a[c], errors="coerce")
        a["kw"] = a["Keyword"].astype(str).str.strip('[]"+').str.lower()
        return a
    return _cached("ads", build)


def ads_negatives():
    """File 12, words Weavve blocked before."""
    return _cached("ads_negatives", lambda: pd.read_excel(path("ads"), sheet_name="Negative Keyword report "))


def ads_red_list():
    """File 12, words Weavve marked red on the Filtered sheet (don't target)."""
    import openpyxl
    wb = openpyxl.load_workbook(path("ads"))
    red = set()
    for row in wb["Filtered"].iter_rows(min_row=2):
        if row[1].fill.fill_type and row[1].fill.fgColor.rgb == "FFFF0000":
            red.add(str(row[1].value).strip('[]"').lower())
    return sorted(red)
