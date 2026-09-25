# ISSS603 · Weavve Home group project

Code for the ISSS603 Weavve Home project. The data belongs to Weavve and is never stored here.

## Team

Chen Zexin · Wang Xiaohan · Meng Xinyu · Zhang Jin · Charles Jr Ignacio Ancheta · Brandon Komajaya

## Set up (once)

```bash
git clone https://github.com/CZXTOM/ISSS603-Weavve.git
cd ISSS603-Weavve
python3 -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
pre-commit install                                      # clears notebook outputs and blocks data files on every commit
```

Then put the Weavve files from eLearn in `data/`, named as in [data/README.md](data/README.md).
If you keep them somewhere else, set `WEAVVE_DATA` to that folder instead.

Outputs (cleaned tables, charts, the cache) go to `~/Desktop/weavve_outputs`. Set `WEAVVE_OUT` to change it.

## Notebooks

Run from the `notebooks` folder, in this order.

| Notebook | What it does | Who |
|---|---|---|
| `EDA_notebook` | Independently audits all 86 raw files, every sheet and every populated column before preprocessing; writes an aggregate-only column audit to `WEAVVE_OUT` | Shared |
| `01_load_raw` | Reads every file once and caches it | Anyone, run first |
| `02_data_checks` | Measures every data problem in the plan, saves `data_checks.json` | Shared |
| `03_team_findings_check` | Reruns the team's first findings, raw and clean | Shared |
| `10_clean_customer` | Orders, customers, loyalty | Customer group |
| `11_clean_product` | Products sold, missing codes | Product group |
| `12_clean_promotion` | Discounts per line and order, campaign types | Promotion group |
| `13_clean_search` | Keywords by month, do-not-bid list | Search group |

The 10 to 13 notebooks list their steps from the team plan. Fill in each step's code under its heading.

`EDA_notebook` can run before the other notebooks. It reads the original files directly and does not use their cache or cleaning rules. If the historical Ads workbook is outside `WEAVVE_DATA`, set `WEAVVE_ADS` to its full path. Its source inventory expects the supplied 38 GSC workbooks and 43 Semrush CSVs; review the inventory if the export changes.

## Rules

1. **No data in the repo.** No csv, xlsx, pkl, json or pictures of data. The pre-commit check refuses them.
2. **Clear notebook outputs before committing.** The pre-commit hook does this for you. If you skipped `pre-commit install`, run `nbstripout notebooks/*.ipynb` first.
3. **Never change the raw files.** Every notebook reads from `data/` and writes to the outputs folder.
4. **Small commits with clear messages**, like `customer: remove cancelled orders`. Pull before you start, push when you stop.
5. Shared code goes in `src/weavve/`. Tell the team before changing it.

## Folders

```
data/          Weavve files, ignored by git (only the README is tracked)
notebooks/     all analysis, outputs cleared
src/weavve/    shared loaders and paths
scripts/       the pre-commit data check
```
