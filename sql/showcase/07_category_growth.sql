-- Which categories grew or declined in the last comparable month?
SELECT
    category,
    gmv,
    previous_gmv,
    change_brl,
    mom_pct
FROM marts.category_growth
WHERE month = DATE '2018-07-01'
ORDER BY change_brl DESC;
