-- Card-trip tip as a % of the pre-tip total, in 1-point bins from 0 to 40.
SELECT round(100.0 * tip_amount / pre_tip_amount) AS tip_pct, count(*) AS trips
FROM card_trips
WHERE pre_tip_amount > 0
GROUP BY 1
HAVING tip_pct BETWEEN 0 AND 40
ORDER BY 1;
