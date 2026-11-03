Checks 48/48 passed | Rows 1,550,922 | Runtime 465.1s | Run 20261102T080756-3d0e7d66

# Olist weekly operating review

Historical replay. Purchase cutoff: 2018-08-31. Order statuses reflect the source's final snapshot.

Comparisons stop at 2018-07-31. August is retained in descriptive totals but excluded from weekly comparisons and forecasts because tail coverage is uncertain.

## Last eligible complete week: 2018-07-23

- Delivered-order merchandise GMV: BRL 236,498.42.
- Orders: 1,610; AOV: BRL 146.89.
- GMV versus preceding complete week: +8.8%.

## Findings across the analysis window

- 533 of 2,970 sellers account for 80% of delivered merchandise GMV.
- Repeat-customer share is 3.00%. Repeat means at least two delivered orders in the observed purchase window.
- Late orders have a mean review score of 2.27, compared with 4.29 for on-time orders. Difference: -2.02 points; 95% Welch interval [-2.06, -1.98]. This does not establish causation.

## Actions to investigate

1. Review late-delivery volume by state and seller before selecting an operational intervention. Track both delay rate and sample size.
2. Test a second-purchase campaign with a randomized holdout. The observed repeat rate alone cannot predict campaign lift.

The three-month forecast and rolling-origin errors are in `analysis.json`. Anomaly flags are investigation prompts, not proof of a business incident. No manual time-saving claim has been measured.

## Repeat purchases after the first delivery

- On time: 704/61,376 customers repeated within 90 days (1.15%); subsequent merchandise GMV per eligible customer: BRL 1.47.
- Late: 37/4,835 customers repeated within 90 days (0.77%); subsequent merchandise GMV per eligible customer: BRL 1.08.

Adjusted late/on-time odds ratio: 0.43, 95% interval [0.23, 0.79], across 42 comparable strata (16,042 customers).

Association, not causal lift. Equal 90-day follow-up begins at first delivery. Excludes earlier repeat purchases and customers whose first observed order was not delivered. Adjustment covers only observed strata and may not generalize outside overlap.

## Handoff: rates and denominators

| handoff   |   orders |   late_orders | late_rate   | order_share   | late_order_share   |
|:----------|---------:|--------------:|:------------|:--------------|:-------------------|
| Timely    |    85212 |          4684 | 5.50%       | 90.79%        | 72.11%             |
| Late      |     8647 |          1812 | 20.96%      | 9.21%         | 27.89%             |

Late-handoff orders have 3.81 times the observed late-delivery rate. Applying the timely-handoff rate gives a scenario of 1,337 fewer late orders; these are not proven avoidable orders.

RJ distance-band comparison: 1,481 observed late orders among 12,005 eligible orders versus 654 expected at the non-RJ band rates. Scenario difference: 827. The separate SP-rate scenario is 940; it is not an upper bound.

## Retention: full cohort and sensitivity

- After first delivery: late minus on-time -0.38 pp, 95% interval [-0.64, -0.12] pp. Late repeat buyers: 37/4835; on time: 704/61376.
- After first purchase through delivery + 90 days: late minus on-time -0.14 pp, 95% interval [-0.55, +0.28] pp. Late repeat buyers: 98/4835; on time: 1329/61376.

Intervals use independent-proportion normal approximations. Broader exposure is longer, and neither estimate establishes causation.

Retention counts (same eligible cohort):

| definition                                      | experience   |   customers |   repeat_customers |   repeat_rate |
|:------------------------------------------------|:-------------|------------:|-------------------:|--------------:|
| After first delivery                            | On time      |       61376 |                704 |    0.0114703  |
| After first delivery                            | Late         |        4835 |                 37 |    0.00765253 |
| After first purchase through delivery + 90 days | On time      |       61376 |               1329 |    0.0216534  |
| After first purchase through delivery + 90 days | Late         |        4835 |                 98 |    0.0202689  |
