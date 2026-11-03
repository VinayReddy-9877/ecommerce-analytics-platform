with weekly as (
    select
        date_trunc('week', delivered_at)::date as week,
        count(*) as delivered_orders,
        count(is_late) as assessed_orders,
        count(*) filter (where is_late = true) as late_orders,
        avg(is_late::int) as late_rate,
        count(review_score) as reviewed_orders,
        round(avg(review_score)::numeric, 2) as avg_review_score
    from {{ ref('fct_orders') }}
    where order_status = 'delivered'
      and delivered_at is not null
      and delivered_at::date <= '{{ var("reporting_end", "2018-07-31") }}'::date
    group by 1
)

select
    *,
    week + 7 <= '{{ var("reporting_end", "2018-07-31") }}'::date + 1
        as is_complete_week
from weekly