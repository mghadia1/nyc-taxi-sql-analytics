SELECT
    quality_rule                                             AS rule,
    count(*)                                                 AS trips,
    round(100.0 * count(*) / sum(count(*)) OVER (), 3)       AS pct_of_trips,
    round(sum(total_amount), 2)                              AS total_amount
FROM trips
GROUP BY quality_rule
ORDER BY quality_rule;
