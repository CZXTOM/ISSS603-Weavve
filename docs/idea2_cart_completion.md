# Idea 2: cart information and completion test

**Status: proposed; not launched.** Reconcile the approved shipping, delivery and return rules first. Then test a clearer cart summary at the same prices. The purpose is to estimate incremental contribution from the presentation change, not to assume a historical funnel gap can be recovered.

## Customer problem and scope

A shopper with items in the cart needs to understand the payable delivery cost or applicable rule, expected dispatch/delivery timing and relevant return conditions before continuing. Inconsistent policies or information that requires leaving the cart are plausible sources of uncertainty. Public copy alone cannot establish their conversion effect or prove that checkout is broken.

The proposed intervention is one concise cart-page summary: the approved delivery charge/rule, timing including any preorder qualifications, and a short current-returns summary linked to the full policy. Use existing theme capabilities if feasible. Do not assume a checkout plugin, unrestricted checkout customisation or a new paid application is available.

## Stage 1: reconcile the rules for every shopper

The policy owner must determine the authoritative fee, delivery/collection distinction, free-shipping thresholds, mixed-stock/preorder treatment, timing and current return conditions. Check the actual configured charges and relevant threshold boundaries.

Apply the approved, truthful rule consistently to the FAQ, shipping page, cart, checkout and support instructions. Both experimental arms must use the same approved charges and terms. Do not preserve an incorrect or misleading control to obtain an A/B comparison.

Record the correction and cost, but do not assign it a measured conversion benefit. A before/after change following a common correction is not the effect of the later randomised cart summary.

## Stage 2: freeze the measurable contrast

**Control:** the current cart after common policy corrections, with existing accurate policy information and normal checkout functionality.

**Treatment:** the same cart, prices, offers, stock and checkout path, with the concise approved cost/timing/returns summary placed at the cart decision point.

If an exact delivery quote depends on destination or basket state, show an accurate approved rule or use an existing reliable estimator. Do not promise an all-in total the system cannot calculate. The operator must verify mobile/desktop, in-stock/preorder and discount cases before live enrollment.

The treatment is the summary package. It does not identify separately the effect of each line of copy.

## Unit, eligibility and assignment

Randomise before the treatment can affect the visitor's cart experience. The preferred unit is the first eligible cart visitor under a persistent first-party assignment key. Use an authenticated person key where available under the declared identity rule; anonymous visitor identifiers are not assumed to be unique humans.

Eligibility requires reaching the cart with a purchasable basket and a supported experience. Freeze bot/staff/test exclusions, geography, stock cases and missing-consent/tracking treatment before assignment. Persist the same allocation across repeat sessions. Predefine how later login/identity merges and conflicting exposures are handled.

The primary analysis includes all assigned eligible cart visitors in their original arm. Do not restrict it to people who subsequently start checkout, click a policy link or purchase. Checkout initiation is downstream of the treatment and can be a secondary outcome, not an eligibility denominator.

Coordinate the registry with Idea 1. Exclude overlapping experimental contacts or define a valid joint design before launch; do not simply add two standalone scenario amounts for the same people and orders.

## Instrumentation prerequisite

Audit the event grain and identity before sizing the trial. A historical AddToCart total can be repeated additions by one shopper, a session measure or another event definition. Therefore orders divided by recorded cart additions is an event ratio until the source definition is verified; it is not automatically unique-visitor conversion.

Record, for both arms:

- Eligible first cart visitor and assignment timestamp before exposure.
- Assigned and displayed variant, identity key and repeat exposures.
- Cart state and the approved summary/configuration version.
- Checkout initiation, payment/error categories and completed orders.
- Purchase/refund linkage, geography/timezone and missing-data coverage.

Keep exact private identifiers and outcome records outside Git. Unknown outcome linkage is not a confirmed zero.

## Outcomes and duration

Proposed design: a 90-day enrollment pilot, a prespecified 30-day purchasing window per assigned cart visitor, and a separately fixed refund-reconciliation lag. The final result is available only after the last enrollee's full purchasing window and lag. These windows are operating choices to approve before launch, not empirically optimal intervals.

Primary endpoint: treatment minus control mean contribution per assigned eligible cart visitor. Include net sales after discounts/refunds and relevant product, fulfilment, payment, return, servicing and experiment costs. Avoid double deduction of discounts. Report incremental fixed costs separately.

Secondary outcomes: purchase rate, orders/net sales per assigned visitor, checkout initiation, payment failures and time to purchase. Guardrails: incorrect fee/ETA information, checkout errors, mobile usability, complaints, support workload and return rates.

Estimate uncertainty with an analysis appropriate to the actual assignment and repeat-visitor structure. A purchase-rate power calculation does not establish contribution precision. A small pilot may establish operational feasibility without resolving a small commercial uplift; say so explicitly.

## Conditional business value

Let E be the verified eligible cart-visitor volume over the stated planning window, f treatment exposure, delta the assumed extra orders per eligible unit, c contribution per incremental order and F the incremental fixed cost:

```text
conditional incremental contribution = E × f × delta × c − F
break-even delta = F / (E × f × c)
```

This is a planning model, not an effect estimate. If only historical cart-addition events A are available, use an explicit calibration s:

```text
E = A × s
```

s must capture the conversion to eligible unique exposures, exclusions and relevant coverage. Do not silently set it to one. The historical order value and margin used for c also need compatible geography, time and cost boundaries. An all-website order reference is only a proxy for a geographically restricted funnel.

Show zero/adverse and assumed beneficial cases, with the chosen cost cap and excluded costs visible. Keep the historical fixed-window full-volume case separate from the actual pilot's eligible units, allocation, exposure and later outcome maturity. No annual recurrence or immediate realised return follows from an eleven-month scenario.

Count common policy correction, theme work, QA, tracking, analysis and additional platform/support costs once. If existing capabilities do not support the design within its approved budget, obtain a revised cost case or defer the experiment.

## Workflow and decision

| Stage | Proposed responsible role | Required evidence |
|---|---|---|
| Authorise and reconcile the policy | Ecommerce operations with customer service | One current rule per delivery/basket case; configured charges and public copy agree |
| Implement the presentation | Store/theme operator | Feasible existing-theme summary at identical terms in both arms |
| Validate measurement and assignment | Analyst with store operator | Event-grain/identity audit, immutable allocation, test-account logs and missing-data rule |
| Observe purchase/payment outcomes | Ecommerce operations | Order linkage and error categories under the frozen protocol |
| Reconcile costs and refunds | Finance/operations | Actual variable/fixed costs, refund lag and private contribution calculation |
| Decide | Named business owner | Result and uncertainty against a predeclared commercial threshold, loss budget and guardrails |

Roles, access, exact costs and operating settings remain unassigned/unverified. Set the enrollment cap, minimum worthwhile contribution, maximum acceptable loss and stopping rules before launch. Operational safety monitoring must not become repeated efficacy significance testing.

Expand the same tested summary only when its evidence and economics justify it. A positive before/after trend or point estimate alone is insufficient. Keep broader checkout redesign, discount offers and new paid tooling outside the claim unless separately specified and costed.
