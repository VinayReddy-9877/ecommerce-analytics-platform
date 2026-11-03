with activity as (
    select distinct customer_unique_id, date_trunc('month',purchased_at)::date as month
    from {{ ref('fct_orders') }} where order_status='delivered'
), membership as (
    select customer_unique_id, min(month) as cohort from activity group by 1
), sizes as (
    select cohort,count(*) as cohort_size from membership group by 1
), observed as (
    select m.cohort, a.month, count(*) as active_customers
    from membership m join activity a using(customer_unique_id) group by 1,2
), grid as (
    select s.*, generate_series(cohort,date_trunc('month','{{ var("cutoff") }}'::date),interval '1 month')::date as month
    from sizes s
)
select g.*, (extract(year from age(g.month,g.cohort))*12+extract(month from age(g.month,g.cohort)))::int as month_number,
       coalesce(o.active_customers,0) as active_customers,
       coalesce(o.active_customers,0)::numeric/g.cohort_size as retention
from grid g left join observed o using(cohort,month)
