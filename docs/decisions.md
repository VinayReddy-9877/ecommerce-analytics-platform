# Design decisions

## Aggregate children before joining
An order with two items, two payments and two reviews can produce eight rows in
a naive join. `int_order_totals` aggregates items/payments independently and picks
one review. Reconciliation tests compare the fact and seller/daily totals with
underlying item values.

## Transactional full refresh
This dataset fits comfortably in PostgreSQL. Full snapshot loads are easier to
verify at this scale than incremental change capture. A single transaction protects all nine
raw tables; reruns DELETE then INSERT to preserve dependent view identities.
An advisory transaction lock serializes ingestion. A failed import rolls back.
COPY streams adapted text rows over the SQLAlchemy-owned psycopg connection.
The same transaction covers every raw table. For larger sources, use chunked
parsing, staged schema promotion and source watermarks. Ingestion replaces the snapshot; it is not incremental.

## Keep the forecasting baseline
Training begins in January 2017 to exclude the sparse launch-period months.
The model competes against a last-month baseline on rolling three-month holdouts.
The lowest mean absolute error wins. There is insufficient history for a strong
annual seasonal claim. Bands reflect empirical validation errors; they are not
calibrated prediction intervals. Prediction performance on this static dataset
is not evidence of performance on today's Olist business.

## Review scores are not an experiment
Welch's test compares mean scores; it does not control for product mix, geography,
customer expectations or selection into leaving reviews. Scores are ordinal.
Large samples can make small differences statistically significant. Report the
point difference and interval alongside the sample sizes; run an intervention
with a control group before promising a ratings improvement.

## Anomalies use prior data only
Each day is compared with the same weekday over eight prior weeks. Six earlier
weekday observations are required. Zero-variance baselines are left unscored.
A three-standard-deviation threshold is a triage heuristic, with no multiple-test
correction or calibrated false-positive rate. Promotions and holidays need
business context. Early missing dates are filled with zero under the assumption
that this snapshot is complete, which cannot be proven from CSVs alone.

## Reproducibility over simulated business operations
GitHub Actions rebuilds an ephemeral database, exports results, and retains the
artifacts. It does not operate a persistent warehouse or automatically refresh a
Power BI tenant. Streamlit reads the latest local exports, cached for 60 seconds.
API and outbound email operations are opt-in and require the owner's credentials.

The anomaly floor is BRL 1,000 in the trailing same-weekday mean; it is a
triage threshold, not a calibrated statistical significance boundary.
