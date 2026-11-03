-- How did monthly delivered GMV change before the uncertain August tail?
SELECT
    month,
    gmv,
    LAG(gmv) OVER (
        ORDER BY month
    ) AS prior_gmv,
    SUM(gmv) OVER (
        ORDER BY month ROWS UNBOUNDED PRECEDING
    ) AS running_gmv
FROM marts.monthly_sales
WHERE month < DATE '2018-08-01'
ORDER BY month;
