"""Snapshot consistency, session isolation, privacy, and schema completeness."""

import ast
import copy
import datetime as dt
from pathlib import Path

import pytest

from wellnesspop import schema as S
from wellnesspop import state
from wellnesspop.demos import DEMO_KEYS, load_demo
from wellnesspop.planner import build_plan, empty_edits
from wellnesspop.validation import check_plan, validate_plan

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("key", DEMO_KEYS)
def test_every_demo_generates_every_output(key, today):
    from wellnesspop.dashboard import build_dashboard
    from wellnesspop.export import export_marketing_csv, export_pdf, export_xlsx
    from wellnesspop.planner import run_simulation

    r = build_plan(validate_plan(load_demo(key, today), today), today=today)
    r = r.with_simulation(run_simulation(r))
    assert r.budget.scenarios and r.break_even.sentence
    assert r.tasks and r.schedule is not None and r.risks
    assert r.staffing.rows and r.marketing.rows
    assert r.simulation_status == "current"
    assert len(build_dashboard(r).kpis) == 7
    assert export_xlsx(r) and export_pdf(r) and export_marketing_csv(r.marketing)
    assert not [i for i in r.issues if i.severity == "error"]


def test_factory_defaults_validate_without_typing(today):
    plan, issues = check_plan(S.default_plan(today), today)
    assert plan is not None, issues
    assert plan.simulation.runs == 10_000 and plan.simulation.seed == 42
    assert plan.ticket_tiers[0].price == 15 and plan.variable_costs[0].mode == 2


def test_schema_completeness_d1(today):
    """Every editable field has a type, default rule, validation, unit and provenance."""
    default = S.default_plan(today)
    for row in S.spec_inventory():
        for k in ("kind", "unit", "default_rule", "validation", "provenance"):
            assert row[k] not in (None, ""), (row["path"], k)
        assert row["provenance"] in S.SOURCE_KINDS
        if row["group"] == "scalar":
            assert S.get_path(default, row["path"], "MISSING") != "MISSING", row["path"]
    for group in S.RECORD_SPECS:
        if group in S.NULLABLE_RECORD_GROUPS:
            continue
        assert set(S.record_defaults(group)) == {s.path for s in S.RECORD_SPECS[group]}, group


def test_session_isolation_and_clear(today):
    a, b = {}, {}
    state.init(a, today)
    state.init(b, today)
    state.load_demo_into(a, "scenario_c", today)
    assert state.plan(a).event.name == "One-Day Wellness Fair"
    assert state.plan(b).event.name == "My wellness event"
    state.simulate(a, today)
    assert state.result(a, today).simulation_status == "current"
    assert state.result(b, today).simulation_status == "not_run"
    state.clear(a, today)
    assert state.plan(a).event.name == "My wellness event"
    assert state.result(a, today).simulation is None


def test_invalid_edit_leaves_plan_intact_and_valid_edit_invalidates_simulation(today):
    s = {}
    state.init(s, today)
    state.load_demo_into(s, "scenario_a", today)
    state.simulate(s, today)
    before = state.plan(s)
    rev = state.revision(s)
    bad = state.raw(s)
    bad["attendance"]["high"] = 9999
    issues = state.commit_plan(s, bad, today)
    assert any(i.severity == "error" for i in issues)
    assert state.plan(s) is before and state.revision(s) == rev
    assert state.result(s, today).simulation_status == "current"
    good = state.raw(s)
    good["attendance"]["likely"] = 45
    assert not [i for i in state.commit_plan(s, good, today) if i.severity == "error"]
    assert state.revision(s) == rev + 1
    assert state.result(s, today).simulation_status == "not_run"


def test_provenance_marks_user_edits_and_keeps_original(today):
    s = {}
    state.init(s, today)
    state.load_demo_into(s, "scenario_a", today)
    raw = state.raw(s)
    raw["venue"]["permit_cost"] = 80
    state.commit_plan(s, raw, today)
    rec = state.plan(s).provenance["venue.permit_cost"]
    assert rec["source_kind"] == "user"
    assert rec["original_source_kind"] == "illustrative" and rec["original_value"] == 25
    rows = {a["field_path"]: a for a in build_plan(state.plan(s), today=today).assumptions}
    assert rows["venue.permit_cost"]["source_kind"] == "user"
    assert rows["attendance.likely"]["source_kind"] == "brief"


def test_task_edits_survive_input_changes(today):
    s = {}
    state.init(s, today)
    state.load_demo_into(s, "scenario_b", today)
    edits = empty_edits()["tasks"]
    edits["overrides"]["pre.venue"] = {"status": "complete"}
    state.commit_edits(s, "tasks", edits)
    raw = state.raw(s)
    raw["event"]["date"] = (dt.date.fromisoformat(raw["event"]["date"]) + dt.timedelta(days=7)).isoformat()
    state.commit_plan(s, raw, today)
    task = next(t for t in state.result(s, today).tasks if t.id == "pre.venue")
    assert task.status == "complete"


def test_fingerprints_track_inputs(today):
    raw = load_demo("scenario_b", today)
    r1 = build_plan(validate_plan(raw, today), today=today)
    r2 = build_plan(validate_plan(copy.deepcopy(raw), today), today=today)
    assert r1.input_fingerprint == r2.input_fingerprint
    raw["processing"]["ticket_fee_rate"] = 0.05
    assert build_plan(validate_plan(raw, today), today=today).input_fingerprint != r1.input_fingerprint


def test_past_dates_need_historical_acknowledgment(today):
    raw = S.default_plan(today)
    raw["event"]["date"] = "2026-01-10"
    raw["marketing"]["earliest_start"] = "2025-12-01"
    plan, issues = check_plan(raw, today)
    assert plan is None and any(i.path == "event.date" for i in issues)
    raw["event"]["historical_ack"] = True
    assert check_plan(raw, today)[0] is not None


def test_no_storage_network_or_logging_of_user_data():
    """Static privacy check over application code (not tests)."""
    banned_imports = {"requests", "urllib", "http", "socket", "sqlite3", "pickle", "shelve",
                      "logging", "httpx", "aiohttp"}
    banned_calls = {"open", "to_csv", "to_excel", "to_pickle"}
    files = list((ROOT / "wellnesspop").rglob("*.py")) + [ROOT / "app.py"]
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for n in names:
                    assert n.split(".")[0] not in banned_imports, (path, n)
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
                assert name not in banned_calls, (path, name)
                assert name not in ("write_text", "write_bytes", "cache_data", "cache_resource"), (path, name)
