"""Reads the Weavve files and builds the order view that every final-report check uses.

Files are found by their letter or number (C to L and 12) under weavve.paths.DATA, either extracted or still
inside the supplied zip files. Each file's SHA-256 is compared with the copy the report used. A different copy
prints a warning but still runs. Nothing is written back, and no person-level output is saved.

The order view applies the Part A rules: cancelled orders out, repeated discount lines out (when asked),
refunds kept with their order, and zero or negative orders left out of purchases (when asked). It does not
divide marketplace sales by 1.09. The checks that need the GST correction apply it themselves.
"""

import hashlib
import math
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from io import BytesIO
from zipfile import ZipFile

import openpyxl

from weavve.paths import DATA

# SHA-256 of the files the final report used, from Weavve data dumps 1 and 2
EXPECTED = {
    "C": "c7c16e8f3d1cca6ef89fe225d30418face577b28a994ddf4e06a3e37db242439",  # C. Orders
    "D": "838f9d50413d7ce117c9d184ebabf1cab945d12ec096dce0ebfe8ced8a06f396",  # D. Product SKU master
    "E": "5f7c02828244c598efa110aca32b2c5c3282912617f568e48fd97c81f7fea363",  # E. Discount report
    "F": "9dc943f8dbc0030c9ab22539b34aa390f4afe0c37d1efafe547c7c5b5f4ea430",  # F. Loyalty
    "G": "7a3dab34f4b14449cf21d6a3d5034cc8874a645240f5f82d35f797e42e13a34c",  # G. Customer and channel map
    "I": "6e9bec7e52b84239d24a79af36793f55434fd4a0acef9dc7bafb7ad14a4a8935",  # I. Clearance sale SKUs
    "J": "0699d5dd98e1afd9b6eded3aa2c2ef10118c7cec42c9d4357fcbbb79b547d935",  # J. Subscribers
    "K": "2d0b23e91b3d4ad6bc5dbb084bdc1d9645441d6812f7e71b3163c3c568061461",  # K. Campaign report
    "L": "dffe9cb5d96855f26a5d2a32ac9a4724402c60115056d8e446f909d3cffb0f7b",  # L. Website funnel
    "12": "412eddfb451fbf63e775cffffda62a86498cf2749e36c4069c295f249ba71d36",  # 12. Google Ads keywords
}
SOURCES = {}  # where each file was read from, and whether it matched


def text(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def num(v):
    if v is None or isinstance(v, bool) or not text(v):
        return None
    try:
        n = float(text(v).replace(",", ""))
    except (ValueError, TypeError):
        return None
    return n if math.isfinite(n) else None


def money(v):
    return Decimal(text(v) or "0")


def day(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if not text(v):
        return None
    try:
        return datetime.fromisoformat(text(v).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _find(code):
    """Bytes and location of the file whose name starts with '<code>.', as a file or inside a zip."""
    prefix = f"{code}."
    extracted = sorted(p for p in DATA.rglob("*.xlsx") if p.name.startswith(prefix))
    if extracted:
        return extracted[0].read_bytes(), str(extracted[0].relative_to(DATA))
    for z in sorted(DATA.rglob("*.zip")):
        with ZipFile(z) as zf:
            for m in zf.namelist():
                if m.rsplit("/", 1)[-1].startswith(prefix) and m.endswith(".xlsx"):
                    return zf.read(m), f"{z.relative_to(DATA)} > {m}"
    raise FileNotFoundError(
        f"Cannot find Weavve file {code} under {DATA}. Put the Weavve files in data/ or set WEAVVE_DATA."
    )


@lru_cache(None)
def payload(code):
    data, where = _find(code)
    actual = hashlib.sha256(data).hexdigest()
    same = actual == EXPECTED.get(code)
    SOURCES[code] = {"file": where, "same_as_report": same}
    if not same:
        print(
            f"Warning: file {code} differs from the copy the report used, "
            f"so some numbers may differ ({where})."
        )
    return data


@lru_cache(None)
def matrix(code, sheet=None):
    wb = openpyxl.load_workbook(BytesIO(payload(code)), read_only=True, data_only=True)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    result = [tuple(r) for r in ws.values if any(text(v) for v in r)]
    wb.close()
    return result


@lru_cache(None)
def rows(code, sheet=None):
    m = matrix(code, sheet)
    headers = [text(v) for v in m[0]]
    named = [h for h in headers if h]
    assert len(named) == len(set(named)), (code, sheet, "duplicate non-blank headers")
    return [{h: r[i] if i < len(r) else None for i, h in enumerate(headers) if h} for r in m[1:]]


def mapping(sheet, key, value):
    records = rows("G", sheet)
    assert all(text(r[key]) and text(r[value]) for r in records)
    assert len({text(r[key]) for r in records}) == len(records)
    return {text(r[key]): text(r[value]) for r in records}


def repeat_positions(records):
    """Positions of order lines that repeat an earlier line's money exactly.

    The export writes these repeats for stacked discounts.
    """
    seen, positions = set(), set()
    for i, r in enumerate(records):
        line = text(r["Line item ID"])
        if line in ("", "0"):
            continue
        kind = text(r["Order or sales reversal"])
        sig = (
            text(r["Order ID"]),
            line,
            kind,
            day(r["Day"]),
            text(r["Product variant SKU at time of sale"]),
            *(money(r[k]) for k in ("Quantity ordered", "Net sales", "Total sales", "Discounts", "Orders")),
            text(r["Refund ID"]) if kind == "reversal" else "",
        )
        if sig in seen:
            positions.add(i)
        else:
            seen.add(sig)
    return positions


def order_view(records=None, *, drop_cancelled=True, drop_repeated=False, positive_only=True):
    """One entry per order, with its person (File G), platform (File G) and date (earliest sale line)."""
    records = rows("C", "Order  Transaction-Level") if records is None else records
    pm = mapping("Person map", "Customer ID", "person_id")
    cm = mapping("Order channel", "Order ID", "channel_detail")
    dup = repeat_positions(records) if drop_repeated else set()
    groups = defaultdict(list)
    for i, r in enumerate(records):
        groups[text(r["Order ID"])].append((i, r))
    out = []
    for oid, rs in groups.items():
        cancelled = any(r["Is canceled order"] in (True, "True") for _, r in rs)
        if drop_cancelled and cancelled:
            continue
        cids = {text(r["Customer ID"]) for _, r in rs}
        persons = {pm[c] for c in cids}
        assert len(cids) == len(persons) == 1, "Ambiguous identity within an Order ID"
        kept = [r for i, r in rs if i not in dup]
        net = sum((money(r["Net sales"]) for r in kept), Decimal(0))
        if positive_only and net <= 0:
            continue
        sales = [day(r["Day"]) for _, r in rs if text(r["Order or sales reversal"]) == "order"]
        dates = sales or [day(r["Day"]) for _, r in rs]
        assert all(d is not None for d in dates)
        out.append(
            {
                "order": oid,
                "customer": next(iter(cids)),
                "person": next(iter(persons)),
                "channel": cm[oid],
                "original_channels": sorted({text(r["Order sales channel"]) for _, r in rs}),
                "date": min(dates),
                "net": float(net),
                "cancelled": cancelled,
                "has_negative_discount": any(money(r["Discounts"]) < 0 for r in kept),
                "discount": float(-sum((money(r["Discounts"]) for r in kept), Decimal(0))),
                "rows": kept,
            }
        )
    return out


def funnel_monthly():
    """File L: Sessions, Add to Cart and Orders Placed for each month, read from the month columns."""
    m = matrix("L")
    header = next(r for r in m if len(r) > 2 and day(r[2]))
    byname = {text(r[0]): r for r in m if r and text(r[0])}
    out = []
    for i, v in enumerate(header):
        if isinstance(v, (datetime, date)):
            out.append(
                {
                    "month": day(v),
                    **{k: num(byname[k][i]) for k in ("Sessions", "Add to Cart", "Orders Placed")},
                }
            )
    return out


@lru_cache(None)
def search_console():
    """File A: Google Search Console exports, one workbook per pair of months, Singapore only.

    Returns {(year, month): {"clicks": Singapore clicks, "queries": {query: clicks}}}. Monthly totals come from the
    Countries sheet. Query clicks are kept only when the workbook's own filter is Singapore, and they cover the top
    queries Search Console lists, not every query.
    """
    books = []
    for p in sorted(DATA.rglob("*.xlsx")):
        if "A.SEO" in str(p):
            books.append(p.read_bytes())
    for z in sorted(DATA.rglob("*.zip")):
        with ZipFile(z) as zf:
            books += [zf.read(m) for m in sorted(zf.namelist()) if "/A.SEO" in m and m.endswith(".xlsx")]
    out = {}
    for data in books:
        wb = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)
        filters = {text(r[0]): text(r[1]) for r in wb["Filters"].iter_rows(values_only=True) if r and len(r) > 1}
        countries = [tuple(r) for r in wb["Countries"].iter_rows(values_only=True)]
        queries = [tuple(r) for r in wb["Queries"].iter_rows(values_only=True)]
        wb.close()
        sg = next((r for r in countries[1:] if r and r[0] == "Singapore"), None)
        qhead = [text(h) for h in queries[0]]
        for i, h in enumerate(countries[0]):
            h = text(h)
            parts = h.split(" ")
            if not h.endswith(" Clicks") or "/" not in parts[0] or sg is None:
                continue
            month, _, year = parts[0].split("/")
            key = (2000 + int(year), int(month))
            if key in out:
                continue
            label = h[: -len(" Clicks")]
            short = date(2000, int(month), 1).strftime("%b") + " Clicks"
            j = next((k for k, q in enumerate(qhead) if q in (label + " Clicks", short)), None)
            singapore = filters.get("Country") == "Singapore"
            out[key] = {
                "clicks": num(sg[i]) or 0.0,
                "queries": {
                    text(r[0]): num(r[j]) or 0.0
                    for r in queries[1:]
                    if singapore and j is not None and r and len(r) > j and text(r[0])
                },
            }
    return out
