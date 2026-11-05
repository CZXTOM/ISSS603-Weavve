"""Conservative, provenance-preserving tables for the non-transaction workbooks.

Rows are retained, including rows after the transaction cutoff. Explicit window flags
let consumers choose a common period without turning snapshots into event histories.
Subscriber profiles are not inferred consented signups; issued reward vouchers are
not inferred membership. Funnel observations remain monthly and geography-specific.
"""

from calendar import monthrange
from collections import Counter
from datetime import date, datetime
from io import BytesIO
import math
import re

import openpyxl


def _text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(_text(value).replace(",", ""))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = _text(value)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _provenance(source, sheet, row):
    return {
        "source_file": source.relative_path,
        "source_sha256": source.sha256,
        "source_sheet": sheet,
        "source_row": row,
    }


def _sheet_records(ws, source):
    """Keep original named fields, including duplicate names with explicit suffixes."""
    values = list(ws.values)
    first = next((i for i, row in enumerate(values) if any(_text(v) for v in row)), None)
    if first is None:
        return []
    seen = Counter()
    headers = []
    for i, value in enumerate(values[first]):
        name = _text(value) or f"unnamed_column_{i + 1}"
        seen[name] += 1
        headers.append(name if seen[name] == 1 else f"{name}__{seen[name]}")
    result = []
    for index, row in enumerate(values[first + 1:], first + 2):
        if not any(_text(v) for v in row):
            continue
        item = {key: row[i] if i < len(row) else None for i, key in enumerate(headers)}
        # Export metadata must never silently replace a source field.
        for key, value in _provenance(source, ws.title, index).items():
            if key in item:
                item[f"raw_{key}"] = item[key]
            item[key] = value
        result.append(item)
    return result


def build_support_tables(catalog, cutoff):
    """Return local tables, warnings and aggregate checks; never mutate source files."""
    cutoff = _as_date(cutoff)
    if cutoff is None:
        raise ValueError("cutoff must be an ISO date or date object")
    tables, warnings, checks = {}, [], {}

    def read(code, requested):
        sources = catalog.files(code)
        if len(sources) != 1:
            raise ValueError(f"Expected one source for {code}; found {len(sources)}")
        source = sources[0]
        book = openpyxl.load_workbook(BytesIO(source.read_bytes()), read_only=True, data_only=True)
        try:
            for table, sheet in requested.items():
                title = sheet if sheet is not None else next(
                    (s for s in book.sheetnames if s.strip().casefold() not in {"read me", "readme", "definitions", "legends"}), book.sheetnames[0])
                if title not in book.sheetnames:
                    raise ValueError(f"Missing required sheet {title!r} in {source.name}")
                tables[table] = _sheet_records(book[title], source)
            return source, book.sheetnames
        finally:
            book.close()

    read("G", {"g_person_map": "Person map", "g_order_channels": "Order channel"})
    persons = {_text(row.get("person_id")) for row in tables["g_person_map"] if _text(row.get("person_id"))}
    orders = {_text(row.get("Order ID")) for row in tables["g_order_channels"]}
    for row in tables["g_person_map"]:
        row["clean_customer_id"] = _text(row.get("Customer ID")) or None
        row["clean_person_id"] = _text(row.get("person_id")) or None
    for row in tables["g_order_channels"]:
        row["clean_order_id"] = _text(row.get("Order ID")) or None
        row["clean_channel_detail"] = _text(row.get("channel_detail")) or None
    read("D", {"products": None})
    read("I", {"clearance_skus": "Clearance SKUs"})
    for table, field in (("products", "Code"), ("clearance_skus", "SKU Code")):
        counts = Counter(_text(r.get(field)) for r in tables[table])
        for row in tables[table]:
            sku = _text(row.get(field))
            row["clean_sku"] = sku or None
            row["clean_sku_missing"] = not sku
            row["clean_sku_duplicated"] = bool(sku and counts[sku] > 1)
    source, sheets = read("E", {"discounts": "Full Discounts Report"})
    book = openpyxl.load_workbook(BytesIO(source.read_bytes()), read_only=True, data_only=True)
    summary_names = {
        "FirstWelcome Order Discount by ": "discount_summary",
        "Discount by Year": "discount_by_year",
        "Alia by Discount Depth": "discount_alia_depth",
        "Discount Detail by Code": "discount_detail_by_code",
    }
    try:
        for sheet in sheets:
            if sheet == "Full Discounts Report":
                continue
            name = summary_names.get(sheet, "discount_" + re.sub(r"\W+", "_", sheet).strip("_").lower())
            tables[name] = _sheet_records(book[sheet], source)
    finally:
        book.close()
    for row in tables["discounts"]:
        row["clean_code_name"] = _text(row.get("Name")) or None
        row["clean_start_date"] = _as_date(row.get("Start"))
        row["clean_end_date"] = _as_date(row.get("End"))
        row["clean_times_used"] = _number(row.get("Times Used In Total"))
        row["clean_usage_observed"] = None if row["clean_times_used"] is None else row["clean_times_used"] > 0
    read("F", {"loyalty_rewards": "Redemptions"})
    for row in tables["loyalty_rewards"]:
        used = _number(row.get("times_used"))
        order = _text(row.get("order_id"))
        row.update({
            "clean_reward_issue_date": _as_date(row.get("date")),
            "clean_reward_usage_status": "unknown" if used is None else "used" if used > 0 else "issued_unused",
            "clean_reward_used": None if used is None else used > 0,
            "clean_order_id": order or None,
            "clean_order_in_g": bool(order and order in orders),
        })
    read("J", {"subscribers": "Subscribers"})
    for row in tables["subscribers"]:
        person = _text(row.get("person_id"))
        created = _as_date(row.get("Profile Created On"))
        row.update({
            "clean_person_id": person or None,
            "clean_person_in_g": bool(person and person in persons),
            "clean_profile_created_date": created,
            "clean_profile_created_by_cutoff": None if created is None else created <= cutoff,
            "clean_initial_source_label": _text(row.get("Initial Source")) or None,
        })
    read("K", {"email_campaigns": None})
    for row in tables["email_campaigns"]:
        sent = _as_date(row.get("Send Date"))
        recipients = _number(row.get("Total Recipients"))
        clicks = _number(row.get("Unique Clicks"))
        opens = _number(row.get("Unique Opens"))
        row.update({
            "clean_send_date": sent,
            "in_transaction_window": None if sent is None else sent <= cutoff,
            "clean_recipients_at_least_20": None if recipients is None else recipients >= 20,
            "clean_unique_click_rate": clicks / recipients if recipients is not None and recipients > 0 and clicks is not None and clicks >= 0 else None,
            "clean_unique_open_rate": opens / recipients if recipients is not None and recipients > 0 and opens is not None and opens >= 0 else None,
            "clean_rate_denominator": "Total Recipients",
        })
    source = catalog.files("L")[0]
    book = openpyxl.load_workbook(BytesIO(source.read_bytes()), read_only=True, data_only=True)
    try:
        ws = book.worksheets[0]
        matrix = list(ws.values)
        header_index = next((i for i, row in enumerate(matrix) if any(isinstance(v, (date, datetime)) for v in row)), None)
        if header_index is None:
            raise ValueError("File L has no date-labelled monthly columns")
        geography = next((_text(row[1]) for row in matrix[:header_index] if len(row) > 1 and "singapore" in _text(row[1]).lower()), None)
        metric_rows = [(i + 1, row) for i, row in enumerate(matrix[header_index + 1:], header_index + 1) if row and _text(row[0])]
        monthly = []
        raw_funnel = []
        for column, value in enumerate(matrix[header_index]):
            if not isinstance(value, (date, datetime)):
                continue
            month = _as_date(value).replace(day=1)
            end = month.replace(day=monthrange(month.year, month.month)[1])
            item = {"month": month, "month_end": end, "geography": geography,
                    "in_transaction_complete_month_window": end <= cutoff,
                    **_provenance(source, ws.title, header_index + 1)}
            for row_number, raw in metric_rows:
                label = _text(raw[0])
                cell = raw[column] if column < len(raw) else None
                item[label] = cell
                raw_funnel.append({"month": month, "metric": label, "value": cell,
                                   "source_column": column + 1, **_provenance(source, ws.title, row_number)})
            sessions, purchases = _number(item.get("Sessions")), _number(item.get("Orders Placed"))
            item["clean_orders_per_session"] = purchases / sessions if sessions is not None and sessions > 0 and purchases is not None and purchases >= 0 else None
            monthly.append(item)
        tables["website_funnel"] = monthly
        tables["website_funnel_cells"] = raw_funnel
    finally:
        book.close()
    warnings.extend([
        "File G person labels use the supplier's matching; no identity accuracy is inferred.",
        "File J profiles are snapshot records, not verified voluntary signups, marketing consent or paid-source labels.",
        "File F records issued reward vouchers and their recorded usage, not a complete membership or points ledger.",
        "Email rates use unique events / Total Recipients; bot filtering and human engagement are not established.",
        "File L is monthly: only months ending on/before cutoff enter the complete-month window; geography is retained.",
    ])
    checks["row_counts"] = {name: len(rows) for name, rows in tables.items()}
    checks["cutoff"] = cutoff.isoformat()
    checks["campaigns_with_invalid_send_date"] = sum(r["clean_send_date"] is None for r in tables["email_campaigns"])
    checks["subscribers_with_unmapped_person"] = sum(bool(r["clean_person_id"]) and not r["clean_person_in_g"] for r in tables["subscribers"])
    return {"tables": tables, "warnings": warnings, "checks": checks}
