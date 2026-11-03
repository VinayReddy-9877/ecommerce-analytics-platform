-- Which sellers contribute the most merchandise value?
WITH ranked AS (
    SELECT
        seller_id,
        gmv,
        RANK() OVER (
            ORDER BY gmv DESC
        ) AS sales_rank,
        SUM(gmv)
            OVER (
                ORDER BY gmv DESC, seller_id ASC ROWS UNBOUNDED PRECEDING
            )
        / SUM(gmv) OVER () AS cumulative_share
    FROM marts.seller_scorecard
)

SELECT * FROM ranked
ORDER BY sales_rank, seller_id;
