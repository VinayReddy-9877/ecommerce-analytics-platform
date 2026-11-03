with sales as (
    select date_trunc('month',o.purchased_at)::date as month,
           coalesce(t.category_english,p.category,'unknown') as category, sum(i.price) as gmv
    from {{ ref('stg_order_items') }} i join {{ ref('fct_orders') }} o using(order_id)
    left join {{ ref('stg_products') }} p using(product_id)
    left join {{ ref('stg_product_category_name_translation') }} t using(category)
    where o.order_status='delivered' group by 1,2
), grid as (
    select distinct m.month,c.category from {{ ref('monthly_sales') }} m cross join (select distinct category from sales) c
), filled as (
    select g.*,coalesce(s.gmv,0) as gmv from grid g left join sales s using(month,category)
), compared as (
    select *,lag(gmv) over(partition by category order by month) as previous_gmv from filled
)
select *,gmv-previous_gmv as change_brl,100*(gmv/nullif(previous_gmv,0)-1) as mom_pct from compared
