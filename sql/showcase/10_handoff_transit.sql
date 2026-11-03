-- Among eligible late single-seller orders, was handoff after the shipping deadline?
WITH deadlines AS (
    SELECT
        order_id,
        COUNT(DISTINCT seller_id) AS sellers,
        MIN(shipping_limit_date::timestamp) AS earliest_limit,
        MAX(shipping_limit_date::timestamp) AS latest_limit
    FROM raw.order_items
    GROUP BY order_id
),

eligible AS (
    SELECT
        o.*,
        d.earliest_limit,
        d.latest_limit
    FROM marts.fct_orders AS o
    INNER JOIN deadlines AS d ON o.order_id = d.order_id
    WHERE
        o.order_status = 'delivered' AND d.sellers = 1
        AND o.carrier_at >= o.approved_at AND o.delivered_at >= o.carrier_at
)

SELECT
    carrier_at > earliest_limit AS late_handoff,
    COUNT(*) AS late_orders,
    AVG(EXTRACT(EPOCH FROM (delivered_at - carrier_at)) / 86400) AS mean_transit_days
FROM eligible
WHERE is_late
GROUP BY late_handoff
ORDER BY late_handoff;
