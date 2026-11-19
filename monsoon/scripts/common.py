"""Shared paths and helpers for the Monsoon pipeline."""
from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path

import requests

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent                  # monsoon/
DATA = ROOT / "data"                   # what the site reads
CACHE = SCRIPTS / ".cache"             # raw downloads (gitignored, re-fetchable)
DATA.mkdir(exist_ok=True)
CACHE.mkdir(exist_ok=True)

UA = {"User-Agent": "monsoon-district-viz/1.0 (data pipeline)"}

# IMD's category buckets for % departure from normal (same as IMD's district maps).
CATS = ["NR", "LD", "D", "N", "E", "LE"]


def category(dep: float | None, actual: float | None = None) -> str | None:
    if dep is None:
        return None
    if actual is not None and actual == 0:
        return "NR"
    if dep <= -99.5:
        return "NR"
    if dep <= -59.5:
        return "LD"
    if dep <= -19.5:
        return "D"
    if dep < 19.5:
        return "N"
    if dep < 59.5:
        return "E"
    return "LE"


def get(url: str, dest: Path, *, method: str = "GET", data=None, retries: int = 4, min_bytes: int = 1) -> Path:
    """Download url to dest unless it is already cached; retries with backoff."""
    if dest.exists() and dest.stat().st_size >= min_bytes:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for i in range(retries):
        try:
            r = requests.request(method, url, data=data, headers=UA, timeout=600)
            r.raise_for_status()
            if len(r.content) < min_bytes:
                raise ValueError(f"{url}: only {len(r.content)} bytes")
            tmp = dest.with_suffix(dest.suffix + ".part")
            tmp.write_bytes(r.content)
            tmp.replace(dest)
            return dest
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"download failed: {url}: {last}")


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def norm_name(s: str) -> str:
    """Loose key for matching district names across sources."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    s = s.replace("&", " AND ")
    s = re.sub(r"\b(DISTRICT|DIST|DT)\b", " ", s)
    return re.sub(r"[^A-Z0-9]+", "", s)


def write_json(name: str, obj) -> Path:
    p = DATA / name
    # allow_nan=False: NaN is not valid JSON, so a missing value must already be None
    p.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(f"wrote {p.relative_to(ROOT)} ({p.stat().st_size/1024:.0f} KB)")
    return p
