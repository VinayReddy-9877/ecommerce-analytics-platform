-- One first-observed customer order, with a full 90-day post-delivery window.
-- Final delivery statuses are retrospective, not reconstructed event-time states.
with ranked as (
    select *,row_number() over(partition by customer_unique_id order by purchased_at,order_id) as purchase_rank
    from {{ ref('fct_orders') }}
), eligible as (
    select * from ranked
    where purchase_rank=1 and order_status='delivered'
      and purchased_at >= '2017-01-01'::date
      and delivered_at >= purchased_at and is_late is not null
      and delivered_at + interval '90 days' < '{{ var("reporting_end") }}'::date + interval '1 day'
), outcomes as (
    select f.customer_unique_id,f.order_id as first_order_id,f.purchased_at as first_purchase_at,
           f.delivered_at as first_delivered_at,f.customer_state,
           date_trunc('month',f.purchased_at)::date as first_purchase_month,
           f.is_late as first_is_late,f.merchandise_value as first_gmv,
           count(o.order_id) filter(where o.purchased_at<=f.delivered_at+interval '30 days') as orders_30d,
           count(o.order_id) filter(where o.purchased_at<=f.delivered_at+interval '60 days') as orders_60d,
           count(o.order_id) as orders_90d,coalesce(sum(o.merchandise_value),0) as followup_gmv_90d
    from eligible f left join {{ ref('fct_orders') }} o
      on f.customer_unique_id=o.customer_unique_id and o.order_id<>f.order_id
      and o.order_status='delivered' and o.purchased_at>f.delivered_at
      and o.purchased_at<=f.delivered_at+interval '90 days'
    group by 1,2,3,4,5,6,7,8
)
select *,orders_30d>0 as repeat_30d,orders_60d>0 as repeat_60d,orders_90d>0 as repeat_90d,
       case when first_gmv<50 then 'Under 50' when first_gmv<100 then '50 to 99'
            when first_gmv<200 then '100 to 199' else '200 or more' end as basket_band
from outcomes
