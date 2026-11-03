select customer_state, count(*) as delivered_orders,
       count(*) filter(where is_late is not null) as delivery_denominator,
       avg(is_late::int) as late_rate, avg(delivery_days) as mean_delivery_days,
       avg(review_score) filter(where is_late) as late_review_score,
       avg(review_score) filter(where not is_late) as on_time_review_score
from {{ ref('fct_orders') }} where order_status='delivered' group by 1
