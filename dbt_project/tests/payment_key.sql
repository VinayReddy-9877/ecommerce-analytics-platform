select order_id,payment_number from {{ ref('stg_order_payments') }} group by 1,2 having count(*)>1
