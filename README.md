# ISSS603 - Weavve Home group project

Shared cleaning and analysis code. Original files, cleaned tables, reports and executed notebook outputs stay local.

## Team

Chen Zexin · Wang Xiaohan · Meng Xinyu · Zhang Jin · Charles Jr Ignacio Ancheta · Brandon Komajaya

## Setup

Use Python 3.12.10 for the tested cleaning environment. Other Python versions create a different dataset ID.

```powershell
git clone https://github.com/CZXTOM/ISSS603-Weavve.git
cd ISSS603-Weavve
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-clean.txt
pre-commit install
$env:WEAVVE_DATA = "C:\private\weavve-originals"
$env:WEAVVE_OUT = "C:\private\weavve-outputs"
python scripts/build_clean_data.py --zip
```

On macOS/Linux, activate with `source .venv/bin/activate` and set variables with `export WEAVVE_DATA=...`
and `export WEAVVE_OUT=...`. The original supplied ZIPs can be read directly; extraction is unnecessary.
See [data/README.md](data/README.md) for required sources.

## One dataset for the team

The build creates `WEAVVE_OUT/clean/<dataset_id>/` with CSV tables, a manifest and a data dictionary.
`--zip` also creates a **private local ZIP** beside that directory. Do not commit or upload it to GitHub.
Without `WEAVVE_OUT`, outputs go to `~/Desktop/weavve_outputs`.

Each teammate uses the same Git commit, unmodified original sources, Python version and pinned Excel reader,
then runs the build. Compare the dataset IDs printed by the notebooks. The ID covers source hashes,
cleaning code, rules and the parser runtime. Identical source copies in ZIP and extracted form are deduplicated;
conflicting copies fail. Current notebooks reject changed sources, stale code and modified tables.

The file [docs/cleaning_contract.md](docs/cleaning_contract.md) defines table grains, filters, exclusions,
GST handling and unresolved interpretation limits. Review the manifest warnings before using the numbers.
A successful build establishes reproducibility of these rules; it does not validate a report's claims.

## Current notebooks

Start Jupyter after setting the environment variables. Run from the `notebooks` folder; restart kernels
when code, input files or dataset selection changes. Never commit executed copies.

| Notebook | Purpose |
|---|---|
| `04_build_clean_data` | Build or verify the shared dataset and create the private ZIP |
| `10_clean_customer` | Customer and purchase summaries from canonical orders |
| `11_clean_product` | Product coverage and clearance flags from canonical lines |
| `12_clean_promotion` | Discount and voucher summaries with explicit scope |
| `13_clean_search` | Selected GSC months, Semrush freshness and historical ads inputs |
| `05_final_report` | Recompute existing Part B formulas and figures from the same tables |

Notebooks `00` to `03` are historical raw-data exploration. Their outputs are not the shared cleaned dataset.
No historical cache is required to run notebook 04 or the current analyses.

Notebook 05 retains a frozen analysis window and observational/scenario assumptions. It optionally compares
excerpts with an explicitly selected local Word file through `WEAVVE_REPORT`. It does not access online
reports, discover a latest draft, or prove every claim. Optional local ads snapshots are needed for Section 10;
missing evidence is reported as skipped. Table 11 comparisons require the matching row and metric column.

## Validation and commits

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python scripts/check_no_data.py --tracked
git diff --check
```

The tests use synthetic records. Private real-data and notebook reruns are performed locally and their
outputs stay outside the repository. The publication guard inspects staged blobs, including notebook
outputs, attachments and execution metadata; clearing only the working copy does not clear staged data.
Run the guard after staging. The pre-commit hook strips notebook outputs and rejects data/report files.

Keep commits small, review staged changes, and push a feature branch for review. Never edit the raw sources.
Shared transformations belong in `src/weavve/`, not in a teammate's notebook.

Set `WEAVVE_ADS` to a separate private snapshot directory if the optional ads JSON files are not beside the originals.
