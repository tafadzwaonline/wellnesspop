"""Backward marketing schedule and channel checklist.

Nothing here sends messages or publishes posts; completion is a checklist state only.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from wellnesspop import schema as S
from wellnesspop.schema import PlanInput

TEMPLATE_DIR = Path(__file__).parent / "templates"


@lru_cache(maxsize=1)
def marketing_rules() -> dict:
    return json.loads((TEMPLATE_DIR / "marketing_rules.json").read_text(encoding="utf-8"))


def empty_marketing_edits() -> dict:
    return {"status": {}, "compress": False}


@dataclass(frozen=True)
class MarketingRow:
    id: str  # activity_id:channel
    activity_id: str
    activity: str
    channel: str
    offset_days: int
    planned_due: dt.date
    due_date: dt.date
    owner_role: str
    status: str
    flags: tuple[str, ...]  # infeasible | compressed | overdue


@dataclass(frozen=True)
class MarketingResult:
    rows: tuple[MarketingRow, ...]
    earliest_start: dt.date
    budget: float
    infeasible_count: int
    compressed: bool
    complete: int
    total: int
    budget_note: str
    channels: tuple[str, ...]


def activity_templates(plan: PlanInput) -> list[dict]:
    """Activities (before channel expansion): custom imported list or generated rules."""
    if plan.marketing_activities is not None:
        return [{"id": a.id, "name": a.name, "offset_days": a.offset_days,
                 "channels": list(a.channels), "owner_role": a.owner_role,
                 "status": a.status} for a in plan.marketing_activities]
    rules = marketing_rules()
    has_early = any(t.preset == "early_bird" for t in plan.ticket_tiers)
    acts = [dict(a) for a in rules["activities"]
            if a.get("condition") != "early_bird" or has_early]
    wr = rules["weekly_reminder"]
    offsets = {a["id"]: a["offset_days"] for a in rules["activities"]}
    day = offsets[wr["after"]] + wr["every_days"]
    n = 1
    while day < offsets[wr["before"]]:
        acts.append({"id": f"{wr['id_prefix']}.{n}", "name": f"{wr['name']} {n}",
                     "offset_days": day, "channels": wr["channels"],
                     "owner_role": wr["owner_role"]})
        day += wr["every_days"]
        n += 1
    return acts


def generate_marketing(plan: PlanInput, edits: dict | None, today: dt.date) -> MarketingResult:
    edits = edits or empty_marketing_edits()
    statuses = edits.get("status", {})
    compress = bool(edits.get("compress"))
    custom = plan.marketing_activities is not None
    selected = plan.marketing.channels
    rows: list[MarketingRow] = []
    seen: set[tuple[str, str, dt.date]] = set()
    for act in activity_templates(plan):
        channels = act["channels"] if custom else [c for c in act["channels"] if c in selected]
        planned = plan.event.date + dt.timedelta(days=act["offset_days"])
        for ch in channels:
            key = (act["name"].rstrip("0123456789 "), ch, planned)
            if key in seen:  # deduplicate reminders sharing activity/channel/date
                continue
            seen.add(key)
            rid = f"{act['id']}:{ch}"
            flags = []
            due = planned
            if planned < plan.marketing.earliest_start:
                if compress:
                    due = plan.marketing.earliest_start
                    flags.append("compressed")
                else:
                    flags.append("infeasible")
            status = statuses.get(rid, act.get("status", "not_started"))
            if status not in S.TASK_STATUSES:
                status = "not_started"
            if status != "complete" and due < today:
                flags.append("overdue")
            rows.append(MarketingRow(rid, act["id"], act["name"], ch, act["offset_days"],
                                     planned, due, act["owner_role"], status, tuple(flags)))
    rows.sort(key=lambda r: (r.due_date, r.activity_id, r.channel))
    return MarketingResult(
        rows=tuple(rows), earliest_start=plan.marketing.earliest_start,
        budget=plan.marketing.budget,
        infeasible_count=sum("infeasible" in r.flags for r in rows), compressed=compress,
        complete=sum(r.status == "complete" for r in rows), total=len(rows),
        budget_note=(f"Marketing budget of ${plan.marketing.budget:,.2f} is included once in "
                     "fixed costs. Marking an activity complete does not send anything."),
        channels=tuple(selected),
    )
