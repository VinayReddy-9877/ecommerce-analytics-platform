-- How often do buyers return in observed cohort months?
SELECT
    cohort,
    month_number,
    cohort_size,
    active_customers,
    retention
FROM marts.cohort_retention
WHERE month_number BETWEEN 1 AND 3
ORDER BY cohort, month_number;
