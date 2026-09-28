"""Matplotlib figures for the README and results document."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

INK = "#1f2937"
ACCENT = "#2563eb"
WARN = "#dc2626"
MUTED = "#9ca3af"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _finish(fig, ax, path: Path) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def tip_histogram(hist: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 3.6))
    colors = [ACCENT if p in (20, 25, 30) else MUTED for p in hist["tip_pct"]]
    ax.bar(hist["tip_pct"], hist["trips"] / 1e6, color=colors, width=0.85)
    ax.set_xlabel("Tip as % of the pre-tip total (card trips, 1-point bins)")
    ax.set_ylabel("Trips (millions)")
    ax.set_title("Card tips pile up on the tablet's preset buttons (blue = 20 / 25 / 30%)", loc="left", color=INK)
    _finish(fig, ax, path)


def demand_heatmap(demand: pd.DataFrame, path: Path) -> None:
    grid = demand.pivot(index="pickup_isodow", columns="pickup_hour", values="avg_trips")
    fig, ax = plt.subplots(figsize=(10, 3.4))
    image = ax.imshow(grid.to_numpy(), cmap="Blues", aspect="auto")
    ax.set_yticks(range(7), DAYS)
    ax.set_xticks(range(0, 24, 2), [f"{h:02d}" for h in range(0, 24, 2)])
    ax.set_xlabel("Pickup hour")
    ax.set_title("Average trips per hour, Jan-Mar 2024", loc="left", color=INK)
    fig.colorbar(image, ax=ax, fraction=0.025)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def speed_by_hour(speed: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 3.6))
    for weekend, color, label in ((False, ACCENT, "Weekday"), (True, MUTED, "Weekend")):
        part = speed[speed["is_weekend"] == weekend]
        ax.plot(part["pickup_hour"], part["median_mph"], marker="o", markersize=3, color=color, label=label)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlabel("Pickup hour")
    ax.set_ylabel("Median speed (mph)")
    ax.set_title("Manhattan-to-Manhattan trips: median door-to-door speed", loc="left", color=INK)
    ax.legend(frameon=False)
    _finish(fig, ax, path)


def daily_volume(days: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 3.6))
    dates = pd.to_datetime(days["pickup_date"])
    ax.plot(dates, days["trips"] / 1e3, color=INK, linewidth=1)
    ax.plot(dates, days["baseline"] / 1e3, color=MUTED, linewidth=1, linestyle="--", label="same-weekday median")
    flagged = days[days["is_anomaly"]]
    ax.scatter(pd.to_datetime(flagged["pickup_date"]), flagged["trips"] / 1e3, color=WARN, zorder=3,
               label="flagged (|robust z| > 3.5)")
    ax.set_ylabel("Trips per day (thousands)")
    ax.set_title("Daily trips and anomaly flags", loc="left", color=INK)
    ax.legend(frameon=False, loc="lower right")
    _finish(fig, ax, path)
