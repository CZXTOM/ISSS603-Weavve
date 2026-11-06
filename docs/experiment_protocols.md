# Checkout audit and experiment protocols

**Status: prepared; not launched.** No live customer allocation, campaign change,
discount activation or operational audit result is recorded here. The shared notebook
checks historical definitions; it does not execute these experiments.

The sequence is: verify the current journey and measurement, resolve the inputs below,
then consider a bounded welcome experiment and a separate existing-member offer.
A broad loyalty relaunch or an acquisition-spend increase is not the default next step.

## Inputs and owners to resolve

Roles are proposed responsibilities, not assigned people. Store named owners and
private business inputs in the team's private implementation record.

| Role / input | Current state | Needed before a live experiment |
|---|---|---|
| Business decision owner | Unassigned | Named person; commercial decision, minimum worthwhile contribution and maximum acceptable loss |
| Campaign operator | Unassigned | Current flow/campaign inventory, exact treatment copy/timing, contact and suppression rules |
| Data owner | Unassigned | Current deduplicated person roster, permission/deliverability, membership and purchase linkage |
| Finance/operations owner | Unassigned | Actual contribution costs, refunds/returns, benefit liability, staff/platform/setup costs |
| Analyst | Unassigned | Frozen protocol, allocation, sample size/precision, analysis code and independent allocation check |
| Store/measurement owner | Unassigned | Current checkout evidence, event definitions, permitted test environment and repair verification |
| Platform capability | Unverified | Current plan entitlement, integrations, required history, access and operational limits |
| Dates and offer terms | Unresolved | Start/end, maximum enrollment, offer amount/minimum/expiry, stacking and redemption rules |

These are missing factual and operating decisions, not evidence that a test has failed.
Where the available audience cannot support useful precision, choose a smaller
feasibility objective or defer; do not promise a proven profit effect.

## 1. Checkout and flow audit

**Question:** Are measurement changes, product availability or journey defects plausible
contributors to the observed acquisition/conversion patterns?

The store/measurement owner and campaign operator should record:

1. Reporting scope: timezone, geography, session/user/order grain, device, attribution,
   event versions, missing periods and consent-related measurement changes.
2. Journey cases: new/returning shopper, supported device, in-stock/unavailable item,
   shipping-cost visibility, applicable and inapplicable code, membership prompts,
   payment-step errors and completion events. Use an agreed test environment or
   read-only evidence; do not create a live order merely to complete this checklist.
3. Flow inventory: trigger, audience, timing, branch, exit, template, incentive,
   expiry, campaign overlap, frequency cap and suppression behaviour.
4. Source-to-order links: what is trackable, identity gaps and the distinction between
   attributed and incremental sales.
5. Defect record: observed behaviour, expected rule, dated evidence, affected scope,
   owner, proposed repair and verification result. A suggested issue remains
   “unverified” until observed.
6. New-visitor and returning-visitor funnel views, product/stock and acquisition-source
   changes where available. Do not infer competitor capture from relative search data.

**Deliverable:** a private current-state inventory, reconciled funnel definitions and
ranked verified issues. Distinguish measurement repairs from customer-experience repairs.
For each repair, define how correct behaviour will be checked; do not label a before/after
sales change its causal effect without an appropriate design.

## 2. Shared experiment design

### Enrollment and assignment

- Unit: one stable person, not email address, cookie, order, redemption or campaign send.
  Reconcile duplicate identities before enrollment; record unresolved linkage coverage.
- Freeze the eligibility rule before assignment. Check permission, contactability,
  purchase status, active experiments and relevant membership state at enrollment.
- Use one private experiment registry to prevent overlapping enrollment and conflicting
  offers. Do not re-randomise a person who returns, changes address or fails delivery.
- Proposed allocation: balanced random assignment. The analyst records the algorithm,
  seed, any prespecified strata and allocation before treatment. The roster and seed
  stay private; reconcile counts and balance without changing allocation to improve results.
- Persist experiment ID, stable person ID, eligibility snapshot/version, assigned arm,
  assignment timestamp/timezone and planned follow-up end. Allocation is immutable.
  Later identity merges follow a predefined resolution rule and are reported.
- Randomise before the first intervention. Keep assigned people in their original arm
  for analysis, including nonopeners, nonredeemers, undelivered contacts and buyers who
  subsequently exit a message flow. Honour later opt-outs operationally without silently
  removing their existing assignment from analysis.

If outcome linkage fails, report coverage and sensitivity; do not code an unknown
purchase outcome as a confirmed zero. Confirm that proposed collection and retention
are supported by the actual permission and platform arrangements.

### Outcomes and accounting

The primary endpoint is the **difference in mean 90-day contribution per assigned
eligible person**, treatment minus control, using intention-to-treat analysis.
Define each window as assignment time inclusive to assignment plus 90 days exclusive.
When source precision is only a calendar date, predefine an equivalent date rule;
do not manufacture timestamps.

Contribution includes observed net sales after discounts/refunds and the attributable
product, fulfilment, payment, return, communication, service and benefit costs.
Count costs incurred by people who would have bought anyway as well as induced buyers.
Do not subtract a discount twice. State how benefits earned but not redeemed and refunds
posted after the purchase window are handled. Freeze the refund-reconciliation lag
before launch and wait for that lag before final analysis.

Allocate any per-person treatment cost consistently. Report setup and additional fixed
operating costs separately:

```text
estimated contribution difference per assigned person = mean(treatment) - mean(control)
trial incremental contribution = treated count × estimated difference
programme net contribution = trial incremental contribution - incremental fixed costs
```

The second line estimates the effect on the treated population at the tested allocation;
it is not a forecast for every future eligible person. Uncertainty in the difference
also applies to the total. Report realised trial costs separately from scaled scenarios.

Secondary endpoints: 90-day purchase rate, orders/net sales per assigned person, time
to first purchase and relevant membership/engagement measures. Opens, clicks and
redemptions are diagnostics; they are not the profit endpoint. Record coverage and
handling of cross-channel purchases before launch. If only website outcomes are
observable, name that narrower estimand and the risk of channel substitution.

Guardrails: opt-outs/complaints, delivery failures, checkout completion where applicable,
discount errors, leakage/abuse, return rate and staff workload. Owners set numeric
thresholds and monitoring cadence before enrollment; all are currently unresolved.

### Precision and decisions

Use the verified eligible intake/roster and a comparable baseline to estimate sample
size and recruitment duration. Purchase-rate power calculations address that binary
endpoint only. Assess contribution precision using a defensible historical distribution
or a clearly labelled pilot; do not assume binary power establishes profit precision.

Freeze enrollment limit/end date, primary analysis, uncertainty method, minimum
commercially meaningful contribution and maximum acceptable loss before launch.
Report a two-sided confidence interval for the primary difference with a person-level
method appropriate to the distribution and any randomisation strata. Predefine
handling of skew, outliers and missing linkage; do not trim high spenders after seeing
which arm benefits.

Keep operational monitoring separate from efficacy testing. Stop/pause for a
prespecified operational guardrail and record the reason; do not repeatedly inspect
significance and stop at a favourable result. Final evaluation waits for the last
enrollee's 90-day window and the specified refund lag.

The private decision record must state what evidence would justify rollout, further
learning or stopping. If the interval remains compatible with material loss and useful
gain, report that uncertainty. A nonsignificant difference is not proof of no effect.
Do not automatically roll out in a numbered month or search small RFM cells for winners.
Any limited, prespecified subgroup estimates remain exploratory unless independently
powered and validated.

## 3. Welcome-flow experiment

**Question:** Does a revised welcome sequence improve 90-day contribution compared
with current business-as-usual communications for eligible new prospects?

**Eligibility:** verified new prospects who have not purchased by assignment, with
current permission and deliverability. Decide which channels establish prior purchase,
how older profiles are treated and how unresolved identities are handled. Historical
profile creation alone does not establish this population.

| Element | Proposed specification |
|---|---|
| Control | Current business-as-usual welcome flow and campaign policy, captured/versioned before launch |
| Treatment | Revised educational sequence addressing product choice, care and purchase concerns; exact copy, timing and any incentive terms remain to be set |
| Contrast | Change only the defined sequence/offer; preserve unrelated campaign eligibility and contact policy across arms |
| Contact coordination | Specify frequency caps, suppression priority and interaction with sale, abandoned-checkout and club flows before assignment |
| Purchase/opt-out exit | Stop relevant prospect messaging when its exit condition is met; retain the person in the assigned analysis arm |
| Primary outcome | Shared 90-day contribution difference per assigned eligible prospect |
| Secondary outcome | 90-day first-purchase rate under the frozen channel definition |

The control is not “no marketing” unless the explicit business question is whether
any contact beats none. A treatment that changes both copy and incentive estimates
the combined package; it cannot identify which component caused a difference.

Do not add a larger-set offer during the primary test. If both experiments could reach
the same person, apply the shared registry's exclusion/priority rule. Confirm treatment
delivery and correct suppression with controlled test accounts before enrollment.

## 4. Existing-member offer experiment

**Question:** Does one precisely defined member offer improve 90-day contribution
among currently eligible existing members compared with current practice?

**Eligibility:** current deduplicated membership plus permission/contactability and
purchase linkage, using a dated person-level export. A previous campaign's recipient
total does not establish the available roster. Define exclusions for staff/test accounts,
other experiments, existing offers and unresolved membership status before assignment.

| Element | Proposed specification |
|---|---|
| Control | Current member benefits and communications without the experimental offer |
| Treatment | One additional member offer; amount, threshold, expiry, exposure, redemption, stacking and repeat-use limits remain unresolved |
| Contact coordination | Keep ordinary campaign rules comparable; specify whether the offer appears by email, account or checkout and how exposure is recorded |
| Primary outcome | Shared 90-day contribution difference per assigned eligible member |
| Secondary outcomes | 90-day purchase rate, repeat timing, net sales, redemption and benefit cost |
| Guardrails | Shared guardrails plus unintended stacking, benefit liability and support effort |

Measure assignment rather than redemption. The counterfactual for a particular redeemed
purchase is unobservable; infer incrementality from the randomised groups. Use all
redemption costs in contribution, including subsidies to people who would buy anyway.

This result applies to the tested member population and offer. It does not validate a
new-member reward ladder, progress display, VIP service or combined popup. Do not assume
the effect repeats in every quarter. Prespecify a later observational follow-up window,
with treatment history retained, to check for purchase pull-forward; longer follow-up
does not by itself prove an indefinitely recurring effect.

## 5. Scenario and handoff record

Keep an adverse-effect case, a zero-effect case and explicitly assumed beneficial
cases. For each, record audience, exposure schedule, value/cost assumptions, fixed costs,
outcome horizon and cash timing. Historical-rate recovery is a scenario, not a forecast.
Separate annual-cohort value, actual rollout exposure and calendar-period receipts.

The private handoff contains the completed inputs/owners table, signed-off operating
settings, protocol version, roster/assignment audit, templates, launch verification,
cost definitions, dated results and the resulting decision. “Signed-off” means the
business owners have resolved their operating settings; this document grants no
authority to launch. Keep all customer data, business results and executed outputs
outside the repository.

Use [recommendation validation](recommendation_validation.md) and
[notebook 06](../notebooks/06_recommendation_checks.ipynb) to check historical definitions.
No historical calculation or synthetic test records the completion of a live audit
or establishes the effect of either proposed intervention.
