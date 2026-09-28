"""DuckDB over the monthly parquet files, plus robust anomaly detection on daily volume."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from nyctaxi import data

QUERIES = (
    "data_quality",
    "daily_trips",
    "hour_weekday_demand",
    "speed_by_hour",
    "tip_by_payment",
    "tip_presets",
    "tip_pct_histogram",
    "airports",
)

# US federal holidays and New Year's Day inside the window: calendar facts, used
# only to label anomalies after they are detected, never to detect them.
HOLIDAYS = {
    "2024-01-01": "New Year's Day",
    "2024-01-15": "Martin Luther King Jr. Day",
    "2024-02-19": "Presidents' Day",
}


def _sql(name: str) -> str:
    return resources.files("nyctaxi").joinpath("sql", f"{name}.sql").read_text()


def connect(trips: list[Path] | pd.DataFrame, zones: Path | pd.DataFrame,
            window: tuple[str, str] = (data.WINDOW_START, data.WINDOW_END)):
    con = duckdb.connect()
    con.execute("SET VARIABLE window_start = ?::TIMESTAMP", [window[0]])
    con.execute("SET VARIABLE window_end = ?::TIMESTAMP", [window[1]])
    if isinstance(trips, pd.DataFrame):
        con.register("raw_trips", trips)
    else:
        con.read_parquet([str(p) for p in trips], union_by_name=True).create_view("raw_trips")
    if isinstance(zones, pd.DataFrame):
        con.register("raw_zones", zones)
    else:
        con.read_csv(str(zones)).create_view("raw_zones")
    con.execute(_sql("00_views"))
    return con


def connect_dir(raw: Path):
    trips = sorted(raw / name for name in data.FILES if name.endswith(".parquet"))
    return connect(trips, raw / "taxi_zone_lookup.csv")


def run(con, name: str) -> pd.DataFrame:
    if name not in QUERIES:
        raise KeyError(f"unknown query {name!r}; choose from {QUERIES}")
    return con.execute(_sql(name)).df()


def flag_anomalous_days(daily: pd.DataFrame, threshold: float = 3.5, window_days: int | None = 21) -> pd.DataFrame:
    """Flag days whose volume is far from what their weekday usually looks like.

    The baseline for each day is the median of the *other* days with the same
    weekday. That removes the weekly cycle, and leaving the day itself out
    means one extreme day cannot pull its own baseline toward it. Deviations
    are scaled by the median absolute deviation (MAD), not the standard
    deviation, so the outliers being hunted do not inflate the yardstick.
    A robust z below -threshold (or above +threshold) is flagged.

    `window_days` limits the peers to same-weekday days within that many days.
    With `None` the baseline is the whole window, which is simpler but wrong
    when volume trends: Jan-Mar 2024 grows, so a window-wide median makes every
    early-January day look low. The first version of this detector did exactly
    that, and docs/results.md keeps both outputs.
    """
    frame = daily.copy()
    baselines = []
    for index, row in frame.iterrows():
        peers = frame[(frame["pickup_isodow"] == row["pickup_isodow"]) & (frame.index != index)]
        if window_days is not None:
            gap = (pd.to_datetime(peers["pickup_date"]) - pd.Timestamp(row["pickup_date"])).abs()
            peers = peers[gap <= pd.Timedelta(days=window_days)]
        baselines.append(peers["trips"].median())
    frame["baseline"] = baselines
    frame["ratio"] = frame["trips"] / frame["baseline"] - 1
    deviation = frame["ratio"] - frame["ratio"].median()
    mad = np.median(np.abs(deviation))
    if mad == 0:
        # more than half the days sit exactly on their baseline: any deviation
        # at all is infinitely unusual on this scale, and none is 0
        frame["robust_z"] = np.where(deviation == 0, 0.0, np.sign(deviation) * np.inf)
    else:
        frame["robust_z"] = 0.6745 * deviation / mad
    frame["is_anomaly"] = frame["robust_z"].abs() > threshold
    frame["holiday"] = frame["pickup_date"].astype(str).map(HOLIDAYS).fillna("")
    return frame
