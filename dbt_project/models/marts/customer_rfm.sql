with customers as (
    select customer_unique_id, '{{ var("cutoff") }}'::date-max(purchased_at)::date as recency_days,
           count(*) as frequency, sum(merchandise_value) as monetary_value
    from {{ ref('fct_orders') }} where order_status='delivered' group by 1
)
select *, case when frequency>=2 and recency_days<=90 then 'Repeat active'
               when frequency>=2 then 'Repeat dormant'
               when recency_days<=90 then 'New / recent'
               else 'One-time dormant' end as segment,
       cume_dist() over(order by monetary_value) as monetary_percentile
from customers
