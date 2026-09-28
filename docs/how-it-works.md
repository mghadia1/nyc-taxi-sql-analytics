# How it works

```
TLC CloudFront ──download──▶ data/raw/*.parquet (3 months, 9.55M rows) + zone CSV
                 (SHA-256)                │
                                          ▼
                    DuckDB: read_parquet([...]) ─▶ 00_views.sql ─▶ 8 analysis queries ─▶ outputs/
                                                   trips / clean_trips / card_trips      CSV, PNG, summary.json
                                                                        │
                                                   daily_trips ─▶ analysis.flag_anomalous_days (pandas)
```

## Why DuckDB on parquet

The three files are 160 MB compressed and 9.55M rows. DuckDB scans parquet directly, reading only the columns a query touches, so there is no load step and no database server. Every analysis runs in 0.3–1.0 s on a laptop. The same SQL would run on a warehouse with small dialect changes, such as `quantile_cont` becoming `PERCENTILE_CONT` in Postgres.

## The views (`00_views.sql`)

- **`trips`** adds derived columns (`duration_min`, `mph`, `pre_tip_amount`, hour, ISO weekday) and a `quality_rule` label. The label is one ordered `CASE`: a trip gets the *first* rule it breaks, so the audit table adds up exactly to the raw row count. A test pins the ordering, for example a trip that is both negative-fare and zero-distance counts only as negative-fare.
- **`clean_trips`** is rule 7 only, joined twice to the zone lookup for pickup and drop-off borough.
- **`card_trips`** is clean trips paid by card, the only trips whose tips are recorded.

The analysis window comes from DuckDB session variables (`SET VARIABLE window_start`), so the SQL has no hard-coded dates, and tests can use their own window.

## Measuring preset tips

For each candidate base (fare only; fare + surcharges; total − tip − tolls; total − tip), I counted how many tips are within one cent of exactly 20%, 25%, or 30% of that base. The base with the most exact matches (total − tip, 56.1%) is the one the analysis uses. The one-cent tolerance allows for the tablet rounding differently from SQL's `round`. For example, 20% of a $26.94 base is $5.388: SQL rounds it to $5.39, but a tablet that truncates would charge $5.38, and both should count. A test uses that base, with tolls included, to pin the tolls-in-base rule.

## Anomaly detection (`analysis.flag_anomalous_days`)

1. **Baseline:** the median of other days with the same weekday within ±21 days. Using the same weekday removes the weekly cycle, and leaving the day itself out stops a crash from dragging its own baseline down.
2. **Deviation:** `trips / baseline − 1`.
3. **Scale:** the median absolute deviation (MAD) of those deviations. The standard deviation would be inflated by the very outliers being hunted, and the MAD is not. If the MAD is 0, the z-score is defined explicitly instead of producing NaN.
4. **Flag:** |0.6745 × deviation / MAD| > 3.5. The 0.6745 factor makes the MAD comparable with a standard deviation under a normal distribution.
5. **Label:** federal holidays are attached *after* detection, so the calendar never influences what gets flagged.

## Tests (11)

The tests use a 12-trip fixture with one row per quality rule. They cover:
- the rule ordering;
- the cash-tip trap, with hand-computed means (18% card vs 15% naive);
- preset detection, including the tolls-in-base case;
- airports and the speed filter;
- the anomaly detector: it flags one injected crash and ignores the weekly cycle; the window-wide baseline shows its trend bias; holiday labels do not cause flags; a zero MAD is handled;
- query allow-listing and checksum rejection.

Two of these tests failed the first time, and both taught something:
- **The synthetic noise.** It was a fixed ±800 trips, which is relatively noisier on low-volume weekend days and produced a false flag on a Saturday. The noise is now proportional to volume.
- **The trend comparison.** It originally compared only day 0, where the ±21-day window is one-sided. It now compares the whole series.

## Things to be able to explain

- Why exclude `payment_type 0` rows instead of keeping them?
- Why is "average tip over all trips" wrong in this dataset?
- How was the tip base chosen, and what would change the conclusion?
- Why the median absolute deviation and not the standard deviation? Why a local baseline?
