# Metric contract

Default purchase cutoff: 31 August 2018. Money is nominal BRL, without currency conversion or inflation adjustment.

| Metric | Definition | Important boundary |
|---|---|---|
| GMV | Sum of item `price` for orders whose final status is delivered | Excludes freight; not Olist net revenue or profit |
| Orders | Distinct delivered order IDs | Non-delivered orders remain in the order fact |
| AOV | GMV / delivered orders | Zero-order periods return null |
| Repeat rate | Customers with 2+ delivered orders / customers with 1+ | Uses customer_unique_id; observed-window rate |
| Late rate | Delivered date later than estimated date / delivered orders with both dates | Compares calendar dates, not midnight timestamps |
| Review score | Latest answered review per order | Deterministic tie break by review ID, then score |
| Cohort | Month of first observed delivered purchase | Earlier lifetime activity outside the dataset is unknown |
| Retention | Distinct cohort customers buying in month N / original cohort size | Missing observed months are zero; future months omitted |
| Seller GMV | Sum of item prices belonging to seller | Whole-order ratings cannot isolate a seller's contribution |
| RFM | Recency in days, delivered-order frequency, merchandise spend | Explicit business segments; no unstable frequency quintiles |

The dataset is a final historical snapshot. Filtering purchases by cutoff does
not recover statuses, reviews, or delivery information as known on that date.
Consequently this is a retrospective purchase-cohort analysis, not a valid
point-in-time predictive feature store. Late-2018 records are sparse; the default
cutoff avoids the September/October tail. August's final delivery outcomes can
still reflect information recorded after August.

Payments are aggregated separately. They include freight and may contain split
tenders. Differences between payments and item+freight totals are audited, not
silently corrected. Review text and customer location details are never sent to
the LLM. Only aggregate KPI and statistical outputs leave the machine when the
explicit `--llm` flag is used.

Geolocation contains multiple observations per ZIP prefix. Its staging model
averages coordinates to one row per prefix; these are approximate centroids, not
customer addresses. All nine CSVs are ingested. Geography is available for future
map analysis, while the dashboard uses state-level summaries.

Weekly comparison/anomaly/forecast eligibility ends on 2018-07-31 by default. August remains in descriptive totals. See retention_method.md for the equal-follow-up customer comparison.
