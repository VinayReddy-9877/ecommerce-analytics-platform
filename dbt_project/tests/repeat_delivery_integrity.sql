select customer_unique_id from {{ ref('repeat_delivery') }}
where orders_30d>orders_60d or orders_60d>orders_90d or followup_gmv_90d<0
   or first_delivered_at+interval '90 days'>='{{ var("reporting_end") }}'::date+interval '1 day'
union all
select customer_unique_id from {{ ref('repeat_delivery') }} group by 1 having count(*)<>1
