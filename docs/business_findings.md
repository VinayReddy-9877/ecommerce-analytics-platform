# Business findings and proposed actions

These are findings from a historical snapshot, not measured results of a business
intervention. Monetary values are merchandise GMV, excluding freight.

## Investigate delivery delays in Rio de Janeiro

RJ has 1,495 late orders among 12,350 delivered orders with known dates: **12.11%**.
SP has more late orders in absolute terms, **1,820**, but its rate is **4.49%**
among 40,494 known deliveries. Prioritize RJ for a rate-and-volume investigation, while
keeping SP in the operational queue because of its larger absolute burden.

Break RJ delays down by seller, product mix, route and promised delivery window.
The dataset alone cannot identify which carrier or process caused a delay.
Choose a route-level pilot only after validating those operational details.
Measure late-delivery rate, delivery time and review scores against a comparable
control. Do not label the observed difference as an achievable improvement.

## Test retention after the first delivery

90-day repeat purchase is **0.77% after a late delivery** versus **1.15% after an
on-time delivery**. Equal follow-up covers 66,211 customers: 37 repeat buyers
among 4,835 late customers and 704 among 61,376 on-time customers.

Counting any repeat purchase from first purchase through first delivery + 90 days
changes the rates to **2.03% late** and **2.17% on time**. That broader outcome has
a longer exposure window. The smaller difference is a reason to report both
definitions and avoid causal claims. Stratified estimates are secondary because
only a subset of customers has comparable observations in both delivery groups.

Use this as a hypothesis for a randomized post-delivery recovery campaign.
Track 90-day repeat purchase and contribution margin after discounts, with a
holdout. Historical follow-up GMV per eligible customer is BRL 1.08 after late
delivery and BRL 1.47 after on-time delivery; it is not recoverable revenue.

## Avoid reacting to an incomplete reporting tail

Sparse orders near the end of the snapshot can distort weekly comparisons.
The conservative reporting policy holds out August from comparisons while
preserving it in full-period totals. The last eligible full week begins
23 July 2018: **BRL 236,498.42 GMV**, **1,610 orders**, **+8.8% week over week**.

A production implementation should obtain source completeness and freshness
signals before releasing weekly comparisons. The July policy is an explicit
historical-analysis choice, not evidence that every July order was observable
at the time.

Source exports: `delivery_performance.csv`, `repeat_delivery_summary.csv`,
`retention_analysis.json`, `weekly_kpis.csv` and `analysis.json` in `reports/`.
