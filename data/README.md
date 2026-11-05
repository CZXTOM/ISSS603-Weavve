# Original inputs stay local

Set `WEAVVE_DATA` to a private folder containing the three original supplied ZIP files:

- Dump 1, part 1: orders, products, discounts, loyalty and historical ads.
- Dump 1, part 2: GSC and Semrush search exports.
- Dump 2: the G to L support workbooks.

The default is this ignored `data/` directory. Extracted copies also work. Preserve original filenames.
The shared build needs A (GSC), B (Semrush), C (orders), D (SKU master), E (discounts), F (rewards),
G (person/channel mapping), I (clearance), J (profiles), K (campaigns), L (monthly funnel) and
12 (historical ads keywords). Source H correspondence is inventoried when supplied; it is not a table.

The catalog records original byte hashes. Identical duplicate copies are deduplicated; conflicting copies
with the same logical name or multiple versions of a required workbook fail. Do not modify an original
to resolve this: point `WEAVVE_DATA` at one agreed source set.

Run `python scripts/build_clean_data.py --zip` from the repository root. Set `WEAVVE_OUT` to a separate
private folder outside both this repository and the source folder. Outputs must not overlap inputs.
The generated manifest, dictionary, CSVs and ZIP are private artifacts; GitHub receives code only.

Optional ads snapshots (`ads_monitor_api_data_2026-10-31.json`, `ads_monitor_api_log_2026-10-31.json`
and `ads_monitor_plan_2026-10-31.json`) are used only by notebook 05's existing Section 10 formulas.
They are not part of the core cleaning contract. A Word report is used only when its local path is
explicitly set in `WEAVVE_REPORT`; no online report is accessed.

Set `WEAVVE_ADS` to a separate private snapshot directory if the optional ads JSON files are not beside the originals.
