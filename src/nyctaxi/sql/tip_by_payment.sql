-- The cash-tip trap: the same "average tip %" computed over all trips and over
-- card trips only.
SELECT
    CASE payment_type WHEN 1 THEN 'card' WHEN 2 THEN 'cash'
                      WHEN 3 THEN 'no charge' WHEN 4 THEN 'dispute' ELSE 'other' END AS payment,
    count(*)                                                   AS trips,
    round(100.0 * avg(tip_amount / nullif(pre_tip_amount, 0)), 2)         AS mean_tip_pct,
    round(100.0 * avg((tip_amount > 0)::INTEGER), 2)           AS pct_with_tip
FROM clean_trips
GROUP BY ALL
UNION ALL
SELECT 'ALL (naive)', count(*), round(100.0 * avg(tip_amount / nullif(pre_tip_amount, 0)), 2),
       round(100.0 * avg((tip_amount > 0)::INTEGER), 2)
FROM clean_trips
ORDER BY trips DESC;
