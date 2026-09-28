"""Command line: `nyctaxi download | analyze`."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from nyctaxi import analysis, charts, data


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="nyctaxi")
    sub = parser.add_subparsers(dest="command", required=True)
    dl = sub.add_parser("download", help="fetch and checksum 3 months of trips + zone lookup (~160 MB)")
    dl.add_argument("--destination", type=Path, default=Path("data/raw"))
    an = sub.add_parser("analyze", help="run every SQL analysis; write CSVs, charts, summary")
    an.add_argument("--raw", type=Path, default=Path("data/raw"))
    an.add_argument("--out", type=Path, default=Path("outputs"))
    args = parser.parse_args(argv)

    if args.command == "download":
        for path in data.download(args.destination):
            print(path)
    else:
        print(json.dumps(analyze(args.raw, args.out), indent=2))


def analyze(raw: Path, out: Path) -> dict:
    for name, expected in data.FILES.items():
        data.verify(raw / name, expected)
    out.mkdir(parents=True, exist_ok=True)
    con = analysis.connect_dir(raw)

    timings, results = {}, {}
    for name in analysis.QUERIES:
        start = time.perf_counter()
        results[name] = analysis.run(con, name)
        timings[name] = round(time.perf_counter() - start, 2)
    days = analysis.flag_anomalous_days(results["daily_trips"])
    results["daily_anomalies"] = days

    for name, frame in results.items():
        frame.to_csv(out / f"{name}.csv", index=False)
    charts.tip_histogram(results["tip_pct_histogram"], out / "tip_histogram.png")
    charts.demand_heatmap(results["hour_weekday_demand"], out / "demand_heatmap.png")
    charts.speed_by_hour(results["speed_by_hour"], out / "speed_by_hour.png")
    charts.daily_volume(days, out / "daily_volume.png")

    quality = results["data_quality"].set_index("rule")
    tips = results["tip_by_payment"].set_index("payment")
    presets = results["tip_presets"].set_index("tip_kind")["pct_of_tipped_card_trips"]
    speed = results["speed_by_hour"]
    weekday = speed[~speed["is_weekend"]].set_index("pickup_hour")["median_mph"]
    summary = {
        "raw_trips": int(quality["trips"].sum()),
        "clean_trips": int(quality.loc["7 clean", "trips"]),
        "clean_pct": float(quality.loc["7 clean", "pct_of_trips"]),
        "mean_tip_pct_all_trips_naive": float(tips.loc["ALL (naive)", "mean_tip_pct"]),
        "mean_tip_pct_card_only": float(tips.loc["card", "mean_tip_pct"]),
        "tipped_card_trips_at_a_preset_pct": round(float(presets.drop("other amount").sum()), 2),
        "weekday_manhattan_median_mph_slowest_hour": {str(weekday.idxmin()): float(weekday.min())},
        "weekday_manhattan_median_mph_fastest_hour": {str(weekday.idxmax()): float(weekday.max())},
        "anomalous_days": days.loc[days["is_anomaly"], ["pickup_date", "trips", "baseline", "robust_z", "holiday"]]
        .assign(pickup_date=lambda f: f["pickup_date"].astype(str)).round(2).to_dict("records"),
        "query_seconds": timings,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
