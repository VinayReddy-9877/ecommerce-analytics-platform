{{ config(indexes=[{'columns': ['customer_unique_id', 'purchased_at']}]) }}
-- Purchase-cohort snapshot, not a reconstruction of status as known on that date.
select * from {{ ref('int_order_totals') }}
where purchased_at < '{{ var("cutoff") }}'::date + interval '1 day'
