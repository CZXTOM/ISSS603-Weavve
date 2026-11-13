# Corrected recommendation evidence

Use the verified shared dataset for Idea 1 and cart-completion diagnostics, explicit
private planning inputs, and optional dated Ads snapshots. These calculations do
not launch a campaign or establish a causal effect. Company data and financial inputs
remain outside Git.

```powershell
python scripts/build_recommendation_evidence.py
python scripts/build_recommendation_evidence.py --ads-dir "C:\private\ads-snapshots"
python scripts/build_recommendation_evidence.py --idea1-scenario "C:\private\idea1-planning.json" --cart-scenario "C:\private\idea2-planning.json" --ads-dir "C:\private\ads-snapshots"
```

The compatibility entry points `analysis/idea1/idea1_v8.py` and
`analysis/idea1/idea1_slide_numbers.py` call the same runner with the same options.
They replace the alternate-workbook and source-prefix execution paths. The output is
private JSON with traceable claim IDs, definitions and evidence status. No business
financial assumption is supplied by default.

## Input and output contract

Set `WEAVVE_DATA` and `WEAVVE_OUT` following the root README and build the shared
dataset first. Original sources and the resulting manifest must verify successfully.
The runner reads canonical typed tables; it does not clean another Excel copy.

Outputs go to `WEAVVE_OUT/recommendation_evidence/<dataset_id>/`. An explicit
`--out-dir` is supported, but the resolved destination must be outside every Git
checkout. Redirected files are rejected. The evidence records dataset identity,
analysis-code hashes, optional input hashes and the checked-out commit. Executed
notebooks and console logs also stay private.

Optional exact welcome-code identifiers belong in a private JSON string list passed
with `--welcome-codes`. Codes are matched exactly after whitespace/case normalisation.
Campaign-name patterns and date-typed codes are not guessed into identifiers. Without
that input, welcome-code comparisons are explicitly unevaluated.

An optional Ads directory contains these private files:

- `ads_monitor_api_data.json`
- `ads_monitor_api_log.json`, if available
- `ads_monitor_plan.json`, if available

Use a dated, coherent snapshot and retain its provenance privately. The runner has no
login or network dependency and never receives a website password. Ads totals and
diagnostics are aggregated without exposing raw keyword text, account IDs or URLs.
Changes on the same date are grouped; the whole change date is included in the prior
descriptive phase. This convention does not establish clean treatment exposure or
causality. Missing days suppress the phase comparison.

## Idea 1 definitions and corrections

The analysis identifies canonical positive nonspecial website/Shopee customers whose
first observed scoped purchase is on the website. This is not first lifetime purchase
across every channel. First individual-order category attributes are joined by exact
SKU, retaining unknown coverage and checking conflicting product mappings.

All early-order monetary value is retained. The identity is initial-episode value plus
later purchase value; excluding early top-ups from the repeat count must not delete
their sales. Purchase-order nets remain retrospective because later refund adjustments
can change them. Signed line-date outcomes retain refunds in their actual event window.

Matched comparisons use the same entry season and complete fixed follow-up. Endpoints
are start-inclusive/end-exclusive, with the last included calendar day observed.
Leap-day handling is explicit. Profile linkage is labelled as historical linkage and
is not membership, permission, deliverability or a verified launch audience.

The proposed early content test has a separate historical risk-set diagnostic. Its
candidate assignment is at day 60, with no earlier post-episode purchase and a 90-day
outcome over purchase ages 60–149. That is a timing hypothesis, not an estimated optimum.
The comparable historical profile variant uses profiles dated by the assignment day.
It cannot prove within-day ordering, historic consent or current eligibility.

Use that risk-set baseline for the proposed test; do not substitute a six-month return
rate from first purchase. Observed buyer value is a selected historical reference,
not a measured marginal-buyer effect. Retain value, audience and cost sensitivities.

## Private profit planning schema

The Idea 1 file and the optional deferred earned-reward file use this fixed-roster schema:

```json
{
  "label": "Synthetic arithmetic example only",
  "eligible_people": 1000,
  "treatment_fraction": 0.5,
  "baseline_purchase_rate": 0.10,
  "baseline_reward_redemption_rate": 0.01,
  "contribution_per_purchaser_before_tested_reward": 50,
  "tested_reward_cost_per_redemption": 10,
  "contact_cost_per_treated_person": 0,
  "additional_operations_cost_per_treated_person": 0,
  "setup_cost": 100,
  "scenarios": {
    "adverse": {"purchase_rate": 0.08, "reward_redemption_rate": 0.06},
    "zero_purchase_lift": {"purchase_rate": 0.10, "reward_redemption_rate": 0.06},
    "benefit": {"purchase_rate": 0.13, "reward_redemption_rate": 0.06}
  },
  "notes": ["Replace synthetic values with documented private inputs"],
  "unpriced_costs": ["Record excluded costs explicitly"]
}
```

For the Idea 1 content-only file, set the tested reward cost, baseline reward rate and
every scenario's reward rate to zero. The validator rejects a hidden incentive.
Rates are probabilities among all assigned people, and one tested reward can be used
at most once in the window. Reward-redemption probability cannot exceed purchase
probability. Include adverse and zero-purchase-lift cases with their own redemption
responses. Contact/operations cost means the **increment over business as usual**,
which can be zero when both arms use the same scheduled message and delivery cost.

The conditional trial model is:

```text
trial net contribution = treated people ×
    [(treatment purchase rate - control purchase rate) × contribution per purchaser
     - (treatment redemption rate - control redemption rate) × tested reward cost
     - incremental contact and operating cost per treated person]
    - incremental fixed cost
```

Purchase contribution is before the tested reward; subtract that reward once. Actual
intention-to-treat contribution uses observed net sales/costs and avoids double
deduction. The simplified model assumes comparable basket/frequency and reward cost;
if those change, use the actual person-level outcome. Additional redemption can lose
money with no purchase uplift. Break-even uplift is conditional on the entered
redemption response and costs.

These are one-off 90-day trial cases, not automatically annual or full-roster rollout
returns. Historical candidate counts require a current eligibility check. Label
contribution rates, value haircuts, effect targets and build-cost caps as assumptions
or proposed limits where they are not observed business inputs. A capped test can be
the defensible action when a large rollout case cannot be supported. Do not hide
negative scenarios or change the cost boundary to manufacture a positive result.

## Cart-completion planning schema

The active Idea 2 proposal uses a separate fixed-period model, passed with
`--cart-scenario` (alias `--idea2-scenario`). The example is synthetic only:

```json
{
  "observed_recorded_carts": 1000,
  "baseline_ratio": 0.25,
  "purchase_order_net_reference": 100,
  "marginal_value_factor": 0.75,
  "assumed_contribution_rate": 0.30,
  "fixed_incremental_cost": 100,
  "variable_cost_per_extra_order": 0,
  "cases": {"adverse": -0.01, "zero": 0, "benefit": 0.01},
  "planning_period_label": "Synthetic fixed observation window"
}
```

Rate changes are absolute changes in orders per recorded cart unit; they are not
verified individual purchase probabilities. The model multiplies additional orders
by the reference value, marginal-value factor and assumed contribution fraction,
then subtracts any extra per-order and fixed costs. Signed decreases in orders also
change variable costs; fixed costs apply in every case. Require adverse, zero and
positive cases. No annualisation is applied.

The canonical ledger order-value reference is not geographically linked to the
Singapore funnel. An assumed value reduction is a sensitivity, not a correction
for that mismatch. The recorded cart count is not a unique-visitor trial roster.
Use the actual treated exposure and full follow-up for a pilot; a full-volume
planning case is a different quantity. Verify all cost boundaries and event grain
before making a live decision. The [cart protocol](idea2_cart_completion.md)
requires truthful policy reconciliation in both arms before the presentation test.

The earned-reward option is deferred. Its model can still be evaluated explicitly
with `--reward-scenario`, but is not the active second recommendation.

## Notebook and claim reconciliation

Notebook 07 calls the same runner. Optional private paths are read from:

- `WEAVVE_WELCOME_CODES`
- `WEAVVE_IDEA1_SCENARIO`
- `WEAVVE_IDEA2_SCENARIO`
- `WEAVVE_DEFERRED_REWARD_SCENARIO`, if evaluating the deferred option
- `WEAVVE_ADS_SNAPSHOTS`

Compare every final slide/report value to its claim ID or scenario row. Keep metric,
population, entry dates, horizon, numerator/denominator, rounding and evidence status
with the private register. Smooth execution proves the defined calculation ran; it
does not prove a treatment effect or that a figure was transcribed correctly.

Sequence the actions in the report: reconcile data and current operations, prepare
the smallest feasible content contrast, run a bounded test with complete follow-up,
then decide whether its contribution supports expansion. Apply the same discipline
to the [cart-completion proposal](idea2_cart_completion.md). Keep the two trial audiences
separate through the shared registry.
