with seller_orders as (
    select i.seller_id, o.order_id, sum(i.price) as gmv,
           max(o.review_score) as order_review_score, bool_or(o.is_late) as is_late
    from {{ ref('stg_order_items') }} i join {{ ref('fct_orders') }} o using(order_id)
    where o.order_status='delivered' group by 1,2
), sellers as (
    select seller_id,count(*) as orders,sum(gmv) as gmv,
           avg(order_review_score) as mean_order_review_score,avg(is_late::int) as late_rate
    from seller_orders group by 1
)
select s.*, d.state, rank() over(order by gmv desc) as gmv_rank
from sellers s join {{ ref('stg_sellers') }} d using(seller_id)
