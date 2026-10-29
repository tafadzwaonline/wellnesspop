"""Snapshot orchestration: one validated input revision -> one immutable ``PlanResult``.

Every output (dashboard, workbook, PDF, CSV) reads from the same snapshot; exports never
recalculate financial totals independently.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass

from wellnesspop import schema as S
from wellnesspop import simulation as sim_mod
from wellnesspop.budget import (BreakEvenResult, BudgetResult, FinancialModel, build_model,
                                calculate_break_even, calculate_budget)
from wellnesspop.marketing import MarketingResult, generate_marketing
from wellnesspop.risk import Risk, generate_risks
from wellnesspop.schedule import ScheduleResult, Task, generate_wbs, schedule_tasks
from wellnesspop.schema import PlanInput
from wellnesspop.simulation import SimulationResult
from wellnesspop.staffing import StaffingResult, calculate_staffing
from wellnesspop.validation import Issue


def empty_edits() -> dict:
    return {"tasks": {"overrides": {}, "tombstones": [], "added": []},
            "risks": {"overrides": {}, "tombstones": [], "added": []},
            "marketing": {"status": {}, "compress": False}}


def _digest(obj) -> str:
    text = json.dumps(S.to_jsonable(obj), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def input_fingerprint(plan: PlanInput) -> str:
    """Fingerprint of everything that affects financial results (excludes provenance notes)."""
    data = plan.to_dict()
    data.pop("provenance", None)
    return _digest({"engine": S.ENGINE_VERSION, "plan": data})


def revision_fingerprint(plan: PlanInput, edits: dict) -> str:
    return _digest({"engine": S.ENGINE_VERSION, "plan": plan.to_dict(), "edits": edits})


@dataclass(frozen=True)
class PlanResult:
    plan: PlanInput
    edits: dict
    today: dt.date
    generated_at: dt.datetime
    input_fingerprint: str
    revision_fingerprint: str
    staffing: StaffingResult
    model: FinancialModel
    budget: BudgetResult
    break_even: BreakEvenResult
    tasks: tuple[Task, ...]
    schedule: ScheduleResult | None
    risks: tuple[Risk, ...]
    marketing: MarketingResult
    assumptions: tuple[dict, ...]
    issues: tuple[Issue, ...]
    simulation: SimulationResult | None = None

    @property
    def simulation_status(self) -> str:
        if self.simulation is None:
            return "not_run"
        return "current" if self.simulation.fingerprint == self.input_fingerprint else "stale"

    @property
    def current_simulation(self) -> SimulationResult | None:
        return self.simulation if self.simulation_status == "current" else None

    def with_simulation(self, simulation: SimulationResult | None) -> "PlanResult":
        from dataclasses import replace
        return replace(self, simulation=simulation)


def build_plan(plan: PlanInput, edits: dict | None = None, today: dt.date | None = None,
               simulation: SimulationResult | None = None) -> PlanResult:
    """Fast deterministic orchestration. Simulation is attached only if supplied."""
    edits = edits or empty_edits()
    today = today or S.today_in(plan.event.timezone)
    staffing = calculate_staffing(plan)
    model = build_model(plan, staffing)
    budget = calculate_budget(plan, staffing, model)
    be = calculate_break_even(plan, staffing, model)
    tasks, task_issues = generate_wbs(plan, staffing, edits.get("tasks"))
    schedule = None
    if not any(i.severity == "error" for i in task_issues):
        schedule = schedule_tasks(tasks, plan.event.date, today)
    risks, risk_issues = generate_risks(plan, edits.get("risks"))
    marketing = generate_marketing(plan, edits.get("marketing"), today)
    tz = S.ZoneInfo(plan.event.timezone)
    return PlanResult(
        plan=plan, edits=edits, today=today, generated_at=dt.datetime.now(tz),
        input_fingerprint=input_fingerprint(plan),
        revision_fingerprint=revision_fingerprint(plan, edits), staffing=staffing, model=model,
        budget=budget, break_even=be, tasks=tuple(tasks), schedule=schedule, risks=tuple(risks),
        marketing=marketing, assumptions=tuple(build_assumptions(plan)),
        issues=tuple(task_issues + risk_issues), simulation=simulation,
    )


def run_simulation(result: PlanResult, seed: int | None = None,
                   runs: int | None = None) -> SimulationResult:
    return sim_mod.simulate(result.plan, result.staffing, seed=seed, runs=runs,
                            fingerprint=result.input_fingerprint)


# ---------------------------------------------------------------------- assumptions


def _record_summary(group: str, row) -> str:
    d = S.to_jsonable(row)
    d.pop("id", None)
    return "; ".join(f"{k}={v}" for k, v in d.items() if v not in (None, [], ""))


def build_assumptions(plan: PlanInput) -> list[dict]:
    """Every effective input with unit and provenance, plus model choices (derived)."""
    prov = plan.provenance or {}
    data = plan.to_dict()
    rows = []
    for spec in S.SCALAR_SPECS:
        rec = prov.get(spec.path, {})
        value = S.get_path(data, spec.path)
        rows.append({
            "field_path": spec.path, "value": value, "unit": spec.unit,
            "source_kind": rec.get("source_kind", spec.provenance),
            "source_reference": rec.get("source_reference", "WellnessPop default rule: "
                                        + spec.default_rule),
            "as_of_date": rec.get("as_of_date", ""), "note": rec.get("note", ""),
            "original_source_kind": rec.get("original_source_kind", ""),
        })
    for group in S.RECORD_SPECS:
        for row in getattr(plan, group) or ():
            key = f"{group}:{row.id}"
            rec = prov.get(key, {})
            rows.append({
                "field_path": key, "value": _record_summary(group, row), "unit": "record",
                "source_kind": rec.get("source_kind", "illustrative"),
                "source_reference": rec.get("source_reference", "WellnessPop default or demo"),
                "as_of_date": rec.get("as_of_date", ""), "note": rec.get("note", ""),
                "original_source_kind": rec.get("original_source_kind", ""),
            })
    derived = [
        ("model.engine_version", S.ENGINE_VERSION, "-", "Calculation engine version"),
        ("model.attendance_distribution", f"modified PERT, lambda={sim_mod.PERT_LAMBDA:g}", "-",
         "R = a + (b-a)*Beta(1+4(m-a)/(b-a), 1+4(b-m)/(b-a))"),
        ("model.no_show_distribution", "scaled beta with concentration", "-",
         "q = l + (h-l)*Beta(z*k, (1-z)*k), z=(mean-l)/(h-l)"),
        ("model.variable_cost_distribution", "triangular on summed rows", "-",
         "Rows move together (shared movement)"),
        ("model.weather", "Bernoulli whole-event cancellation", "-",
         "Hybrid events: whole-event approximation"),
        ("model.quantile_method", sim_mod.QUANTILE_METHOD, "-", "numpy.quantile method"),
        ("model.zero_tolerance", "1e-9", "USD", "Residues within this are treated as zero"),
        ("derived.fixed_cost_ledger", "sum of ledger means", "USD",
         "venue + permit + insurance + forfeited deposit + fixed rows + staffing + marketing"),
    ]
    for path, value, unit, formula in derived:
        rows.append({"field_path": path, "value": value, "unit": unit, "source_kind": "derived",
                     "source_reference": formula, "as_of_date": "", "note": "",
                     "original_source_kind": ""})
    return rows
