select * from {{ ref('cohort_retention') }} where retention not between 0 and 1 or (month_number=0 and retention<>1)
