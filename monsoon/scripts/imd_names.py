"""Step 3: match IMD district names to geoBoundaries districts.

IMD lists 740 meteorological districts (2026); geoBoundaries has 735 (2021 LGD). Names
are matched automatically (normalised spelling, same state), then by the explicit table
in name_overrides.csv (hand-checked). Anything left is written as unmatched: never guessed.

Output: monsoon/data/name_mapping.csv  (imd_name, imd_group, district_id, map_name, method)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from common import CACHE, DATA, SCRIPTS, norm_name
from imd_pdf import parse

# IMD group header (subdivision or state) -> geoBoundaries ADM1 names it can belong to.
GROUP_STATES = {
    "ANDAMAN & NICOBAR ISLANDS": ["Andaman and Nicobar Islands"],
    "ARUNACHAL PRADESH": ["Arunachal Pradesh"], "ASSAM": ["Assam"], "MEGHALAYA": ["Meghalaya"],
    "NMMT": ["Nagaland", "Manipur", "Mizoram", "Tripura"], "MIZORAM": ["Mizoram"], "MANIPUR": ["Manipur"],
    "TRIPURA": ["Tripura"], "NAGALAND": ["Nagaland"], "SHWB & SIKKIM": ["West Bengal", "Sikkim"],
    "WEST BENGAL": ["West Bengal"], "SIKKIM": ["Sikkim"], "GANGETIC WEST BENGAL": ["West Bengal"],
    "ODISHA": ["Odisha"], "JHARKHAND": ["Jharkhand"], "BIHAR": ["Bihar"],
    "UTTAR PRADESH": ["Uttar Pradesh"], "WEST UTTAR PRADESH": ["Uttar Pradesh"], "EAST UTTAR PRADESH": ["Uttar Pradesh"],
    "UTTARAKHAND": ["Uttarakhand"], "DELHI AND HARYANA AND CHANDIGARH": ["Haryana", "Delhi", "Chandigarh"],
    "HARYANA": ["Haryana"], "DELHI (UT)": ["Delhi"], "CHANDIGARH (UT)": ["Chandigarh"], "PUNJAB": ["Punjab"],
    "HIMACHAL PRADESH": ["Himachal Pradesh"], "JAMMU & KASHMIR AND LADAKH": ["Jammu and Kashmir", "Ladakh"],
    "JAMMU & KASHMIR (UT)": ["Jammu and Kashmir"], "LADAKH (UT)": ["Ladakh"],
    "RAJASTHAN": ["Rajasthan"], "EAST RAJASTHAN": ["Rajasthan"], "WEST RAJASTHAN": ["Rajasthan"],
    "MADHYA PRADESH": ["Madhya Pradesh"], "WEST MADHYA PRADESH": ["Madhya Pradesh"], "EAST MADHYA PRADESH": ["Madhya Pradesh"],
    "GUJARAT": ["Gujarat"], "GUJARAT REGION": ["Gujarat"], "SAURASHTRA & KUTCH": ["Gujarat"],
    "DADRA & NAGAR HAVELI AND DAMAN & DIU (UT)": ["Dadra and Nagar Haveli and Daman and Diu"],
    "KONKAN & GOA": ["Maharashtra", "Goa"], "MAHARASHTRA": ["Maharashtra"], "GOA": ["Goa"],
    "MADHYA MAHARASHTRA": ["Maharashtra"], "MARATHWADA": ["Maharashtra"], "VIDARBHA": ["Maharashtra"],
    "CHHATTISGARH": ["Chhattisgarh"], "ANDHRA PRADESH": ["Andhra Pradesh"],
    "COASTAL ANDHRA PRADESH & YANAM": ["Andhra Pradesh", "Puducherry"], "PUDUCHERRY (UT)": ["Puducherry"],
    "RAYALASEEMA": ["Andhra Pradesh"], "TELANGANA": ["Telangana"],
    "TAMILNADU & PUDUCHERRY & KARAIKAL": ["Tamil Nadu", "Puducherry"], "TAMILNADU": ["Tamil Nadu"],
    "COASTAL KARNATAKA": ["Karnataka"], "NORTHERN INTERIOR KARNATAKA": ["Karnataka"],
    "SOUTHERN INTERIOR KARNATAKA": ["Karnataka"], "KERALA": ["Kerala"], "LAKSHADWEEP": ["Lakshadweep"],
}


def main(pdf: Path | None = None) -> None:
    pdf = pdf or sorted((CACHE / "imd").glob("district_dist_*.pdf"))[-1]
    imd = parse(pdf)["rows"]
    gb = json.loads((CACHE / "districts_full.geojson").read_text("utf-8"))["features"]
    gbp = [f["properties"] for f in gb]
    overrides = {}
    ov = SCRIPTS / "name_overrides.csv"
    if ov.exists():
        for r in csv.DictReader(ov.open(encoding="utf-8")):
            overrides[(r["imd_group"], r["imd_name"])] = r
    ids = {p["id"] for p in gbp}
    bad = [(k, r[c]) for k, r in overrides.items() for c in ("district_id", "parent_id") if r[c] and r[c] not in ids]
    if bad:
        raise SystemExit(f"name_overrides.csv has ids not on the map: {bad}")

    used, out = set(), []
    for r in imd:
        key = (r["state"], r["name"])
        states = GROUP_STATES.get(r["state"], [])
        did, method, parent, note = None, "unmatched", "", ""
        if key in overrides:
            o = overrides[key]
            did, parent, note = o["district_id"] or None, o["parent_id"], o["note"]
            method = "manual" if did else "no-polygon"
        else:
            cands = [p for p in gbp if norm_name(p["name"]) == norm_name(r["name"]) and p["gb_state"] in states]
            if len(cands) == 1:
                did, method = cands[0]["id"], "auto"
        p = next((p for p in gbp if p["id"] == did), None)
        out.append({"imd_name": r["name"], "imd_group": r["state"], "district_id": did or "",
                    "map_name": p["name"] if p else "", "method": method, "parent_id": parent, "note": note,
                    "display_state": (p or next((q for q in gbp if q["id"] == parent), {})).get("gb_state", "")})
        if did:
            used.add(did)

    path = DATA / "name_mapping.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    # Search aliases for the site: IMD's spelling and present-day names -> map district.
    aliases = []
    for o in out:
        target = o["district_id"] or o["parent_id"]
        if not target:
            continue
        a = {"q": o["imd_name"].title(), "id": target}
        if not o["district_id"]:
            a["note"] = o["note"]
        if norm_name(a["q"]) != norm_name(next(p["name"] for p in gbp if p["id"] == target)) or "note" in a:
            aliases.append(a)
    (DATA / "aliases.json").write_text(json.dumps(aliases, separators=(",", ":")), "utf-8")
    print(f"{len(aliases)} search aliases")
    unmatched = [o for o in out if o["method"] == "unmatched"]
    orphans = [p for p in gbp if p["id"] not in used]
    print(f"{len(out)} IMD districts: {sum(o['method']=='auto' for o in out)} auto, "
          f"{sum(o['method']=='manual' for o in out)} manual, {sum(o['method']=='no-polygon' for o in out)} no polygon (new district), "
          f"{len(unmatched)} unmatched; {len(orphans)} map districts with no IMD row")
    for o in unmatched:
        print("  IMD unmatched:", o["imd_group"], "|", o["imd_name"])
    for p in orphans:
        print("  map orphan:", p["gb_state"], "|", p["name"], "|", p["id"])


if __name__ == "__main__":
    main()
