-- Does counting purchases before first delivery change the repeat-rate gap?
WITH outcomes AS (
    SELECT
        f.customer_unique_id,
        f.first_is_late,
        f.repeat_90d,
        BOOL_OR(o.order_id IS NOT NULL) AS any_repeat
    FROM marts.repeat_delivery AS f LEFT JOIN marts.fct_orders AS o
        ON
            f.customer_unique_id = o.customer_unique_id AND f.first_order_id <> o.order_id
            AND o.order_status = 'delivered' AND f.first_purchase_at < o.purchased_at
            AND o.purchased_at <= f.first_delivered_at + INTERVAL '90 days'
    GROUP BY f.customer_unique_id, f.first_is_late, f.repeat_90d
)

SELECT
    first_is_late,
    COUNT(*) AS customers,
    AVG(repeat_90d::INT) AS after_delivery_rate,
    AVG(any_repeat::INT) AS after_purchase_rate
FROM outcomes
GROUP BY first_is_late;
