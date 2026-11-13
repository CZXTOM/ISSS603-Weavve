# Recommendation validation

Use the shared dataset to distinguish descriptive findings, operational hypotheses and
measured treatment effects. This guide defines checks and proposed decisions; it
contains no private results and does not certify a report's conclusions.

Run [notebook 06](../notebooks/06_recommendation_checks.ipynb) or
[the recommendation-check CLI](../scripts/check_recommendations.py) after the
[shared-data setup](../README.md#setup). Keep generated results and executed notebooks
outside Git. Record the Git commit, dataset ID, source cutoff, analysis parameters
and limitations alongside every private result. A successful run establishes that
the selected calculation executed, not that a recommendation will work.

```powershell
python scripts/check_recommendations.py
# Optional: supply explicit planning assumptions from a private file.
python scripts/check_recommendations.py --scenario C:\private\planning-assumptions.json
```

The default destination is `WEAVVE_OUT/recommendation_checks/`; an explicit
`--out-dir` must remain outside Git worktrees. In the notebook, set
`WEAVVE_RECOMMENDATION_SCENARIO` to the private assumptions file to include optional
economics and power calculations. These are conditional scenarios, not measured
effects. No business assumptions are required to run the historical checks.

## Comparable populations and outcomes

| Question | Required definition | Interpretation limit |
|---|---|---|
| How many website newcomers arrived? | First eligible purchase across the configured website/Shopee scope; retain only people whose first eligible purchase is on the website. State inclusive entry dates and exclusions. | This is not necessarily first-ever purchase across every channel. Other-channel identities may be incomplete. |
| Has customer value changed? | Use a fixed follow-up horizon and the same seasonal entry interval in each cohort. Restrict every cohort to an entry interval that can fully mature in the latest year. | Cohort-year-to-date sales expose customers for different durations. Restricting only the newest cohort selects different entry seasons. |
| Can a customer be identified at purchase? | Separate initial order, total first-calendar-day purchases and the full initial purchase episode. Freeze the predictor at its intended decision time. | First-day totals are unavailable at the first checkout; an episode containing later dates is unavailable on day one. |
| What is subsequent value? | Report value after the defining purchase or episode separately from the value used to create the segment. Fit any quantile threshold using historical mature cohorts, then freeze it for later evaluation. | Total value partly contains the variable defining a high-spend segment; retrospective concentration is not prospective targeting accuracy. |
| What share returned within a horizon? | Require complete follow-up or use an explicitly defined time-to-event method. State repeat-purchase and same-day/episode rules. | Customers whose future is unobserved cannot be treated as completed-horizon nonreturners. |
| Did the funnel deteriorate? | Match complete months, geography, device/channel scope and event definitions. Inspect missing or duplicate months. | Aggregate traffic and orders do not isolate new-customer acquisition or identify a cause. Similar totals across sources do not validate tracking. |
| Who can receive an intervention? | Current person-level membership, contact permission, deliverability, purchase eligibility and suppression records. | Profile creation is not voluntary signup. A past campaign recipient count is not a current eligible roster. |

The analysis must state whether values include only positive purchase orders or signed
transactions including refunds. Purchase-only summaries describe buying behaviour;
they cannot substitute for net contribution. Preserve the cleaner's unresolved
identity, refund and channel warnings.

Dates must state timezone, boundary inclusion and timestamp precision. Calendar-date
orders cannot silently acquire precise times by comparison with profile timestamps.
For equal seasonal windows across leap years, document the leap-day rule and inspect
the resulting entry dates and observation lengths.

## Diagnose before selecting an intervention

First reconcile the funnel and customer definitions. Where available, separate new
visitors from returning visitors; inspect source, device, availability and checkout
step changes. A decomposition of orders into traffic and conversion describes the
arithmetic of a change. It does not establish that fixing either factor would recover
the historical difference.

Record actual current welcome and loyalty flows, campaigns, discount stacking,
membership rules and template behaviour. Historical exports and screenshots identify
checks to perform; they do not establish current defects or their prevalence.
The [audit protocol](experiment_protocols.md#1-checkout-and-flow-audit) supplies the
evidence record.

## Contribution and time

Use the same cost boundary for historical comparisons and scenarios:

```text
person contribution over horizon H =
    net sales excluding tax, after discounts and refunds
  - attributable product and variable fulfilment/payment/return costs
  - attributable communication, service and benefit costs
```

Specify shipping income/cost, reward liabilities and the treatment of late refunds.
Do not subtract a discount again when net sales already reflects it. A future-year
revenue estimate requires corresponding future costs and uncertainty. If actual costs
are missing, publish a labelled sensitivity, not measured profit.

Keep these quantities separate:

- **Mature cohort contribution:** an intake cohort followed for the full horizon.
- **Rollout contribution:** only the treatment exposure actually planned, including holdouts.
- **Calendar-period contribution:** outcomes recognised by that period's cutoff.
- **Programme net contribution:** incremental contribution less setup and ongoing fixed costs.

For an illustrative conversion-based scenario, show every assumption:

```text
expected extra buyers = eligible people × treatment exposure × assumed rate difference
scenario contribution = expected extra buyers × assumed incremental value × assumed margin
                      - incremental costs not already included
                      - setup and ongoing fixed costs
```

Historical converters' average value need not equal induced buyers' value. Include
adverse and zero-effect cases. Do not multiply a one-off offer effect across quarters
without evidence about repeated exposure, purchase timing and persistence.

Historical average sales times an assumed margin is not a safe acquisition bid cap.
Evaluate all campaign costs and all outcomes. Under a deliberately simplified ad-only
model, break-even ROAS is the reciprocal of contribution margin; a target ROAS does
not demonstrate that the required margin exists.

## Evidence language and experiment limits

Use “associated with” for comparisons based on observed membership, redemption,
discount use or pre/post periods. Selection, timing and changing exposure remain
possible explanations. A large p-value does not establish no effect or equivalence;
equivalence requires a prespecified acceptable difference and an appropriate design.

An experiment validates the population, treatment, comparator and horizon actually
tested. An existing-member offer cannot validate a new-member rewards package.
Recruitment duration is separate from full outcome follow-up. Power for a large
purchase-rate effect does not establish power for a smaller target or for contribution.
Report uncertainty and feasible decision rules before collecting outcomes.

## Proposal disposition

These are next steps, not launch decisions. See the separate
[experiment protocols](experiment_protocols.md) for eligibility, costs and decision rules.

| Proposal | Next step |
|---|---|
| Checkout and current-flow checks | Prioritise diagnosis; fix demonstrated defects and verify the repair. |
| Welcome education and an incentive | One bounded experiment against business as usual after current-flow and eligibility checks. |
| Larger-set offer | Defer until the first test and offer economics justify a separate experiment. |
| Increased acquisition spend based on observed high-value buyers | Do not use the retrospective segment as a bid instruction; establish total campaign contribution and prospective targeting performance. |
| Combined popup and membership | Test the journey; measure membership opt-in and purchase completion separately. |
| Lower first-reward threshold | Treat as a design hypothesis; model liability and subsidy before a separate test. |
| Progress display and head start | Test mechanism and cost; redemption correlations do not justify suppressing earned benefits. |
| VIP service or gifts | Define service capacity and costs; pilot service first, with gifts conditional on incremental contribution. |
| Checkout membership invitation | Test completion and friction as well as opt-in. |
| Retail receipt upload | Establish retailer cooperation, platform access, moderation, identity, fraud/returns and channel economics before a pilot. |
| Timed reminders and win-back | Treat timing as provisional; coordinate current flows and suppressions. |
| Existing-member offer | Separate controlled trial on a verified roster; no automatic transfer to new members or repeated-quarter gains. |

## Private handoff

For each retained claim, save the metric, population, period, horizon, denominator,
definition, dataset/commit, calculation location, uncertainty and limitations in the
private report. Keep discrepancies unresolved until the original implementation or
definition explains them. Do not replace a small boundary discrepancy with a claim
that the entire result is invalid.

No customer records, derived business results, reports or executed outputs belong in
this repository. The publication guard supplements review of source and prose; it
does not detect every confidential fact.
