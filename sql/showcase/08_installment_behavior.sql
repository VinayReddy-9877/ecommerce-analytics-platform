-- How does merchandise AOV differ by maximum installment count per order?
WITH payment AS (
    SELECT
        order_id,
        MAX(payment_installments::int) AS installments
    FROM raw.order_payments
    GROUP BY order_id
)

SELECT
    p.installments,
    COUNT(*) AS orders,
    AVG(o.merchandise_value) AS merchandise_aov
FROM marts.fct_orders AS o INNER JOIN payment AS p ON o.order_id = p.order_id
WHERE o.order_status = 'delivered'
GROUP BY p.installments
ORDER BY p.installments;
