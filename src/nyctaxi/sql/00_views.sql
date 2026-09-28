-- Inputs: raw_trips (the TLC yellow-taxi schema) and raw_zones (taxi_zone_lookup).
-- Every cleaning rule lives here, once, as the CASE in `trips.quality_rule`.

CREATE OR REPLACE VIEW zones AS
SELECT LocationID AS location_id, Borough AS borough, Zone AS zone, service_zone
FROM raw_zones;

CREATE OR REPLACE VIEW trips AS
WITH base AS (
    SELECT
        *,
        date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime) / 60.0 AS duration_min,
        total_amount - tip_amount                                               AS pre_tip_amount
    FROM raw_trips
)
SELECT
    *,
    trip_distance / nullif(duration_min / 60.0, 0)  AS mph,
    tpep_pickup_datetime::DATE                      AS pickup_date,
    hour(tpep_pickup_datetime)                      AS pickup_hour,
    isodow(tpep_pickup_datetime)                    AS pickup_isodow,   -- 1 = Monday
    -- Ordered: a trip is labelled with the FIRST rule it breaks.
    CASE
        WHEN tpep_pickup_datetime <  getvariable('window_start')
          OR tpep_pickup_datetime >= getvariable('window_end')   THEN '1 pickup outside Jan-Mar 2024'
        WHEN payment_type = 0                                    THEN '2 payment_type 0 (no rate code, passengers, surcharges)'
        WHEN fare_amount <= 0 OR total_amount <= 0               THEN '3 non-positive fare or total (voids, refunds, disputes)'
        WHEN duration_min <= 0 OR duration_min > 180             THEN '4 duration not in (0, 180] minutes'
        WHEN trip_distance <= 0 OR trip_distance > 100           THEN '5 distance not in (0, 100] miles'
        WHEN trip_distance / (duration_min / 60.0) > 80          THEN '6 average speed over 80 mph'
        ELSE                                                          '7 clean'
    END AS quality_rule
FROM base;

CREATE OR REPLACE VIEW clean_trips AS
SELECT t.*, pz.borough AS pickup_borough, pz.zone AS pickup_zone, dz.borough AS dropoff_borough
FROM trips AS t
LEFT JOIN zones AS pz ON pz.location_id = t.PULocationID
LEFT JOIN zones AS dz ON dz.location_id = t.DOLocationID
WHERE t.quality_rule = '7 clean';

-- Card trips are the only ones whose tips are recorded: TLC notes that cash
-- tips are not included, so a cash trip's tip_amount is 0 whatever was given.
CREATE OR REPLACE VIEW card_trips AS
SELECT * FROM clean_trips WHERE payment_type = 1;
