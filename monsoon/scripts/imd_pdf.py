"""Parse IMD's "DISTRICT RAINFALL DISTRIBUTION" PDF (Hydromet Division, New Delhi).

Each page lists state headers, then numbered district rows with two column groups:
DAY (actual, normal, %dep, cat) and PERIOD (actual, normal, %dep, cat). Missing values
are blank and the category reads ND. We keep only the PERIOD (cumulative) columns.
"""
from __future__ import annotations

import re
from pathlib import Path

import pypdf

NUM = r"(-?\d+(?:\.\d+)?)"
CAT = r"(LE|E|N|D|LD|NR|ND)"
# PERIOD group = last four tokens; actual / normal / dep can be blank when ND.
# Older (July/August) PDFs print the departure without a "%" sign.
TAIL = re.compile(rf"(?:{NUM}\s+)?(?:{NUM}\s+)?(?:(-?\d+)%?\s+)?{CAT}\s*$")


def parse(pdf: Path) -> dict:
    text = "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(str(pdf)).pages)
    period = re.search(r"PERIOD:\s*(\d\d-\d\d-\d{4})\s*to\s*(\d\d-\d\d-\d{4})", text)
    rows, state = [], None
    for line in text.splitlines():
        line = line.rstrip()
        m = re.match(r"^\s*(\d+)\s+(.+)$", line)
        is_district = bool(m) and not line.startswith(" ")
        body = m.group(2) if is_district else line.strip()
        # Split off the PERIOD group (the last occurrence of a CAT token).
        cats = list(re.finditer(rf"\b{CAT}\b", body))
        if len(cats) < 2:
            continue
        name_end = None
        # the name ends where the first numeric token / first CAT group begins
        first = re.search(rf"\s(?:-?\d+(?:\.\d+)?|{CAT})(?:\s|%|$)", " " + body)
        name_end = first.start() - 1 if first else None
        name = body[:name_end].strip() if name_end else body
        tail = body[cats[-2].end():]
        tm = TAIL.search(tail.strip())
        if not tm:
            continue
        a, n, dep, cat = tm.groups()
        rec = {"name": name, "actual": float(a) if a else None, "normal": float(n) if n else None,
               "dep": int(dep) if dep is not None else None, "cat": cat}
        if is_district:
            rows.append({**rec, "state": state})
        elif re.match(r"[A-Za-z]", name):
            state = name  # a subdivision or state header (wrapped numeric lines are skipped)
    return {"from": period.group(1) if period else None, "to": period.group(2) if period else None, "rows": rows}


if __name__ == "__main__":
    import json
    import sys

    r = parse(Path(sys.argv[1]))
    print(r["from"], r["to"], len(r["rows"]))
    print(json.dumps(r["rows"][:5], indent=1))
    print(sorted({x["state"] for x in r["rows"]}))
