"""Step 8: check our gridded numbers against IMD's own published figures, and write meta.json.

1. All-India season and monthly % of LPA vs IMD's "Salient Features of the 2026 SW Monsoon".
2. District cumulative departure vs IMD's station-based district table (DISTRICT RAINFALL
   DISTRIBUTION PDF, archived by the Wayback Machine on 24 Sep 2026 and earlier dates),
   for every IMD district matched to a map district with an unchanged boundary.

The site shows IMD's official all-India figure as the headline and these results in Method.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path

import numpy as np
import pypdf

from aggregate import NORMAL_YEARS, THIS_YEAR, season_dates
from common import CACHE, DATA, category, write_json
from imd_pdf import parse

SALIENT = "https://mausam.imd.gov.in/Forecast/marquee_data/Salient_Features_SW_MONSOON%20_2026_30_sep.pdf"
WAYBACK = "https://web.archive.org/web/{ts}/https://mausam.imd.gov.in/Rainfall/DISTRICT_RAINFALL_DISTRIBUTION_COUNTRY_INDIA_cd.pdf"


def official() -> dict:
    t = "\n".join(p.extract_text() for p in pypdf.PdfReader(str(CACHE / "imd" / "salient_2026.pdf")).pages)
    t = re.sub(r"\s+", " ", t)
    out = {"source": SALIENT, "regions": {}, "monthly": {}}
    for name in ["All India", "Northwest India", "Central India", "East & Northeast India", "South Peninsula", "Monsoon Core Zone"]:
        m = re.search(re.escape(name) + r"\s+([\d.]+)\s+([\d.]+)\s+(\d+)", t)
        if m:
            out["regions"][name] = {"lpa_mm": float(m.group(1)), "actual_mm": float(m.group(2)), "pct_of_lpa": int(m.group(3))}
    for k, mon in zip(["6", "7", "8", "9"], ["June", "July", "August", "September"]):
        m = re.search(mon + r"\s+([\d.]+)\s+([\d.]+)\s+(\d+)", t)
        if m:
            out["monthly"][k] = {"lpa_mm": float(m.group(1)), "actual_mm": float(m.group(2)), "pct_of_lpa": int(m.group(3))}
    m = re.search(r"monsoon rainfall was [\d.]+ mm which is\s+(\d+(?:st|nd|rd|th) lowest since \d{4})\s+and\s+(\d+(?:st|nd|rd|th) lowest since \d{4})", t)
    out["rank"] = [m.group(1), m.group(2)] if m else []
    m = re.search(r"Out of the total (\d+) meteorological districts", t)
    out["n_districts"] = int(m.group(1)) if m else None
    return out


def ours_cum(upto: date):
    feats = json.loads((CACHE / "districts_full.geojson").read_text("utf-8"))["features"]
    ids = [f["properties"]["id"] for f in feats]
    nd = len(ids)
    daily = {y: np.load(CACHE / "agg" / f"{y}.npy") for y in list(NORMAL_YEARS) + [THIS_YEAR]}
    normal = np.nanmean(np.stack([daily[y] for y in NORMAL_YEARS]), 0)
    k = season_dates(THIS_YEAR).index(upto) + 1
    act = daily[THIS_YEAR][:nd, :k].sum(1)
    nrm = normal[:nd, :k].sum(1)
    return {i: (float(a), float(n)) for i, a, n in zip(ids, act, nrm)}


def compare(pdf: Path) -> dict | None:
    rep = parse(pdf)
    if not rep["from"] or rep["from"] != f"01-06-{THIS_YEAR}":
        return None
    d, m, y = map(int, rep["to"].split("-"))
    upto = date(y, m, d)
    ours = ours_cum(upto)
    mapping = {(r["imd_group"], r["imd_name"]): r for r in csv.DictReader((DATA / "name_mapping.csv").open(encoding="utf-8"))}
    pairs = []
    for r in rep["rows"]:
        mrow = mapping.get((r["state"], r["name"]))
        if not mrow or not mrow["district_id"] or "boundary changed" in mrow.get("note", "") or r["dep"] is None:
            continue
        a, n = ours[mrow["district_id"]]
        if np.isnan(a) or n <= 0:
            continue
        pairs.append((r["dep"], round((a - n) / n * 100), r["name"], mrow["district_id"]))
    if not pairs:
        return None
    imd = np.array([p[0] for p in pairs], float)
    me = np.array([p[1] for p in pairs], float)
    order = ["NR", "LD", "D", "N", "E", "LE"]
    ci = np.array([order.index(category(v)) for v in imd])
    cm = np.array([order.index(category(v)) for v in me])
    diff = me - imd
    worst = sorted(pairs, key=lambda p: -abs(p[1] - p[0]))[:5]
    return {
        "period": f"{THIS_YEAR}-06-01 to {upto.isoformat()}", "districts_compared": len(pairs),
        "pearson_r": round(float(np.corrcoef(imd, me)[0, 1]), 3),
        "spearman_r": round(float(np.corrcoef(imd.argsort().argsort(), me.argsort().argsort())[0, 1]), 3),
        "median_abs_diff_pts": round(float(np.median(np.abs(diff))), 1),
        "mean_diff_pts": round(float(diff.mean()), 1),
        "same_category_pct": round(float((ci == cm).mean() * 100), 1),
        "within_one_category_pct": round(float((np.abs(ci - cm) <= 1).mean() * 100), 1),
        "largest_gaps": [{"district": p[2].title(), "imd": p[0], "ours": p[1]} for p in worst],
        # two or more IMD categories apart: the gridded estimate is not reliable for that district
        "flagged": int((np.abs(ci - cm) >= 2).sum()),
        "_pairs": {p[3]: {"imd": p[0], "ours": p[1], "flag": bool(abs(order.index(category(p[0])) - order.index(category(p[1]))) >= 2)} for p in pairs},
    }


def main() -> None:
    off = official()
    india = json.loads((DATA / "india.json").read_text("utf-8"))
    ours26 = india["years"][str(THIS_YEAR)]
    checks = {"all_india": {"imd_pct_of_lpa": off["regions"].get("All India", {}).get("pct_of_lpa"),
                            "ours_pct_of_normal": ours26["pct_of_normal"],
                            "imd_lpa_mm": off["regions"].get("All India", {}).get("lpa_mm"),
                            "ours_normal_mm": india["normal_cum"][-1]},
              "monthly": {k: {"imd": v["pct_of_lpa"], "ours": ours26["monthly_pct"].get(k)} for k, v in off["monthly"].items()},
              "districts": []}
    for pdf in sorted((CACHE / "imd").glob("district_dist_*.pdf")):
        r = compare(pdf)
        if r:
            r["snapshot"] = WAYBACK.format(ts=pdf.stem.split("_")[-1])
            checks["districts"].append(r)
    rows = list(csv.DictReader((DATA / "name_mapping.csv").open(encoding="utf-8")))
    names = {"imd_districts": len(rows), "auto": sum(r["method"] == "auto" for r in rows),
             "manual": sum(r["method"] == "manual" for r in rows),
             "no_polygon": [{"imd": r["imd_name"].title(), "note": r["note"]} for r in rows if r["method"] == "no-polygon"],
             "map_districts": len(json.loads((CACHE / "districts_full.geojson").read_text("utf-8"))["features"])}
    latest = checks["districts"][-1] if checks["districts"] else None
    if latest:
        write_json("imd_check.json", {"period": latest["period"], "snapshot": latest["snapshot"], "districts": latest["_pairs"]})
    for c in checks["districts"]:
        c.pop("_pairs", None)
    weekly = json.loads((DATA / "weekly_2026.json").read_text("utf-8"))
    write_json("meta.json", {"generated": date.today().isoformat(), "official": off, "checks": checks, "names": names,
                             "missing_days_2026": weekly["missing_days"], "normal_years": india["normal_years"]})
    print(json.dumps(checks, indent=1))


if __name__ == "__main__":
    main()
