-- How many customers account for 80% of delivered merchandise value?
with ranked as (
    select customer_unique_id, monetary_value,
           row_number() over(order by monetary_value desc,customer_unique_id) as position,
           sum(monetary_value) over(order by monetary_value desc,customer_unique_id rows unbounded preceding)
             /sum(monetary_value) over() as cumulative_share
    from marts.customer_rfm
)
select min(position) as customers_needed from ranked where cumulative_share>=0.8;
