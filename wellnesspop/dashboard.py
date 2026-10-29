"""One-screen project dashboard measures, all read from a single ``PlanResult``."""

from __future__ import annotations

from dataclasses import dataclass

from wellnesspop import fmt
from wellnesspop.planner import PlanResult


@dataclass(frozen=True)
class Kpi:
    key: str
    label: str
    value: str
    detail: str
    status: str  # good | warn | bad | info


@dataclass(frozen=True)
class Dashboard:
    kpis: tuple[Kpi, ...]
    supporting: tuple[tuple[str, str], ...]
    top_risks: tuple[str, ...]
    revision: str
    simulation_status: str


def build_dashboard(result: PlanResult) -> Dashboard:
    b, be, plan = result.budget, result.break_even, result.plan
    likely = b.likely
    target = plan.goals.target_net_income
    kpis = [Kpi("net", "Projected net income (likely)", fmt.money(likely.net),
                f"Target {fmt.money(target)} - "
                + ("meets target" if likely.net >= target - 1e-9 else "below target"),
                "good" if likely.net >= target - 1e-9 else "bad")]
    limit = b.spending_limit
    if limit is None:
        kpis.append(Kpi("cost", "Projected total cost", fmt.money(likely.total_cost),
                        "Spending limit not supplied", "info"))
    else:
        within = likely.total_cost <= limit + 1e-9
        kpis.append(Kpi("cost", "Projected total cost vs limit", fmt.money(likely.total_cost),
                        f"Limit {fmt.money(limit)} - " + ("within limit" if within else
                                                          "over limit"),
                        "good" if within else "bad"))
    status = result.simulation_status
    sim = result.current_simulation
    if sim is not None:
        p = sim.probability_break_even
        kpis.append(Kpi("prob", "Probability of breaking even", fmt.pct(p),
                        f"{sim.runs:,} runs, seed {sim.seed}",
                        "good" if p >= 0.7 else ("warn" if p >= 0.4 else "bad")))
    else:
        kpis.append(Kpi("prob", "Probability of breaking even",
                        "Run simulation" if status == "not_run" else "Results out of date",
                        "Open the Simulation page to run it for the current inputs", "warn"))
    days = (plan.event.date - result.today).days
    kpis.append(Kpi("days", "Days to event", str(days),
                    f"{plan.event.date:%a %d %b %Y} ({plan.event.timezone})",
                    "info" if days >= 0 else "warn"))
    top = tuple(f"{r.title} ({r.band}, score {r.score})" for r in result.risks
                if r.status != "closed")[:3]
    kpis.append(Kpi("risks", "Top risks", str(len(top)) + " shown",
                    "; ".join(top) or "No open risks",
                    "bad" if any("Critical" in t for t in top) else "info"))
    s = result.staffing
    gaps = []
    if s.total_gap:
        gaps.append(f"{s.total_gap} more people recommended")
    if s.missing_credentials:
        gaps.append(f"{len(s.missing_credentials)} credential(s) unconfirmed")
    kpis.append(Kpi("staffing", "Staffing coverage",
                    "Covered" if s.coverage_ok else "Gaps", "; ".join(gaps) or
                    f"Planned peak {fmt.num(s.planned_peak)} people",
                    "good" if s.coverage_ok else "warn"))
    m = result.marketing
    kpis.append(Kpi("marketing", "Marketing tasks complete", f"{m.complete} / {m.total}",
                    f"{m.infeasible_count} before earliest start" if m.infeasible_count else
                    "All scheduled on or after earliest start",
                    "warn" if m.infeasible_count else "info"))
    supporting = [
        ("Venue capacity", str(plan.venue.capacity)),
        ("Break-even registrations",
         str(be.registrations) if be.registrations is not None else "Not achievable within capacity"),
    ]
    if sim is not None:
        supporting.append(("Net income P10 - P90",
                           f"{fmt.money(sim.p10)} to {fmt.money(sim.p90)}"))
    else:
        supporting.append(("Net income P10 - P90", "Run simulation"))
    if result.schedule is not None:
        supporting.append(("Schedule problems", str(len(result.schedule.problems))))
    return Dashboard(tuple(kpis), tuple(supporting), top, result.revision_fingerprint, status)
