select review_id, order_id, review_score::int as score, review_answer_timestamp::timestamp as answered_at
from {{ source('raw', 'order_reviews') }}
