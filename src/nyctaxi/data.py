"""Download and verify the NYC TLC files: three months of yellow-taxi trips and the zone lookup."""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

BASE = "https://d37ci6vzurychx.cloudfront.net"

# SHA-256 recorded 2026-09-22. TLC occasionally republishes a month with
# corrections; if a hash stops matching, re-run and re-record results rather
# than editing the hash alone.
FILES = {
    "yellow_tripdata_2024-01.parquet": "c4d59da7bbc8abaeeeb1727947ee93d9891a71acb42854bd80db1571b2030510",
    "yellow_tripdata_2024-02.parquet": "c76c43c18c6c6664080dd920baab4928988d5786a6b65980792ca7cd796f9f20",
    "yellow_tripdata_2024-03.parquet": "2d4cdc8fb96726cdd3803b13b02d2e61e71d45720aff0ebc693a8bdd1f249823",
    "taxi_zone_lookup.csv": "1a99e105092230f8620f301edcca7f80d3080642ff404d28ed957d3fa222c8ed",
}

# The analysis window. Each monthly file contains a few trips whose clock says
# 2002 or 2009; they are counted by the data-quality audit, then excluded.
WINDOW_START = "2024-01-01"
WINDOW_END = "2024-04-01"


def url_for(name: str) -> str:
    folder = "misc" if name.endswith(".csv") else "trip-data"
    return f"{BASE}/{folder}/{name}"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path, expected: str) -> None:
    actual = sha256_of(path)
    if actual != expected:
        raise ValueError(f"checksum mismatch for {path.name}: {actual}")


def download(destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, expected in FILES.items():
        path = destination / name
        if not path.exists():
            urllib.request.urlretrieve(url_for(name), path)
        verify(path, expected)
        paths.append(path)
    return paths
