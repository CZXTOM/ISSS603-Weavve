# Data goes here, and never into git

Put the Weavve files from eLearn in this folder, so it looks like this:

```
data/
  A.SEO _ GSC Impressions & Clicks _ 2023 -2026/
  B.SEO _ Semrush Organic Keywords _ 2023 Jan - 2026 Jul/
  C.Order _ Transaction-Level (All-Time).xlsx
  D.Product _ SKU Master File.xlsx
  E.Discount Report _ All-Time.xlsx
  F.Loyalty _ Customers, Earning Actions, Redemptions History _ All-Time.xlsx
  12.WH Google Ads 2019 - 2026 Keywords.xlsx
  G.Customer & Channel Mapping (for file C).xlsx
  J.Subscribers (no PII, with person_id) 2026-10-08.xlsx
  K.Campaign report - Weavvehome - 2026-10-08.xlsx
  L.Website Conversion Funnel _ 2024 to Sep 2026.xlsx
```

Files G to L came in the second data dump. Notebook 05 needs G, J, K and L, and it can also read them straight
from the zip files.

Notebook 05 can use two more files, which stay here as well. The ads monitor snapshots
(`ads_monitor_api_data_2026-10-31.json`, `ads_monitor_api_log_2026-10-31.json` and `ads_monitor_plan_2026-10-31.json`)
let it rebuild Section 10 of the final report. The report's Word file (`*Final_Report*.docx`) lets it check every
number against the report.

Everything in this folder except this README is ignored by git. If your files live somewhere else,
set `WEAVVE_DATA` to that folder instead, for example `export WEAVVE_DATA=~/Documents/Weavve/Data`.
