SELECT pickup_date, pickup_isodow, count(*) AS trips, round(sum(total_amount), 2) AS revenue
FROM clean_trips
GROUP BY ALL
ORDER BY pickup_date;
