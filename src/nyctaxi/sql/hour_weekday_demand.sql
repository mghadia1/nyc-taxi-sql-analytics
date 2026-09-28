-- Average trips per hour slot: count divided by how many of that weekday the window holds.
WITH days AS (
    SELECT pickup_isodow, count(DISTINCT pickup_date) AS n_days FROM clean_trips GROUP BY 1
)
SELECT
    c.pickup_isodow,
    c.pickup_hour,
    round(count(*) / any_value(d.n_days), 1) AS avg_trips
FROM clean_trips AS c
JOIN days AS d USING (pickup_isodow)
GROUP BY c.pickup_isodow, c.pickup_hour
ORDER BY c.pickup_isodow, c.pickup_hour;
