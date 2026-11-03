with months as (
    select date_trunc('month',day)::date as month, sum(orders) as orders, sum(gmv) as gmv
    from {{ ref('daily_sales') }} group by 1
), compared as (
    select *, lag(gmv) over(order by month) as previous_gmv,
           sum(gmv) over(order by month) as cumulative_gmv from months
)
select *, (gmv/ nullif(previous_gmv,0)-1)*100 as mom_pct,
       gmv/nullif(orders,0) as aov from compared
