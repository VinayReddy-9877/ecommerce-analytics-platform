select 'delivered_without_timestamp' as issue,count(*) from marts.fct_orders
where order_status='delivered' and delivered_at is null
union all
select 'delivery_before_purchase',count(*) from marts.fct_orders where delivered_at<purchased_at
union all
select 'multiple_reviews_per_order',count(*) from
(select order_id from staging.stg_order_reviews group by 1 having count(*)>1) r
union all
select 'missing_product_category',count(*) from staging.stg_products where category is null;
