select date_trunc('week',day)::date as week, sum(orders) as orders, sum(gmv) as gmv,
       sum(gmv)/nullif(sum(orders),0) as aov, count(*)=7 as is_complete_week
from {{ ref('daily_sales') }} group by 1
