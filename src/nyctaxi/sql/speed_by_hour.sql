-- Median door-to-door speed for trips that start and end in Manhattan, by
-- hour, split weekday vs weekend. A congestion proxy, not a traffic sensor.
SELECT
    pickup_hour,
    pickup_isodow >= 6                              AS is_weekend,
    count(*)                                        AS trips,
    round(quantile_cont(mph, 0.5), 2)               AS median_mph,
    round(quantile_cont(duration_min, 0.5), 2)      AS median_minutes
FROM clean_trips
WHERE pickup_borough = 'Manhattan' AND dropoff_borough = 'Manhattan'
GROUP BY ALL
ORDER BY is_weekend, pickup_hour;
