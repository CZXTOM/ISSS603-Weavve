"""Where the data lives and where outputs go.

Data never goes into this repo. Put the Weavve files in data/ (ignored by git),
or point the WEAVVE_DATA environment variable at your own copy.
Outputs go to ~/Desktop/weavve_outputs unless WEAVVE_OUT says otherwise.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("WEAVVE_DATA", ROOT / "data")).expanduser()
OUT = Path(os.environ.get("WEAVVE_OUT", Path.home() / "Desktop" / "weavve_outputs")).expanduser()
CACHE = OUT / "cache"

FILES = {
    "gsc": "A.SEO _ GSC Impressions & Clicks _ 2023 -2026",       # file 1, folder of workbooks
    "semrush": "B.SEO _ Semrush Organic Keywords _ 2023 Jan - 2026 Jul",  # file 2, folder of csv
    "orders": "C.Order _ Transaction-Level (All-Time).xlsx",       # file 3
    "skus": "D.Product _ SKU Master File.xlsx",                    # file 4
    "discounts": "E.Discount Report _ All-Time.xlsx",              # file 8
    "loyalty": "F.Loyalty _ Customers, Earning Actions, Redemptions History _ All-Time.xlsx",  # file 9.1
    "ads": "12.WH Google Ads 2019 - 2026 Keywords.xlsx",           # file 12
}


def path(key):
    p = DATA / FILES[key]
    if not p.exists():
        raise FileNotFoundError(f"Can't find {p}. Put the Weavve files in {DATA} or set WEAVVE_DATA. See data/README.md")
    return p


def ensure_out():
    CACHE.mkdir(parents=True, exist_ok=True)
    return OUT
