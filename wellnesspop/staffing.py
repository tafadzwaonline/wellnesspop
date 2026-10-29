"""Staffing costs, coverage recommendations, and credential gaps."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from wellnesspop.schema import PlanInput, StaffRole, label

TEMPLATE_DIR = Path(__file__).parent / "templates"


@lru_cache(maxsize=1)
def role_templates() -> tuple[dict, ...]:
    """Public role suggestions (planning aids, not staffing or certification regulations)."""
    return tuple(json.loads((TEMPLATE_DIR / "roles.json").read_text(encoding="utf-8")))


@dataclass(frozen=True)
class StaffRow:
    id: str
    role: str
    count: int
    hours: float
    pay_basis: str
    rate: float
    volunteer: bool
    cost: float
    retained_fraction: float
    coverage_ratio: float | None
    recommended_count: int | None
    gap: int
    required_certifications: tuple[str, ...]
    confirmed_certifications: tuple[str, ...]
    missing_certifications: tuple[str, ...]
    unconfirmed_rate: bool


@dataclass(frozen=True)
class StaffingResult:
    rows: tuple[StaffRow, ...]
    total_cost: float
    planned_peak: float
    peak_source: str
    total_gap: int
    missing_credentials: tuple[str, ...]  # "Role: credential"
    has_paid_staff: bool
    has_volunteers: bool

    @property
    def coverage_ok(self) -> bool:
        return self.total_gap == 0 and not self.missing_credentials


def row_cost(role: StaffRole) -> float:
    if role.volunteer:
        return 0.0
    if role.pay_basis == "hourly":
        return role.count * role.hours * role.rate
    return role.count * role.rate


def calculate_staffing(plan: PlanInput) -> StaffingResult:
    if plan.attendance.planned_peak is not None:
        peak, source = plan.attendance.planned_peak, "organizer-supplied planned peak"
    else:
        peak, source = plan.attendance.high, "high registration estimate (conservative)"
    rows = []
    missing_all: list[str] = []
    for r in plan.staffing:
        recommended = None
        if r.coverage_ratio:
            recommended = math.ceil(peak / r.coverage_ratio - 1e-9) if peak > 0 else 0
        gap = max((recommended or 0) - r.count, 0)
        missing = tuple(c for c in r.required_certifications if c not in r.confirmed_certifications)
        missing_all += [f"{r.role}: {label(c)}" for c in missing]
        rows.append(StaffRow(
            id=r.id, role=r.role, count=r.count, hours=r.hours, pay_basis=r.pay_basis,
            rate=r.rate, volunteer=r.volunteer, cost=row_cost(r),
            retained_fraction=r.retained_fraction, coverage_ratio=r.coverage_ratio,
            recommended_count=recommended, gap=gap,
            required_certifications=r.required_certifications,
            confirmed_certifications=r.confirmed_certifications, missing_certifications=missing,
            unconfirmed_rate=(not r.volunteer and r.rate == 0 and r.count > 0),
        ))
    return StaffingResult(
        rows=tuple(rows), total_cost=sum(r.cost for r in rows), planned_peak=peak,
        peak_source=source, total_gap=sum(r.gap for r in rows),
        missing_credentials=tuple(missing_all),
        has_paid_staff=any(not r.volunteer and r.count > 0 for r in plan.staffing),
        has_volunteers=any(r.volunteer and r.count > 0 for r in plan.staffing),
    )
