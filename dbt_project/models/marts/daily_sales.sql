with calendar as (
    select generate_series(min(purchased_at)::date, '{{ var("cutoff") }}'::date, interval '1 day')::date as day
    from {{ ref('fct_orders') }}
), daily as (
    select purchased_at::date as day, count(*) as orders,
           sum(merchandise_value) as gmv, sum(freight_value) as freight
    from {{ ref('fct_orders') }} where order_status='delivered' group by 1
)
select c.day, coalesce(d.orders,0) as orders, coalesce(d.gmv,0) as gmv,
       coalesce(d.freight,0) as freight, d.gmv/nullif(d.orders,0) as aov
from calendar c left join daily d using(day)
