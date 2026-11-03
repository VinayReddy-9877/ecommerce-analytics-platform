-- Does the order-level total reconcile to delivered line items without fanout?
WITH lines AS (
    SELECT SUM(i.price) AS line_gmv FROM staging.stg_order_items AS i
    INNER JOIN marts.fct_orders AS o ON i.order_id = o.order_id
    WHERE o.order_status = 'delivered'
),

orders AS (
    SELECT SUM(merchandise_value) AS order_gmv
    FROM marts.fct_orders
    WHERE order_status = 'delivered'
)

SELECT
    lines.line_gmv,
    orders.order_gmv,
    lines.line_gmv - orders.order_gmv AS difference
FROM lines CROSS JOIN orders;
