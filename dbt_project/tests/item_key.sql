select order_id,item_number from {{ ref('stg_order_items') }} group by 1,2 having count(*)>1
