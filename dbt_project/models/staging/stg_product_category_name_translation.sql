select product_category_name as category, product_category_name_english as category_english
from {{ source('raw', 'product_category_name_translation') }}
