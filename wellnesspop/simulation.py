"""Vectorized Monte Carlo forecast and one-at-a-time (tornado) sensitivity.

Uses a local ``numpy.random.default_rng(seed)``; global RNG state is never touched.
Draw order is fixed so results reproduce for the same input snapshot, seed, engine
version, and pinned numerical dependencies.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
from scipy import stats

from wellnesspop import fmt
from wellnesspop.budget import FinancialModel, build_model, evaluate, normalize_zero
from wellnesspop.schema import ENGINE_VERSION, MIN_RUNS, PlanInput
from wellnesspop.staffing import StaffingResult

PERT_LAMBDA = 4.0
QUANTILE_METHOD = "linear"
HISTOGRAM_BINS = 40


# ------------------------------------------------------------------ distributions


def pert_params(a: float, m: float, b: float, lam: float = PERT_LAMBDA) -> tuple[float, float]:
    return 1 + lam * (m - a) / (b - a), 1 + lam * (b - m) / (b - a)


def sample_pert(rng, a, m, b, n):
    if b == a:
        return np.full(n, float(a))
    al, be = pert_params(a, m, b)
    return a + (b - a) * rng.beta(al, be, n)


def ppf_pert(p, a, m, b):
    if b == a:
        return float(a)
    al, be = pert_params(a, m, b)
    return float(a + (b - a) * stats.beta.ppf(p, al, be))


def scaled_beta_params(low, mean, high, k):
    z = (mean - low) / (high - low)
    return z * k, (1 - z) * k


def sample_scaled_beta(rng, low, mean, high, k, n):
    if high == low:
        return np.full(n, float(low))
    al, be = scaled_beta_params(low, mean, high, k)
    return low + (high - low) * rng.beta(al, be, n)


def ppf_scaled_beta(p, low, mean, high, k):
    if high == low:
        return float(low)
    al, be = scaled_beta_params(low, mean, high, k)
    return float(low + (high - low) * stats.beta.ppf(p, al, be))


def sample_triangular(rng, lo, mo, hi, n):
    if hi == lo:
        return np.full(n, float(lo))
    return rng.triangular(lo, mo, hi, n)


def ppf_triangular(p, lo, mo, hi):
    if hi == lo:
        return float(lo)
    return float(stats.triang.ppf(p, (mo - lo) / (hi - lo), loc=lo, scale=hi - lo))


# ------------------------------------------------------------------------ results


@dataclass(frozen=True)
class TornadoRow:
    name: str
    kind: str  # continuous | weather
    unit: str
    low_input: float
    high_input: float
    net_at_low: float
    net_at_high: float
    baseline_net: float

    @property
    def impact_range(self) -> float:
        return abs(self.net_at_high - self.net_at_low)


@dataclass(frozen=True)
class SimulationResult:
    fingerprint: str
    seed: int
    runs: int
    engine_version: str
    net: np.ndarray
    cancelled: np.ndarray
    probability_break_even: float
    p10: float
    p50: float
    p90: float
    mean: float
    cancelled_share: float
    histogram_counts: tuple[int, ...]
    histogram_edges: tuple[float, ...]
    tornado: tuple[TornadoRow, ...]
    baseline_expected_net: float
    dimensions: tuple[str, ...]
    elapsed_seconds: float
    explainer: tuple[str, ...]


def _expected_net(model, R, q, v, fixed, p, tier_q) -> float:
    e = evaluate(model, R, q, v, fixed, tier_no_show=tier_q)
    return float((1 - p) * e.ordinary_net + p * e.cancelled_net)


def tornado_rows(plan: PlanInput, model: FinancialModel) -> tuple[list[TornadoRow], float]:
    att, ns = plan.attendance, plan.no_show
    base = {
        "R": att.likely, "q": ns.mean, "v": model.var_mean, "fixed": model.fixed_means.copy(),
        "p": model.weather_p,
        "tier_q": {t.id: t.no_show_mean for t in model.tiers if t.has_no_show_override},
    }

    def run(**over) -> float:
        args = {**base, **over}
        return _expected_net(model, args["R"], args["q"], args["v"], args["fixed"], args["p"],
                             args["tier_q"])

    baseline = run()
    rows: list[TornadoRow] = []

    def add(name, unit, lo, hi, net_lo, net_hi, kind="continuous"):
        rows.append(TornadoRow(name, kind, unit, lo, hi, net_lo, net_hi, baseline))

    if att.high > att.low:
        lo = min(ppf_pert(0.1, att.low, att.likely, att.high), model.capacity)
        hi = min(ppf_pert(0.9, att.low, att.likely, att.high), model.capacity)
        add("Registrations", "registrations", lo, hi, run(R=lo), run(R=hi))
    if ns.high > ns.low:
        lo = ppf_scaled_beta(0.1, ns.low, ns.mean, ns.high, ns.concentration)
        hi = ppf_scaled_beta(0.9, ns.low, ns.mean, ns.high, ns.concentration)
        add("No-show rate", "fraction", lo, hi, run(q=lo), run(q=hi))
    for t in model.tiers:
        if t.has_no_show_override and t.no_show_high > t.no_show_low:
            lo = ppf_scaled_beta(0.1, t.no_show_low, t.no_show_mean, t.no_show_high,
                                 t.no_show_concentration)
            hi = ppf_scaled_beta(0.9, t.no_show_low, t.no_show_mean, t.no_show_high,
                                 t.no_show_concentration)
            add(f"No-show rate: {t.label}", "fraction", lo, hi,
                run(tier_q={**base["tier_q"], t.id: lo}),
                run(tier_q={**base["tier_q"], t.id: hi}))
    if model.var_high > model.var_low:
        lo = ppf_triangular(0.1, model.var_low, model.var_mode, model.var_high)
        hi = ppf_triangular(0.9, model.var_low, model.var_mode, model.var_high)
        add("Variable cost per attendee", "USD", lo, hi, run(v=lo), run(v=hi))
    for i, item in enumerate(model.ledger):
        if item.uncertain and item.high > item.low:
            lo = ppf_triangular(0.1, item.low, item.mode, item.high)
            hi = ppf_triangular(0.9, item.low, item.mode, item.high)
            f_lo, f_hi = base["fixed"].copy(), base["fixed"].copy()
            f_lo[i], f_hi[i] = lo, hi
            add(f"Fixed cost: {item.label}", "USD", lo, hi, run(fixed=f_lo), run(fixed=f_hi))
    if plan.event.setting != "indoor":
        add("Weather cancellation (probability 0 to 1)", "probability", 0.0, 1.0, run(p=0.0),
            run(p=1.0), kind="weather")
    rows.sort(key=lambda r: (-r.impact_range, r.name))
    return rows, baseline


def simulate(plan: PlanInput, staffing: StaffingResult, seed: int | None = None,
             runs: int | None = None, fingerprint: str = "") -> SimulationResult:
    seed = plan.simulation.seed if seed is None else int(seed)
    runs = plan.simulation.runs if runs is None else int(runs)
    if runs < MIN_RUNS:
        raise ValueError(f"at least {MIN_RUNS} runs are required")
    started = time.perf_counter()
    model = build_model(plan, staffing)
    rng = np.random.default_rng(seed)
    att, ns = plan.attendance, plan.no_show
    dims = []

    R = np.minimum(sample_pert(rng, att.low, att.likely, att.high, runs), model.capacity)
    if att.high > att.low:
        dims.append("registrations (PERT)")
    q = sample_scaled_beta(rng, ns.low, ns.mean, ns.high, ns.concentration, runs)
    if ns.high > ns.low:
        dims.append("event no-show rate (scaled beta)")
    tier_q = {}
    for t in model.tiers:
        if t.has_no_show_override:
            tier_q[t.id] = sample_scaled_beta(rng, t.no_show_low, t.no_show_mean, t.no_show_high,
                                              t.no_show_concentration, runs)
            if t.no_show_high > t.no_show_low:
                dims.append(f"no-show rate: {t.label} (scaled beta)")
    v = sample_triangular(rng, model.var_low, model.var_mode, model.var_high, runs)
    if model.var_high > model.var_low:
        dims.append("variable cost per attendee (triangular, rows summed)")
    fixed = np.empty((len(model.ledger), runs))
    for i, item in enumerate(model.ledger):
        if item.uncertain:
            fixed[i] = sample_triangular(rng, item.low, item.mode, item.high, runs)
            if item.high > item.low:
                dims.append(f"fixed cost: {item.label} (triangular)")
        else:
            fixed[i] = item.mode
    p = model.weather_p if plan.event.setting != "indoor" else 0.0
    cancelled = rng.random(runs) < p
    if p > 0:
        dims.append("weather cancellation (Bernoulli)")

    e = evaluate(model, R, q, v, fixed if len(model.ledger) else None, cancelled=cancelled,
                 tier_no_show=tier_q)
    net = normalize_zero(e.net)
    prob = float(np.mean(net >= 0))
    p10, p50, p90 = (float(x) for x in np.quantile(net, [0.1, 0.5, 0.9], method=QUANTILE_METHOD))
    lo, hi = float(net.min()), float(net.max())
    if hi - lo < 1e-6:
        lo, hi = lo - 1, hi + 1
    counts, edges = np.histogram(net, bins=HISTOGRAM_BINS, range=(lo, hi))
    tornado, baseline = tornado_rows(plan, model)
    elapsed = time.perf_counter() - started
    explainer = _explain(prob, p10, p50, p90, tornado, p, runs)
    return SimulationResult(
        fingerprint=fingerprint, seed=seed, runs=runs, engine_version=ENGINE_VERSION, net=net,
        cancelled=cancelled, probability_break_even=prob, p10=p10, p50=p50, p90=p90,
        mean=float(net.mean()), cancelled_share=float(cancelled.mean()),
        histogram_counts=tuple(int(c) for c in counts),
        histogram_edges=tuple(float(x) for x in edges), tornado=tuple(tornado),
        baseline_expected_net=baseline, dimensions=tuple(dims), elapsed_seconds=elapsed,
        explainer=explainer,
    )


def _explain(prob, p10, p50, p90, tornado, p, runs) -> tuple[str, ...]:
    out = [
        f"In {prob:.0%} of {runs:,} simulated versions of this event, income covered costs.",
        f"In a typical outcome the event nets about {fmt.money(p50)}; in a bad case (1 in 10 "
        f"outcomes are worse) it nets {fmt.money(p10)}, and in a good case (1 in 10 are better) "
        f"{fmt.money(p90)}.",
    ]
    continuous = [r for r in tornado if r.kind == "continuous" and r.impact_range > 0]
    if continuous:
        top = continuous[0]
        out.append(f"The assumption that moves the result most is {top.name.lower()}: its "
                   f"plausible range shifts expected net income by about "
                   f"{fmt.money(top.impact_range)}.")
    if p > 0:
        out.append(f"Weather cancels the event in about {p:.0%} of runs; those runs keep only "
                   "prepaid, non-refunded income and lose the costs marked as retained.")
    out.append("This is a forecast built from your assumptions, not a guarantee. Inputs are "
               "sampled independently of each other.")
    return tuple(out)
