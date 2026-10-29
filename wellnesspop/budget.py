"""Shared financial evaluator, deterministic budget, and break-even search.

One evaluator (``evaluate``) is used by the budget, break-even search, Monte Carlo
simulation, and sensitivity analysis. It accepts scalars or NumPy arrays.

Definitions (see docs/decisions.md):
    R   registrations, capped at venue capacity
    A_j registrations allocated to tier j times (1 - no-show rate of tier j)
    Ticket gross_j = price_j * (A_j if billed on attendance else R_j)
    Net = ticket net + additional net - fixed costs - A * variable cost
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from wellnesspop import fmt
from wellnesspop.schema import AdditionalRevenue, NoShowInput, PlanInput, TicketTier
from wellnesspop.staffing import StaffingResult

ZERO_TOL = 1e-9  # USD; floating residues at most this size are treated as exactly zero


def normalize_zero(net):
    arr = np.asarray(net, dtype=float)
    return np.where(np.abs(arr) <= ZERO_TOL, 0.0, arr)


# --------------------------------------------------------------------------- ledger


@dataclass(frozen=True)
class LedgerItem:
    id: str
    source: str  # venue, permit, insurance, deposit, fixed_cost, staffing, marketing
    label: str
    category: str
    low: float
    mode: float
    high: float
    uncertain: bool
    retained_fraction: float

    @property
    def mean(self) -> float:
        return (self.low + self.mode + self.high) / 3 if self.uncertain else self.mode


def _known(id_, source, label, category, amount, retained) -> LedgerItem:
    return LedgerItem(id_, source, label, category, amount, amount, amount, False, retained)


def build_ledger(plan: PlanInput, staffing: StaffingResult) -> tuple[LedgerItem, ...]:
    """Canonical fixed-cost ledger. Each cost has exactly one authoritative source."""
    v = plan.venue
    items: list[LedgerItem] = []
    if v.rental_total > 0:
        items.append(_known("ledger-rental", "venue", f"Venue rental ({v.name})", "venue",
                            v.rental_total, v.rental_retained_fraction))
    if v.permit_required:
        items.append(_known("ledger-permit", "permit", "Permit", "permit", v.permit_cost,
                            v.permit_retained_fraction))
    if v.insurance_required:
        items.append(_known("ledger-insurance", "insurance", "Insurance", "insurance",
                            v.insurance_cost, v.insurance_retained_fraction))
    forfeit = v.security_deposit * v.security_deposit_forfeit_fraction
    if forfeit > 0:
        items.append(_known("ledger-deposit-forfeit", "deposit",
                            "Security deposit expected to be forfeited", "venue", forfeit, 1.0))
    for c in plan.fixed_costs:
        items.append(LedgerItem(c.id, "fixed_cost", c.label, c.category, c.low, c.mode, c.high,
                                c.uncertain, c.retained_fraction))
    for r in staffing.rows:
        items.append(_known(r.id, "staffing", f"Staffing: {r.role}", "staffing", r.cost,
                            r.retained_fraction))
    if plan.marketing.budget > 0:
        items.append(_known("ledger-marketing", "marketing", "Marketing budget", "marketing",
                            plan.marketing.budget, plan.marketing.budget_retained_fraction))
    return tuple(items)


# ---------------------------------------------------------------------------- model


@dataclass(frozen=True)
class FinancialModel:
    capacity: float
    fee_rate: float
    tiers: tuple[TicketTier, ...]
    addons: tuple[AdditionalRevenue, ...]
    ledger: tuple[LedgerItem, ...]
    var_low: float
    var_mode: float
    var_high: float
    var_retained: float
    no_show: NoShowInput
    weather_p: float

    @property
    def var_mean(self) -> float:
        return (self.var_low + self.var_mode + self.var_high) / 3

    @property
    def fixed_means(self) -> np.ndarray:
        return np.array([i.mean for i in self.ledger], dtype=float)


def build_model(plan: PlanInput, staffing: StaffingResult) -> FinancialModel:
    vcs = plan.variable_costs
    lo = sum(v.low for v in vcs)
    mo = sum(v.mode for v in vcs)
    hi = sum(v.high for v in vcs)
    mean_total = sum(v.mean for v in vcs)
    # Aggregated rows move together; retention is weighted by each row's mean cost.
    retained = (sum(v.mean * v.retained_fraction for v in vcs) / mean_total) if mean_total else 0.0
    return FinancialModel(
        capacity=float(plan.venue.capacity), fee_rate=plan.processing.ticket_fee_rate,
        tiers=plan.ticket_tiers, addons=plan.additional_revenue,
        ledger=build_ledger(plan, staffing), var_low=lo, var_mode=mo, var_high=hi,
        var_retained=retained, no_show=plan.no_show,
        weather_p=plan.weather.cancellation_probability,
    )


@dataclass
class Evaluation:
    registrations: np.ndarray
    attendees: np.ndarray
    tier_registrations: list
    tier_attendees: list
    tier_billable: list
    tier_gross: list
    ticket_gross: np.ndarray
    ticket_fees: np.ndarray
    ticket_net: np.ndarray
    addon_units: list
    addon_gross: list
    addon_fees: list
    addl_gross: np.ndarray
    addl_fees: np.ndarray
    addl_net: np.ndarray
    fixed_total: np.ndarray
    variable_expense: np.ndarray
    ordinary_net: np.ndarray
    cancelled_net: np.ndarray
    net: np.ndarray
    extra: dict = field(default_factory=dict)

    @property
    def total_cost(self):
        return self.fixed_total + self.variable_expense


def evaluate(model: FinancialModel, registrations, no_show, variable_cost, fixed_amounts=None,
             cancelled=None, tier_no_show: dict | None = None) -> Evaluation:
    """Evaluate the financial model. All numeric inputs may be scalars or 1-D arrays.

    fixed_amounts: shape (n_ledger,) or (n_ledger, n); defaults to ledger means.
    cancelled: boolean scalar/array; ``None`` means the event proceeds.
    tier_no_show: optional {tier_id: rate(s)} for tiers with their own no-show override.
    """
    R = np.minimum(np.maximum(np.asarray(registrations, dtype=float), 0.0), model.capacity)
    q_event = np.asarray(no_show, dtype=float)
    v = np.asarray(variable_cost, dtype=float)
    tier_no_show = tier_no_show or {}

    quota_total = float(sum(t.free_quota or 0 for t in model.tiers))
    quota_alloc = np.minimum(R, quota_total)
    remaining = np.maximum(R - quota_total, 0.0)

    tier_R, tier_A, tier_bill, tier_gross = [], [], [], []
    for t in model.tiers:
        if t.allocation == "free_quota":
            r_j = quota_alloc * ((t.free_quota or 0) / quota_total) if quota_total else R * 0.0
        else:
            r_j = remaining * t.weight
        if t.has_no_show_override:
            q_j = np.asarray(tier_no_show.get(t.id, t.no_show_mean), dtype=float)
        else:
            q_j = q_event
        a_j = r_j * (1.0 - q_j)
        billable = a_j if t.billing_basis == "attended" else r_j
        tier_R.append(r_j)
        tier_A.append(a_j)
        tier_bill.append(billable)
        tier_gross.append(t.price * billable)
    A = sum(tier_A) if tier_A else R * 0.0
    ticket_gross = sum(tier_gross) if tier_gross else R * 0.0
    ticket_fees = ticket_gross * model.fee_rate
    ticket_net = ticket_gross - ticket_fees

    add_units, add_gross, add_fees = [], [], []
    for a in model.addons:
        if a.quantity_basis == "fixed":
            units = np.broadcast_to(np.asarray(a.quantity, dtype=float), np.shape(A)).copy()
        else:
            units = A * a.uptake_rate * a.units_per_buyer
        gross = units * a.unit_price
        add_units.append(units)
        add_gross.append(gross)
        add_fees.append(gross * a.fee_rate)
    addl_gross = sum(add_gross) if add_gross else A * 0.0
    addl_fees = sum(add_fees) if add_fees else A * 0.0
    addl_net = addl_gross - addl_fees

    amounts = model.fixed_means if fixed_amounts is None else np.asarray(fixed_amounts, float)
    if amounts.size == 0:
        fixed_total = np.asarray(0.0)
        fixed_retained = np.asarray(0.0)
    else:
        retained_w = np.array([i.retained_fraction for i in model.ledger], dtype=float)
        if amounts.ndim == 1:
            fixed_total = np.asarray(amounts.sum())
            fixed_retained = np.asarray((amounts * retained_w).sum())
        else:
            fixed_total = amounts.sum(axis=0)
            fixed_retained = (amounts * retained_w[:, None]).sum(axis=0)
    variable_expense = A * v
    ordinary_net = ticket_net + addl_net - fixed_total - variable_expense

    # Cancellation branch: only prepaid lines keep receipts, net of refunds and fees.
    cancel_rev = A * 0.0
    for t, r_j in zip(model.tiers, tier_R):
        if t.billing_basis == "registered" and t.price > 0:
            g = t.price * r_j
            cancel_rev = cancel_rev + g * (1 - t.refund_fraction) - g * model.fee_rate * (
                1 - t.refund_fraction * t.fee_refund_fraction)
    for a, units in zip(model.addons, add_units):
        if a.prepaid:
            g = units * a.unit_price
            cancel_rev = cancel_rev + g * (1 - a.refund_fraction) - g * a.fee_rate * (
                1 - a.refund_fraction * a.fee_refund_fraction)
    cancelled_net = cancel_rev - fixed_retained - variable_expense * model.var_retained

    if cancelled is None:
        net = ordinary_net
    else:
        net = np.where(np.asarray(cancelled, dtype=bool), cancelled_net, ordinary_net)
    return Evaluation(
        registrations=R, attendees=A, tier_registrations=tier_R, tier_attendees=tier_A,
        tier_billable=tier_bill, tier_gross=tier_gross, ticket_gross=ticket_gross,
        ticket_fees=ticket_fees, ticket_net=ticket_net, addon_units=add_units,
        addon_gross=add_gross, addon_fees=add_fees, addl_gross=addl_gross, addl_fees=addl_fees,
        addl_net=addl_net, fixed_total=fixed_total, variable_expense=variable_expense,
        ordinary_net=ordinary_net, cancelled_net=cancelled_net, net=net,
    )


def evaluate_baseline(model: FinancialModel, registrations, cancelled=None) -> Evaluation:
    """Deterministic evaluation: mean no-show, mean variable cost, mean fixed amounts."""
    return evaluate(model, registrations, model.no_show.mean, model.var_mean,
                    cancelled=cancelled)


# --------------------------------------------------------------------------- budget


@dataclass(frozen=True)
class LineItem:
    label: str
    kind: str  # ticket | additional
    registrations: float | None
    attendees: float | None
    units: float
    price: float
    gross: float
    fees: float
    net: float


@dataclass(frozen=True)
class ScenarioBudget:
    name: str
    registrations: float
    attendees: float
    lines: tuple[LineItem, ...]
    ticket_gross: float
    ticket_fees: float
    ticket_net: float
    addl_gross: float
    addl_fees: float
    addl_net: float
    revenue_net: float
    fixed_total: float
    variable_expense: float
    total_cost: float
    processing_fees: float
    net: float


@dataclass(frozen=True)
class BudgetResult:
    ledger: tuple[LedgerItem, ...]
    fixed_total: float
    variable_cost_per_attendee: float
    scenarios: dict  # low / likely / high -> ScenarioBudget
    rental_advance: float
    security_deposit: float
    cash_required_upfront: float
    spending_limit: float | None
    target_net_income: float
    notes: tuple[str, ...]

    @property
    def likely(self) -> ScenarioBudget:
        return self.scenarios["likely"]


def _f(x) -> float:
    return float(np.asarray(x))


def scenario_budget(model: FinancialModel, name: str, registrations: float) -> ScenarioBudget:
    e = evaluate_baseline(model, registrations)
    lines = []
    for t, r_j, a_j, bill, gross in zip(model.tiers, e.tier_registrations, e.tier_attendees,
                                        e.tier_billable, e.tier_gross):
        g = _f(gross)
        lines.append(LineItem(t.label, "ticket", _f(r_j), _f(a_j), _f(bill), t.price, g,
                              g * model.fee_rate, g * (1 - model.fee_rate)))
    for a, units, gross, fees in zip(model.addons, e.addon_units, e.addon_gross, e.addon_fees):
        lines.append(LineItem(a.label, "additional", None, None, _f(units), a.unit_price,
                              _f(gross), _f(fees), _f(gross) - _f(fees)))
    return ScenarioBudget(
        name=name, registrations=_f(e.registrations), attendees=_f(e.attendees),
        lines=tuple(lines), ticket_gross=_f(e.ticket_gross), ticket_fees=_f(e.ticket_fees),
        ticket_net=_f(e.ticket_net), addl_gross=_f(e.addl_gross), addl_fees=_f(e.addl_fees),
        addl_net=_f(e.addl_net), revenue_net=_f(e.ticket_net + e.addl_net),
        fixed_total=_f(e.fixed_total), variable_expense=_f(e.variable_expense),
        total_cost=_f(e.total_cost), processing_fees=_f(e.ticket_fees + e.addl_fees),
        net=_f(normalize_zero(e.ordinary_net)),
    )


def calculate_budget(plan: PlanInput, staffing: StaffingResult,
                     model: FinancialModel | None = None) -> BudgetResult:
    model = model or build_model(plan, staffing)
    att = plan.attendance
    scenarios = {n: scenario_budget(model, n, r)
                 for n, r in (("low", att.low), ("likely", att.likely), ("high", att.high))}
    v = plan.venue
    notes = [
        "Low/likely/high use registration estimates, the mean no-show rate, the mean variable "
        "cost, and the mean of any uncertain fixed cost. They assume the event goes ahead; "
        "weather risk appears in the simulation.",
        "Expected attendees can be fractional because they are averages, not head counts.",
        "Total cost is fixed costs plus variable costs. Processing fees are deducted from "
        "revenue and shown separately.",
    ]
    if v.security_deposit > 0:
        notes.append("The refundable security deposit is cash you need up front, not an expense"
                     + (" (except the share marked as expected to be forfeited)."
                        if v.security_deposit_forfeit_fraction > 0 else "."))
    if any(t.allocation == "free_quota" for t in plan.ticket_tiers):
        notes.append("Fixed free places are a simplified reservation: they are filled first and "
                     "are not observed ticket sales.")
    return BudgetResult(
        ledger=model.ledger, fixed_total=float(model.fixed_means.sum()),
        variable_cost_per_attendee=model.var_mean, scenarios=scenarios,
        rental_advance=v.rental_advance, security_deposit=v.security_deposit,
        cash_required_upfront=v.rental_advance + v.security_deposit,
        spending_limit=plan.goals.spending_limit,
        target_net_income=plan.goals.target_net_income, notes=tuple(notes),
    )


# ------------------------------------------------------------------------ break-even


@dataclass(frozen=True)
class BreakEvenResult:
    status: str  # achievable | not_achievable
    registrations: int | None
    attendees_at_registrations: float | None
    onsite_attendance: int | None
    sentence: str
    price_status: str  # ok | not_applicable | covered
    price_target: str
    required_price: float | None
    raw_required_price: float | None
    price_basis_registrations: float
    price_sentence: str
    simple: dict | None  # closed-form check for a constant blended price, when valid


def _simple_formula(plan: PlanInput, model: FinancialModel) -> dict | None:
    tiers = plan.ticket_tiers
    if (plan.additional_revenue or any(t.allocation != "weighted" for t in tiers)
            or any(t.billing_basis != "attended" or t.has_no_show_override for t in tiers)):
        return None
    price = sum(t.price * t.weight for t in tiers)
    q, f, v = model.no_show.mean, model.fee_rate, model.var_mean
    F = float(model.fixed_means.sum())
    contribution = price * (1 - f) - v
    out = {"blended_price": price, "contribution_per_attendee": contribution, "fixed": F}
    if contribution > 0:
        out["break_even_attendance"] = math.ceil(F / contribution - 1e-9)
        out["break_even_registrations"] = (math.ceil(F / ((1 - q) * contribution) - 1e-9)
                                           if q < 1 else None)
    return out


def calculate_break_even(plan: PlanInput, staffing: StaffingResult,
                         model: FinancialModel | None = None,
                         price_target: str | None = None) -> BreakEvenResult:
    model = model or build_model(plan, staffing)
    cap = int(model.capacity)
    grid = np.arange(0, cap + 1, dtype=float)
    e = evaluate_baseline(model, grid)
    net = normalize_zero(e.ordinary_net)
    hits = np.nonzero(net >= 0)[0]
    if hits.size:
        n = int(hits[0])
        if n == 0:
            onsite = 0
        else:
            prev, cur = net[n - 1], net[n]
            r_star = (n - 1) + (-prev) / (cur - prev)
            a_star = _f(evaluate_baseline(model, r_star).attendees)
            onsite = math.ceil(a_star - 1e-9)
        a_n = float(e.attendees[n])
        status = "achievable"
        sentence = (f"At the current prices and costs, this event needs {n} registrations "
                    f"(about {fmt.num(a_n)} people on site) to cover its costs.")
        if n == 0:
            sentence = "At the current prices and costs, this event covers its costs even with no registrations."
    else:
        n, a_n, onsite, status = None, None, None, "not_achievable"
        marginal = net[-1] - net[-2] if cap >= 1 else 0.0
        if marginal <= 0:
            sentence = ("Not achievable within venue capacity: each extra registration adds no "
                        "net money at current prices, costs, and no-show rates.")
        else:
            sentence = (f"Not achievable within venue capacity: even {cap} registrations leave a "
                        f"loss of {fmt.money(-net[-1])}.")

    # Break-even price at likely registrations, holding everything else constant.
    likely = plan.attendance.likely
    b = evaluate_baseline(model, likely)
    costs = _f(b.fixed_total + b.variable_expense)
    paid = [i for i, t in enumerate(model.tiers) if t.price > 0]
    per_attendee = [i for i, a in enumerate(model.addons)
                    if a.quantity_basis == "per_attendee" and a.unit_price >= 0]
    if price_target is None:
        if paid:
            price_target = "tickets"
        elif per_attendee:
            price_target = model.addons[per_attendee[0]].id
        else:
            price_target = "tickets"
    raw_price = None
    if price_target == "tickets":
        target_label = "required average paid ticket price"
        units = sum(_f(b.tier_billable[i]) for i in paid)
        other = _f(b.addl_net) + sum(_f(b.tier_gross[i]) * (1 - model.fee_rate)
                                     for i in range(len(model.tiers)) if i not in paid)
        denom = units * (1 - model.fee_rate)
    else:
        k = next(i for i, a in enumerate(model.addons) if a.id == price_target)
        addon = model.addons[k]
        target_label = f"required {addon.label} price"
        units = _f(b.addon_units[k])
        other = _f(b.ticket_net) + sum(_f(b.addon_gross[j]) - _f(b.addon_fees[j])
                                       for j in range(len(model.addons)) if j != k)
        denom = units * (1 - addon.fee_rate)
    if denom <= ZERO_TOL:
        price_status, price = "not_applicable", None
        price_sentence = "Not applicable: no paid units to price at likely registrations."
    else:
        raw_price = (costs - other) / denom
        if raw_price <= 0:
            price_status, price = "covered", 0.0
            price_sentence = (f"The {target_label} is $0.00: other revenue already covers costs "
                              f"at {fmt.num(likely)} registrations.")
        else:
            price_status, price = "ok", raw_price
            price_sentence = (f"At {fmt.num(likely)} registrations, the {target_label} to break "
                              f"even is {fmt.money(raw_price)}.")
    return BreakEvenResult(
        status=status, registrations=n, attendees_at_registrations=a_n,
        onsite_attendance=onsite, sentence=sentence, price_status=price_status,
        price_target=target_label, required_price=price, raw_required_price=raw_price,
        price_basis_registrations=likely, price_sentence=price_sentence,
        simple=_simple_formula(plan, model),
    )
