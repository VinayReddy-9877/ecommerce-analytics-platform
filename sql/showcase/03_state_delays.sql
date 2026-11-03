-- Which states combine high late-delivery rate with meaningful volume?
SELECT
    customer_state,
    COUNT(*) AS delivered_orders,
    COUNT(is_late) AS known_deliveries,
    COUNT(*) FILTER (WHERE is_late) AS late_orders,
    AVG(is_late::int) AS late_rate
FROM marts.fct_orders
WHERE order_status = 'delivered'
GROUP BY customer_state
HAVING COUNT(is_late) >= 100
ORDER BY late_rate DESC;
