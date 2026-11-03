select order_id, customer_id, order_status, order_purchase_timestamp::timestamp as purchased_at, order_approved_at::timestamp as approved_at, order_delivered_carrier_date::timestamp as carrier_at, order_delivered_customer_date::timestamp as delivered_at, order_estimated_delivery_date::timestamp as estimated_at
from {{ source('raw', 'orders') }}
