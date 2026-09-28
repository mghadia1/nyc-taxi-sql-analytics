"""Offline tests on hand-built trips shaped like the TLC schema."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nyctaxi import analysis, data

ZONES = pd.DataFrame({
    "LocationID": [1, 132, 138, 161, 236],
    "Borough": ["EWR", "Queens", "Queens", "Manhattan", "Manhattan"],
    "Zone": ["Newark Airport", "JFK Airport", "LaGuardia Airport", "Midtown Center", "Upper East Side North"],
    "service_zone": ["EWR", "Airports", "Airports", "Yellow Zone", "Yellow Zone"],
})


def trip(pickup, minutes, miles, fare, tip, payment=1, pu=161, do=236, tolls=0.0):
    start = pd.Timestamp(pickup)
    other = 1.0 + 0.5 + 2.5   # extra + mta_tax + congestion (improvement surcharge below)
    total = fare + other + 1.0 + tolls + tip
    return {
        "VendorID": 2, "tpep_pickup_datetime": start,
        "tpep_dropoff_datetime": start + pd.Timedelta(minutes=minutes),
        "passenger_count": 1, "trip_distance": miles, "RatecodeID": 1, "store_and_fwd_flag": "N",
        "PULocationID": pu, "DOLocationID": do, "payment_type": payment,
        "fare_amount": fare, "extra": 1.0, "mta_tax": 0.5, "tip_amount": tip, "tolls_amount": tolls,
        "improvement_surcharge": 1.0, "total_amount": total, "congestion_surcharge": 2.5, "Airport_fee": 0.0,
    }


@pytest.fixture
def con():
    rows = [
        # clean card trips; pre-tip total = fare + 5.00
        trip("2024-01-10 08:00", 12, 2.0, 15.0, 4.00),              # 20% of 20.00 -> preset
        trip("2024-01-10 09:00", 10, 1.5, 11.0, 4.00),              # 25% of 16.00 -> preset
        trip("2024-01-10 10:00", 10, 1.5, 15.0, 6.00),              # 30% of 20.00 -> preset
        trip("2024-01-10 11:00", 10, 1.5, 15.0, 3.00),              # 15% -> not a preset
        trip("2024-01-10 12:00", 10, 1.5, 15.0, 0.00),              # untipped card trip
        trip("2024-01-10 13:00", 40, 17.0, 70.0, 0.00, payment=2, pu=132),   # cash, from JFK
        # one row per quality rule
        trip("2002-12-31 23:00", 10, 1.0, 10.0, 0.0),               # 1 outside window
        {**trip("2024-01-11 08:00", 10, 1.0, 10.0, 0.0), "payment_type": 0},  # 2 payment type 0
        trip("2024-01-11 09:00", 10, 1.0, -10.0, 0.0),              # 3 negative fare
        trip("2024-01-11 10:00", 0, 1.0, 10.0, 0.0),                # 4 zero duration
        trip("2024-01-11 11:00", 10, 0.0, 10.0, 0.0),               # 5 zero distance
        trip("2024-01-11 12:00", 10, 20.0, 10.0, 0.0),              # 6 120 mph
    ]
    return analysis.connect(pd.DataFrame(rows), ZONES)


def test_each_quality_rule_labels_exactly_one_row(con):
    dq = analysis.run(con, "data_quality").set_index("rule")["trips"]
    assert dq.sum() == 12
    assert dq["7 clean"] == 6
    assert all(dq.drop("7 clean") == 1)


def test_rule_order_first_rule_wins(con):
    # a negative-fare trip that is ALSO zero-distance is counted under rule 3 only
    both = trip("2024-01-12 08:00", 10, 0.0, -5.0, 0.0)
    c = analysis.connect(pd.DataFrame([both]), ZONES)
    assert c.execute("SELECT quality_rule FROM trips").fetchone()[0].startswith("3 ")


def test_cash_tip_trap(con):
    tips = analysis.run(con, "tip_by_payment").set_index("payment")
    assert tips.loc["cash", "mean_tip_pct"] == 0
    # card: (20 + 25 + 30 + 15 + 0) / 5 = 18%; naive adds the cash zero: 90 / 6 = 15%
    assert tips.loc["card", "mean_tip_pct"] == pytest.approx(18.0)
    assert tips.loc["ALL (naive)", "mean_tip_pct"] == pytest.approx(15.0)


def test_preset_tips_are_detected(con):
    presets = analysis.run(con, "tip_presets").set_index("tip_kind")["trips"]
    assert presets.to_dict() == {"20%": 1, "25%": 1, "30%": 1, "other amount": 1}


def test_preset_uses_total_including_tolls():
    # 20% of (15 fare + 5 surcharges + 6.94 tolls) = 5.388 -> 5.39
    with_tolls = trip("2024-01-10 08:00", 12, 2.0, 15.0, 5.39, tolls=6.94)
    c = analysis.connect(pd.DataFrame([with_tolls]), ZONES)
    assert analysis.run(c, "tip_presets").set_index("tip_kind").loc["20%", "trips"] == 1


def test_airports_and_speed(con):
    airports = analysis.run(con, "airports").set_index("airport")
    assert airports.loc["JFK", "trips"] == 1
    assert airports.loc["non-airport", "trips"] == 5
    speed = analysis.run(con, "speed_by_hour").set_index("pickup_hour")
    assert speed.loc[8, "median_mph"] == pytest.approx(10.0)     # 2 miles in 12 minutes
    assert 13 not in speed.index                                 # JFK trip is not Manhattan-Manhattan


def _daily(counts: list[int], start: str = "2024-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=len(counts), freq="D")
    return pd.DataFrame({"pickup_date": dates, "pickup_isodow": dates.isocalendar().day.to_numpy(),
                         "trips": counts})


def test_anomaly_detector_flags_a_crash_and_ignores_the_weekly_cycle():
    rng = np.random.default_rng(0)
    weekly = [100, 100, 100, 100, 110, 70, 60]          # weekends are always low
    # noise proportional to volume (1%); a fixed +-800 made low-volume weekend days
    # relatively noisier and produced a false flag in the first version of this test
    counts = [int(weekly[i % 7] * 1000 * (1 + rng.normal(0, 0.01))) for i in range(63)]
    counts[30] = counts[30] // 2                         # one crash
    flagged = analysis.flag_anomalous_days(_daily(counts))
    assert flagged.loc[flagged["is_anomaly"]].index.tolist() == [30]


def test_window_wide_baseline_misreads_a_trend():
    # steady 1% daily growth, no anomalies at all
    counts = [int(50_000 * 1.01 ** i) for i in range(84)]
    local = analysis.flag_anomalous_days(_daily(counts), window_days=21)
    wide = analysis.flag_anomalous_days(_daily(counts), window_days=None)
    # the window-wide baseline mistakes the trend for deviation almost 5x more;
    # the local one still carries some bias at the edges, where its window is one-sided
    assert wide["ratio"].abs().mean() > 4 * local["ratio"].abs().mean()
    assert not local["is_anomaly"].any()


def test_holiday_label_is_applied_after_detection():
    frame = analysis.flag_anomalous_days(_daily([100_000] * 21, start="2023-12-25"))
    assert frame.loc[frame["pickup_date"] == "2024-01-01", "holiday"].item() == "New Year's Day"
    assert not frame["is_anomaly"].any()
    assert (frame["robust_z"] == 0).all()                 # MAD of 0 must not produce NaN


def test_unknown_query_rejected(con):
    with pytest.raises(KeyError):
        analysis.run(con, "trips")


def test_checksum_mismatch(tmp_path):
    path = tmp_path / "bad.parquet"
    path.write_bytes(b"x")
    with pytest.raises(ValueError, match="checksum mismatch"):
        data.verify(path, next(iter(data.FILES.values())))
