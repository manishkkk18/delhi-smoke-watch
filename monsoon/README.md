# The Monsoon, District by District

**Did the 2026 monsoon show up for your district?** A season retrospective: weekly
cumulative rainfall against normal for every district, when the rains arrived, and what
it meant for kharif sowing.

Live: https://manishkkk18.github.io/delhi-smoke-watch/monsoon/

This is a standalone static site (HTML + CSS + D3, no build step). It shares nothing with
the Smoke Watch app in `web/`; the only link between them is that
`web/scripts/deploy-pages.sh` copies this folder into the published site at `/monsoon/`,
so it goes out with every deploy of the main site.

```
monsoon/
  index.html  favicon.svg  og.png
  css/monsoon.css            all styling (tokens at the top)
  js/                        main.js, map.js, district.js, onset.js, sowing.js, common.js
  vendor/                    d3 7.9.0, topojson-client 3.1.0 (pinned copies)
  data/                      static JSON the page reads (written by scripts/)
  scripts/                   the data pipeline (Python)
```

## Refreshing the data

Needs Python 3.11+ and Node (for `npx mapshaper`). From `monsoon/scripts/`:

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # macOS/Linux: .venv/bin/pip
.venv/Scripts/python build_boundaries.py   # 1. geoBoundaries districts + states
.venv/Scripts/python fetch_grid.py         # 2. IMD gridded rain 1971-2025 + 2026 real-time (~1.4 GB, slow server; resumable)
.venv/Scripts/python imd_names.py          # 3. IMD district names -> map districts (+ search aliases)
.venv/Scripts/python build_topo.py         # 4. simplified TopoJSON for the browser
.venv/Scripts/python aggregate.py          # 5. district / state / India series and weekly departures
.venv/Scripts/python onset.py              # 6. monsoon advance lines and city arrival dates
.venv/Scripts/python sowing.py             # 7. kharif sowing from PIB releases
.venv/Scripts/python verify.py             # 8. compare with IMD's published figures -> data/meta.json
```

Downloads are cached in `scripts/.cache/` (gitignored), so re-runs only fetch what's
missing. Then commit `monsoon/data/` and deploy the main site as usual (`npm run deploy`
in `web/`, or let the scheduled Refresh workflow do it).

**For a new season** (e.g. 2027): set `THIS_YEAR` and `HISTORY` in `aggregate.py`,
`START`/`END`/`COVERED_ALL` in `onset.py`, the release ids in `sowing.py`, add the new
IMD "Salient Features" PDF and Wayback snapshots to `scripts/.cache/imd/`, and update the
hero/OG text in `index.html`.

### Before you trust a refresh

`verify.py` prints the checks shown on the page:

* all-India season and monthly % of normal against IMD's Salient Features report;
* district departures against IMD's own (station-based) district table, from Wayback
  Machine snapshots of `DISTRICT_RAINFALL_DISTRIBUTION_COUNTRY_INDIA_cd.pdf`.

If these drift apart, look before publishing.

Results for 2026 (snapshot to 24 Sep, 697 districts with matching boundaries): 97% of
districts are within one IMD category of IMD's own figure, the median gap is 10 percentage
points and the rank correlation is 0.74. All-India comes out at 90% against IMD's 87%: the
rain that fell agrees (756 mm vs 759 mm), but the grid's 1971–2020 normal (840 mm) is below
IMD's LPA (868.6 mm), so percentages here run 2–3 points wetter. The page leads with IMD's
official 87%.

Where few gauges fed the grid (northeastern hills, Ladakh, parts of J&K) the gridded normal
can be far off: 19 districts are two or more categories from IMD's figure. `verify.py`
writes them to `data/imd_check.json`; the map gives them a dashed outline and their card
leads with IMD's station-based number instead of the gridded one.

## Sources

| What | Source | Notes |
|---|---|---|
| District rainfall, normals, history | IMD Pune 0.25° gridded daily rainfall (Pai et al. 2014): [final 1901–2025](https://imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html), real-time 2026 | IMD's weekly district PDFs are overwritten weekly and not archived, so they can't give a 2026 week-by-week series. Normal = 1971–2020. |
| Official season totals | [IMD Salient Features of the 2026 SW Monsoon](https://mausam.imd.gov.in/Forecast/marquee_data/Salient_Features_SW_MONSOON%20_2026_30_sep.pdf) | headline 87% of LPA |
| District cross-check | IMD district rainfall PDF via the Wayback Machine | verification only |
| Monsoon advance | IMD daily [press releases](https://internal.imd.gov.in/pages/press_release_mausam.php) ("Northern Limit of Monsoon passes through …") | places geocoded once with OpenStreetMap Nominatim, cached in `scripts/geocode_cache.json` |
| Normal onset dates | [IMD CRS Research Report 3/2020](https://internal.imd.gov.in/press_release/20200515_pr_804.pdf), Table 2 (1961–2019 normals, 135 cities parsed) | IMD's normal isochrones exist only as a map figure, so they are shown as city dates |
| Kharif sowing | Agriculture Ministry weekly area reports via PIB ([4 Sep 2026](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2307791)) | the state-wise table (agriwelfare.gov.in / UPAG) was unreachable; only states each release names are used, others are missing, not zero |
| Boundaries | [geoBoundaries](https://www.geoboundaries.org/) gbOpen IND ADM2 (2021, LGD), ODbL 1.0 | simplified with mapshaper 0.7.101 |

## District names

IMD lists 740 districts; the 2021 map has 735. `scripts/name_overrides.csv` is the
hand-checked table for spellings, renamings (Allahabad → Prayagraj, Osmanabad → Dharashiv)
and districts created after 2021, which have no shape of their own and point to the
district they were carved from (`parent_id`). The full result is `data/name_mapping.csv`;
`imd_names.py` stops with an error if an id in the overrides doesn't exist on the map.

## Design notes

Light "monsoon paper" theme: warm paper, ink-blue type, teal for rain, ochre/brown for
deficit. Fraunces (headlines) and Source Sans 3 (interface). The map uses IMD's six
categories on a diverging brown–teal scale centred on a pale "normal"; it was checked with
a colour-vision simulator (every pair of colours stays distinguishable, worst ΔE 15.7), and
"no rain" and "no data" also carry hatching. D3 + SVG rather than a tile map: 735 polygons
recoloured per week is light work, there's no basemap to load, and pinch-zoom works on phones.
