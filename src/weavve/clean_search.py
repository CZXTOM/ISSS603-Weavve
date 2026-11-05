"""Search tables with explicit source adjudication and no invented missing-query zeros.

GSC monthly selection requires an explicit Singapore/Web filter, a full calendar
month, coherent period headers, a canonical Date filter and a unique Singapore row.
The canonical filters are the first contiguous Filter/Value block, not handwritten
summary blocks appended later. A primary candidate matches that Date range. When
no full primary exists, use the latest coherent export's previous-month candidate.
Future/nonadjacent comparison periods and unresolved same-priority conflicts are
retained but excluded. All original workbook rows and candidates remain auditable.

This is a reproducible policy, not a claim that source metadata is infallible or
that absent query rows have zero traffic. Semrush feature visibility and historical
red-tier labels are retained separately; neither establishes paid cannibalization.
"""

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime
from io import BytesIO, StringIO
import csv
import hashlib
import re

import openpyxl

from .clean_support import _as_date, _number, _provenance, _sheet_records, _text


MONTHS = {name.lower(): i for i, names in enumerate(
    [(), ("Jan", "January"), ("Feb", "February"), ("Mar", "March"),
     ("Apr", "April"), ("May",), ("Jun", "June"), ("Jul", "July"),
     ("Aug", "August"), ("Sep", "Sept", "September"), ("Oct", "October"),
     ("Nov", "November"), ("Dec", "December")]) for name in names}


def _range(value):
    """Parse GSC numeric column periods or named-month Date filter periods."""
    raw = _text(value)
    numeric = re.findall(r"\b\d{1,2}/\d{1,2}/(?:\d{4}|\d{2})\b", raw)
    try:
        if len(numeric) == 2:
            parsed = []
            for item in numeric:
                month, day, year = map(int, item.split("/"))
                parsed.append(date(year + 2000 if year < 100 else year, month, day))
            return tuple(parsed)
        named = re.findall(r"\b([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b", raw)
        if len(named) == 2:
            return tuple(date(int(year), MONTHS[month.lower()], int(day)) for month, day, year in named)
    except (ValueError, KeyError):
        return None
    return None


def _full_month(period):
    start, end = period
    return start.day == 1 and end == start.replace(day=monthrange(start.year, start.month)[1])


def _canonical_filters(matrix):
    result, active, ended = {}, False, False
    duplicate_block = False
    allowed = {name.casefold(): name for name in ("Search type", "Date", "Country", "Query", "Page", "Device", "Search appearance")}
    for row in matrix:
        first = _text(row[0]) if row else ""
        second = _text(row[1]) if len(row) > 1 else ""
        if first.lower() == "filter" and second.lower() == "value":
            if active or ended:
                duplicate_block = True
                ended = True
            else:
                active = True
            continue
        if not active or ended:
            continue
        if first.lower() not in allowed:
            if first and second:
                result["_unrecognized_filter"] = first
            ended = True
            continue
        key = allowed[first.lower()]
        if key in result:
            result["_ambiguous_filter_key"] = key
            duplicate_block = True
            ended = True
        else:
            result[key] = row[1] if len(row) > 1 else None
    return result, duplicate_block


def _first_table(matrix):
    first = next((i for i, row in enumerate(matrix) if any(_text(x) for x in row)), None)
    if first is None:
        return [], []
    return matrix[first], [(i + 1, row) for i, row in enumerate(matrix[first + 1:], first + 1)
                           if any(_text(x) for x in row)]


def _metric_column(headers, period, metric, all_periods):
    aliases = {"clicks": {"clicks"}, "impressions": {"impressions", "imp"},
               "ctr": {"ctr"}, "position": {"position", "pos"}}[metric]
    columns = []
    for index, value in enumerate(headers):
        name = _text(value)
        parts = name.rsplit(" ", 1)
        if len(parts) != 2 or parts[-1].lower() not in aliases:
            continue
        label = parts[0].strip()
        if label.lower().startswith("diff"):
            continue
        parsed = _range(label)
        if parsed == period:
            columns.append(index)
        elif parsed is None and re.fullmatch(r"[A-Za-z]+\s+20\d{2}", label):
            month_name, year = label.split()
            if month_name.lower() in MONTHS:
                matching = [p for p in all_periods
                            if (p[0].year, p[0].month) == (int(year), MONTHS[month_name.lower()])]
                if len(matching) == 1 and matching[0] == period:
                    columns.append(index)
        elif parsed is None and label.lower() in MONTHS:
            matching = [p for p in all_periods if p[0].month == MONTHS[label.lower()]]
            if len(matching) == 1 and matching[0] == period:
                columns.append(index)
    return columns[0] if len(columns) == 1 else None


def _cell(row, column):
    return row[column] if column is not None and column < len(row) else None


def _gsc(catalog, cutoff):
    candidates, raw_rows, query_candidates, warnings = [], [], [], []
    for source in sorted(catalog.files("A"), key=lambda s: s.relative_path):
        source_id = hashlib.sha256((source.relative_path + ":" + source.sha256).encode()).hexdigest()[:24]
        book = openpyxl.load_workbook(BytesIO(source.read_bytes()), read_only=True, data_only=True)
        try:
            matrices = {sheet.title: list(sheet.values) for sheet in book}
        finally:
            book.close()
        for sheet, matrix in matrices.items():
            for row_number, row in enumerate(matrix, 1):
                if any(_text(v) for v in row):
                    raw_rows.append({"raw_values": list(row), **_provenance(source, sheet, row_number)})
        filters, duplicate_block = _canonical_filters(matrices.get("Filters", []))
        if duplicate_block:
            warnings.append(f"{source.name}: extra Filters block retained in raw rows but not allowed to overwrite canonical filters.")
        primary_period = _range(filters.get("Date"))
        country_head, country_rows = _first_table(matrices.get("Countries", []))
        query_head, query_rows = _first_table(matrices.get("Queries", []))
        periods = sorted({_range(h) for h in country_head
                          if _text(h).lower().endswith(" clicks") and _range(h) is not None})
        all_query_metric_columns = {col for p in periods for metric in ("clicks", "impressions", "ctr", "position")
                                    if (col := _metric_column(query_head, p, metric, periods)) is not None}
        sg = [(n, row) for n, row in country_rows if row and _text(row[0]).casefold() == "singapore"]
        if not periods:
            candidates.append({"candidate_id": f"{source_id}:unparsed", "month": None,
                               "eligible": False, "selected": False, "reason": "missing_or_unparsed_period_headers",
                               "filters": filters, **_provenance(source, "Countries", None)})
            warnings.append(f"{source.name}: no parseable GSC click-period headers.")
            continue
        for period in periods:
            start, end = period
            candidate_id = f"{source_id}:{start.isoformat()}:{end.isoformat()}"
            primary = primary_period == period
            reasons = []
            if "_ambiguous_filter_key" in filters or "_unrecognized_filter" in filters:
                reasons.append("ambiguous_or_unrecognized_filter_scope")
            if _text(filters.get("Country")).casefold() != "singapore":
                reasons.append("missing_explicit_singapore_filter")
            if _text(filters.get("Search type")).casefold() != "web":
                reasons.append("missing_or_nonweb_search_filter")
            if any(_text(filters.get(k)) for k in ("Query", "Page", "Device", "Search appearance")):
                reasons.append("additional_scope_filter")
            if not _full_month(period):
                reasons.append("not_full_calendar_month")
            if end > cutoff:
                reasons.append("period_after_transaction_cutoff")
            if primary_period is None or primary_period not in periods:
                reasons.append("filter_date_not_matched_to_header")
            elif not primary:
                primary_start = primary_period[0]
                months_back = (primary_start.year - start.year) * 12 + primary_start.month - start.month
                if months_back != 1:
                    reasons.append("comparison_not_previous_month")
            if len(sg) != 1:
                reasons.append("missing_or_ambiguous_singapore_row")
            country_columns = {m: _metric_column(country_head, period, m, periods)
                               for m in ("clicks", "impressions", "ctr", "position")}
            query_columns = {m: _metric_column(query_head, period, m, periods)
                             for m in ("clicks", "impressions", "ctr", "position")}
            if country_columns["clicks"] is None:
                reasons.append("ambiguous_country_click_header")
            if query_columns["clicks"] is None:
                reasons.append("missing_or_ambiguous_query_click_header")
            country_row = sg[0][1] if len(sg) == 1 else ()
            clicks = _number(_cell(country_row, country_columns["clicks"]))
            if clicks is None:
                reasons.append("missing_country_click_count")
            elif clicks < 0:
                reasons.append("invalid_negative_country_click_count")
            candidate = {
                "candidate_id": candidate_id, "month": start.replace(day=1),
                "period_start": start, "period_end": end, "is_primary_period": primary,
                "export_primary_start": primary_period[0] if primary_period else None,
                "export_primary_end": primary_period[1] if primary_period else None,
                "is_full_calendar_month": _full_month(period), "filters": filters,
                "has_extra_filter_block": duplicate_block, "country_headers": list(country_head),
                "query_headers": list(query_head), "eligible": not reasons, "selected": False,
                "reason": ";".join(reasons) if reasons else "eligible_not_selected",
                **{m: _number(_cell(country_row, col)) for m, col in country_columns.items()},
                **_provenance(source, "Countries", sg[0][0] if len(sg) == 1 else None),
            }
            observed_clicks, period_queries = [], []
            for row_number, raw in query_rows:
                if not raw or not _text(raw[0]):
                    continue
                item = {"candidate_id": candidate_id, "month": candidate["month"],
                        "period_start": start, "period_end": end, "query": _text(raw[0]),
                        **{m: _number(_cell(raw, col)) for m, col in query_columns.items()},
                        **_provenance(source, "Queries", row_number)}
                raw_clicks = _cell(raw, query_columns["clicks"])
                item["clicks_observed"] = item["clicks"] is not None
                item["query_clicks_status"] = (
                    "observed" if item["clicks_observed"] else
                    "missing_column" if query_columns["clicks"] is None else
                    "missing_blank" if not _text(raw_clicks) else "unparseable")
                item["has_any_period_numeric_metric"] = any(
                    _number(_cell(raw, col)) is not None for col in all_query_metric_columns)
                query_candidates.append(item)
                period_queries.append(item)
                observed_clicks.append(item["clicks"])
            candidate["query_rows"] = len(observed_clicks)
            known_clicks = [v for v in observed_clicks if v is not None]
            candidate["observed_query_rows"] = len(known_clicks)
            candidate["missing_query_rows"] = len(observed_clicks) - len(known_clicks)
            candidate["observed_query_clicks_sum"] = sum(known_clicks) if known_clicks else None
            candidate["observed_query_click_coverage"] = (sum(known_clicks) / clicks
                if known_clicks and clicks is not None and clicks > 0 else None)
            candidate["query_rows_without_any_period_metrics"] = sum(
                not r["has_any_period_numeric_metric"] for r in period_queries)
            candidate["unparseable_query_click_rows"] = sum(
                r["query_clicks_status"] == "unparseable" for r in period_queries)
            candidate["query_clicks_sum"] = (sum(observed_clicks)
                if observed_clicks and all(v is not None for v in observed_clicks) else None)
            candidate["query_click_coverage"] = (candidate["query_clicks_sum"] / clicks
                if candidate["query_clicks_sum"] is not None and clicks else None)
            candidates.append(candidate)
    by_month = defaultdict(list)
    query_signatures = defaultdict(list)
    for row in query_candidates:
        query_signatures[row["candidate_id"]].append((row["query"], row["clicks"], row["impressions"], row["ctr"], row["position"]))
    for item in candidates:
        if item.get("eligible"):
            by_month[item["month"]].append(item)
    months = []
    for month, items in sorted(by_month.items()):
        # Last is best by documented priority; paths only resolve identical values.
        priority = max((int(r["is_primary_period"]), r["export_primary_end"]) for r in items)
        best = [r for r in items if (int(r["is_primary_period"]), r["export_primary_end"]) == priority]
        fingerprints = {repr((r["clicks"], r["impressions"], r["ctr"], r["position"],
                              sorted(query_signatures[r["candidate_id"]], key=lambda v: v[0]))) for r in best}
        if len(fingerprints) > 1:
            for row in best:
                row["eligible"] = False
                row["reason"] = "conflicting_same_priority_exports"
            warnings.append(f"{month}: conflicting equally preferred exports; no monthly row selected.")
            continue
        chosen = min(best, key=lambda r: (r["source_file"], r["candidate_id"]))
        chosen["selected"] = True
        chosen["reason"] = "selected_primary" if chosen["is_primary_period"] else "selected_previous_month_fallback"
        for row in items:
            if row is not chosen:
                row["reason"] = "superseded_by_preferred_export"
        months.append({k: v for k, v in chosen.items() if k not in ("country_headers", "query_headers")})
    chosen_ids = {r["candidate_id"] for r in months}
    queries = [r for r in query_candidates if r["candidate_id"] in chosen_ids]
    if any(r["missing_query_rows"] for r in months):
        warnings.append("Some selected GSC rows have unknown click metrics. Partial observed-query sums and coverage are separate from complete source-row sums; blank metrics are not zeros or proof of absence.")
    warnings.append("GSC query tables are incomplete observed rows; absent queries are unknown, never imputed as zero.")
    return {"gsc_months": months, "gsc_queries": queries, "gsc_month_candidates": candidates,
            "gsc_query_candidates": query_candidates, "gsc_raw_rows": raw_rows}, warnings


def _file_month(name):
    match = re.search(r"\b([A-Za-z]+)\s+(20\d{2})\b", name)
    if match and match[1].lower() in MONTHS:
        return date(int(match[2]), MONTHS[match[1].lower()], 1)
    return None


def _keyword(value):
    # Lexical cleanup only. No synonyms, singular/plural or word-order grouping.
    return " ".join(_text(value).strip('"[]').lower().split())


def _fill_identity(fill):
    """Compare source styles with their source legend, without guessing a color's meaning."""
    if fill is None or fill.patternType != "solid":
        return None
    color = fill.fgColor
    if color.type not in {"rgb", "indexed", "theme"}:
        return None
    return (fill.patternType, color.type, getattr(color, color.type), color.tint)


def _annotate_keyword_tiers(book, tiers):
    labels_by_fill = defaultdict(set)
    for cells in book["Categories"].iter_rows():
        for cell in cells:
            label = _text(cell.value)
            fill = _fill_identity(cell.fill)
            if label and fill:
                labels_by_fill[fill].add(label)
    marked = defaultdict(list)
    cells_by_row = {i: cells for i, cells in enumerate(book["Filtered"].iter_rows(), 1)}
    header = next(cells for cells in cells_by_row.values() if any(_text(c.value) for c in cells))
    keyword_column = [_text(c.value) for c in header].index("Keyword")
    for row in tiers:
        cell = cells_by_row[row["source_row"]][keyword_column]
        fill = _fill_identity(cell.fill)
        labels = sorted(labels_by_fill.get(fill, set()))
        text_label = _text(row.get("KW List tier colour"))
        red_from_fill = any("do not retarget" in label.casefold() for label in labels)
        red_from_text = "do not retarget" in text_label.casefold()
        row["clean_keyword_cell_fill"] = list(fill) if fill else None
        row["source_fill_tier_labels"] = labels
        row["historical_tier_label_conflict"] = bool(labels and text_label and text_label not in labels)
        row["historical_red_list_direct_evidence"] = red_from_fill or red_from_text
        row["historical_red_list_evidence"] = (
            "keyword_cell_fill_matches_source_legend" if red_from_fill else
            "explicit_tier_label" if red_from_text else None)
        if red_from_fill or red_from_text:
            marked[_keyword(row.get("Keyword"))].append(row["source_row"])
    return marked


def build_search_tables(catalog, cutoff):
    cutoff = _as_date(cutoff)
    if cutoff is None:
        raise ValueError("cutoff must be an ISO date or date object")
    tables, warnings = _gsc(catalog, cutoff)
    semrush = []
    for source in sorted(catalog.files("B"), key=lambda s: s.relative_path):
        month = _file_month(source.name)
        if month is None:
            warnings.append(f"{source.name}: filename month could not be parsed.")
        for row_number, raw in enumerate(csv.DictReader(StringIO(source.read_bytes().decode("utf-8-sig"))), 2):
            stamp = _as_date(raw.get("Timestamp"))
            position_type = _text(raw.get("Position Type"))
            semrush.append({**raw, "file_month": month, "row_timestamp": stamp,
                            "is_stale_observation": stamp < month if stamp and month else None,
                            "row_after_cutoff": stamp > cutoff if stamp else None,
                            "clean_position": _number(raw.get("Position")),
                            "clean_search_volume": _number(raw.get("Search Volume")),
                            "visibility_class": "organic" if position_type.casefold() == "organic" else "serp_feature" if position_type else "unknown",
                            **_provenance(source, None, row_number)})
    tables["semrush_keywords"] = semrush
    sources = catalog.files("12")
    if len(sources) != 1:
        raise ValueError("Expected one File 12 workbook")
    source = sources[0]
    book = openpyxl.load_workbook(BytesIO(source.read_bytes()), read_only=True, data_only=True)
    try:
        tables["ads_keywords"] = _sheet_records(book["Search keyword report All time "], source)
        tables["ads_negatives"] = _sheet_records(book["Negative Keyword report "], source)
        tiers = _sheet_records(book["Filtered"], source)
        tables["ads_keyword_tiers"] = tiers
        tables["ads_tier_definitions"] = [{"raw_values": list(row), **_provenance(source, "Categories", i)}
                                           for i, row in enumerate(book["Categories"].values, 1) if any(_text(v) for v in row)]
        red_evidence = _annotate_keyword_tiers(book, tiers)
    finally:
        book.close()
    red_keywords = set(red_evidence)
    for table in ("ads_keywords", "ads_keyword_tiers"):
        for row in tables[table]:
            key = _keyword(row.get("Keyword"))
            impressions, clicks = _number(row.get("Impr.")), _number(row.get("Clicks"))
            row.update({"clean_keyword": key or None,
                        "historical_red_list_flag": key in red_keywords,
                        "historical_red_list_source_rows": red_evidence.get(key, []),
                        "clean_impressions": impressions, "clean_clicks": clicks,
                        "clean_ctr": clicks / impressions if impressions is not None and impressions > 0 and clicks is not None and clicks >= 0 else None,
                        "period_scope": "source_all_time_unspecified_dates"})
    for row in tables["ads_negatives"]:
        row["clean_keyword"] = _keyword(row.get("Negative keyword")) or None
    tier_conflicts = sum(row["historical_tier_label_conflict"] for row in tiers)
    if tier_conflicts:
        warnings.append(f"Historical Ads has {tier_conflicts} rows where the keyword-cell legend label differs from the text tier; both are retained, and explicit do-not-retarget evidence is flagged.")
    warnings.extend([
        "Semrush rows retain file month and observation timestamp separately; feature visibility is not a traditional organic rank or realized traffic.",
        "Historical Google Ads red-list flags preserve the supplier's caution; they do not prove current paid cannibalization.",
        "File 12 has no explicit period dates; its all-time metrics are not a matched campaign benchmark.",
    ])
    return {"tables": tables, "warnings": warnings,
            "checks": {"row_counts": {name: len(rows) for name, rows in tables.items()},
                       "gsc_selected_months": [r["month"].isoformat() for r in tables["gsc_months"]],
                       "gsc_rejected_candidates": sum(not r["eligible"] for r in tables["gsc_month_candidates"]),
                       "cutoff": cutoff.isoformat()}}
