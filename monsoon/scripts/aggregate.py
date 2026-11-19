"""Step 5: grid -> districts, states and all-India; weekly cumulative departures.

* District rainfall = area-weighted mean of the 0.25-degree cells it overlaps (weight =
  overlap area of cell and district, in km^2 via cos(latitude)). Cells with no data that
  day are left out of the mean; if none are left, the day is missing (never filled).
* Normal = mean of 1971-2020 for that calendar day (IMD's long-period-average base
  period). Departure = (actual - normal) / normal over the cumulative period from 1 June.
* Weeks end on Wednesdays, as in IMD's weekly district statistics.

Outputs (monsoon/data/):
  weekly_2026.json   per district: cumulative % departure for each week of 2026 (the map)
  series/<state>.json per district: weekly cumulative mm for 2021-2026 and normal (the card)
  states.json        per state: season actual, normal, departure (sowing chart)
  india.json         all-India: daily cumulative actual vs normal per year, monthly %
"""
from __future__ import annotations

import json
import math
from datetime import date, timedelta

import netCDF4
import numpy as np
from shapely.geometry import box, shape
from shapely.strtree import STRtree

from common import CACHE, DATA, category, slug, write_json
from fetch_grid import GRID

LON0, LAT0, RES, NX, NY = 66.5, 6.5, 0.25, 135, 129
NORMAL_YEARS = range(1971, 2021)
HISTORY = [2021, 2022, 2023, 2024, 2025]
THIS_YEAR = 2026
NDAYS = 122  # 1 June - 30 September


def season_dates(y: int) -> list[date]:
    return [date(y, 6, 1) + timedelta(days=i) for i in range(NDAYS)]


WEEK_ENDS = [i for i, d in enumerate(season_dates(THIS_YEAR)) if d.weekday() == 2]  # Wednesdays


# ---------------------------------------------------------------- weights
def weights():
    cache = CACHE / "weights.npz"
    feats = json.loads((CACHE / "districts_full.geojson").read_text("utf-8"))["features"]
    ids = [f["properties"]["id"] for f in feats]
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        if list(z["ids"]) == ids:
            return feats, ids, z["W"]
    W = np.zeros((len(feats), NY, NX), dtype=np.float32)
    geoms = [shape(f["geometry"]) for f in feats]
    tree = STRtree(geoms)
    for j in range(NY):
        lat = LAT0 + j * RES
        km2 = (RES * 111.32) ** 2 * math.cos(math.radians(lat))
        for i in range(NX):
            lon = LON0 + i * RES
            cell = box(lon - RES / 2, lat - RES / 2, lon + RES / 2, lat + RES / 2)
            for k in tree.query(cell, predicate="intersects"):
                a = geoms[k].intersection(cell).area
                if a > 0:
                    W[k, j, i] = a / (RES * RES) * km2
    np.savez_compressed(cache, W=W, ids=np.array(ids, dtype=object))
    return feats, ids, W


# ---------------------------------------------------------------- reading grids
def year_cube(y: int) -> np.ndarray:
    """(122, NY, NX) daily rain, NaN where missing."""
    if y == THIS_YEAR:
        out = np.full((NDAYS, NY, NX), np.nan, dtype=np.float32)
        for k, d in enumerate(season_dates(y)):
            p = GRID / f"rt_{d:%Y%m%d}.grd"
            if p.exists() and p.stat().st_size == NX * NY * 4:
                a = np.fromfile(p, "<f4").reshape(NY, NX)
                out[k] = np.where(a < 0, np.nan, a)
        return out
    ds = netCDF4.Dataset(str(GRID / f"rf25_{y}.nc"))
    v = ds["RAINFALL"]
    start = (date(y, 6, 1) - date(y, 1, 1)).days
    a = np.ma.filled(v[start:start + NDAYS].astype(np.float32), np.nan)
    ds.close()
    return np.where(a < 0, np.nan, a)


def aggregate(cube: np.ndarray, W: np.ndarray) -> np.ndarray:
    """(n_units, 122) daily area-weighted means; NaN when no valid cell."""
    Wf = W.reshape(W.shape[0], -1)                         # units x cells
    C = cube.reshape(cube.shape[0], -1)                    # days x cells
    valid = ~np.isnan(C)
    num = np.nan_to_num(C) @ Wf.T                           # days x units
    den = valid.astype(np.float32) @ Wf.T
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(den > 0, num / den, np.nan)
    return out.T


def cum(a: np.ndarray) -> np.ndarray:
    """Cumulative sum along days; becomes NaN from the first missing day on."""
    c = np.cumsum(np.nan_to_num(a), axis=-1)
    bad = np.cumsum(np.isnan(a), axis=-1) > 0
    return np.where(bad, np.nan, c)


def dep(actual, normal):
    if actual is None or normal is None or math.isnan(actual) or math.isnan(normal) or normal <= 0:
        return None
    return round((actual - normal) / normal * 100)


def ri(x):
    return None if x is None or math.isnan(x) else round(float(x))


def r1(x):
    return None if x is None or math.isnan(float(x)) else round(float(x), 1)


def main() -> None:
    feats, ids, W = weights()
    names = {f["properties"]["id"]: f["properties"] for f in feats}
    states = sorted({p["gb_state"] for p in names.values()})
    S = np.stack([W[[k for k, i in enumerate(ids) if names[i]["gb_state"] == s]].sum(0) for s in states])
    INDIA = W.sum(0, keepdims=True)
    U = np.concatenate([W, S, INDIA])                       # districts, states, India
    nd, ns = len(ids), len(states)

    daily = {}
    years = list(NORMAL_YEARS) + [y for y in HISTORY if y not in NORMAL_YEARS] + [THIS_YEAR]
    for y in years:
        cache = CACHE / "agg" / f"{y}.npy"
        if cache.exists():
            daily[y] = np.load(cache)
            continue
        cache.parent.mkdir(exist_ok=True)
        daily[y] = aggregate(year_cube(y), U).astype(np.float32)
        np.save(cache, daily[y])
        print("aggregated", y, flush=True)

    normal_daily = np.nanmean(np.stack([daily[y] for y in NORMAL_YEARS]), axis=0)
    normal_cum = np.cumsum(normal_daily, axis=1)   # NaN for units with no grid data (some islands)
    cur = cum(daily[THIS_YEAR])
    wk = WEEK_ENDS

    # ---- weekly map file
    week_dates = [season_dates(THIS_YEAR)[i].isoformat() for i in wk]
    missing_days = [season_dates(THIS_YEAR)[i].isoformat() for i in range(NDAYS) if np.isnan(daily[THIS_YEAR][-1, i])]
    dist = {}
    for k, did in enumerate(ids):
        dist[did] = {
            "d": [dep(r1(cur[k, i]), normal_cum[k, i]) for i in wk],
            "a": r1(cur[k, -1]), "n": r1(normal_cum[k, -1]),
        }
    write_json("weekly_2026.json", {"weeks": week_dates, "missing_days": missing_days, "districts": dist})

    # ---- per-state series for the district card (weekly cumulative mm)
    (DATA / "series").mkdir(exist_ok=True)
    for s in states:
        out = {}
        for k, did in enumerate(ids):
            if names[did]["gb_state"] != s:
                continue
            out[did] = {"normal": [ri(normal_cum[k, i]) for i in wk]}
            for y in HISTORY + [THIS_YEAR]:
                c = cum(daily[y][k])
                out[did][str(y)] = [ri(c[i]) for i in wk]
            # season departure for each of the last six years and its rank (1 = driest)
            seasons = {y: dep(float(cum(daily[y][k])[-1]), normal_cum[k, -1]) for y in HISTORY + [THIS_YEAR]}
            out[did]["season_dep"] = {str(y): v for y, v in seasons.items()}
        write_json(f"series/{slug(s)}.json", {"weeks": week_dates, "districts": out})

    # ---- states
    st = {}
    for j, s in enumerate(states):
        k = nd + j
        st[s] = {"actual": r1(cur[k, -1]), "normal": r1(normal_cum[k, -1]), "dep": dep(r1(cur[k, -1]), normal_cum[k, -1]),
                 "weekly_dep": [dep(r1(cur[k, i]), normal_cum[k, i]) for i in wk], "slug": slug(s)}
    write_json("states.json", st)

    # ---- India
    k = nd + ns
    months = [(6, 0, 30), (7, 30, 61), (8, 61, 92), (9, 92, 122)]
    india = {"normal_years": "1971-2020", "dates": [d.isoformat()[5:] for d in season_dates(THIS_YEAR)],
             "normal_cum": [r1(x) for x in normal_cum[k]], "years": {}}
    for y in HISTORY + [THIS_YEAR]:
        c = cum(daily[y][k])
        mon = {}
        for m, a, b in months:
            act = np.nansum(daily[y][k, a:b]) if not np.isnan(daily[y][k, a:b]).any() else np.nan
            mon[str(m)] = None if math.isnan(act) else round(float(act) / float(normal_daily[k, a:b].sum()) * 100)
        india["years"][str(y)] = {"cum": [None if math.isnan(x) else round(float(x), 1) for x in c],
                                  "pct_of_normal": None if math.isnan(c[-1]) else round(float(c[-1]) / float(normal_cum[k, -1]) * 100, 1),
                                  "monthly_pct": mon}
    # category counts (map districts) for this year
    cats = {}
    for did in ids:
        c = category(dist[did]["d"][-1]) if dist[did]["d"] else None
        cats[c or "missing"] = cats.get(c or "missing", 0) + 1
    india["category_counts_2026"] = cats
    write_json("india.json", india)
    print("all-India 2026:", india["years"]["2026"]["pct_of_normal"], "% of normal; normal season",
          round(float(normal_cum[k, -1]), 1), "mm; categories", cats)


if __name__ == "__main__":
    main()
