import datetime as dt

from wellnesspop.demos import load_demo
from wellnesspop.schedule import (apply_task_table, generate_wbs, schedule_tasks,
                                  task_table_rows)
from wellnesspop.staffing import calculate_staffing
from wellnesspop.validation import validate_plan


def _wbs(raw, today, edits=None):
    plan = validate_plan(raw, today)
    staff = calculate_staffing(plan)
    tasks, issues = generate_wbs(plan, staff, edits)
    return plan, staff, tasks, issues


def _sched(raw, today, edits=None):
    plan, staff, tasks, issues = _wbs(raw, today, edits)
    assert not [i for i in issues if i.severity == "error"], issues
    return plan, schedule_tasks(tasks, plan.event.date, today)


def test_three_phases_and_conditional_tasks(today):
    _, _, tasks, _ = _wbs(load_demo("scenario_a", today), today)
    ids = {t.id for t in tasks}
    assert {"phase.pre_event", "phase.event_day", "phase.post_event"} <= ids
    assert {"pre.permit.submit", "pre.ins.bind", "pre.rain.decision", "pre.vol.confirm"} <= ids
    assert "pre.fair.vendors" not in ids
    _, _, tasks, _ = _wbs(load_demo("scenario_c", today), today)
    assert "pre.fair.vendors" in {t.id for t in tasks}
    _, _, tasks, _ = _wbs(load_demo("scenario_b", today), today)
    ids = {t.id for t in tasks}
    assert "pre.permit.submit" not in ids and "pre.rain.plan" not in ids
    assert "post.deposit" in ids


def test_backward_schedule_respects_dependencies_and_permit_lead(today):
    plan, s = _sched(load_demo("scenario_a", today), today)
    by = s.by_id()
    for st in s.tasks:
        for p in st.task.predecessor_ids:
            if st.task.phase == "event_day" and by[p].task.phase == "event_day":
                continue
            assert by[p].finish + dt.timedelta(days=st.task.lag_days) <= st.start
    lead = plan.venue.permit_lead_days
    assert (by["pre.permit.approval"].start - by["pre.permit.submit"].finish).days >= lead
    assert by["pre.ins.bind"].finish <= plan.event.date - dt.timedelta(days=plan.venue.insurance_lead_days)
    assert by["day.deliver"].start == plan.event.date
    assert by["post.survey"].start == plan.event.date + dt.timedelta(days=1)
    assert by["post.review"].start >= by["post.close"].finish
    assert by["pre.vol.confirm"].finish <= plan.event.date - dt.timedelta(days=7)


def test_changing_event_date_reschedules_and_keeps_edits(today):
    raw = load_demo("scenario_b", today)
    edits = {"overrides": {"pre.venue": {"name": "Book community room", "status": "complete",
                                         "owner_role": "Program lead"}},
             "tombstones": [], "added": []}
    _, s1 = _sched(raw, today, edits)
    raw["event"]["date"] = (dt.date.fromisoformat(raw["event"]["date"]) + dt.timedelta(days=14)).isoformat()
    _, s2 = _sched(raw, today, edits)
    b1, b2 = s1.by_id(), s2.by_id()
    for tid, t in b1.items():
        if not t.task.is_group and not t.task.manual_start:
            assert (b2[tid].start - t.start).days == 14
    assert b2["pre.venue"].task.name == "Book community room"
    assert b2["pre.venue"].task.status == "complete"


def test_overdue_permit_is_flagged_not_moved(today):
    raw = load_demo("scenario_a", today)
    raw["event"]["date"] = (today + dt.timedelta(days=20)).isoformat()
    raw["rain"]["alternate_date"] = (today + dt.timedelta(days=27)).isoformat()
    plan, s = _sched(raw, today)
    sub = s.by_id()["pre.permit.submit"]
    assert sub.start < today
    assert "overdue" in sub.flags
    assert s.problems


def test_cycle_missing_dependency_and_negative_duration(today):
    raw = load_demo("scenario_b", today)
    edits = {"overrides": {"pre.goals": {"predecessor_ids": ["pre.registration"]}},
             "tombstones": [], "added": []}
    _, _, _, issues = _wbs(raw, today, edits)
    assert any("cycle" in i.message for i in issues)
    edits = {"overrides": {}, "tombstones": ["pre.budget"], "added": []}
    _, _, _, issues = _wbs(raw, today, edits)
    assert any("missing task 'pre.budget'" in i.message for i in issues)
    edits = {"overrides": {"pre.goals": {"duration_days": -2}}, "tombstones": [], "added": []}
    _, _, _, issues = _wbs(raw, today, edits)
    assert any("negative" in i.message for i in issues)


def test_pinned_date_conflict(today):
    raw = load_demo("scenario_b", today)
    event = dt.date.fromisoformat(raw["event"]["date"])
    edits = {"overrides": {"pre.supplies": {"manual_start": (event - dt.timedelta(days=1)).isoformat()}},
             "tombstones": [], "added": []}
    _, s = _sched(raw, today, edits)
    assert {"pinned", "conflict"} <= set(s.by_id()["pre.supplies"].flags)


def test_table_editing_add_delete_and_tombstones(today):
    raw = load_demo("scenario_b", today)
    plan, staff, tasks, _ = _wbs(raw, today)
    rows = task_table_rows(tasks)
    rows = [r for r in rows if r["id"] != "post.review"]  # delete an unreferenced task
    rows.append({"id": None, "name": "Order flowers", "phase": "pre_event",
                 "parent_id": "phase.pre_event", "duration_days": 1, "offset_days": -5,
                 "owner_role": "Organizer", "status": "not_started",
                 "predecessor_ids": "pre.budget", "manual_start": None})
    for r in rows:
        if r["id"] == "pre.goals":
            r["name"] = "Agree goals with partners"
    new, issues = apply_task_table(plan, staff, {"overrides": {}, "tombstones": [], "added": []}, rows)
    assert new is not None, issues
    assert "post.review" in new["tombstones"]
    assert new["overrides"]["pre.goals"] == {"name": "Agree goals with partners"}
    assert new["added"][0]["name"] == "Order flowers"
    _, _, tasks2, _ = _wbs(raw, today, new)
    ids = {t.id for t in tasks2}
    assert "post.review" not in ids and new["added"][0]["id"] in ids


def test_deleting_referenced_task_is_refused(today):
    raw = load_demo("scenario_b", today)
    plan, staff, tasks, _ = _wbs(raw, today)
    rows = [r for r in task_table_rows(tasks) if r["id"] != "pre.budget"]
    new, issues = apply_task_table(plan, staff, {"overrides": {}, "tombstones": [], "added": []}, rows)
    assert new is None and any("pre.budget" in i.message for i in issues)
