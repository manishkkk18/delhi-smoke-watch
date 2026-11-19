"""Step 4: the light TopoJSON the browser draws (mapshaper, via npx; needs Node).

Layers: `districts` (id, name, state) and `states` (dissolved from districts).
Simplified with Visvalingam, keeping every district (keep-shapes), ~300 KB.
"""
from __future__ import annotations

import json
import shutil
import subprocess

from common import CACHE, DATA

MAPSHAPER = "mapshaper@0.7.101"  # pinned


def main() -> None:
    src = json.loads((CACHE / "districts_full.geojson").read_text("utf-8"))
    for f in src["features"]:
        p = f["properties"]
        if p["name"].upper() == "DATA NOT AVAILABLE":  # unnamed polygon in the source
            p["name"] = "Unnamed area"
        f["properties"] = {"id": p["id"], "name": p["name"], "state": p["gb_state"]}
    tmp = CACHE / "districts_props.geojson"
    tmp.write_text(json.dumps(src), "utf-8")
    out = DATA / "districts.topo.json"
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    cmd = [npx, "-y", MAPSHAPER, "-i", str(tmp), "name=districts",
           "-simplify", "visvalingam", "weighted", "2.5%", "keep-shapes",
           "-clean",
           "-dissolve", "state", "+", "name=states",
           "-o", "format=topojson", "quantization=2e4", "target=districts,states", str(out)]
    subprocess.run(cmd, check=True)
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
