select order_id from {{ ref('fct_orders') }} where merchandise_value<0 or freight_value<0 or review_score not between 1 and 5
