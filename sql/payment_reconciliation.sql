-- Payment differences are diagnostics, not a reason to rewrite source amounts.
select order_id,order_status,merchandise_value,freight_value,payment_value,
       payment_value-merchandise_value-freight_value as difference
from marts.fct_orders
where abs(payment_value-merchandise_value-freight_value)>0.05
order by abs(payment_value-merchandise_value-freight_value) desc;
