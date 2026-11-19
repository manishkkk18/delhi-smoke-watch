"""Step 6: monsoon onset and advance, 2026 vs normal.

Sources (both IMD):
* Daily press releases, listed at https://internal.imd.gov.in/pages/press_release_mausam.php
  On each advance day IMD writes "The Northern Limit of Monsoon (NLM) passes through
  <places and lat/lon points>". We take the NLM for every date from 10 May to 15 July.
* Normal onset dates (1961-2019) for 140 cities: Table-2 of IMD CRS Research Report
  3/2020 (Pai et al.), https://internal.imd.gov.in/press_release/20200515_pr_804.pdf

Place names are geocoded once with OpenStreetMap Nominatim and kept in
geocode_cache.json (committed, so re-runs are reproducible; fix a bad hit by editing it).
A city's 2026 arrival date = the first NLM date whose covered area (south of the line)
contains the city; after IMD's "covered the entire country" date, everything is covered.

Output: data/onset_2026.json
"""
from __future__ import annotations

import json
import re
import time
from datetime import date

import pypdf
import requests
from shapely.geometry import Point, Polygon
from shapely.validation import make_valid

from common import CACHE, SCRIPTS, UA, get, write_json

LIST = "https://internal.imd.gov.in/pages/press_release_mausam.php"
PR_BASE = "https://internal.imd.gov.in/press_release/"
REPORT = "https://internal.imd.gov.in/press_release/20200515_pr_804.pdf"
START, END = date(2026, 5, 10), date(2026, 7, 15)
COVERED_ALL = date(2026, 7, 9)   # IMD Salient Features 2026: "covered the entire country by 9th July"
GEOCACHE = SCRIPTS / "geocode_cache.json"
PRDIR = CACHE / "imd" / "pr"

LATLON = re.compile(r"(\d+(?:\.\d+)?)\s*°?\s*N?\s*/\s*(\d+(?:\.\d+)?)\s*°?\s*E")


def pdf_text(p) -> str:
    try:
        return "\n".join((pg.extract_text() or "") for pg in pypdf.PdfReader(str(p)).pages)
    except Exception:  # noqa: BLE001
        return ""


def press_releases() -> list[tuple[date, str]]:
    html = get(LIST, CACHE / "imd" / "press_release_list.html", min_bytes=10**5).read_text("utf-8", "ignore")
    out = []
    for f in sorted(set(re.findall(r"press_release/(2026\d{4}_pr_\d+\.pdf)", html))):
        d = date(int(f[:4]), int(f[4:6]), int(f[6:8]))
        if START <= d <= END:
            out.append((d, f))
    return out


def nlm_strings() -> dict[str, str]:
    """date -> the 'passes through ...' text (the last one IMD issued that day)."""
    found: dict[str, str] = {}
    for d, f in press_releases():
        try:
            p = get(PR_BASE + f, PRDIR / f, min_bytes=1000)
        except RuntimeError as e:
            print("skip", f, e)
            continue
        t = re.sub(r"\s+", " ", pdf_text(p)).replace("Dist.", "Dist")
        m = re.search(r"Northern Limit of (?:the )?Monsoon(?: \(NLM\))? (?:now |continues to |still )?pass(?:es)? through (.+?)(?:\.\s|❖|➢|•|$)", t)
        if m:
            found[d.isoformat()] = re.sub(r"\s*as on .*$", "", m.group(1)).strip().rstrip(".")
    return found


def tokens(s: str) -> list[str]:
    s = s.replace(" and ", ", ")
    return [x.strip() for x in s.split(",") if x.strip()]


# Spelling fixes for the geocoder only (IMD's spellings are kept for display).
GEO_ALIASES = {"Vishakhapatnam": "Visakhapatnam", "Medikeri": "Madikeri", "Mengluru": "Mangaluru",
               "Tiruvananthpuram": "Thiruvananthapuram", "Ambagarh Chowk": "Ambagarh Chowki", "Tulasipur": "Tulsipur",
               "Uthagamandalam": "Ooty", "Hissar": "Hisar", "Bhatinda": "Bathinda", "J&K": "Jammu and Kashmir", "Chattisgarh": "Chhattisgarh",
               "Andman Nicobar": "Andaman and Nicobar Islands"}
# Within ~10 km of a published line counts as reached that day (IMD lists the places the line passes through).
ON_LINE_DEG = 0.1

_geo = json.loads(GEOCACHE.read_text("utf-8")) if GEOCACHE.exists() else {}


def geocode(name: str, hint: str = "") -> list[float] | None:
    name, hint = GEO_ALIASES.get(name, name), GEO_ALIASES.get(hint, hint)
    key = f"{name}|{hint}"
    if key in _geo:
        return _geo[key]
    q = f"{name}, {hint}, India" if hint else f"{name}, India"
    time.sleep(1.1)  # Nominatim usage policy: max 1 request per second
    r = requests.get("https://nominatim.openstreetmap.org/search", params={"q": q, "format": "json", "limit": 1},
                     headers=UA, timeout=60)
    js = r.json() if r.ok else []
    _geo[key] = [round(float(js[0]["lon"]), 3), round(float(js[0]["lat"]), 3)] if js else None
    GEOCACHE.write_text(json.dumps(_geo, indent=1, sort_keys=True), "utf-8")
    return _geo[key]


def point_of(tok: str) -> tuple[list[float] | None, str]:
    m = LATLON.search(tok)
    if m:
        return [float(m.group(2)), float(m.group(1))], "latlon"
    return geocode(tok), "place"


def close_ring(c: list[list[float]]) -> list[list[float]]:
    """Turn an NLM line (west -> east) into the area the monsoon covers: everything south/east of it.

    A line that ends in the far north (past 25N: the Himalaya / northeast) is closed north to 40N
    and then east; one that ends out over the Bay or Myanmar is closed east along its last latitude.
    Then down to the equator and back west under India. js/onset.js uses the same rule.
    """
    end = c[-1]
    tail = [[end[0], 40.0], [100.0, 40.0]] if end[1] > 25 else [[100.0, end[1]]]
    return c + tail + [[100.0, 0.0], [c[0][0], 0.0]]


def normal_cities() -> list[dict]:
    t = pdf_text(get(REPORT, CACHE / "imd" / "pr_804.pdf", min_bytes=10**6))
    t = t[t.find("Table-2: Normal monsoon onset"):]
    rows = []
    for m in re.finditer(r"^([A-Z][A-Za-z .()-]+?),\s*([A-Za-z &]+?)\s+(\d\d-[A-Z][a-z]{2})\s+(\d\d-[A-Z][a-z]{2})\b", t, re.M):
        city, state, _old, new = m.groups()
        rows.append({"city": city.strip(), "state": state.strip(), "normal": new})
    # de-duplicate (the table lists Jagdalpur twice); keep the first
    seen, out = set(), []
    for r in rows:
        if r["city"] not in seen:
            seen.add(r["city"])
            out.append(r)
    return out


def to_date(dm: str) -> str:
    d = date(2026, ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].index(dm[3:6]) + 1, int(dm[:2]))
    return d.isoformat()


def main() -> None:
    raw = nlm_strings()
    lines, last = [], None
    for d in sorted(raw):
        if raw[d] == last:   # "continues to pass through" the same places: not a new position
            continue
        last = raw[d]
        pts, skipped = [], []
        for tok in tokens(raw[d]):
            p, kind = point_of(tok)
            (pts.append(p) if p else skipped.append(tok))
        if lines and pts == lines[-1]["coords"]:   # same places, different spelling
            continue
        lines.append({"date": d, "text": raw[d], "coords": pts, "unlocated": skipped})
    print(f"{len(raw)} days with an NLM statement, {len(lines)} distinct positions")

    covered = [(ln["date"], make_valid(Polygon(close_ring(ln["coords"]))).buffer(ON_LINE_DEG))
               for ln in lines if len(ln["coords"]) > 1]

    cities = []
    for r in normal_cities():
        p = geocode(r["city"], r["state"])
        if not p:
            cities.append({**r, "normal": to_date(r["normal"]), "lonlat": None, "arrived": None})
            continue
        pt = Point(p)
        arrived = next((d for d, poly in covered if poly.contains(pt)), None)
        if arrived is None or arrived > COVERED_ALL.isoformat():
            arrived = COVERED_ALL.isoformat()
        nd = to_date(r["normal"])
        cities.append({"city": r["city"], "state": r["state"], "lonlat": p, "normal": nd, "arrived": arrived,
                       "days_late": (date.fromisoformat(arrived) - date.fromisoformat(nd)).days})

    write_json("onset_2026.json", {
        "kerala": {"onset": "2026-06-04", "normal": "2026-06-01"},
        "all_india": {"covered": COVERED_ALL.isoformat(), "normal": "2026-07-08"},
        "lines": lines, "cities": cities,
        "sources": {"nlm": LIST, "normals": REPORT,
                    "season": "https://mausam.imd.gov.in/Forecast/marquee_data/Salient_Features_SW_MONSOON%20_2026_30_sep.pdf"},
    })
    unl = sorted({u for ln in lines for u in ln["unlocated"]})
    print("cities:", len(cities), "unlocated NLM places:", unl or "none")


if __name__ == "__main__":
    main()
