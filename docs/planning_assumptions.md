# Conditional planning inputs

The recommendation checker has no built-in business forecast. Supply a private JSON file with
explicit assumptions only when a conditional comparison is useful. Do not commit that file or its outputs.
The example below is synthetic and is not a Weavve estimate.

```json
{
  "label": "Synthetic illustration only",
  "annual_eligible": 1200,
  "baseline_rate": 0.10,
  "target_rates": {"adverse": 0.08, "zero_lift": 0.10, "benefit": 0.15},
  "mature_buyer_net_sales": 100,
  "value_horizon_days": 365,
  "contribution_margin": 0.50,
  "setup_cost": 100,
  "annual_operating_cost": 200,
  "additional_cost_per_treated_person": 1,
  "rollout": [{"months": 6, "fraction": 0.5}, {"months": 6, "fraction": 1.0}],
  "outcome_days": 90,
  "unpriced_costs": ["List any material excluded costs here"],
  "notes": ["Synthetic illustration; replace every assumption with documented inputs"],
  "alpha": 0.05,
  "power": 0.80
}
```

All fields except `alpha` and `power` are required. Rates and fractions use 0–1, not percentages.
Rollout periods must cover exactly twelve months. Target cases must include zero uplift and an adverse
case; labels are user-defined. The normal power approximation requires rates strictly between zero and one.
Equal baseline and target has no finite required sample and is written as `null`.

`annual_eligible` is a verified eligible arrival rate when available; a historical profile count used instead
must be labelled as an unverified proxy in `notes`. It is not a current member register and should not
be used to model a one-off existing-member trial as recurring annual arrivals. Plan that trial using its
verified fixed roster and a separately specified analysis, not this arrival-based timetable.

`mature_buyer_net_sales` is sales per incremental buyer over `value_horizon_days`, not immediate cash.
Assigning historical converter value to incremental buyers is itself an assumption. `contribution_margin`
must have a documented cost boundary. Include payment, fulfilment, product, return and incentive costs
where relevant. Do not deduct an incentive again when it is already reflected in net sales or that margin.
`additional_cost_per_treated_person` covers treatment/subsidy costs outside that boundary for **all**
treated people, including those who would purchase anyway. A per-person average may itself need estimation.
`setup_cost` and `annual_operating_cost` are subtracted once from both exposure scenarios. Costs listed
as unpriced remain excluded; recording them does not turn the result into net profit.

For uniform arrivals, treatment exposure is the sum of months × allocation divided by twelve. The tool
reports full-exposure and rollout-exposure **mature cohort contribution** after the entered costs. Neither
is realised launch-calendar-year profit. Calendar-year cash requires acquisition/purchase timing and an
observed revenue/cost schedule; the checker deliberately does not manufacture it.

The sample-size calculation is the conventional two-sided normal approximation for two independent
proportions, with fixed analysis and equal allocation. It is planning for the **secondary binary purchase
endpoint**, not the primary contribution endpoint. Contribution precision needs transaction-level outcome
variance and a predeclared suitable analysis. Recruitment assumes the same eligible arrival rate and
50:50 allocation throughout, then adds the full outcome follow-up for the last recruit. It does not apply
the separate rollout allocation; changing allocation, clustering or sequential monitoring requires a
separate design. Do not reuse the result for subgroup selection or assume a 90-day effect repeats quarterly.

```powershell
python scripts/check_recommendations.py --scenario "C:\private\planning-assumptions.json"
```

For notebook 06, set `WEAVVE_RECOMMENDATION_SCENARIO` before starting the kernel. Omit it to run only
historical diagnostics. The private output records input-file and analysis-code hashes for traceability.
