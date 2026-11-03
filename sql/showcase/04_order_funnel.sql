-- How many orders have evidence of each milestone in the final snapshot?
-- This is milestone coverage, not reconstructed status transitions.
SELECT
    COUNT(*) AS purchased,
    COUNT(approved_at) AS approved,
    COUNT(carrier_at) AS handed_to_carrier,
    COUNT(delivered_at) AS delivered_timestamp
FROM marts.fct_orders;
