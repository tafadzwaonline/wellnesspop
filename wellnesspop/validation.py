"""Validate raw plan dictionaries (forms, demos, imports) into an immutable ``PlanInput``.

Validation never mutates its input. It returns structured issues rather than UI messages.
"""

from __future__ import annotations

import copy
import datetime as dt
import math
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from wellnesspop import schema as S

TOLERANCE = 1e-6


@dataclass(frozen=True)
class Issue:
    path: str
    message: str
    severity: str = "error"  # error | warning

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class PlanValidationError(ValueError):
    def __init__(self, issues: list[Issue]):
        self.issues = issues
        super().__init__("; ".join(str(i) for i in issues if i.severity == "error"))


class _Collector:
    def __init__(self) -> None:
        self.issues: list[Issue] = []

    def error(self, path: str, message: str) -> None:
        self.issues.append(Issue(path, message, "error"))

    def warn(self, path: str, message: str) -> None:
        self.issues.append(Issue(path, message, "warning"))

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)


_MISSING = object()
_TRUE = {"true", "yes", "y", "1"}
_FALSE = {"false", "no", "n", "0"}


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    try:  # pandas NaT / NA
        import pandas as pd

        return value is pd.NaT or value is pd.NA
    except ImportError:  # pragma: no cover
        return False


def coerce(spec: S.FieldSpec, value: Any, path: str, c: _Collector) -> Any:
    """Coerce one value according to its spec. Records an error and returns _MISSING on failure."""
    if _is_blank(value):
        if spec.nullable:
            return None
        if spec.kind == "list_enum":
            return ()
        c.error(path, "is required")
        return _MISSING
    kind = spec.kind
    try:
        if kind == "str":
            if not isinstance(value, (str, int, float)) or isinstance(value, bool):
                raise ValueError("must be text")
            out = str(value).strip()
            if spec.max_len and len(out) > spec.max_len:
                raise ValueError(f"must be at most {spec.max_len} characters")
            return out
        if kind in ("int",):
            if isinstance(value, bool):
                raise ValueError("must be a whole number")
            if isinstance(value, str):
                value = float(value.strip().replace(",", ""))
            num = float(value)
            if not math.isfinite(num) or num != int(num):
                raise ValueError("must be a whole number")
            out = int(num)
            _check_range(spec, out)
            return out
        if kind in ("float", "money", "signed_money", "rate"):
            if isinstance(value, bool):
                raise ValueError("must be a number")
            if isinstance(value, str):
                value = value.strip().replace(",", "").replace("$", "")
            num = float(value)
            if not math.isfinite(num):
                raise ValueError("must be a finite number")
            if kind == "rate" and not 0 <= num <= 1:
                raise ValueError("must be a fraction between 0 and 1 (e.g. 0.2 for 20%)")
            if kind == "money" and num < 0:
                raise ValueError("must not be negative")
            _check_range(spec, num)
            return num
        if kind == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)) and value in (0, 1):
                return bool(value)
            text = str(value).strip().lower()
            if text in _TRUE:
                return True
            if text in _FALSE:
                return False
            raise ValueError("must be true or false")
        if kind == "date":
            if isinstance(value, dt.datetime):
                return value.date()
            if isinstance(value, dt.date):
                return value
            if hasattr(value, "to_pydatetime"):
                return value.to_pydatetime().date()
            return dt.date.fromisoformat(str(value).strip()[:10])
        if kind == "time":
            if isinstance(value, dt.time):
                return value.replace(second=0, microsecond=0)
            text = str(value).strip()
            return dt.time.fromisoformat(text if len(text) > 5 else text.zfill(5))
        if kind == "enum":
            text = str(value).strip().lower()
            matches = [c for c in spec.choices if c.lower() == text]
            if not matches:
                raise ValueError(f"must be one of: {', '.join(spec.choices)}")
            return matches[0]
        if kind == "list_enum":
            items = value
            if isinstance(value, str):
                items = [p for p in value.replace(";", ",").split(",")]
            if not isinstance(items, (list, tuple)):
                raise ValueError("must be a list")
            out: list[str] = []
            for item in items:
                text = str(item).strip().lower()
                if not text:
                    continue
                if text not in spec.choices:
                    raise ValueError(f"contains unknown value '{text}'")
                if text not in out:
                    out.append(text)
            return tuple(out)
        if kind == "tz":
            text = str(value).strip()
            ZoneInfo(text)
            return text
    except (ValueError, TypeError, ZoneInfoNotFoundError) as exc:
        msg = str(exc) if str(exc) and "could not convert" not in str(exc) else "invalid value"
        if isinstance(exc, ZoneInfoNotFoundError):
            msg = "is not a valid IANA timezone"
        c.error(path, msg)
        return _MISSING
    raise AssertionError(f"unknown kind {kind}")


def _check_range(spec: S.FieldSpec, num: float) -> None:
    if spec.min is not None and num < spec.min:
        raise ValueError(f"must be at least {spec.min:g}")
    if spec.max is not None and num > spec.max:
        raise ValueError(f"must be at most {spec.max:g}")


def _validate_scalars(raw: dict, c: _Collector) -> dict:
    out: dict = {}
    for key in raw:
        if key not in S.TOP_LEVEL_KEYS:
            c.error(key, "is not a recognised field")
    groups = {p.split(".")[0] for p in S.SPEC_BY_PATH if "." in p}
    for group in groups:
        allowed = {p.split(".", 1)[1] for p in S.SPEC_BY_PATH if p.startswith(group + ".")}
        sub = raw.get(group)
        if sub is None:
            c.error(group, "section is missing")
            continue
        if not isinstance(sub, dict):
            c.error(group, "must be a section of fields")
            continue
        for key in sub:
            if key not in allowed:
                c.error(f"{group}.{key}", "is not a recognised field")
    for spec in S.SCALAR_SPECS:
        value = S.get_path(raw, spec.path, _MISSING)
        if value is _MISSING:
            if spec.nullable:
                value = None
            else:
                c.error(spec.path, "is required")
                continue
        coerced = coerce(spec, value, spec.path, c)
        if coerced is not _MISSING:
            S.set_path(out, spec.path, coerced)
    return out


def _validate_records(raw: dict, norm: dict, c: _Collector) -> None:
    duration = 1.25
    if "event" in norm and {"start_time", "end_time", "date"} <= set(norm["event"]):
        e = norm["event"]
        duration = max(
            (dt.datetime.combine(e["date"], e["end_time"])
             - dt.datetime.combine(e["date"], e["start_time"])).total_seconds() / 3600, 0)
    channels = tuple(S.get_path(norm, "marketing.channels", ()) or ("email",))
    for group, specs in S.RECORD_SPECS.items():
        rows = raw.get(group, _MISSING)
        if rows is None and group in S.NULLABLE_RECORD_GROUPS:
            norm[group] = None
            continue
        if rows is _MISSING:
            rows = []
        if not isinstance(rows, (list, tuple)):
            c.error(group, "must be a list of rows")
            continue
        allowed = {s.path for s in specs}
        seen: set[str] = set()
        out_rows = []
        for i, row in enumerate(rows):
            base = f"{group}[{i + 1}]"
            if not isinstance(row, dict):
                c.error(base, "must be a record")
                continue
            for key in row:
                if key not in allowed:
                    c.error(f"{base}.{key}", "is not a recognised column")
            defaults = S.record_defaults(group, duration_hours=duration, channels=channels)
            out: dict = {}
            for spec in specs:
                value = row.get(spec.path, _MISSING)
                if value is _MISSING or (_is_blank(value) and not spec.nullable
                                         and spec.path in defaults
                                         and spec.path not in ("label", "role", "name")):
                    value = defaults.get(spec.path)
                coerced = coerce(spec, value, f"{base}.{spec.path}", c)
                if coerced is not _MISSING:
                    out[spec.path] = coerced
            rid = out.get("id")
            if rid:
                if rid in seen:
                    c.error(f"{base}.id", f"duplicate ID '{rid}'")
                seen.add(rid)
            out_rows.append(out)
        norm[group] = out_rows


def _cross_checks(norm: dict, today: dt.date, c: _Collector) -> None:
    if c.has_errors:
        return
    ev, venue, att, ns = norm["event"], norm["venue"], norm["attendance"], norm["no_show"]
    if norm["schema_version"] != S.SCHEMA_VERSION:
        c.error("schema_version", f"unsupported schema version (expected {S.SCHEMA_VERSION})")
    if not ev["name"]:
        c.error("event.name", "is required")
    if not venue["name"]:
        c.error("venue.name", "is required")
    if ev["end_time"] <= ev["start_time"]:
        c.error("event.end_time", "must be after the start time (same-day events only)")
    local_today = S.today_in(ev["timezone"]) if today is None else today
    if ev["date"] < local_today and not ev["historical_ack"]:
        c.error("event.date", "is in the past; tick the historical-plan acknowledgment to keep it")
    if norm["marketing"]["earliest_start"] < local_today and not ev["historical_ack"]:
        c.error("marketing.earliest_start",
                "is in the past; tick the historical-plan acknowledgment to keep it")

    rain = norm["rain"]
    if ev["setting"] in ("outdoor", "hybrid") and not rain["has_rain_plan"]:
        c.warn("rain.has_rain_plan", "Outdoor or hybrid event without a rain plan")
    if rain["has_rain_plan"]:
        if rain["alternate_date"] is None and not rain["alternate_venue"]:
            c.error("rain.alternate_date", "Enter an alternate date or an alternate venue")
        if rain["alternate_date"] is not None and rain["alternate_date"] <= ev["date"]:
            c.error("rain.alternate_date", "must be after the event date")
    else:
        rain["alternate_date"] = None
        rain["alternate_venue"] = None

    cap = venue["capacity"]
    if norm["goals"]["target_attendance"] > cap:
        c.error("goals.target_attendance", "cannot exceed venue capacity")
    if venue["rental_advance"] > venue["rental_total"] + TOLERANCE:
        c.error("venue.rental_advance", "cannot exceed the rental total")
    if not att["low"] >= 0:
        c.error("attendance.low", "must not be negative")
    if not att["low"] <= att["likely"] <= att["high"]:
        c.error("attendance.likely", "registrations must satisfy low <= likely <= high")
    if att["high"] > cap:
        c.error("attendance.high", f"cannot exceed venue capacity ({cap})")
    if att["planned_peak"] is not None and att["planned_peak"] > cap:
        c.error("attendance.planned_peak", "cannot exceed venue capacity")
    _check_no_show("no_show", ns["low"], ns["mean"], ns["high"], ns["concentration"], c)

    weather = norm["weather"]
    if ev["setting"] == "indoor" and weather["cancellation_probability"] != 0:
        weather["cancellation_probability"] = 0.0
        c.warn("weather.cancellation_probability", "Indoor event: weather cancellation set to 0")

    for i, row in enumerate(norm["fixed_costs"]):
        base = f"fixed_costs[{i + 1}]"
        if not row["label"]:
            c.error(f"{base}.label", "is required")
        if row["uncertain"]:
            lo = row["low"] if row["low"] is not None else row["amount"]
            mo = row["mode"] if row["mode"] is not None else row["amount"]
            hi = row["high"] if row["high"] is not None else row["amount"]
            if not lo <= mo <= hi:
                c.error(f"{base}.mode", "uncertain cost must satisfy low <= mode <= high")
            row.update(low=lo, mode=mo, high=hi, amount=(lo + mo + hi) / 3)
        else:
            row.update(low=row["amount"], mode=row["amount"], high=row["amount"])

    for i, row in enumerate(norm["variable_costs"]):
        if not row["low"] <= row["mode"] <= row["high"]:
            c.error(f"variable_costs[{i + 1}].mode", "must satisfy low <= mode <= high")
        if not row["label"]:
            c.error(f"variable_costs[{i + 1}].label", "is required")

    tiers = norm["ticket_tiers"]
    weighted = [t for t in tiers if t["allocation"] == "weighted"]
    if not tiers:
        c.error("ticket_tiers", "at least one ticket tier is required (a free tier is allowed)")
    elif not weighted:
        c.error("ticket_tiers", "at least one weighted tier is required to absorb registrations")
    elif abs(sum(t["weight"] for t in weighted) - 1) > TOLERANCE:
        c.error("ticket_tiers",
                f"weighted tier shares must sum to 100% (currently "
                f"{sum(t['weight'] for t in weighted):.1%})")
    for i, t in enumerate(tiers):
        base = f"ticket_tiers[{i + 1}]"
        if not t["label"]:
            c.error(f"{base}.label", "is required")
        if t["allocation"] == "free_quota":
            if t["price"] != 0:
                c.error(f"{base}.price", "fixed free places must have price 0")
            if t["free_quota"] is None:
                c.error(f"{base}.free_quota", "is required for fixed free places")
            if t["billing_basis"] != "attended":
                c.error(f"{base}.billing_basis", "free places cannot be prepaid")
        else:
            t["free_quota"] = None
        override = [t["no_show_low"], t["no_show_mean"], t["no_show_high"]]
        if any(v is not None for v in override):
            if any(v is None for v in override):
                c.error(f"{base}.no_show_mean", "override needs low, mean and high together")
            else:
                if t["no_show_concentration"] is None:
                    t["no_show_concentration"] = ns["concentration"]
                _check_no_show(base, *override, t["no_show_concentration"], c)
        else:
            t["no_show_concentration"] = None
    quota_total = sum(t["free_quota"] or 0 for t in tiers)
    if quota_total > cap:
        c.error("ticket_tiers", "fixed free places exceed venue capacity")

    for i, r in enumerate(norm["additional_revenue"]):
        base = f"additional_revenue[{i + 1}]"
        if not r["label"]:
            c.error(f"{base}.label", "is required")
        if r["prepaid"] and r["quantity_basis"] != "fixed":
            c.error(f"{base}.prepaid",
                    "prepaid lines must use a fixed quantity (pre-sale quantities are not modeled)")

    for i, s in enumerate(norm["staffing"]):
        base = f"staffing[{i + 1}]"
        if not s["role"]:
            c.error(f"{base}.role", "is required")
        if s["coverage_ratio"] is not None and s["coverage_ratio"] <= 0:
            c.error(f"{base}.coverage_ratio", "must be positive")
        if s["volunteer"]:
            s["rate"] = 0.0

    for i, a in enumerate(norm["marketing_activities"] or []):
        if not a["name"]:
            c.error(f"marketing_activities[{i + 1}].name", "is required")


def _check_no_show(base: str, low: float, mean: float, high: float, k: float,
                   c: _Collector) -> None:
    if not low <= mean <= high:
        c.error(f"{base}.mean" if base == "no_show" else f"{base}.no_show_mean",
                "no-show rates must satisfy low <= mean <= high")
    elif high > low and not low < mean < high:
        c.error(f"{base}.mean" if base == "no_show" else f"{base}.no_show_mean",
                "mean must be strictly between low and high (or set all three equal)")
    if not k > 0:
        c.error(f"{base}.concentration", "must be positive")


def check_plan(raw: dict, today: dt.date | None = None) -> tuple[S.PlanInput | None, list[Issue]]:
    """Validate a raw plan. Returns (plan or None, issues)."""
    c = _Collector()
    if not isinstance(raw, dict):
        return None, [Issue("plan", "must be a dictionary")]
    raw = copy.deepcopy(raw)
    if raw.get("currency") not in (None, S.CURRENCY):
        c.error("currency", "only USD is supported; mixed currencies are rejected")
    norm = _validate_scalars(raw, c)
    _validate_records(raw, norm, c)
    _cross_checks(norm, today, c)
    if c.has_errors:
        return None, c.issues
    provenance = raw.get("provenance") or {}
    if not isinstance(provenance, dict):
        c.error("provenance", "must be a mapping")
        return None, c.issues
    return _build(norm, provenance), c.issues


def validate_plan(raw: dict, today: dt.date | None = None) -> S.PlanInput:
    plan, issues = check_plan(raw, today)
    if plan is None:
        raise PlanValidationError(issues)
    return plan


def _build(norm: dict, provenance: dict) -> S.PlanInput:
    groups = {name: cls(**norm[name]) for name, cls in S.GROUP_CLASSES.items()}
    records = {}
    for group, cls in S.RECORD_CLASSES.items():
        rows = norm[group]
        records[group] = None if rows is None else tuple(cls(**r) for r in rows)
    return S.PlanInput(schema_version=norm["schema_version"], currency=norm["currency"],
                       provenance=copy.deepcopy(provenance), **groups, **records)
