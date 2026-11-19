"""Step 2: download IMD Pune 0.25-degree gridded daily rainfall.

* Final (quality-controlled) yearly NetCDF, 1901-2025:
  https://imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html  (POST RF25=<year> to RF25.php)
* Real-time daily grids for the current year (2026), one binary file per day:
  https://imdpune.gov.in/cmpg/Realtimedata/Rainfall/rain.php    (POST rain=<DDMMYYYY>)
  135 x 129 float32 (lon 66.5-100 E, lat 6.5-38.5 N), -999 = no data.

Reference: Pai et al. (2014), MAUSAM 65(1):1-18.

Usage: python fetch_grid.py [--years 1971-2025] [--realtime 2026]
Files are cached in scripts/.cache/grid/; re-running only fetches what is missing.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from common import CACHE, get

GRID = CACHE / "grid"
ARCHIVE = "https://imdpune.gov.in/cmpg/Griddata/RF25.php"
REALTIME = "https://imdpune.gov.in/cmpg/Realtimedata/Rainfall/rain.php"
SEASON = ((6, 1), (9, 30))


def years(spec: str) -> list[int]:
    a, _, b = spec.partition("-")
    return list(range(int(a), int(b or a) + 1))


def fetch_archive(y: int):
    return get(ARCHIVE, GRID / f"rf25_{y}.nc", method="POST", data={"RF25": str(y)}, min_bytes=10**7)


def fetch_realtime_day(d: date):
    return get(REALTIME, GRID / f"rt_{d:%Y%m%d}.grd", method="POST", data={"rain": f"{d:%d%m%Y}"}, min_bytes=135 * 129 * 4)


def season_days(y: int):
    d, end = date(y, *SEASON[0]), date(y, *SEASON[1])
    while d <= end:
        yield d
        d += timedelta(days=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="1971-2025")
    ap.add_argument("--realtime", default="2026")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    ap_workers = a.workers
    missing = []

    def one_day(d):
        try:
            fetch_realtime_day(d)
        except RuntimeError as e:
            missing.append(d.isoformat())
            print("MISSING", d, e, flush=True)

    def one_year(y):
        try:
            print("archive", y, fetch_archive(y).stat().st_size // 1024, "KB", flush=True)
        except RuntimeError as e:
            print("FAILED archive", y, e, flush=True)

    with ThreadPoolExecutor(ap_workers) as ex:  # the server is slow per file, not per connection
        days = [d for y in (years(a.realtime) if a.realtime else []) for d in season_days(y)]
        list(ex.map(one_day, days))
        print("realtime done; missing days:", sorted(missing) or "none", flush=True)
        list(ex.map(one_year, years(a.years)))


if __name__ == "__main__":
    main()
