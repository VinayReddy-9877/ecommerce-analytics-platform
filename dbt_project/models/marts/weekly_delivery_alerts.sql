with weekly as (
    select *
    from {{ ref('weekly_delivery_kpis') }}
    where is_complete_week = true
),

history as (
    select
        week,
        delivered_orders,
        assessed_orders,
        late_orders,
        late_rate,
        avg_review_score,

        count(*) over (
            order by week
            rows between 8 preceding and 1 preceding
        ) as baseline_weeks,

        min(assessed_orders) over (
            order by week
            rows between 8 preceding and 1 preceding
        ) as min_baseline_orders,

        lag(week, 8) over (
            order by week
        ) as oldest_baseline_week,

        avg(late_rate) over (
            order by week
            rows between 8 preceding and 1 preceding
        ) as baseline_mean,

        stddev_samp(late_rate) over (
            order by week
            rows between 8 preceding and 1 preceding
        ) as baseline_stddev,

        sum(late_orders) over (
            order by week
            rows between 4 preceding and 1 preceding
        ) as previous_late_orders,

        sum(assessed_orders) over (
            order by week
            rows between 4 preceding and 1 preceding
        ) as previous_assessed_orders

    from weekly
)

select
    week,
    delivered_orders,
    late_orders,
    round(late_rate * 100, 2) as late_rate_pct,
    avg_review_score,

    round(
        previous_late_orders * 100.0
        / nullif(previous_assessed_orders, 0),
        2
    ) as previous_4_week_late_rate_pct,

    round(
        (
            late_rate -
            previous_late_orders::numeric
            / nullif(previous_assessed_orders, 0)
        ) * 100,
        2
    ) as change_vs_previous_4w_pp,

    round(
        (baseline_mean + 2 * baseline_stddev) * 100,
        2
    ) as alert_threshold_pct,

    case
        when baseline_weeks = 8
         and week - oldest_baseline_week = 56
         and min_baseline_orders >= 200
         and assessed_orders >= 200
         and late_rate > baseline_mean + 2 * baseline_stddev
        then true
        else false
    end as late_rate_alert

from history