"""Load the three public demonstration scenarios with dates relative to today."""

from __future__ import annotations

import copy
import datetime as dt
import json
from functools import lru_cache
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent.parent / "data" / "demo"
DEMO_KEYS = ("scenario_a", "scenario_b", "scenario_c")


@lru_cache(maxsize=None)
def _read(key: str) -> dict:
    if key not in DEMO_KEYS:
        raise KeyError(key)
    return json.loads((DEMO_DIR / f"{key}.json").read_text(encoding="utf-8"))


def demo_titles() -> dict[str, str]:
    return {k: _read(k)["_demo"]["title"] for k in DEMO_KEYS}


def demo_summary(key: str) -> str:
    return _read(key)["_demo"]["summary"]


def load_demo(key: str, today: dt.date) -> dict:
    """Return a raw plan for a demo with the event shifted to a future date."""
    raw = copy.deepcopy(_read(key))
    meta = raw.pop("_demo")
    date = today + dt.timedelta(days=meta["event_min_days"])
    if meta.get("event_weekday") is not None:
        date += dt.timedelta(days=(meta["event_weekday"] - date.weekday()) % 7)
    raw["event"]["date"] = date.isoformat()
    raw["marketing"]["earliest_start"] = today.isoformat()
    if meta.get("alternate_offset_days"):
        raw["rain"]["alternate_date"] = (date + dt.timedelta(days=meta["alternate_offset_days"])).isoformat()
    for rec in raw.get("provenance", {}).values():
        rec.setdefault("as_of_date", "2026-09-25" if rec.get("source_kind") == "brief"
                       else today.isoformat())
    return raw
