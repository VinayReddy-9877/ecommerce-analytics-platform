select geolocation_zip_code_prefix as zip_prefix, avg(geolocation_lat::numeric) as latitude, avg(geolocation_lng::numeric) as longitude
from {{ source('raw', 'geolocation') }}
group by 1
