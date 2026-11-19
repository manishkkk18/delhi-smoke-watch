"""Step 7: kharif sowing, from the Agriculture Ministry's weekly PIB releases.

The ministry's state-wise area table (agriwelfare.gov.in / UPAG) could not be reached
(pages missing, UPAG returning 502 in Nov 2026), so this uses what PIB publishes:
* the all-India crop table (normal area, this year, same week last year), and
* the states each release NAMES as the major increases / decreases vs last year, per crop
  group, with the change in lakh hectares. States not named are simply not reported: we
  never set them to zero.

Latest release found: area as on 4 Sep 2026 (PIB PRID 2307791, posted 8 Sep 2026).
Output: data/sowing_2026.json
"""
from __future__ import annotations

import html
import re

from common import CACHE, get, write_json

RELEASES = {  # area-as-on date -> PIB release id
    "2026-08-21": 2302874,
    "2026-08-28": 2305161,
    "2026-09-04": 2307791,
}
URL = "https://www.pib.gov.in/PressReleasePage.aspx?PRID={}"
GROUPS = {"Rice": "Rice", "Pulses": "Pulses", "Shri Anna": "Coarse cereals", "Shree Anna": "Coarse cereals",
          "Oilseeds": "Oilseeds", "Sugarcane": "Sugarcane", "Cotton": "Cotton", "Jute": "Jute & mesta"}
STATES = {"Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
          "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
          "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
          "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Jammu and Kashmir", "Jammu & Kashmir"}
ITEM = re.compile(r"([A-Z][A-Za-z&. ]+?)\s*\((\d+(?:\.\d+)?)\s*lakh ha\)")


def text_of(pid: int) -> str:
    s = get(URL.format(pid), CACHE / "pib" / f"{pid}.html", min_bytes=10**4).read_text("utf-8", "ignore")
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)))


def parse(t: str) -> dict:
    # crop-wise all-India table: "<n> <Crop> normal this_year last_year change"
    totals = {}
    for m in re.finditer(r"\b(Rice|Pulses|Shri Anna\s*&\s*Coarse Cereals|Shree Anna\s*&\s*Coarse Cereals|Oilseeds|Sugarcane|Jute\s*&\s*Mesta|Cotton|Grand Total)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(-?\d+\.\d+)", t):
        name = m.group(1)
        key = next((v for k, v in GROUPS.items() if name.startswith(k)), "Total" if name == "Grand Total" else name)
        totals.setdefault(key, {"normal": float(m.group(2)), "this_year": float(m.group(3)),
                                "last_year": float(m.group(4)), "change": float(m.group(5))})
    # narrative per crop group: sections start "<Group>: About ..."; only the first copy of the text
    end = t.find("*****")
    narrative = t[: end if end > 0 else len(t)]
    heads = list(re.finditer(r"(Rice|Pulses|Sh(?:ri|ree) Anna & Coarse Cereals|Oilseeds|Sugarcane|Jute & Mesta|Cotton)\s*:\s*About", narrative))
    states: dict[str, dict[str, float]] = {}
    unparsed = []
    for h, nxt in zip(heads, heads[1:] + [None]):
        group = next(v for k, v in GROUPS.items() if h.group(1).startswith(k))
        body = narrative[h.start(): nxt.start() if nxt else len(narrative)]
        body = body[: body.find("Overall")] if "Overall" in body else body   # the summary repeats names
        for sent in re.split(r"(?<=\.)\s+(?=[A-Z])|On the other hand,", body):
            low = sent.lower()
            if "reported in" not in low and "reported mainly in" not in low:
                continue
            sign = -1 if ("decrease" in low or "lower" in low or "decline" in low) else (1 if ("increase" in low or "higher" in low) else 0)
            if not sign:
                continue
            at = low.find("reported in") if "reported in" in low else low.find("reported mainly in")
            for name, val in ITEM.findall(sent[at:]):
                name = re.sub(r"^(reported (?:mainly )?in|the states of|states of|in|and)\s+", "", name.strip(), flags=re.I).strip()
                if name not in STATES:
                    unparsed.append(f"{group}: {name} ({val})")
                    continue
                states.setdefault(name, {})[group] = round(sign * float(val), 2)
    return {"totals": totals, "states": states, "unparsed": unparsed}


def main() -> None:
    out = {"releases": {}, "source_note": __doc__.split("\n\n")[1].strip()}
    for d, pid in RELEASES.items():
        r = parse(text_of(pid))
        r["url"] = URL.format(pid)
        out["releases"][d] = r
        print(d, "totals:", list(r["totals"]), "| states named:", len(r["states"]), "| unparsed:", r["unparsed"])
    out["latest"] = max(RELEASES)
    write_json("sowing_2026.json", out)
    for s, v in sorted(out["releases"][out["latest"]]["states"].items()):
        print(f"  {s:20s} {v}")


if __name__ == "__main__":
    main()
