# Delivery investigation methods

The delivered-order purchase cohort ends on the cutoff in reports/analysis.json. Final source statuses are retrospective. `olist deepdive` reads the same raw files plus validated exports; do not alter raw files between the pipeline and diagnostics.

## Handling versus transit

One row per delivered order. Items are aggregated before joining. Handoff analysis requires one seller, an item deadline, nonnegative approval-to-carrier handling time, and nonnegative carrier-to-customer transit time. Multi-seller orders are excluded because a shared carrier timestamp cannot identify which seller handed off when. Both earliest and latest item deadlines are exported as a sensitivity check.

Handoff after the deadline is an operational proxy. Timely handoff followed by late delivery could reflect transit, recording issues, customer availability, route/service selection or inaccurate promises. Do not label the carrier at fault.

## Geography and models

Filter coordinates to latitude -34..6 and longitude -74..-34. Use median latitude/longitude for each ZIP prefix; calculate haversine distance with Earth radius 6371.0088 km. Single-seller orders only. Missing locations remain missing.

Compare transit days and the calendar-date late flag against log(1+distance). Then add customer state and purchase month fixed effects. OLS uses HC3 robust intervals; the late model is a descriptive linear probability model, not a calibrated classifier. R squared is in-sample variance accounted for, not causality or out-of-sample accuracy. Seller, carrier, category and service-level confounding remain.

`state_diagnostics.csv` also reports median promised days and actual-delivery slack. This allows a comparison of promise padding by state without pretending similar distances imply identical service.

## RJ scenario

Multiply RJ known-delivery count by SP observed late rate, then subtract from RJ observed late count. Missing delivery dates are excluded from both rates. The review scenario transfers zero to the full observed late/on-time review gap to the changed share of orders. It is not a confidence interval, forecast, ROI estimate or measured improvement.

Do not multiply avoided orders by a customer repeat-rate gap: the populations and units differ. Retention comparisons use first-delivery customers with a complete 90-day follow-up window.

## Retention sensitivity

Keep exactly the same eligible customer cohort as marts.repeat_delivery. Primary outcome: subsequent delivered orders purchased after first delivery and within 90 days. Sensitivity: subsequent delivered orders purchased after first purchase through first delivery + 90 days. This includes purchases before a customer could experience the first delivery and gives a longer exposure window to slower deliveries. It is a diagnostic definition, not a causal retention claim.

Lead with the full-cohort rates, not the adjusted odds ratio from sparse overlapping strata. An experiment is needed to estimate intervention effects.

## Commercial analysis

Seller concentration sums line-item merchandise value for delivered orders. Installment analysis aggregates payments to maximum installments per order before joining; it does not multiply the order value across payment methods. Maximum installments is a mixed-payment proxy, not a financing contract. GMV excludes freight and is not Olist revenue.

## Comparison updates

reports/findings.json contains handoff base rates, independent-proportion normal
intervals for retention differences, and an RJ distance-band scenario. Reference
bands use non-RJ eligible single-seller orders and RJ weights, excluding unknown
distance. The 827-order difference is descriptive. Different reference populations
produce different scenarios; the SP comparison is not an upper bound.
