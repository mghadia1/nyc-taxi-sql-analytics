-- How many card tips are exactly one of the tablet's preset percentages?
-- A tip "matches" p when it is within one cent of p x the pre-tip total
-- (fare, surcharges, taxes and tolls). The base was chosen by trying the
-- candidate bases and keeping the one that explains the most tips exactly; see
-- docs/results.md.
WITH tipped AS (
    SELECT tip_amount, pre_tip_amount FROM card_trips WHERE tip_amount > 0
),
labelled AS (
    SELECT
        CASE
            WHEN abs(tip_amount - round(0.20 * pre_tip_amount, 2)) <= 0.01 THEN '20%'
            WHEN abs(tip_amount - round(0.25 * pre_tip_amount, 2)) <= 0.01 THEN '25%'
            WHEN abs(tip_amount - round(0.30 * pre_tip_amount, 2)) <= 0.01 THEN '30%'
            ELSE 'other amount'
        END AS tip_kind
    FROM tipped
)
SELECT
    tip_kind,
    count(*)                                            AS trips,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2)  AS pct_of_tipped_card_trips
FROM labelled
GROUP BY tip_kind
ORDER BY tip_kind;
