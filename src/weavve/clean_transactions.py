"""Pure transaction cleaning shared by local notebooks and exports.

Input dictionaries are raw workbook records. Source columns are preserved;
lower-case fields describe the cleaned view. Amounts are Decimal and dates are
datetime.date. No input is mutated, no file is read, and no data is embedded here.
"""

from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re


MARKETPLACE_SOURCE = "Easy Shopee, TikTok & Lazada"
WEBSITE_SOURCE = "Online Store"
ANNOTATIONS = ("Discount name", "Discount code", "Discount title", "Discount type", "Discount value")
MONEY_FIELDS = ("Quantity ordered", "Net sales", "Total sales", "Discounts", "Orders")
LINE_FIELDS = {
    "source_row", "order_id", "customer_id", "person_id", "channel_detail", "is_website",
    "order_date", "line_date", "net_raw", "net", "discount_raw", "discount", "gst_adjusted",
    "sku", "product_match", "is_order_level", "clearance_sku", "clearance_timing",
    "clearance_status", "clearance_quarter_start", "clearance_quarter_end",
    "is_special_account", "discount_code_is_date", "exclusion_reason", "duplicate_of_source_row",
}


def _text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _identifier(value, label):
    result = _text(value)
    if not result or isinstance(value, bool):
        raise ValueError(f"Missing or invalid {label}")
    if isinstance(value, (float, Decimal)) and not Decimal(str(value)).is_finite():
        raise ValueError(f"Non-finite {label}")
    return result


def _money(value, label):
    if value is None or isinstance(value, bool) or not _text(value):
        raise ValueError(f"Missing or invalid numeric value for {label}")
    try:
        result = Decimal(_text(value))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric value for {label}") from exc
    if not result.is_finite():
        raise ValueError(f"Non-finite numeric value for {label}")
    return result


def _day(value, label):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(_text(value).replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise ValueError(f"Missing or invalid date for {label}") from exc


def _cancelled(value):
    if value is True or value == 1 or _text(value).lower() == "true":
        return True
    if value is False or value == 0 or _text(value).lower() == "false":
        return False
    raise ValueError("Is canceled order must be a boolean, 0, 1, True or False")


def _index(rows, key, value=None, label="mapping"):
    result = {}
    for row in rows:
        identity = _identifier(row.get(key), f"{label} {key}")
        if identity in result:
            raise ValueError(f"Duplicate {label} key: {identity}")
        result[identity] = _identifier(row.get(value), f"{label} {value}") if value else dict(row)
    return result


def _clearance_rule(row):
    if row is None:
        return "not_listed", None, None
    remarks = _text(row.get("Remarks (estimated)"))
    match = re.fullmatch(r"(On clearance|Discontinued) since Q([1-4]) (\d{4})", remarks, re.I)
    if not match:
        return "unknown", None, None
    status, quarter, year = match.groups()
    quarter, year = int(quarter), int(year)
    start = date(year, quarter * 3 - 2, 1)
    end = date(year + (quarter == 4), quarter * 3 % 12 + 1, 1)
    return "clearance" if status.lower() == "on clearance" else "discontinued", start, end


def clean_transactions(
    order_rows, person_rows, channel_rows, product_rows, clearance_rows, *,
    special_person_ids=(), gst_from=date(2025, 8, 26), gst_divisor=Decimal("1.09"),
):
    """Return cleaned line/order tables, exclusions, aggregate checks and warnings.

    A cancelled flag removes the whole order. Repeated economic lines are removed
    only when an earlier retained line has a different discount annotation. Equal
    lines with identical annotations are retained and flagged for review.

    The tax adjustment requires the original marketplace label, a qualifying line
    date, nonzero Net sales, and Net sales == Total sales on that line. Refunds keep
    their signed amounts; order_date uses the earliest sale line. Nonpositive
    orders remain in the table with is_purchase=False.

    is_website means original Online Store, not every File G Own store platform.
    Customer analysis eligibility is a positive website/Shopee order belonging to
    a nonspecial person. Unknown SKUs and listed clearance SKUs are never removed.
    Clearance timing is relative to the line date; within-quarter timing remains
    uncertain. Discontinuation is explicitly separate from a clearance start.
    discount_code_is_date flags Excel date-valued discount codes without guessing
    the original code. Discount annotation means name, code, title, type or value;
    a code change alone can identify an otherwise identical stacked-discount line.

    The optional source_row metadata preserves an upstream Excel row number;
    otherwise input row zero is assumed to be Excel row 2. All joins validate
    uniqueness and full transaction coverage before exclusions are applied.
    """
    gst_from = _day(gst_from, "gst_from")
    gst_divisor = _money(gst_divisor, "gst_divisor")
    if gst_divisor <= 0:
        raise ValueError("gst_divisor must be positive")
    people = _index(person_rows, "Customer ID", "person_id", "person map")
    channels = _index(channel_rows, "Order ID", "channel_detail", "channel map")
    products = _index(product_rows, "Code", label="product master")
    clearance = _index(clearance_rows, "SKU Code", label="clearance list")
    special = {_identifier(p, "special person ID") for p in special_person_ids}
    prepared, source_rows = [], set()
    groups = defaultdict(list)
    for position, original in enumerate(order_rows, start=2):
        raw = dict(original)
        collision = (set(raw) & LINE_FIELDS) - {"source_row"}
        if collision:
            raise ValueError(f"Raw records collide with normalized fields: {sorted(collision)}")
        source_row = raw.get("source_row", position)
        if isinstance(source_row, bool) or not isinstance(source_row, int) or source_row < 2 or source_row in source_rows:
            raise ValueError("source_row must be a unique integer Excel row number >= 2")
        source_rows.add(source_row)
        oid = _identifier(raw.get("Order ID"), f"Order ID at row {source_row}")
        cid = _identifier(raw.get("Customer ID"), f"Customer ID at row {source_row}")
        if cid not in people:
            raise ValueError(f"Customer ID missing from person map at row {source_row}: {cid}")
        if oid not in channels:
            raise ValueError(f"Order ID missing from channel map at row {source_row}: {oid}")
        kind = _text(raw.get("Order or sales reversal")).lower()
        if kind not in ("order", "reversal"):
            raise ValueError(f"Invalid Order or sales reversal at row {source_row}")
        amounts = {key: _money(raw.get(key), f"{key} at row {source_row}") for key in MONEY_FIELDS}
        record = {
            "raw": raw, "source_row": source_row, "order_id": oid, "customer_id": cid,
            "person_id": people[cid], "line_date": _day(raw.get("Day"), f"Day at row {source_row}"),
            "kind": kind, "amounts": amounts, "cancelled": _cancelled(raw.get("Is canceled order")),
            "line_id": _text(raw.get("Line item ID")),
            "original_channel": _identifier(raw.get("Order sales channel"), f"Order sales channel at row {source_row}"),
        }
        groups[oid].append(record)
        prepared.append(record)

    warnings, counters = [], Counter()
    lines, excluded, orders = [], [], []
    for oid in sorted(groups):
        records = sorted(groups[oid], key=lambda r: r["source_row"])
        cids = {r["customer_id"] for r in records}
        if len(cids) != 1:
            raise ValueError(f"Ambiguous Customer ID within order {oid}")
        cid = next(iter(cids))
        person = people[cid]
        original_channels = sorted({r["original_channel"] for r in records})
        sale_dates = [r["line_date"] for r in records if r["kind"] == "order"]
        order_date = min(sale_dates or [r["line_date"] for r in records])
        if not sale_dates:
            counters["orders_without_sale_line"] += 1
        is_cancelled = any(r["cancelled"] for r in records)
        is_website = WEBSITE_SOURCE in original_channels
        is_special = person in special
        if is_cancelled:
            counters["cancelled_orders"] += 1
        seen = defaultdict(list)
        kept = []
        for row in records:
            raw, amounts = row["raw"], row["amounts"]
            sku = _text(raw.get("Product variant SKU at time of sale"))
            status, start, end = _clearance_rule(clearance.get(sku))
            timing = "unknown" if start is None else "before" if row["line_date"] < start else "within" if row["line_date"] < end else "after"
            gst = (row["original_channel"] == MARKETPLACE_SOURCE and row["line_date"] >= gst_from
                   and amounts["Net sales"] != 0 and amounts["Net sales"] == amounts["Total sales"])
            divisor = gst_divisor if gst else Decimal(1)
            line = {
                **raw, "source_row": row["source_row"], "order_id": oid, "customer_id": cid,
                "person_id": person, "channel_detail": channels[oid], "is_website": is_website,
                "order_date": order_date, "line_date": row["line_date"],
                "net_raw": amounts["Net sales"], "net": amounts["Net sales"] / divisor,
                "discount_raw": -amounts["Discounts"], "discount": -amounts["Discounts"] / divisor,
                "gst_adjusted": gst, "sku": sku, "product_match": bool(sku and sku in products),
                "is_order_level": row["line_id"] in ("", "0"), "clearance_sku": sku in clearance,
                "clearance_timing": timing, "clearance_status": status,
                "clearance_quarter_start": start, "clearance_quarter_end": end,
                "is_special_account": is_special,
                "discount_code_is_date": isinstance(raw.get("Discount code"), date),
            }
            if is_cancelled:
                excluded.append({**line, "exclusion_reason": "cancelled_order", "duplicate_of_source_row": None})
                counters["cancelled_rows"] += 1
                continue
            signature = (
                oid, row["line_id"], row["kind"], row["line_date"], sku,
                *(amounts[k] for k in MONEY_FIELDS),
                _text(raw.get("Refund ID")) if row["kind"] == "reversal" else "",
            )
            annotation = tuple(_text(raw.get(k)) for k in ANNOTATIONS)
            duplicate = None
            if not line["is_order_level"]:
                duplicate = next((source for previous, source in seen[signature] if previous != annotation), None)
                if duplicate is None:
                    if seen[signature]:
                        counters["same_annotation_candidates_retained"] += 1
                    seen[signature].append((annotation, row["source_row"]))
            if duplicate is not None:
                excluded.append({**line, "exclusion_reason": "repeated_discount_line", "duplicate_of_source_row": duplicate})
                counters["repeated_discount_rows"] += 1
                continue
            lines.append(line)
            kept.append(line)
            counters["refund_rows"] += row["kind"] == "reversal"
        if is_cancelled:
            continue
        totals = {key: sum((r[key] for r in kept), Decimal(0)) for key in ("net_raw", "net", "discount_raw", "discount")}
        purchase = totals["net"] > 0
        orders.append({
            "order_id": oid, "customer_id": cid, "person_id": person, "channel_detail": channels[oid],
            "original_channels": original_channels, "order_date": order_date, **totals,
            "is_purchase": purchase, "is_special_account": is_special,
            "customer_analysis_eligible": purchase and not is_special and (is_website or channels[oid] == "Shopee"),
            "is_website": is_website,
        })

    if counters["same_annotation_candidates_retained"]:
        warnings.append(f"Retained {counters['same_annotation_candidates_retained']} same-money line candidates with identical discount annotations; review separately.")
    if counters["orders_without_sale_line"]:
        warnings.append(f"Used earliest observed line date for {counters['orders_without_sale_line']} orders without a sale line; their original sale dates are unavailable.")
    unknown_timing = sum(r["clearance_sku"] and r["clearance_timing"] == "unknown" for r in lines)
    if unknown_timing:
        warnings.append(f"Clearance timing could not be parsed for {unknown_timing} retained SKU-listed lines.")
    raw_net = sum((r["amounts"]["Net sales"] for r in prepared), Decimal(0))
    kept_raw_net = sum((r["net_raw"] for r in lines), Decimal(0))
    excluded_raw_net = sum((r["net_raw"] for r in excluded), Decimal(0))
    checks = {
        "input_rows": len(prepared), "input_orders": len(groups), "raw_customer_ids": len({r['customer_id'] for r in prepared}),
        "person_map_rows": len(people), "mapped_people": len(set(people.values())), "channel_map_rows": len(channels),
        "cancelled_orders": counters["cancelled_orders"], "cancelled_rows": counters["cancelled_rows"],
        "rows_after_cancellations": len(prepared) - counters["cancelled_rows"],
        "repeated_discount_rows": counters["repeated_discount_rows"], "excluded_rows": len(excluded),
        "clean_rows": len(lines), "clean_orders": len(orders), "purchase_orders": sum(o["is_purchase"] for o in orders),
        "nonpositive_orders": sum(not o["is_purchase"] for o in orders), "refund_rows": counters["refund_rows"],
        "gst_adjusted_rows": sum(r["gst_adjusted"] for r in lines),
        "gst_net_reduction": sum((r["net_raw"] - r["net"] for r in lines), Decimal(0)),
        "unknown_sku_rows": sum(not r["product_match"] and not r["is_order_level"] for r in lines),
        "order_level_rows": sum(r["is_order_level"] for r in lines),
        "clearance_sku_rows": sum(r["clearance_sku"] for r in lines),
        "special_account_orders": sum(o["is_special_account"] for o in orders),
        "customer_analysis_eligible_orders": sum(o["customer_analysis_eligible"] for o in orders),
        "same_annotation_candidates_retained": counters["same_annotation_candidates_retained"],
        "orders_without_sale_line": counters["orders_without_sale_line"],
        "input_net_raw": raw_net, "retained_net_raw": kept_raw_net, "excluded_net_raw": excluded_raw_net,
        "rows_reconcile": len(prepared) == len(lines) + len(excluded),
        "raw_net_reconciles": raw_net == kept_raw_net + excluded_raw_net,
    }
    return {
        "tables": {
            "order_lines": sorted(lines, key=lambda r: (r["order_id"], r["source_row"])),
            "orders": sorted(orders, key=lambda r: (r["order_date"], r["order_id"])),
            "excluded_order_lines": sorted(excluded, key=lambda r: r["source_row"]),
        },
        "checks": checks, "warnings": warnings,
    }
