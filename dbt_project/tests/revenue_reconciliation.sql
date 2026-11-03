select 1 where abs((select sum(merchandise_value) from {{ ref('fct_orders') }} where order_status='delivered')-(select sum(gmv) from {{ ref('daily_sales') }}))>0.01
