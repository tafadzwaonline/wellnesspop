"""Staffing, risk, marketing, and dashboard tests."""

import datetime as dt

import pytest

from wellnesspop.budget import calculate_budget
from wellnesspop.dashboard import build_dashboard
from wellnesspop.demos import load_demo
from wellnesspop.marketing import generate_marketing
from wellnesspop.planner import build_plan, run_simulation
from wellnesspop.risk import apply_risk_table, band, generate_risks, risk_table_rows
from wellnesspop.staffing import calculate_staffing
from wellnesspop.validation import validate_plan


# ---------------------------------------------------------------------- staffing

def test_staffing_costs_coverage_and_credentials(hand_raw, today):
    hand_raw["attendance"].update(high=55)
    hand_raw["staffing"] = [
        {"id": "a", "role": "Instructor", "count": 2, "pay_basis": "flat", "rate": 100,
         "required_certifications": "cpr, first_aid", "confirmed_certifications": ["cpr"]},
        {"id": "b", "role": "Helper", "count": 1, "hours": 3, "pay_basis": "hourly", "rate": 20},
        {"id": "c", "role": "Check-in", "count": 1, "hours": 3, "pay_basis": "hourly", "rate": 20,
         "volunteer": True, "coverage_ratio": 30},
    ]
    s = calculate_staffing(validate_plan(hand_raw, today))
    costs = {r.id: r.cost for r in s.rows}
    assert costs == {"a": 200, "b": 60, "c": 0}
    assert s.total_cost == 260
    check = next(r for r in s.rows if r.id == "c")
    assert check.recommended_count == 2 and check.gap == 1  # ceil(55 / 30)
    assert s.missing_credentials == ("Instructor: First aid",)
    hand_raw["attendance"]["planned_peak"] = 30
    s = calculate_staffing(validate_plan(hand_raw, today))
    assert next(r for r in s.rows if r.id == "c").gap == 0


def test_staffing_change_updates_budget_and_simulation(today):
    raw = load_demo("scenario_c", today)
    base = build_plan(validate_plan(raw, today), today=today)
    raw["staffing"][0]["rate"] += 50  # four instructors, flat fee
    more = build_plan(validate_plan(raw, today), today=today)
    assert more.budget.likely.net == pytest.approx(base.budget.likely.net - 200)
    assert more.input_fingerprint != base.input_fingerprint
    s1, s2 = run_simulation(base), run_simulation(more)
    assert s2.mean < s1.mean


# -------------------------------------------------------------------------- risks

def test_risk_library_conditions_scores_and_sorting(today):
    plan = validate_plan(load_demo("scenario_c", today), today)
    risks, issues = generate_risks(plan)
    ids = [r.id for r in risks]
    assert "risk.vendor_dropout" in ids and "risk.weather" in ids and "risk.permit" not in ids
    assert not issues
    keys = [(-r.score, r.id) for r in risks]
    assert keys == sorted(keys)
    assert [band(s) for s in (4, 5, 9, 10, 16, 17, 25)] == [
        "Low", "Medium", "Medium", "High", "High", "Critical", "Critical"]
    plan_b = validate_plan(load_demo("scenario_b", today), today)
    assert "risk.weather" not in [r.id for r in generate_risks(plan_b)[0]]


def test_risk_edit_does_not_change_simulation_inputs(today):
    plan = validate_plan(load_demo("scenario_a", today), today)
    base = build_plan(plan, today=today)
    rows = risk_table_rows(list(base.risks))
    for r in rows:
        if r["id"] == "risk.weather":
            r["likelihood"], r["impact"], r["status"] = 5, 5, "monitoring"
    edits, issues = apply_risk_table(plan, base.edits["risks"], rows)
    assert edits is not None, issues
    after = build_plan(plan, {**base.edits, "risks": edits}, today=today)
    top = after.risks[0]
    assert top.id == "risk.weather" and top.score == 25 and top.band == "Critical"
    assert after.input_fingerprint == base.input_fingerprint
    assert after.plan.weather.cancellation_probability == 0.25


def test_risk_validation(today):
    plan = validate_plan(load_demo("scenario_a", today), today)
    rows = risk_table_rows(list(generate_risks(plan)[0]))
    rows[0]["likelihood"] = 9
    edits, issues = apply_risk_table(plan, {"overrides": {}, "tombstones": [], "added": []}, rows)
    assert edits is None and issues


# ---------------------------------------------------------------------- marketing

def test_marketing_offsets_reminders_and_early_bird(today):
    plan = validate_plan(load_demo("scenario_a", today), today)
    m = generate_marketing(plan, None, today)
    offsets = {}
    for r in m.rows:
        offsets.setdefault(r.activity_id, r.offset_days)
    assert offsets["mkt.save_the_date"] == -42 and offsets["mkt.registration_open"] == -28
    assert offsets["mkt.early_bird_close"] == -14 and offsets["mkt.final_reminder"] == -2
    assert offsets["mkt.day_of"] == 0 and offsets["mkt.thank_you"] == 1
    assert sorted(v for k, v in offsets.items() if k.startswith("mkt.reminder")) == [-21, -14, -7]
    assert all(r.channel in plan.marketing.channels for r in m.rows)
    assert len({(r.activity_id, r.channel) for r in m.rows}) == len(m.rows)
    plan_b = validate_plan(load_demo("scenario_b", today), today)
    assert "mkt.early_bird_close" not in {r.activity_id for r in generate_marketing(plan_b, None, today).rows}


def test_marketing_earliest_start_conflict_and_compression(today):
    raw = load_demo("scenario_b", today)
    raw["event"]["date"] = (today + dt.timedelta(days=20)).isoformat()
    plan = validate_plan(raw, today)
    m = generate_marketing(plan, None, today)
    assert m.infeasible_count > 0
    c = generate_marketing(plan, {"status": {}, "compress": True}, today)
    assert c.infeasible_count == 0
    assert all(r.due_date >= plan.marketing.earliest_start for r in c.rows)
    assert any("compressed" in r.flags for r in c.rows)


def test_marketing_completion_retained_across_regeneration(today):
    raw = load_demo("scenario_a", today)
    plan = validate_plan(raw, today)
    first = generate_marketing(plan, None, today).rows[0]
    edits = {"status": {first.id: "complete"}, "compress": False}
    raw["event"]["date"] = (dt.date.fromisoformat(raw["event"]["date"]) + dt.timedelta(days=7)).isoformat()
    raw["rain"]["alternate_date"] = (dt.date.fromisoformat(raw["event"]["date"]) + dt.timedelta(days=7)).isoformat()
    m = generate_marketing(validate_plan(raw, today), edits, today)
    row = next(r for r in m.rows if r.id == first.id)
    assert row.status == "complete" and m.complete == 1


def test_marketing_budget_counted_once(hand_raw, today):
    hand_raw["marketing"]["budget"] = 80
    plan = validate_plan(hand_raw, today)
    b = calculate_budget(plan, calculate_staffing(plan))
    assert b.fixed_total == pytest.approx(480)


# ---------------------------------------------------------------------- dashboard

def test_dashboard_seven_kpis_and_stale_simulation(today):
    raw = load_demo("scenario_a", today)
    r = build_plan(validate_plan(raw, today), today=today)
    d = build_dashboard(r)
    assert len(d.kpis) == 7
    assert next(k for k in d.kpis if k.key == "prob").value == "Run simulation"
    sim = run_simulation(r)
    d = build_dashboard(r.with_simulation(sim))
    assert next(k for k in d.kpis if k.key == "prob").value.endswith("%")
    raw["attendance"]["likely"] = 45
    r2 = build_plan(validate_plan(raw, today), today=today, simulation=sim)
    assert r2.simulation_status == "stale"
    assert next(k for k in build_dashboard(r2).kpis if k.key == "prob").value == "Results out of date"
    assert next(k for k in d.kpis if k.key == "days").value == str(
        (r.plan.event.date - today).days)
