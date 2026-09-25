"""Generate the output-free EDA deliverable from versioned notebook cells."""

import json
from pathlib import Path
from textwrap import dedent


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "notebooks" / "EDA_notebook.ipynb"


def md(source):
    return {"cell_type": "markdown", "metadata": {}, "source": dedent(source).strip() + "\n"}


def code(source):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": dedent(source).strip() + "\n"}


cells = [
    md("""
    # EDA_notebook: source-wide audit before preprocessing

    **Purpose.** Inventory all seven supplied source groups, read every workbook sheet and CSV, and profile every populated column at its physical position. The work is a raw-data diagnostic, not a cleaned analytical table. It keeps cancelled, reversed, unknown and conflicting observations visible. Nothing in this notebook estimates causal lift, margin or October campaign CTR.

    **Input grain.** The data consist of 38 GSC comparison workbooks, 43 Semrush CSVs, one order workbook, one current product master, one discount workbook, one loyalty workbook and one historical Ads workbook. Workbooks may have multiple sheets. Each table profile counts nonempty rows; wholly blank spreadsheet rows are counted separately. Source files are hashed. The audit does not silently drop populated columns with blank headers.

    **Set up.** Install `requirements.txt` and run from `notebooks/` (or the repository root). Set `WEAVVE_DATA` to the dated data-dump directory, or put that directory's contents in `data/`. If the Ads workbook is outside that directory, set `WEAVVE_ADS` to its full path. Set `WEAVVE_OUT` to a local output directory if desired. The only written artifact is an aggregate JSON file outside the Git repository; source files are read-only. Committed notebook outputs must stay clear.
    """),
    md("""
    ## Rules fixed before viewing results

    | Question | Audit rule | Interpretation limit |
    |---|---|---|
    | What is covered? | Inventory 86 expected files and every sheet, hash every file, retain populated blank-header columns by position. | A file count or matching hash establishes coverage of this export, not source validity. |
    | What is missing? | Missingness denominator is the nonempty row count in each physical table. Wholly blank rows are reported separately. | Blank spreadsheet spacers do not represent lost customers or searches. |
    | What is a distinct value? | Exact count below 50,000; `distinct_at_least=50000` above that cap. Values stay in memory and are never exported. | A capped count is a lower bound. It is not a count of people, orders or campaigns. |
    | What is numeric? | For nonidentifier fields, parse finite numbers including percent strings. Report distribution only when the field is a named measure or at least 80% parseable. Do not add unlike measures or mixed discount value units. | Quantiles can expose implausible tails but do not define valid records. |
    | What is a date? | Parse native Excel dates, ISO dates and common slash formats for date-like headers. Preserve an unparsed count. | Order `Day`, Semrush row timestamp and filename month have different meanings. |
    | What is sensitive? | Do not emit customer/order/line identifiers, names, emails, SKUs, query or keyword text, URLs, discount codes, campaigns, descriptions or category values. | Schema names, source names, counts and distributions remain reviewable. |

    The profiler flags potential issues; it does not delete rows, impute categories, normalize codes, join customer identities or choose profitable actions. Inspect each material flag in context before changing an analytical denominator. In particular, a repeated Line item ID may reflect legitimate reversal or discount allocation. GSC comparison workbooks have overlapping periods and sometimes different country filters. Semrush rows can predate the filename month. Historical Ads tabs can overlap, and their all-time CTR is not a prospective CTR estimate.
    """),
    code("""
    import json
    import os
    import sys
    from collections import Counter, defaultdict
    from pathlib import Path

    WORKDIR = Path.cwd().resolve()
    REPO = WORKDIR.parent if WORKDIR.name == 'notebooks' else WORKDIR
    if not (REPO / 'src' / 'weavve' / 'eda_audit.py').is_file():
        raise FileNotFoundError('Start Jupyter from the repository root or notebooks/')
    sys.path.insert(0, str(REPO / 'src'))
    from weavve.eda_audit import audit

    DATA = Path(os.environ.get('WEAVVE_DATA', REPO / 'data')).expanduser().resolve()
    ADS = os.environ.get('WEAVVE_ADS')
    OUT = Path(os.environ.get('WEAVVE_OUT', Path.home() / 'Desktop' / 'weavve_outputs')).expanduser().resolve()
    print({'data_directory_exists': DATA.is_dir(), 'ads_override': bool(ADS),
           'output_directory': str(OUT)})
    """),
    md("""
    ## Run the comprehensive column audit

    The audit reads each file once, profiles every sheet and saves aggregate-only results to `WEAVVE_OUT/eda_column_audit.json`. The file includes per-source SHA-256 and per-column counts; keep it local under the repository's no-data policy. The output is deliberately not a table of source values or top categories.
    """),
    code("""
    profile = audit(DATA, ADS)
    OUT.mkdir(parents=True, exist_ok=True)
    audit_path = OUT / 'eda_column_audit.json'
    audit_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')
    print(profile['summary'])
    print({'aggregate_audit': str(audit_path)})
    """),
    md("""
    ## Coverage and triage

    The first table distinguishes source groups from physical sheets. The second counts flags by source group. A flag is a prompt to inspect scope, type or provenance; it is not a correction rule. For a detailed column review, call `show_columns(group, source_fragment, sheet)` below. The full audit JSON contains every populated column for every table, including columns that are not flagged.
    """),
    code("""
    by_group = defaultdict(lambda: {'files': 0, 'tables': 0, 'rows': 0, 'columns': 0})
    for source in profile['files']:
        by_group[source['group']]['files'] += 1
    for table in profile['tables']:
        group = by_group[table['group']]
        group['tables'] += 1
        group['rows'] += table['rows']
        group['columns'] += table['active_columns']
    print('Coverage by source group (sheet rows can overlap across exports):')
    for group, counts in sorted(by_group.items()):
        print(group, counts)

    flags = Counter((table['group'], flag.split(':')[0])
                    for table in profile['tables'] for flag in table['flags'])
    print('Flag counts by group and type:')
    for key, count in sorted(flags.items()):
        print(key, count)

    def show_columns(group, source_fragment='', sheet=None):
        # Print safe per-column summaries for selected source tables.
        selected = [t for t in profile['tables'] if t['group'] == group
                    and source_fragment.casefold() in t['source'].casefold()
                    and (sheet is None or t['sheet'] == sheet)]
        for table in selected:
            print('\\n', table['source'], '/', table['sheet'],
                  'rows=', table['rows'], 'blank_rows=', table['blank_rows'])
            for column in table['columns']:
                print(column)
        return len(selected)

    print('Example: show_columns("Orders", sheet="Order  Transaction-Level")')
    print('Example: show_columns("GSC", source_fragment="Dec 25", sheet="Countries")')
    """),
    md("""
    ## Prioritize column issues for the report

    The next cell ranks missing, mixed-type and nonnumeric-measure fields **without converting flags into cleaning decisions**. It also checks schema consistency for the Semrush CSV exports. A GSC header string contains comparison dates, so its natural variation must not be mistaken for a malformed schema. Review a field's source definition and its effect on a planned claim before deciding whether to transform it.
    """),
    code("""
    issues = []
    for table in profile['tables']:
        for column in table['columns']:
            issue = {'group': table['group'], 'source': table['source'],
                     'sheet': table['sheet'], 'position': column['position'],
                     'header': column['header'], 'rows': table['rows']}
            if column['missing_pct'] is not None and column['missing_pct'] >= 50:
                issues.append({**issue, 'issue': 'at_least_half_missing',
                               'count': column['missing'], 'pct': column['missing_pct']})
            if len(column['raw_types']) > 1:
                issues.append({**issue, 'issue': 'mixed_raw_types',
                               'count': column['nonmissing'], 'pct': None})
            numeric = column.get('numeric')
            if numeric and numeric['unparseable_nonmissing']:
                issues.append({**issue, 'issue': 'unparsed_measure',
                               'count': numeric['unparseable_nonmissing'], 'pct': None})
    print('Issue counts (same field may have multiple issues):',
          dict(Counter(item['issue'] for item in issues)))
    print('Largest missingness exposures:')
    for item in sorted((i for i in issues if i['issue'] == 'at_least_half_missing'),
                       key=lambda i: -i['count'])[:12]:
        print(item)
    print('Largest numeric parsing exposures:')
    for item in sorted((i for i in issues if i['issue'] == 'unparsed_measure'),
                       key=lambda i: -i['count'])[:12]:
        print(item)
    semrush_schemas = Counter(tuple(c['header'] for c in t['columns'])
                              for t in profile['tables'] if t['group'] == 'Semrush')
    print('Semrush physical schema variants:', len(semrush_schemas),
          'file counts:', sorted(semrush_schemas.values(), reverse=True))
    """),
    md("""
    ## Verified source snapshot and what the flags mean

    On the 29 August 2026 supplied dump plus the separate historical Ads workbook, a single local verification run read **86 files**, **292 physical sheets/tables**, **310,884 nonempty sheet rows** and **2,958 populated column positions**. All **86 source hashes** agreed with the independent local source manifest. Sheet rows overlap across comparison exports and are **not** a count of unique visits, orders or customers. The local run left this committed notebook output-free.

    The audit found **three GSC tables with duplicate header text**, **two headerless GSC exclusion sheets**, and six `Dates` sheets in addition to the regular GSC tabs. The Ads `Categories` sheet is a headerless annotation area. These are included in the audit but need separate interpretation before analysis. The order sheet has five fields at least 50% missing; the main discount sheet has four. The Ads `Max. CPC` and `Interaction rate` fields contain values the generic numeric parser cannot read. None of these flags licenses dropping records. Inspect their nonmissing denominator and meaning before making a cleaning rule.

    This is **complete physical coverage of populated columns**, not complete semantic EDA. The JSON is a column inventory and triage record. It does not establish whether repeated order lines are separate economic events, whether a blank GSC filter implies Singapore scope, whether a current SKU master represents historic products, or whether a discount was funded by Weavve. Those are the next evidence checks. Retain the source hashes and the specific source names when reporting any figure.
    """),
    md("""
    ## Decisions this audit does not settle

    1. **Order economics.** Reconcile signed reversals, cancellation and repeated sale-line signatures at the correct economic grain. `Net sales` is after discounts, excluding GST and shipping, so adding the separate `Discounts` field would double count.
    2. **Track A profit.** Any retention or promotion recommendation needs eligible population, incremental response, order contribution after variable costs and funding, and a breakeven sensitivity. Column completeness cannot supply missing margin or causal lift.
    3. **Search scope.** Build a GSC month × export × country/search-type matrix before comparing periods. Listed query and page clicks are not automatically whole-site clicks. Preserve inconsistent workbooks as a separate stratum.
    4. **Track B CTR.** Treat Semrush organic rankings and historical Ads CTR as candidate-selection evidence. Document the keyword selection process and evaluate live paid-search CTR against a declared impression denominator; do not forecast it by relabelling organic metrics.
    5. **Unknowns.** Keep unmatched historic SKUs, unlinked loyalty events, ambiguous discount codes and missing filters explicit. Selective preprocessing comes after quantifying each alternative's impact.

    The report should show data issues, their effect and mitigation; the presentation can use supported customer and search opportunities. They are complementary deliverables, so duplicate slides and PDF paragraphs are unnecessary.
    """),
]


notebook = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                          "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 5}
TARGET.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(TARGET)
