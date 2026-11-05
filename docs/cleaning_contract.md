# Shared local dataset contract

This contract defines the cleaned tables that the team should use as the common input to new analysis. Build the dataset from the supplied original exports, then load it through `weavve.clean.load_dataset`. Do not copy cleaning logic into individual notebooks or edit exported cells to make a result match an earlier report.

The dataset is a reproducible analytical view. It preserves unresolved source limitations; it does not certify customer identity, causal effects, consent, profitability or the completeness of third-party tracking.

## Build and hand off the same version

Use Python **3.12.10** and **openpyxl 3.1.5**. The Excel reader is pinned in `requirements-clean.txt`; install the specified Python version separately. The broader notebook environment may additionally use pandas and plotting packages. The core cleaner does not need a live account or network connection.

1. Check out the agreed Git commit containing the cleaner, tests and this contract.
2. Place the original supplied workbooks, CSVs and/or ZIPs in a private input directory. Set `WEAVVE_DATA` to that directory.
3. Set `WEAVVE_OUT` to a separate private output directory outside the repository and outside the raw input directory. Input and output directories must not overlap.
4. Run `python scripts/build_clean_data.py`. Add `--zip` only when a private local handoff bundle is needed. Explicit `--data` and `--out` paths are also supported.
5. Record the printed dataset ID with the Git commit and compare it with the other team members' IDs before comparing results.

The required sources are A, B, C, D, E, F, G, I, J, K, L and File 12. Marketing email files, when supplied, appear in the source inventory but are not converted into inferred campaign events or analytical email-body tables.

The source catalog identifies files by source group and basename, independently of the machine's absolute directory. Byte-identical copies of the same logical file are deduplicated. Conflicting versions of that logical file, or multiple different workbooks for a single-workbook source, fail the build. Temporary Excel lock files and macOS metadata copies are ignored. Originals are read without extraction or modification.

The **dataset ID** is a SHA-256 fingerprint of:

- The logical source inventory, including each source's content hash and size.
- The cleaning rule parameters.
- The contents of the source catalog and cleaning/export modules.
- The exact Python and openpyxl runtime versions.

The Git commit is a useful handoff reference, but the ID is computed from the listed inputs rather than from a branch name. Identical originals, cleaning code, rule parameters and runtime should produce the same ID. A different ID requires investigating those inputs before interpreting any analytical difference.

Outputs live under `WEAVVE_OUT/clean/<dataset_id>/`. The directory contains CSV tables, `manifest.json` and `DATA_DICTIONARY.md`. The manifest records table schemas, row counts, content hashes, rule parameters, source hashes, checks and warnings. `latest.json` is a local pointer, not an assertion that all findings in a newer dataset have been reviewed.

The optional ZIP contains the local tables and their manifest/dictionary. It is private data, even when identifiers are anonymized. **Never commit the outputs, manifest, ZIP, notebook outputs or source files to GitHub.** Share a private bundle only through an authorized private channel. GitHub receives the code, tests and documentation.

## Load tables through the manifest

```python
from weavve.clean import load_dataset

dataset = load_dataset()  # uses WEAVVE_DATA and WEAVVE_OUT
orders = dataset.table("orders")
purchases = [row for row in orders if row["is_purchase"]]
website_purchases = [row for row in purchases if row["is_website"]]

# Optional pandas convenience; validation still runs before the frame is returned.
monthly_search = dataset.frame("gsc_months")
```

Set `WEAVVE_CLEAN` or pass an explicit dataset directory to select a particular build. The normal `load_dataset` path verifies that its source/code/rule/runtime fingerprint matches the current environment. It also verifies every table. A stale dataset fails rather than silently mixing an old export with new analysis code.

Each `table()` call checks the CSV's hash, schema and row count before decoding its values. Modified or missing tables fail. Do not bypass verification in team analysis. Rebuild after changing a source or cleaning rule; do not hand-edit a table or its manifest. These checks detect inconsistency with the recorded manifest, not malicious replacement of an entire bundle and manifest; use the agreed Git commit, originals and dataset ID for provenance.

## Types and naming

Original named source columns remain available alongside normalized fields. Derived transaction fields use descriptive lower-case names; supporting workbook fields generally use `clean_` prefixes. Never substitute an original money or channel column for its normalized counterpart without explicitly changing the analytical definition.

The manifest is authoritative for each exported column's type. Dates are ISO calendar dates; source datetimes are ISO timestamps. Transaction money is parsed and computed as `Decimal`, serialized without rounding, and decoded back to `Decimal`. Display rounding belongs in the report, not the shared data. Rates are fractions rather than percentages unless an original source column says otherwise. Multiply a normalized rate by 100 for a percentage display.

CSV has fewer types than Excel. Mixed-type raw columns may be serialized as strings; a date-valued coupon is still flagged explicitly. Blank typed cells decode to `None`; blank string cells remain empty strings. Lists and dictionaries use JSON cells, with nested dates represented as ISO strings. The original source and hash remain the authority for exact workbook values and types. Workbook formula cells are read using their stored values; the cleaner does not calculate Excel formulas.

Supporting and search rows carry `source_file`, `source_sha256`, `source_sheet` and `source_row`. `source_row` is the physical spreadsheet row, or the CSV data row including its header. Transaction line rows retain File C's physical `source_row`; the manifest identifies that source. These locators are safer keys than a descriptive label that may repeat. A renamed display label is not a new person, product or campaign.

## Transaction tables

| Table | Grain and key | Intended use |
|---|---|---|
| `order_lines` | One retained File C row; unique `source_row` | Signed line-level sales, discounts, products and traceability. Multiple rows can belong to one order. |
| `orders` | One noncancelled order; unique `order_id` | Order economics and explicit purchase/customer eligibility. Includes nonpositive orders. |
| `excluded_order_lines` | One excluded File C row; unique `source_row` | Review cancellation and repeated-line exclusions. Do not add these back to cleaned sales. |

The retained and excluded line sets partition the input rows. Aggregate checks reconcile input raw net sales to retained plus excluded raw net sales. A successful reconciliation establishes arithmetic conservation under these rules; it does not independently prove their business interpretation.

### Identity and channel

`customer_id` retains the supplied account identifier. `person_id` comes from File G's customer map. `channel_detail` comes from File G's order map. Required mapping keys must be unique, every transaction must be covered, and an order cannot contain ambiguous customer identifiers. Invalid or missing required values fail the build.

`is_website` means that the order has an original **Online Store** channel. It does not mean every File G **Own store** order: that supplier category can contain other direct-store channels. `original_channels` on `orders` preserves the observed original labels. Use the supplied platform detail for marketplace analysis rather than treating an ambiguous source label as a person or business account.

Configured special accounts remain in the economic tables with `is_special_account=True`. They are excluded only by the explicit customer eligibility flag. Supplier identity matching remains provisional evidence: matched person labels do not establish perfect cross-channel identity, and unlinked platforms do not support reliable person-level repeat estimates.

### Cancellations and repeated discount lines

If any row marks an order cancelled, all its rows enter `excluded_order_lines` with `exclusion_reason="cancelled_order"`. This is a completed-purchase convention; a cancellation flag does not establish the order's shipment history.

A repeated economic line is excluded only when it matches an earlier retained line's order, line identifier, sale/reversal kind, line date, SKU, numeric fields and relevant refund identifier, while its discount annotation differs. Annotation includes discount name, code, title, type and value. The exclusion records `duplicate_of_source_row` and `exclusion_reason="repeated_discount_line"`.

Equal economic lines with identical annotations remain in the dataset and generate a review count. Order-level rows without a usable line identifier are not automatically deduplicated. This rule is deliberately narrower than dropping every repeated-looking row.

### Money and refunds

| Field | Meaning |
|---|---|
| `net_raw` | Original signed Net sales before the cleaner's tax adjustment. |
| `net` | Signed Net sales after the conditional per-line tax adjustment. Refunds retain their sign. |
| `discount_raw` | Original Discounts with its sign reversed; positive values normally represent a discount. |
| `discount` | Sign-reversed Discounts after the same conditional tax adjustment. Reversals can remain negative. |
| `gst_adjusted` | The line met the configured tax-inclusion evidence gate. |

The current gate requires the original combined marketplace source label, a line date on or after the configured change date, nonzero Net sales and exact equality between that line's Net sales and Total sales. Qualifying net and discount amounts are divided by the configured divisor. Other lines remain unchanged. The rule is applied **per line**, including a qualifying reversal, before order aggregation; do not apply it again to exported order totals.

The gate is an evidence-based interpretation of an export inconsistency, not confirmation from invoices or official tax advice. Confirm the change date, affected sources and discount basis with the data owner before treating the result as accounting truth. The exact parameters are recorded in the manifest. A supplier clarification should produce a new documented rule and dataset version rather than an undocumented manual correction.

`line_date` is the source row's date. `order_date` is the earliest sale-line date for that order; if no sale line exists, the earliest observed line date is used and a warning is recorded. Refunds retain their source line dates but aggregate with their original order under `order_date`. This supports purchase/cohort economics. It is not a cash-flow or refund-processing-date ledger.

### Purchases and customer eligibility

`is_purchase` is true only when a noncancelled order's corrected signed `net` is strictly positive. Zero/negative orders remain available for economic reconciliation. Counting every `orders` row as a purchase changes the denominator.

`customer_analysis_eligible` requires a positive purchase, a nonspecial person and either the website definition above or File G's Shopee platform. It does not remove sales from other platforms. It is a starting population flag, not a cohort table: downstream analyses must still state entry dates, follow-up length, same-day ties, return definitions and observation censoring. The shared cleaner does not automatically exclude quick repeat purchases or manufacture a complete lifetime history.

### Products and clearance

`sku` is the source code, and `product_match` indicates an exact match to File D. Missing/unmatched SKUs remain in the dataset; unknown is not a known product category. `is_order_level` identifies rows without a usable line identifier and is distinct from a product row with a missing SKU.

`clearance_sku` says the SKU appears in File I's snapshot. It is **not a lifetime exclusion**. `clearance_status` distinguishes clearance, discontinuation, unknown remarks and unlisted SKUs. Recognized quarter-level remarks produce `clearance_quarter_start` and `clearance_quarter_end`, with the end being the first day of the next quarter. `clearance_timing` compares the line date with that interval: `before`, `within`, `after` or `unknown`. The exact start date within a quarter remains unknown. No clearance sale history is deleted.

`discount_code_is_date` identifies Excel date-valued code cells. The raw value remains available; the cleaner does not guess an original coupon string or invent a prefix-to-campaign mapping.

## Supporting workbook tables

These tables preserve the supplied rows. Source-row provenance is the fallback key unless a validated natural key is stated. Later snapshot records are not silently discarded to force them into the transaction window.

| Table | Grain and principal fields | Scope and limits |
|---|---|---|
| `g_person_map` | One supplied customer ID mapping; `clean_customer_id`, `clean_person_id` | Customer IDs are unique for transaction joins; several IDs may map to one person label. |
| `g_order_channels` | One supplied order mapping; `clean_order_id`, `clean_channel_detail` | Order IDs are unique for transaction joins. Preserve platform detail. |
| `products` | One File D SKU record; `clean_sku`, missing/duplicate flags | Current source catalogue, not proof that every historic SKU still exists. Duplicate join keys fail the full build. |
| `clearance_skus` | One File I SKU record; `clean_sku` and original remarks | Snapshot listing and estimated timing; no blanket historical exclusion. Duplicate join keys fail the full build. |
| `discounts` | One File E full-report record; `clean_code_name`, start/end dates, times-used/usage flag | Issued code records are not people, signups or orders. Missing usage is unknown, not zero. |
| `discount_summary` | One source summary row from the welcome-discount sheet | Keep the supplier's aggregation and denominator; do not add to detail rows. |
| `discount_by_year` | One source group/year summary row | Preserve original grouping; not independently reconstructed from transaction codes. |
| `discount_alia_depth` | One source offer-depth summary row | A separate aggregate, not extra discount events. |
| `discount_detail_by_code` | One source code/group summary row | Code labels are not a guaranteed transaction campaign lookup. |
| `loyalty_rewards` | One File F reward-voucher record | `clean_reward_usage_status` is `used`, `issued_unused` or `unknown`; `clean_order_in_g` checks only the supplied order-map link. |
| `subscribers` | One File J profile record | `clean_profile_created_date`, `clean_profile_created_by_cutoff`, `clean_person_in_g`, literal initial-source label. |
| `email_campaigns` | One File K campaign record | Send-date cutoff flag, recipient-size flag, normalized unique-event rates; all source campaigns retained. |
| `website_funnel` | One File L month | Source counts/rates, geography, month end and complete-month eligibility. |
| `website_funnel_cells` | One source metric/month cell | `month`, `metric`, `value`, `source_column` and provenance for the wide monthly table. |

Additional File E sheets, if present, are exported under distinct `discount_...` names. The manifest lists the actual tables and columns for a build; do not assume a source-supplied aggregate is additive to another.

### Loyalty, profiles and email

File F records reward voucher issuance/redemption history and observed use. It is not a full membership roster, current points ledger or membership-start event stream. A used reward's order-map link does not establish that the order survived cancellation cleaning; join to `orders` for that question.

File J is a profile snapshot. Profile creation is not verified voluntary signup, marketing consent, deliverability or a complete event history. `clean_person_in_g=False` can mean a missing/unlinked person identifier; it does not prove the person has never purchased. The supplied link method can favor website matches. Bare source labels are retained literally: `google` is not automatically labelled paid advertising. Current snapshot values must not be projected backward as historical states.

For File K, `in_transaction_window` means a valid Send Date on/before the transaction cutoff. It does not make different years seasonally comparable. `clean_recipients_at_least_20` is a size flag, not an automatic exclusion. `clean_unique_click_rate` and `clean_unique_open_rate` divide recorded unique events by **Total Recipients**, using valid nonnegative events and a positive denominator. These fractions can differ from the supplier's precomputed rate columns. The cleaner does not infer the supplier's delivered-recipient denominator, bot filtering or human response. Privacy-prefetched opens and automated clicks remain measurement limitations.

### Monthly funnel boundaries

The transaction cutoff is the latest normalized order date in the noncancelled order table. File L remains monthly. `in_transaction_complete_month_window=True` requires the **month end** to be on/before that cutoff; an incomplete final transaction month is not treated as a complete month. All monthly source observations remain available for explicit alternative comparisons.

The source's Singapore-only geography is retained when present; missing geography remains unknown. A comparison with transaction totals must align geography, channel, cancellation/refund definitions and dates. Correlation between series does not establish identical coverage. `clean_orders_per_session` is calculated from the source counts with a positive session denominator; it does not estimate causal conversion lift.

## Search tables and selection policy

| Table | Grain/key | Use |
|---|---|---|
| `gsc_raw_rows` | Source workbook/sheet/physical row | All nonblank source rows, including headers and appended summaries, as `raw_values`. |
| `gsc_month_candidates` | Source workbook/period; `candidate_id` | Every parseable country-click period, or an explicit unparsed candidate; filters, headers, eligibility, selection and reason. |
| `gsc_query_candidates` | Candidate/source query row | Parsed observations for every candidate, including excluded periods. |
| `gsc_months` | One selected observation per month | Comparable monthly Singapore/Web totals under the policy below. |
| `gsc_queries` | Selected candidate/source query row | Observed query rows for selected monthly sources. |
| `semrush_keywords` | Source CSV/row | Original fields plus file month, observation timestamp, stale flag, position and visibility class. |
| `ads_keywords` | Source all-time keyword-report row | Original match type and metrics, lexical keyword cleanup, computed CTR and historical red-list flag. |
| `ads_negatives` | Source negative-keyword row | Original match type, campaign/list/level plus lexical keyword cleanup. |
| `ads_keyword_tiers` | Source Filtered-sheet row | Supplier tier label and historical warning flag, kept separately from all-time keyword rows. |
| `ads_tier_definitions` | Source Categories-sheet row | Original tier definitions and provenance. |

### Google Search Console

Selection never depends on which filename happens to be read first.

1. Read only the first contiguous canonical `Filter`/`Value` block. Preserve appended blocks in `gsc_raw_rows` and emit a warning rather than letting handwritten summaries overwrite canonical filters. Conflicting keys within the canonical block or unrecognized scope filters are unresolved and excluded.
2. Parse dated periods from Countries click headers. Map query columns by their explicit dates, unambiguous month names or month/year labels; never assume query and country columns have the same order.
3. Require explicit Singapore and Web filters, no additional narrowing scope, a unique Singapore country row, a valid country click count and an unambiguous query click column. The candidate must cover a full calendar month ending on/before the transaction cutoff.
4. A primary candidate's period matches the canonical Date filter. That filter must itself match a country period header. A comparison candidate must be the immediately preceding calendar month; future, erroneous-year or nonadjacent comparisons are retained with exclusion reasons.
5. Prefer an eligible primary candidate. If none exists, select the eligible previous-month candidate from the latest coherent primary-period export. This allows a full-month comparison export to replace an incomplete primary export without pretending the incomplete period was full.
6. Equally preferred conflicting exports are not arbitrarily resolved: no monthly row is selected, and the conflict is flagged. Identical observations can use a deterministic source-path tie break. Superseded candidates remain available for inspection.

Missing eligible months are absent from `gsc_months`, not filled with zero. A query missing from an export is unknown, not a zero-click query. Missing metric cells remain missing. `query_clicks_sum` is calculated only when every retained query row has a numeric click value; `query_click_coverage` compares that sum with the selected country total when the denominator is positive. Neither field establishes that the export contains every query.

For partial source rows, `observed_query_rows` and `missing_query_rows` count present and missing/unparseable click values separately. `observed_query_clicks_sum` sums only numeric click cells, and `observed_query_click_coverage` divides that partial sum by the country total. Both are missing if there are no observed click cells; a present zero remains a measured zero. `query_rows_without_any_period_metrics` counts retained query labels without a numeric metric in either export period; their purpose is unknown. `unparseable_query_click_rows` counts nonblank click cells that could not be parsed. Query tables expose `clicks_observed`, `query_clicks_status` (`observed`, `missing_blank`, `missing_column` or `unparseable`) and `has_any_period_numeric_metric` for tracing these distinctions.

An analysis can restrict itself to numeric observed query rows for its declared months, but must disclose the missing rows and partial country-click coverage. Privacy filtering, export limits and other source behavior mean coverage is incomplete even for an eligible month with no missing cells. Do not call the selected query set a complete organic audience or an exhaustive do-not-bid list.

This policy resolves metadata consistently; it does not prove every source header is correct. Review `reason`, `eligible`, `selected`, `filters` and the original rows before overriding an unresolved source. Any approved override should be encoded, tested and versioned rather than applied in one notebook.

### Semrush and historical Google Ads

Semrush's `file_month` is parsed from the filename; `row_timestamp` comes from the row. `is_stale_observation` marks a timestamp before the file month. Missing timestamps remain unknown, and `row_after_cutoff` flags observations beyond the transaction cutoff. Rows are retained rather than silently assigned the filename's date.

`visibility_class` separates traditional organic positions from SERP features and unknown types. A feature row is not automatically a traditional organic top-ten position; either kind of visibility is not evidence of realized free clicks or paid cannibalization. Preserve `Position Type` when defining a ranking population.

File 12 retains each keyword row's original match type, campaign, ad group and all-time metrics. `clean_keyword` applies only whitespace, quote/bracket and case cleanup. It preserves plus signs, so older analyses that stripped `+` can produce different distinct counts. It does not merge synonyms, word order or singular/plural forms.

`historical_red_list_flag` reflects explicit supplier “do not retarget” evidence for the normalized keyword: either its text tier or the Filtered sheet's keyword-cell fill matching that label in the Categories legend. The code reads the legend rather than assigning meaning to a hardcoded RGB color. `historical_red_list_source_rows` identifies the supporting Filtered rows. Those rows also retain the fill identity, matching legend labels, direct evidence type and text-versus-fill conflict flag. Conflicting labels are retained rather than silently reconciled. This is a historical caution, not a current causal verdict; absence from that tier is not clearance to bid.

Historical negatives preserve their original scope and match type; the cleaner does not apply them as if they were current campaign settings. File 12 has no explicit period dates, so its metrics cannot silently become a like-for-like benchmark for a dated campaign. Current campaign exports, intervention logs and incrementality tests require their own declared sources and comparisons. No automatic phrase-match performance attribution, CTR-to-profit inference or paid/organic causal classification is produced here.

## Review and change control

Before using a table, state its grain, eligibility flag, period, geography, identity basis, money basis and denominator. Join at the documented key and check the resulting cardinality; a reward, discount, SKU or query row is not an order or person.

Review the manifest warnings and aggregate checks after each build. Structural failures stop the build; warnings identify limitations retained in the outputs. Passing a build establishes that the specified transformations and integrity checks ran. It does not validate an intervention's effectiveness or make an earlier report's interpretation correct.

Changes to source interpretation belong in code with a focused synthetic regression test and an explanation of the resulting analytical definition. Confirm provisional business assumptions with the data owner where needed, especially the tax gate, account treatment, matching semantics, campaign-code interpretation and clearance timing. Rebuild all downstream analyses against the resulting dataset ID and preserve the old version for comparison.

## Existing report-analysis adapter

Notebook 05 also records a separate private `final/analysis_manifest.json` with the dataset ID,
analysis-script hashes and hashes of any supplied ads snapshots. Optional snapshots are outside the
core data contract. Multiple candidates for the same snapshot are rejected.

The legacy report-analysis adapter preserves every selected GSC query row. A blank row with a repeated
query label cannot erase that label's observed numeric value. Query splits use observed numeric rows,
while coverage reports count blank source rows separately. Blank rows and wholly unknown query keys
are different counts. Multiple numeric rows sharing one month/query label fail pending a grain review.

The existing funnel comparison now uses only complete months within the transaction window. Its period
and geography still differ from the all-time ads conversion export, so it is not a like-for-like validation
of ad conversions. The product cohort requires a complete 730-day observation window. Product taxonomy,
margin assumptions and causal interpretations remain analysis decisions to review separately.
