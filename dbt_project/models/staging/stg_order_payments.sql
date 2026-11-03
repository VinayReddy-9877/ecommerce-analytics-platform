select order_id, payment_sequential::int as payment_number, payment_type, payment_installments::int as installments, payment_value::numeric(14,2) as payment_value
from {{ source('raw', 'order_payments') }}
