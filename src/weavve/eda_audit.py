"""Read-only, aggregate column audit of the supplied Weavve files.

No cell values, identifiers, search terms, URLs, or category labels leave memory.
The returned structure contains source names, schema, counts and distributions only.
"""

from __future__ import annotations

import csv
import hashlib
import math
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook


EXPECTED_FILES = {"GSC": 38, "Semrush": 43, "Orders": 1,
                  "Product": 1, "Discount": 1, "Loyalty": 1, "Ads": 1}
BOOKS = {
    "Orders": "C.Order _ Transaction-Level (All-Time).xlsx",
    "Product": "D.Product _ SKU Master File.xlsx",
    "Discount": "E.Discount Report _ All-Time.xlsx",
    "Loyalty": "F.Loyalty _ Customers, Earning Actions, Redemptions History _ All-Time.xlsx",
    "Ads": "12.WH Google Ads 2019 - 2026 Keywords.xlsx",
}
SENSITIVE = re.compile(r"(?:^|[^a-z])(?:id|name|email|code|sku|keyword|query|queries|url|page|description|title|reason|campaign|group|filter)(?:$|[^a-z])", re.I)
MEASURE = re.compile(r"clicks?|impressions?|\bimp\b|\bctr\b|position|cost|cpc|cpm|sales|discounts?|quantity|points|volume|traffic|competition|difficulty|conversions?|rate|spent|weight|meters|height|length|width|stock|orders|used|value", re.I)
DATE_NAME = re.compile(r"date|timestamp|\bday\b|\bstart\b|\bend\b|issued", re.I)
CARDINALITY_CAP = 50_000


def blank(value):
    return value is None or isinstance(value, str) and not value.strip()


def value_type(value):
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (date, datetime)):
        return "date"
    if isinstance(value, (int, float)):
        return "number"
    return "text"


def number(value):
    if blank(value) or isinstance(value, bool) or isinstance(value, (date, datetime)):
        return None
    text = str(value).strip().replace(",", "")
    if text.endswith("%"):
        text = text[:-1]
    try:
        result = float(text)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def parsed_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for pattern in ("%d/%m/%Y", "%m/%d/%Y", "%d-%b-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    return None


def quantile(sorted_values, fraction):
    if not sorted_values:
        return None
    point = (len(sorted_values) - 1) * fraction
    low = math.floor(point)
    high = math.ceil(point)
    return round(sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (point - low), 4)


class Column:
    def __init__(self, position, header):
        self.position = position
        self.header = header
        self.missing = 0
        self.types = Counter()
        self.distinct = set()
        self.distinct_capped = False
        self.numbers = []
        self.numeric_parseable = 0
        self.dates = []
        self.date_parseable = 0
        self.text_lengths = []
        # Treat any identifier-like field as sensitive, including numeric IDs.
        self.sensitive = bool(SENSITIVE.search(header))
        self.measure = bool(MEASURE.search(header)) and not self.sensitive
        self.date_field = bool(DATE_NAME.search(header))

    def add(self, value):
        if blank(value):
            self.missing += 1
            return
        self.types[value_type(value)] += 1
        canonical = str(value).strip()
        if not self.distinct_capped:
            self.distinct.add(canonical)
            if len(self.distinct) >= CARDINALITY_CAP:
                self.distinct_capped = True
                self.distinct.clear()
        if isinstance(value, str):
            self.text_lengths.append(len(value))
        if not self.sensitive:
            parsed = number(value)
            if parsed is not None:
                self.numeric_parseable += 1
                self.numbers.append(parsed)
        if self.date_field:
            parsed = parsed_date(value)
            if parsed is not None:
                self.date_parseable += 1
                self.dates.append(parsed)

    def result(self, rows):
        nonmissing = rows - self.missing
        output = {
            "position": self.position, "header": self.header,
            "missing": self.missing, "missing_pct": round(100 * self.missing / rows, 2) if rows else None,
            "nonmissing": nonmissing, "raw_types": dict(self.types),
            "distinct_count": None if self.distinct_capped else len(self.distinct),
            "distinct_at_least": CARDINALITY_CAP if self.distinct_capped else None,
        }
        if self.text_lengths:
            output["text_length"] = {"min": min(self.text_lengths),
                                      "median": quantile(sorted(self.text_lengths), .5),
                                      "max": max(self.text_lengths)}
        if self.numbers and (self.measure or self.numeric_parseable / nonmissing >= .8):
            values = sorted(self.numbers)
            output["numeric"] = {
                "parseable": self.numeric_parseable,
                "unparseable_nonmissing": nonmissing - self.numeric_parseable,
                "negative": sum(x < 0 for x in values), "zero": sum(x == 0 for x in values),
                "min": quantile(values, 0), "p25": quantile(values, .25),
                "median": quantile(values, .5), "p75": quantile(values, .75),
                "p99": quantile(values, .99), "max": quantile(values, 1),
            }
        if self.date_field:
            output["date"] = {"parseable": self.date_parseable,
                              "unparseable_nonmissing": nonmissing - self.date_parseable,
                              "min": min(self.dates).isoformat() if self.dates else None,
                              "max": max(self.dates).isoformat() if self.dates else None}
        return output


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(data, ads=None):
    data = Path(data).expanduser().resolve()
    if not data.is_dir():
        raise FileNotFoundError(f"WEAVVE_DATA is not a directory: {data}")
    paths = []
    for group, name in BOOKS.items():
        path = Path(ads).expanduser().resolve() if group == "Ads" and ads else data / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing {group} source: {path}; set WEAVVE_ADS for a separate Ads workbook")
        paths.append((group, path))
    paths.extend(("GSC", p) for p in sorted(data.glob("A.SEO*/*/*.xlsx")) if not p.name.startswith("~$"))
    paths.extend(("Semrush", p) for p in sorted(data.glob("B.SEO*/*.csv")))
    counts = Counter(group for group, _ in paths)
    if dict(counts) != EXPECTED_FILES:
        raise ValueError(f"Source-count drift: {dict(counts)}; expected {EXPECTED_FILES}. Review the inventory before comparing results")
    return paths


def table_profile(rows, header, source, group, sheet, header_row, headerless=False):
    columns = [Column(i + 1, str(name).strip() if not blank(name) else "") for i, name in enumerate(header)]
    row_count = blank_rows = 0
    for row in rows:
        if not any(not blank(v) for v in row):
            blank_rows += 1
            continue
        row_count += 1
        while len(columns) < len(row):
            added = Column(len(columns) + 1, "")
            added.missing = row_count - 1
            columns.append(added)
        for i, col in enumerate(columns):
            col.add(row[i] if i < len(row) else None)
    # A populated blank-header column is retained by its 1-based position.
    active = [col.result(row_count) for col in columns if row_count - col.missing]
    names = [col["header"] for col in active if col["header"]]
    duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
    flags = []
    if headerless:
        flags.append("headerless_sheet")
    if any(not col["header"] for col in active):
        flags.append("populated_blank_header")
    if duplicates:
        flags.append("duplicate_header")
    if row_count == 0:
        flags.append("no_data_rows")
    for col in active:
        if col["missing_pct"] is not None and col["missing_pct"] >= 50:
            flags.append(f"high_missing:{col['position']}")
        numeric = col.get("numeric")
        if numeric and numeric["unparseable_nonmissing"]:
            flags.append(f"non_numeric_measure:{col['position']}")
        dates = col.get("date")
        if dates and dates["unparseable_nonmissing"]:
            flags.append(f"unparsed_date:{col['position']}")
    return {"group": group, "source": source, "sheet": sheet, "header_row": header_row,
            "headerless": headerless, "rows": row_count, "blank_rows": blank_rows,
            "columns": active, "active_columns": len(active), "duplicate_headers": duplicates,
            "flags": flags}


def workbook_tables(group, path, source):
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        for sheet in book:
            iterator = iter(sheet.iter_rows(values_only=True))
            first = next(iterator, ())
            headerless = not any(not blank(v) for v in first)
            if headerless:
                from itertools import chain
                rows = chain((first,), iterator)
                header = ()
                header_row = None
            else:
                rows = iterator
                header = first
                header_row = 1
            yield table_profile(rows, header, source, group, sheet.title, header_row, headerless)
    finally:
        book.close()


def csv_tables(group, path, source):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader, ())
        yield table_profile(reader, header, source, group, "CSV", 1)


def audit(data, ads=None):
    paths = inventory(data, ads)
    result = {"method": "All source files and all sheets; every populated column by physical position. "
                        "Missingness uses nonempty rows. Distinct counts are exact below 50000 and lower-bounded above. "
                        "Numeric summaries are restricted to measure headers; no values or sensitive labels are exported.",
              "expected_file_counts": EXPECTED_FILES, "files": [], "tables": []}
    for group, path in paths:
        source = path.name if group not in {"GSC", "Semrush"} else str(path.relative_to(Path(data).resolve())).replace("\\", "/")
        result["files"].append({"group": group, "source": source, "bytes": path.stat().st_size,
                                "sha256": sha256(path)})
        result["tables"].extend((csv_tables if path.suffix.lower() == ".csv" else workbook_tables)(group, path, source))
    result["summary"] = {
        "files": len(result["files"]), "tables": len(result["tables"]),
        "data_rows": sum(t["rows"] for t in result["tables"]),
        "populated_columns": sum(t["active_columns"] for t in result["tables"]),
        "groups": dict(Counter(f["group"] for f in result["files"])),
        "flagged_tables": sum(bool(t["flags"]) for t in result["tables"]),
    }
    return result
