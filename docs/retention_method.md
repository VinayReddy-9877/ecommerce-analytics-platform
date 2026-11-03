# Delivery experience and repeat purchasing

Question: does the first observed delivery experience correlate with a subsequent
purchase, when every customer gets the same follow-up window?

- Rank **all** observed purchases per customer by purchase timestamp and order ID.
- Retain customers whose first observed order was delivered, purchased on/after
  2017-01-01, has known estimated/actual delivery dates, and was delivered at or
  after purchase.
- Follow-up begins at actual delivery, when the experience has occurred.
- Require the entire 90-day window to end before 2018-08-01. Customers with less
  observation time are excluded, rather than treated as non-repeaters.
- Count a later delivered-order purchase only if its timestamp is strictly after
  first delivery and at most 90 days later. Orders placed before first delivery
  do not qualify. 30/60-day sensitivity rates use the same eligible 90-day cohort.
- The outcome uses final delivery statuses, so it is retrospective. The first
  observed order is not guaranteed to be the person's first lifetime purchase.

On-time: 704/61,376 = 1.15%, Wilson 95% interval 1.07%–1.23%.
Late: 37/4,835 = 0.77%, Wilson 95% interval 0.56%–1.05%.
Difference: -0.38 percentage points. These are customer rates, not repeat-order
shares. There are 793 repeat orders among 741 repeating customers.

A Mantel-Haenszel comparison uses first-purchase month x customer state x basket
band (under BRL 50, 50–99, 100–199, 200+). Require >=20 customers in each exposure
group per stratum, and outcome variation. The informative overlap is 42 strata /
16,042 customers. Odds ratio 0.43 (95% interval 0.23–0.79). This is an odds ratio,
not a risk ratio. Strata without outcome variation carry no information for this
estimate and are excluded from the reported informative overlap.

This is adjustment for measured covariates, not a controlled experiment. Product
mix, income, intent and other confounders remain. Selection into delivered first
orders and the shorter observation frame also limit generalization. Do not
translate the association into recovered customers or additional revenue.

Subsequent merchandise GMV per eligible customer is BRL 1.47 (on time) versus
BRL 1.08 (late). These low amounts include zero for non-repeaters and are descriptive,
not an estimate of money recoverable by eliminating delays.
