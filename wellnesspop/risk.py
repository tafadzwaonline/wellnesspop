"""Likelihood-impact risk register generated from a conditional library plus user edits.

Risk scores are prioritization aids. Changing a score never changes simulation inputs;
linked assumptions must be edited separately.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from wellnesspop import schema as S
from wellnesspop.schema import PlanInput
from wellnesspop.validation import Issue

TEMPLATE_DIR = Path(__file__).parent / "templates"
EDITABLE_FIELDS = ("title", "likelihood", "impact", "owner_role", "response", "response_note",
                   "status", "assumption_refs")
BANDS = ((4, "Low"), (9, "Medium"), (16, "High"), (25, "Critical"))


@lru_cache(maxsize=1)
def risk_library() -> tuple[dict, ...]:
    return tuple(json.loads((TEMPLATE_DIR / "risk_library.json").read_text(encoding="utf-8")))


@dataclass(frozen=True)
class Risk:
    id: str
    title: str
    likelihood: int
    impact: int
    owner_role: str
    response: str
    response_note: str
    status: str
    assumption_refs: tuple[str, ...]
    source: str  # template | user

    @property
    def score(self) -> int:
        return self.likelihood * self.impact

    @property
    def band(self) -> str:
        return band(self.score)


def band(score: int) -> str:
    for limit, name in BANDS:
        if score <= limit:
            return name
    return "Critical"


def empty_risk_edits() -> dict:
    return {"overrides": {}, "tombstones": [], "added": []}


def _active(cond: str, plan: PlanInput) -> bool:
    return {
        "all": True,
        "weather": plan.event.setting in ("outdoor", "hybrid"),
        "permit": plan.venue.permit_required,
        "fair": plan.event.event_type == "one_day_fair",
    }[cond]


def _coerce(fields: dict) -> dict:
    out = dict(fields)
    if "assumption_refs" in out:
        val = out["assumption_refs"] or ()
        if isinstance(val, str):
            val = [p.strip() for p in val.split(",")]
        out["assumption_refs"] = tuple(p for p in val if p)
    for key in ("likelihood", "impact"):
        if key in out and out[key] is not None:
            out[key] = int(out[key])
    for key in ("response_note", "title", "owner_role"):
        if key in out and out[key] is None:
            out[key] = ""
    return out


def template_risks(plan: PlanInput) -> list[Risk]:
    return [Risk(id=r["id"], title=r["title"], likelihood=r["likelihood"], impact=r["impact"],
                 owner_role=r["owner_role"], response=r["response"],
                 response_note=r["response_note"], status="open",
                 assumption_refs=tuple(r["assumption_refs"]), source="template")
            for r in risk_library() if _active(r["condition"], plan)]


def generate_risks(plan: PlanInput, edits: dict | None = None) -> tuple[list[Risk], list[Issue]]:
    edits = edits or empty_risk_edits()
    tomb = set(edits.get("tombstones", ()))
    risks = []
    for r in template_risks(plan):
        if r.id in tomb:
            continue
        ov = edits.get("overrides", {}).get(r.id)
        risks.append(replace(r, **_coerce(ov)) if ov else r)
    for row in edits.get("added", ()):
        f = _coerce(row)
        risks.append(Risk(id=f["id"], title=f.get("title") or "New risk",
                          likelihood=f.get("likelihood", 3), impact=f.get("impact", 3),
                          owner_role=f.get("owner_role") or "Organizer",
                          response=f.get("response", "mitigate"),
                          response_note=f.get("response_note", ""),
                          status=f.get("status", "open"),
                          assumption_refs=f.get("assumption_refs", ()), source="user"))
    issues = []
    seen = set()
    for r in risks:
        where = f"risk {r.id}"
        if r.id in seen:
            issues.append(Issue(where, "duplicate risk ID"))
        seen.add(r.id)
        if not 1 <= r.likelihood <= 5 or not 1 <= r.impact <= 5:
            issues.append(Issue(where, "likelihood and impact must be whole numbers 1-5"))
        if r.response not in S.RISK_RESPONSES:
            issues.append(Issue(where, f"response must be one of {', '.join(S.RISK_RESPONSES)}"))
        if r.status not in S.RISK_STATUSES:
            issues.append(Issue(where, f"status must be one of {', '.join(S.RISK_STATUSES)}"))
        if not r.title.strip():
            issues.append(Issue(where, "title is required"))
        if not r.owner_role.strip():
            issues.append(Issue(where, "owner role is required"))
    risks.sort(key=lambda r: (-r.score, r.id))
    return risks, issues


def risk_table_rows(risks: list[Risk]) -> list[dict]:
    return [{"id": r.id, "title": r.title, "likelihood": r.likelihood, "impact": r.impact,
             "owner_role": r.owner_role, "response": r.response, "response_note": r.response_note,
             "status": r.status, "assumption_refs": ", ".join(r.assumption_refs)} for r in risks]


def apply_risk_table(plan: PlanInput, edits: dict, rows: list[dict]) -> tuple[dict | None, list[Issue]]:
    base = {r.id: r for r in template_risks(plan)}
    current, _ = generate_risks(plan, edits)
    new = {"overrides": {}, "tombstones": list(edits.get("tombstones", [])), "added": []}
    seen = set()
    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, str) or not rid.strip() or rid in seen:
            rid = S.new_id("risk")
        seen.add(rid)
        fields = {k: row.get(k) for k in EDITABLE_FIELDS if k in row}
        fields = {k: (None if v != v else v) for k, v in fields.items()}
        for k in ("likelihood", "impact", "response", "status"):
            if fields.get(k) is None:
                fields.pop(k, None)  # blank cells fall back to the template or default
        try:
            fields = _coerce(fields)
        except (TypeError, ValueError):
            return None, [Issue(f"risk {rid}", "likelihood and impact must be whole numbers")]
        if rid in base:
            diff = {k: v for k, v in fields.items() if getattr(base[rid], k) != v}
            if diff:
                new["overrides"][rid] = {k: list(v) if isinstance(v, tuple) else v
                                         for k, v in diff.items()}
            if rid in new["tombstones"]:
                new["tombstones"].remove(rid)
        else:
            new["added"].append({k: list(v) if isinstance(v, tuple) else v
                                 for k, v in {"id": rid, **fields}.items()})
    for r in current:
        if r.id not in seen and r.id in base and r.id not in new["tombstones"]:
            new["tombstones"].append(r.id)
    _, issues = generate_risks(plan, new)
    if any(i.severity == "error" for i in issues):
        return None, issues
    return new, issues
