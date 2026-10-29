"""Work breakdown structure generation, task edits, and backward scheduling.

Dates use calendar days in the event's local timezone. Finish dates are exclusive:
``finish = start + duration_days``; zero-duration tasks are milestones.
Pre-event tasks are scheduled backward (as late as their deadlines and successors
allow), event-day tasks from the event date, and post-event tasks forward.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from wellnesspop import schema as S
from wellnesspop.schema import PlanInput
from wellnesspop.staffing import StaffingResult
from wellnesspop.validation import Issue

TEMPLATE_DIR = Path(__file__).parent / "templates"
GROUP_IDS = {p: f"phase.{p}" for p in S.PHASES}
EDITABLE_FIELDS = ("name", "phase", "parent_id", "duration_days", "offset_days", "owner_role",
                   "status", "predecessor_ids", "manual_start")


@lru_cache(maxsize=1)
def task_templates() -> tuple[dict, ...]:
    data = json.loads((TEMPLATE_DIR / "wbs_templates.json").read_text(encoding="utf-8"))
    return tuple(data["tasks"])


@dataclass(frozen=True)
class Task:
    id: str
    parent_id: str | None
    phase: str
    name: str
    duration_days: int
    anchor: str
    offset_days: int
    lag_days: int
    lead_rule: str
    predecessor_ids: tuple[str, ...]
    owner_role: str
    status: str
    manual_start: dt.date | None
    source: str  # template | user | group
    is_group: bool = False


def empty_task_edits() -> dict:
    return {"overrides": {}, "tombstones": [], "added": []}


def _condition_active(cond: str, plan: PlanInput, staffing: StaffingResult) -> bool:
    return {
        "all": True,
        "permit": plan.venue.permit_required,
        "insurance": plan.venue.insurance_required,
        "weather": plan.event.setting in ("outdoor", "hybrid"),
        "paid_staff": staffing.has_paid_staff,
        "volunteers": staffing.has_volunteers,
        "fair": plan.event.event_type == "one_day_fair",
        "deposit": plan.venue.security_deposit > 0,
    }[cond]


def _field_days(plan: PlanInput, path: str) -> int:
    group, name = path.split(".")
    return int(getattr(getattr(plan, group), name))


def template_tasks(plan: PlanInput, staffing: StaffingResult) -> tuple[list[Task], set[str]]:
    """Return (active template tasks, ids of inactive template tasks)."""
    active, inactive = [], set()
    for t in task_templates():
        if not _condition_active(t["condition"], plan, staffing):
            inactive.add(t["id"])
            continue
        offset = t["offset_days"]
        rule = t.get("lead_rule", "")
        if "offset_field" in t:
            days = _field_days(plan, t["offset_field"])
            offset -= days
            rule = f"{rule} ({days} days)"
        lag = _field_days(plan, t["lag_field"]) if "lag_field" in t else 0
        if lag:
            rule = f"{rule} ({lag} days)"
        active.append(Task(
            id=t["id"], parent_id=GROUP_IDS[t["phase"]], phase=t["phase"], name=t["name"],
            duration_days=t["duration_days"], anchor="event", offset_days=offset, lag_days=lag,
            lead_rule=rule.strip(), predecessor_ids=tuple(t["predecessors"]),
            owner_role=t["owner_role"], status="not_started", manual_start=None,
            source="template"))
    return active, inactive


def _group_tasks() -> list[Task]:
    return [Task(id=gid, parent_id=None, phase=p, name=S.label(p), duration_days=0,
                 anchor="event", offset_days=0, lag_days=0, lead_rule="",
                 predecessor_ids=(), owner_role="Organizer", status="not_started",
                 manual_start=None, source="group", is_group=True)
            for p, gid in GROUP_IDS.items()]


def _coerce_task_fields(fields: dict) -> dict:
    out = dict(fields)
    if "predecessor_ids" in out:
        val = out["predecessor_ids"]
        if isinstance(val, str):
            val = [p.strip() for p in val.split(",")]
        out["predecessor_ids"] = tuple(p for p in (val or ()) if p)
    if "manual_start" in out and isinstance(out["manual_start"], str):
        out["manual_start"] = dt.date.fromisoformat(out["manual_start"]) if out["manual_start"] else None
    for key in ("duration_days", "offset_days", "lag_days"):
        if key in out and out[key] is not None:
            out[key] = int(out[key])
    return out


def generate_wbs(plan: PlanInput, staffing: StaffingResult,
                 edits: dict | None = None) -> tuple[list[Task], list[Issue]]:
    """Template tasks + user edits. Returns tasks (groups first) and validation issues."""
    edits = edits or empty_task_edits()
    templates, inactive = template_tasks(plan, staffing)
    tombstones = set(edits.get("tombstones", ()))
    overrides = edits.get("overrides", {})
    tasks: list[Task] = []
    for t in templates:
        if t.id in tombstones:
            continue
        ov = overrides.get(t.id)
        tasks.append(replace(t, **_coerce_task_fields(ov)) if ov else t)
    for row in edits.get("added", ()):
        fields = _coerce_task_fields(row)
        phase = fields.get("phase", "pre_event")
        tasks.append(Task(
            id=fields["id"], parent_id=fields.get("parent_id") or GROUP_IDS.get(phase),
            phase=phase, name=fields.get("name") or "New task",
            duration_days=fields.get("duration_days", 1), anchor="event",
            offset_days=fields.get("offset_days", -7 if phase == "pre_event" else
                                   (0 if phase == "event_day" else 1)),
            lag_days=fields.get("lag_days", 0), lead_rule="",
            predecessor_ids=fields.get("predecessor_ids", ()),
            owner_role=fields.get("owner_role") or "Organizer",
            status=fields.get("status", "not_started"),
            manual_start=fields.get("manual_start"), source="user"))
    issues: list[Issue] = []
    # Drop references to template tasks switched off by conditions (not user deletions).
    cleaned = []
    for t in tasks:
        preds = tuple(p for p in t.predecessor_ids if p not in inactive or p in tombstones)
        if preds != t.predecessor_ids:
            issues.append(Issue(f"task {t.id}", "dependency on a task no longer needed was "
                                "removed", "warning"))
        cleaned.append(replace(t, predecessor_ids=preds))
    all_tasks = _group_tasks() + cleaned
    issues += validate_tasks(all_tasks)
    return all_tasks, issues


def validate_tasks(tasks: list[Task]) -> list[Issue]:
    issues: list[Issue] = []
    by_id: dict[str, Task] = {}
    for t in tasks:
        if not t.id:
            issues.append(Issue("task", "every task needs an ID"))
            continue
        if t.id in by_id:
            issues.append(Issue(f"task {t.id}", "duplicate task ID"))
        by_id[t.id] = t
    rank = {p: i for i, p in enumerate(S.PHASES)}
    for t in tasks:
        where = f"task {t.id}"
        if t.phase not in S.PHASES:
            issues.append(Issue(where, f"unknown phase '{t.phase}'"))
            continue
        if t.status not in S.TASK_STATUSES:
            issues.append(Issue(where, f"unknown status '{t.status}'"))
        if t.duration_days < 0:
            issues.append(Issue(where, "duration cannot be negative"))
        if not t.is_group and not (t.name or "").strip():
            issues.append(Issue(where, "task name is required"))
        if t.is_group:
            continue
        if t.parent_id not in by_id:
            issues.append(Issue(where, f"parent '{t.parent_id}' does not exist"))
        for p in t.predecessor_ids:
            if p == t.id:
                issues.append(Issue(where, "a task cannot depend on itself"))
            elif p not in by_id:
                issues.append(Issue(where, f"depends on missing task '{p}'; update its "
                                    "dependencies before deleting"))
            elif by_id[p].is_group:
                issues.append(Issue(where, "cannot depend on a phase group"))
            elif rank.get(by_id[p].phase, 0) > rank[t.phase]:
                issues.append(Issue(where, f"cannot depend on later-phase task '{p}'"))
    # Hierarchy cycles
    for t in tasks:
        seen, cur = set(), t
        while cur is not None and cur.parent_id:
            if cur.id in seen:
                issues.append(Issue(f"task {t.id}", "hierarchy contains a cycle"))
                break
            seen.add(cur.id)
            cur = by_id.get(cur.parent_id)
    if _topological(tasks) is None:
        issues.append(Issue("tasks", "dependencies contain a cycle"))
    return issues


def _topological(tasks: list[Task]) -> list[str] | None:
    ids = {t.id for t in tasks}
    indeg = {t.id: 0 for t in tasks}
    succ: dict[str, list[str]] = {t.id: [] for t in tasks}
    for t in tasks:
        for p in t.predecessor_ids:
            if p in ids:
                indeg[t.id] += 1
                succ[p].append(t.id)
    queue = [i for i, d in indeg.items() if d == 0]
    order = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for s in succ[n]:
            indeg[s] -= 1
            if indeg[s] == 0:
                queue.append(s)
    return order if len(order) == len(tasks) else None


# ------------------------------------------------------------------------- schedule


@dataclass(frozen=True)
class ScheduledTask:
    task: Task
    wbs_code: str
    start: dt.date
    finish: dt.date  # exclusive
    deadline: dt.date | None  # latest finish (pre-event) or earliest start (post-event)
    flags: tuple[str, ...]  # overdue, late_start, conflict, pinned

    @property
    def is_milestone(self) -> bool:
        return self.task.duration_days == 0 and not self.task.is_group


@dataclass(frozen=True)
class ScheduleResult:
    tasks: tuple[ScheduledTask, ...]
    issues: tuple[Issue, ...]
    event_date: dt.date
    today: dt.date

    def by_id(self) -> dict[str, ScheduledTask]:
        return {s.task.id: s for s in self.tasks}

    @property
    def problems(self) -> tuple[ScheduledTask, ...]:
        return tuple(s for s in self.tasks if set(s.flags) & {"overdue", "late_start", "conflict"})


def schedule_tasks(tasks: list[Task], event_date: dt.date, today: dt.date) -> ScheduleResult:
    """Schedule validated tasks. Raises ValueError if dependencies are cyclic."""
    work = [t for t in tasks if not t.is_group]
    order = _topological(work)
    if order is None:
        raise ValueError("dependencies contain a cycle")
    by_id = {t.id: t for t in work}
    succ: dict[str, list[str]] = {t.id: [] for t in work}
    for t in work:
        for p in t.predecessor_ids:
            succ[p].append(t.id)
    start: dict[str, dt.date] = {}
    finish: dict[str, dt.date] = {}
    deadline: dict[str, dt.date] = {}
    flags: dict[str, list[str]] = {t.id: [] for t in work}
    days = dt.timedelta

    for t in work:
        if t.phase == "event_day":
            start[t.id] = t.manual_start or event_date + days(t.offset_days)
            finish[t.id] = start[t.id] + days(t.duration_days)
            if t.manual_start:
                flags[t.id].append("pinned")

    for tid in reversed(order):
        t = by_id[tid]
        if t.phase != "pre_event":
            continue
        latest = event_date + days(t.offset_days)
        for s in succ[tid]:
            st = by_id[s]
            if st.phase == "post_event":
                continue
            latest = min(latest, start[s] - days(st.lag_days))
        deadline[tid] = latest
        if t.manual_start:
            start[tid] = t.manual_start
            finish[tid] = t.manual_start + days(t.duration_days)
            flags[tid].append("pinned")
            if finish[tid] > latest:
                flags[tid].append("conflict")
        else:
            finish[tid] = latest
            start[tid] = latest - days(t.duration_days)

    for tid in order:
        t = by_id[tid]
        if t.phase != "post_event":
            continue
        earliest = event_date + days(t.offset_days)
        for p in t.predecessor_ids:
            earliest = max(earliest, finish[p] + days(t.lag_days))
        deadline[tid] = earliest
        if t.manual_start:
            start[tid] = t.manual_start
            flags[tid].append("pinned")
            if t.manual_start < earliest:
                flags[tid].append("conflict")
        else:
            start[tid] = earliest
        finish[tid] = start[tid] + days(t.duration_days)

    # Precedence checks (pinned dates or event-day anchors can be infeasible).
    for t in work:
        for p in t.predecessor_ids:
            if t.phase == "event_day" and by_id[p].phase == "event_day":
                continue  # same-day ordering is not modeled in calendar days
            if finish[p] + days(t.lag_days) > start[t.id] and "conflict" not in flags[t.id]:
                flags[t.id].append("conflict")
        if t.status != "complete":
            # Exclusive finish: a task is late once today reaches its finish date;
            # a milestone is late the day after its date.
            due_passed = (finish[t.id] < today) if t.duration_days == 0 else (finish[t.id] <= today)
            if due_passed:
                flags[t.id].append("overdue")
            elif t.status == "not_started" and start[t.id] < today:
                flags[t.id].append("late_start")

    groups = [t for t in tasks if t.is_group]
    children: dict[str | None, list[Task]] = {}
    for t in tasks:
        children.setdefault(t.parent_id, []).append(t)

    codes: dict[str, str] = {}

    def number(parent: str | None, prefix: str) -> None:
        kids = children.get(parent, [])
        kids = sorted(kids, key=lambda k: (S.PHASES.index(k.phase) if k.is_group else 0,
                                           start.get(k.id, event_date), k.id))
        for i, k in enumerate(kids, 1):
            codes[k.id] = f"{prefix}{i}"
            number(k.id, f"{prefix}{i}.")

    number(None, "")

    def span(tid: str) -> tuple[dt.date, dt.date] | None:
        dates = []
        for k in children.get(tid, []):
            if k.id in start:
                dates.append((start[k.id], finish[k.id]))
            sub = span(k.id)
            if sub:
                dates.append(sub)
        if not dates:
            return None
        return min(d[0] for d in dates), max(d[1] for d in dates)

    result = []
    for t in groups + work:
        if t.is_group:
            s = span(t.id) or (event_date, event_date)
            result.append(ScheduledTask(t, codes.get(t.id, ""), s[0], s[1], None, ()))
        else:
            st, fi = start[t.id], finish[t.id]
            sub = span(t.id)
            if sub:  # a task with subtasks spans them too
                st, fi = min(st, sub[0]), max(fi, sub[1])
            result.append(ScheduledTask(t, codes.get(t.id, ""), st, fi, deadline.get(t.id),
                                        tuple(flags[t.id])))
    result.sort(key=lambda s: [int(x) for x in s.wbs_code.split(".") if x.isdigit()])
    return ScheduleResult(tuple(result), (), event_date, today)


# --------------------------------------------------------------------- task editing


def task_table_rows(tasks: list[Task]) -> list[dict]:
    return [{"id": t.id, "name": t.name, "phase": t.phase, "parent_id": t.parent_id,
             "duration_days": t.duration_days, "offset_days": t.offset_days,
             "owner_role": t.owner_role, "status": t.status,
             "predecessor_ids": ", ".join(t.predecessor_ids), "manual_start": t.manual_start}
            for t in tasks if not t.is_group]


def apply_task_table(plan: PlanInput, staffing: StaffingResult, edits: dict,
                     rows: list[dict]) -> tuple[dict | None, list[Issue]]:
    """Turn an edited task table into new edits. Returns (edits, issues); edits is None on error."""
    templates, _ = template_tasks(plan, staffing)
    template_by_id = {t.id: t for t in templates}
    current, _ = generate_wbs(plan, staffing, edits)
    current_ids = {t.id for t in current if not t.is_group}
    new = {"overrides": {}, "tombstones": list(edits.get("tombstones", [])), "added": []}
    seen = set()
    for row in rows:
        rid = (row.get("id") or "").strip() if isinstance(row.get("id"), str) else row.get("id")
        if not rid or rid in seen or rid.startswith("phase."):
            rid = S.new_id("task")
        seen.add(rid)
        fields = {k: row.get(k) for k in EDITABLE_FIELDS if k in row}
        fields = {k: (None if v != v else v) for k, v in fields.items()}  # NaN -> None
        if isinstance(fields.get("manual_start"), dt.datetime):
            fields["manual_start"] = fields["manual_start"].date()
        for k in ("name", "phase", "duration_days", "offset_days", "owner_role", "status"):
            if fields.get(k) is None or (isinstance(fields.get(k), str) and not fields[k].strip()):
                fields.pop(k, None)  # blank cells fall back to the template or default
        try:
            fields = _coerce_task_fields(fields)
        except (TypeError, ValueError):
            return None, [Issue(f"task {rid}", "invalid number or date")]
        if rid in template_by_id:
            base = template_by_id[rid]
            diff = {k: v for k, v in fields.items() if getattr(base, k) != v}
            if diff:
                new["overrides"][rid] = _jsonable_fields(diff)
            if rid in new["tombstones"]:
                new["tombstones"].remove(rid)
        else:
            new["added"].append(_jsonable_fields({"id": rid, **fields}))
    for tid in current_ids - seen:
        if tid in template_by_id and tid not in new["tombstones"]:
            new["tombstones"].append(tid)
    tasks, issues = generate_wbs(plan, staffing, new)
    if any(i.severity == "error" for i in issues):
        return None, issues
    return new, issues


def _jsonable_fields(fields: dict) -> dict:
    out = {}
    for k, v in fields.items():
        if isinstance(v, tuple):
            v = list(v)
        if isinstance(v, dt.date):
            v = v.isoformat()
        out[k] = v
    return out
