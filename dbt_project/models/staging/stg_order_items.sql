select order_id, order_item_id::int as item_number, product_id, seller_id, price::numeric(14,2) as price, freight_value::numeric(14,2) as freight, shipping_limit_date::timestamp as shipping_limit_at
from {{ source('raw', 'order_items') }}
