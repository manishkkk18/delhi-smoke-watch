"""Step 1: district boundaries.

geoBoundaries gbOpen IND ADM2 (2021, LGD-based, 736 districts, ODbL 1.0). The file has
no state column, so each district gets the state (geoBoundaries ADM1, current states and UTs)
containing its interior point. Names are stored without diacritics.

Outputs scripts/.cache/districts_full.geojson (full detail, for rainfall aggregation).
The light TopoJSON for the browser is made by `simplify.mjs` (mapshaper).
"""
from __future__ import annotations

import json

from shapely.geometry import mapping, shape

import unicodedata

from common import CACHE, get, slug


def ascii_name(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().strip()

GB = "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND"


def main() -> None:
    adm2 = json.loads(get(f"{GB}/ADM2/geoBoundaries-IND-ADM2.geojson", CACHE / "gb_adm2.geojson", min_bytes=10**6).read_text("utf-8"))
    adm1 = json.loads(get(f"{GB}/ADM1/geoBoundaries-IND-ADM1.geojson", CACHE / "gb_adm1.geojson", min_bytes=10**5).read_text("utf-8"))
    states = [(ascii_name(f["properties"]["shapeName"]), shape(f["geometry"])) for f in adm1["features"]]

    feats, seen = [], {}
    for f in adm2["features"]:
        g = shape(f["geometry"])
        if not g.is_valid:
            g = g.buffer(0)
        name = ascii_name(f["properties"]["shapeName"])
        p = g.representative_point()
        st = next((s for s, sg in states if sg.contains(p)), None)
        if st is None:  # coastal slivers: nearest state
            st = min(states, key=lambda s: s[1].distance(p))[0]
        base = f"{slug(st)}--{slug(name)}"
        seen[base] = seen.get(base, 0) + 1
        did = base if seen[base] == 1 else f"{base}-{seen[base]}"
        feats.append({"type": "Feature",
                      "properties": {"id": did, "name": name, "gb_state": st, "gb_id": f["properties"]["shapeID"]},
                      "geometry": mapping(g)})
    out = CACHE / "districts_full.geojson"
    out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}), "utf-8")
    print(f"{len(feats)} districts -> {out}")


if __name__ == "__main__":
    main()
