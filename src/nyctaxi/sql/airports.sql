-- Trips touching an airport zone (JFK 132, LaGuardia 138, Newark 1) at either end.
WITH tagged AS (
    SELECT
        *,
        CASE
            WHEN 132 IN (PULocationID, DOLocationID) THEN 'JFK'
            WHEN 138 IN (PULocationID, DOLocationID) THEN 'LaGuardia'
            WHEN 1   IN (PULocationID, DOLocationID) THEN 'Newark'
            ELSE 'non-airport'
        END AS airport
    FROM clean_trips
)
SELECT
    airport,
    count(*)                                                     AS trips,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2)           AS pct_of_trips,
    round(100.0 * sum(total_amount) / sum(sum(total_amount)) OVER (), 2) AS pct_of_revenue,
    round(avg(total_amount), 2)                                  AS mean_total,
    round(quantile_cont(duration_min, 0.5), 1)                   AS median_minutes,
    round(100.0 * avg(tip_amount / nullif(pre_tip_amount, 0)) FILTER (WHERE payment_type = 1), 2) AS card_mean_tip_pct
FROM tagged
GROUP BY airport
ORDER BY trips DESC;
