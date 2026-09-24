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
```

Everything in this folder except this README is ignored by git. If your files live somewhere else,
set `WEAVVE_DATA` to that folder instead, for example `export WEAVVE_DATA=~/Documents/Weavve/Data`.
