# Idea 2: test visibility of an existing earned reward

**Status: deferred option; not launched.** The earned-reward roster and profit case are not established, so this remains a future protocol rather than the main revised recommendation. It evaluates a clearer explanation of an existing benefit in one scheduled member-message slot. It does not change points earning, the first-reward threshold, membership entry, checkout design or VIP benefits.

## Decision and customer benefit

An existing member should be able to understand a benefit they have already earned, its conditions and how to use it. A clear reminder may help them use that benefit on a relevant purchase. It may also subsidise an order they would have placed anyway. The commercial question is whether the reminder adds contribution after all costs.

Historical membership, spending and redemption comparisons do not identify that effect. Existing member-reminder messages must be inspected rather than assuming a contact gap. A lower reward threshold or broader programme relaunch requires a different test.

## Prerequisites

Before enrollment, the business owner must confirm that the programme is operating and that an earned reward can actually be redeemed under its current terms. The current member roster, contact permission, deliverability, unused valid rewards, purchase linkage and existing flows must be reconciled.

A historical campaign recipient total is not the eligible roster. A transaction's voucher code does not establish current membership, an unused balance or contact permission. If the required export or operational capability is unavailable, defer the test and complete the operational investigation first. Do not create a new reward solely to make this experiment possible.

Proposed responsibilities remain unassigned: a business decision owner, campaign operator, data analyst and finance/operations owner. Their operating settings belong in a private implementation record.

## Population, assignment and comparator

The unit is one deduplicated person with:

- Current membership and a verified, valid unused earned reward.
- Current permission and deliverability for the proposed contact.
- Purchase linkage within the declared outcome channels.
- No enrollment in Idea 1 or another conflicting experiment.
- No active post-purchase or reward contact that conflicts with the test.

Freeze any recency restriction before assignment and justify it as an operating choice. Do not describe it as an empirically optimal purchase cycle. Record exclusions and linkage coverage. Do not replace unknown outcomes with zeros.

Use the private experiment registry to prevent overlapping enrollment. Assign eligible people once to balanced treatment and control groups, before the first message. Preserve assignment after delivery failures, opt-outs, purchases or flow exits. Any prespecified strata should support balance and precision, not post-hoc selection of apparent winning segments.

**Control:** the current verified points/member message in its normal scheduled slot, with existing benefits, recorded before launch.

**Treatment:** the same scheduled slot, delivery timing and benefits, with a defined email showing the member's existing earned reward, its current conditions, expiry and redemption steps. Keep product links and other offer content comparable unless a combined content contrast is explicitly intended.

Keep ordinary campaign eligibility, contact load and caps comparable. The intervention replaces the content of one member message; it does not add a duplicate contact. If current practice already presents the earned reward in the proposed way, there is no useful contrast and this design should be deferred or formally revised. No surprise reward, points top-up, threshold cut or extra percentage discount is added.

## Workflow

1. The data and campaign owners reconcile the private roster, entitlements, identity and suppressions.
2. The finance/operations owner freezes the cost and refund boundaries. The business owner sets the commercial threshold and loss budget.
3. The operator verifies personalised content, links, expiry, stacking and redemption with authorised test accounts. Repair observed defects before enrolling customers.
4. The analyst records the protocol version, immutable person-level allocation and planned follow-up.
5. The operator sends the defined message and records delivery, complaints, opt-outs and deviations.
6. The analyst links purchases, discounts, returns and servicing costs for both groups, then evaluates after the last participant's outcome window and the specified refund lag.
7. The owner records a decision to stop, investigate further or expand the same tested treatment. A further programme change needs its own evidence.

## Outcomes and accounting

The primary endpoint is the difference in mean **90-day contribution per assigned eligible person**, treatment minus control. Define the interval from assignment inclusive to assignment plus 90 days exclusive. Freeze a date-only equivalent if timestamps are unavailable.

Contribution includes net sales after discounts and refunds, less relevant product, fulfilment, payment, return, communication and servicing costs. Count reward use and costs for all assigned people in both groups, including people who would purchase without the reminder. A discount already deducted in net sales must not be subtracted again. Contact and operations charges in a separate incremental model mean the difference from business as usual; do not charge the full normal email cost again when both groups use the same slot. The finance owner must define the treatment of existing reward liability and late refunds.

Secondary outcomes are purchase rate, orders and net sales per assigned person, recorded reward use and repeat timing. Delivery, opt-outs, complaints, redemption errors, excessive subsidy and operator workload are guardrails. A higher redemption rate is not sufficient to declare success.

Report incremental fixed setup and operating costs separately. For the treated population:

```text
estimated incremental contribution =
    treated people × (mean treatment contribution − mean control contribution)
  − incremental fixed costs
```

Keep this trial estimate separate from an extrapolation to a wider population.

## Planning economics and decisions

No default effect, current eligible count or profit figure is supplied. The decision needs a verified roster, a comparable baseline and actual contribution costs. Power for purchase rate does not establish precision for contribution. Estimate contribution variance using appropriate historical outcomes or a clearly labelled feasibility pilot; freeze the final analysis method before efficacy testing.

The fixed-roster planning model can quantify a decision hurdle without assuming the effect is real. Let p0 and p1 be control and treatment purchase probabilities, q0 and q1 the corresponding probabilities of redeeming the tested reward, c the assumed contribution per purchaser over the full window before that reward, d its cost per redemption, e incremental contact/operations cost per treated person over current practice, F incremental fixed cost and N the number treated:

```text
conditional net contribution = N × [(p1 − p0)c − (q1 − q0)d − e] − F
break-even purchase-rate difference = [(q1 − q0)d + e + F/N] / c
```

The break-even expression requires c > 0 and is conditional on the entered redemption response. q0 and q1 use all assigned people as their denominators, not only purchasers or redeemers. The model assumes one tested reward can be redeemed at most once per person, a common contribution per purchaser and a common reward cost across the arms. If the intervention changes basket value, frequency or the mix of reward costs, use person-level realised contribution for the primary result. These are planning assumptions, not separately observed individual counterfactuals.

The model values purchases before the tested reward and subtracts its incremental redemption cost once. Do not apply that subtraction to sales already net of the same reward. Equal-slot contact can have zero incremental delivery cost, while preparation and additional handling can still have a cost. Unverified costs are not established as zero.

Show an adverse case, a zero-purchasing-response case and an assumed beneficial case. With zero purchasing response, extra subsidy/contact and fixed costs can still produce a loss. Material unpriced costs remain explicitly excluded; they do not become zero.

Before launch, set the minimum worthwhile contribution, maximum acceptable loss, enrollment limit, follow-up, refund lag and uncertainty-based decision rule. Operational monitoring should not become repeated significance testing. A positive point estimate or nonsignificant result alone does not justify rollout.

This trial concerns the tested earned-reward reminder, population and horizon. It does not establish a new-member reward ladder, VIP benefits, checkout redesign or a repeated annual effect. See [experiment protocols](experiment_protocols.md) for shared assignment and accounting principles.

## Publication

Keep rosters, assignments, company-supplied financial inputs, derived results and executed outputs outside Git. Commit methods, code and explicitly synthetic fixtures. The private report should record the dataset, source cutoff, protocol, cost boundary, eligible export date and result provenance.
