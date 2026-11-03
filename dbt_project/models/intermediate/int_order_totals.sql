-- Each child relation is reduced to one row per order BEFORE joining.
with items as (
    select order_id, sum(price) as merchandise_value, sum(freight) as freight_value,
           count(*) as item_count, count(distinct seller_id) as seller_count
    from {{ ref('stg_order_items') }} group by 1
), payments as (
    select order_id, sum(payment_value) as payment_value
    from {{ ref('stg_order_payments') }} group by 1
), reviews as (
    select *, row_number() over (
        partition by order_id order by answered_at desc nulls last, review_id desc, score desc
    ) as position from {{ ref('stg_order_reviews') }}
)
select o.*, c.customer_unique_id, c.state as customer_state,
       coalesce(i.merchandise_value,0) as merchandise_value,
       coalesce(i.freight_value,0) as freight_value,
       coalesce(i.item_count,0) as item_count, coalesce(i.seller_count,0) as seller_count,
       p.payment_value, r.score as review_score,
       case when o.delivered_at is not null and o.estimated_at is not null
            then o.delivered_at::date > o.estimated_at::date end as is_late,
       extract(epoch from (o.delivered_at-o.purchased_at))/86400.0 as delivery_days
from {{ ref('stg_orders') }} o
join {{ ref('stg_customers') }} c using (customer_id)
left join items i using (order_id)
left join payments p using (order_id)
left join reviews r on o.order_id=r.order_id and r.position=1
