import time

import numpy as np
import pytest

from wellnesspop.budget import build_model
from wellnesspop.demos import load_demo
from wellnesspop.planner import build_plan, run_simulation
from wellnesspop.simulation import simulate
from wellnesspop.staffing import calculate_staffing
from wellnesspop.validation import validate_plan


def _sim(raw, today, **kw):
    plan = validate_plan(raw, today)
    return plan, simulate(plan, calculate_staffing(plan), **kw)


def test_deterministic_limit_reproduces_hand_net_every_trial(hand_raw, today):
    hand_raw["attendance"].update(low=40, likely=40, high=40)
    _, sim = _sim(hand_raw, today)
    assert sim.runs == 10_000
    assert np.allclose(sim.net, 156.80, atol=0.005)
    assert sim.probability_break_even == 1.0


def test_seed_reproducibility_and_seed_sensitivity(today):
    raw = load_demo("scenario_a", today)
    _, a = _sim(raw, today)
    _, b = _sim(raw, today)
    _, c = _sim(raw, today, seed=7)
    assert np.array_equal(a.net, b.net) and np.array_equal(a.cancelled, b.cancelled)
    assert not np.array_equal(a.net, c.net)


def test_global_rng_untouched(today):
    np.random.seed(123)
    expected = np.random.random()
    np.random.seed(123)
    _sim(load_demo("scenario_b", today), today)
    assert np.random.random() == expected


def test_three_uncertain_inputs_sampled_within_bounds(hand_raw, today):
    hand_raw["no_show"].update(low=0.1, mean=0.2, high=0.3)
    hand_raw["variable_costs"][0].update(low=1, mode=2, high=4)
    plan, sim = _sim(hand_raw, today)
    assert len(sim.dimensions) == 3
    staff = calculate_staffing(plan)
    model = build_model(plan, staff)
    # Bounds: worst case 25 regs, 30% no-show, $4 cost; best 55 regs, 10% no-show, $1 cost.
    worst = 25 * 0.7 * (20 * 0.97 - 4) - 400
    best = 55 * 0.9 * (20 * 0.97 - 1) - 400
    assert sim.net.min() >= worst - 1e-6 and sim.net.max() <= best + 1e-6
    assert model.var_mean == pytest.approx(7 / 3)


def test_wider_symmetric_attendance_widens_spread(hand_raw, today):
    hand_raw["attendance"].update(low=35, likely=40, high=45)
    _, narrow = _sim(hand_raw, today)
    hand_raw["attendance"].update(low=20, likely=40, high=60)
    _, wide = _sim(hand_raw, today)
    assert (wide.p90 - wide.p10) > (narrow.p90 - narrow.p10)


def _outdoor(raw, p):
    raw["event"]["setting"] = "outdoor"
    raw["rain"].update(has_rain_plan=True, alternate_venue="Gym")
    raw["weather"]["cancellation_probability"] = p
    raw["attendance"].update(low=40, likely=40, high=40)
    return raw


def test_cancellation_probability_zero_and_one(hand_raw, today):
    _, never = _sim(_outdoor(hand_raw, 0.0), today)
    assert never.cancelled_share == 0 and np.allclose(never.net, 156.8)
    hand_raw["fixed_costs"][0]["retained_fraction"] = 0.5
    _, always = _sim(_outdoor(hand_raw, 1.0), today)
    assert always.cancelled_share == 1
    assert np.allclose(always.net, -200.0)  # attendance revenue lost, half the fixed cost kept


def test_prepaid_refund_and_processing_fee_on_cancellation(hand_raw, today):
    raw = _outdoor(hand_raw, 1.0)
    raw["ticket_tiers"][0].update(billing_basis="registered", refund_fraction=1,
                                  fee_refund_fraction=0)
    raw["fixed_costs"][0]["retained_fraction"] = 0
    _, sim = _sim(raw, today)
    # Full refund of 40 x $20 but processor keeps 3% fees: -$24.
    assert np.allclose(sim.net, -24.0)
    raw["ticket_tiers"][0].update(refund_fraction=0.5)
    _, sim = _sim(raw, today)
    # Keep $400 receipts; fees retained on 800 * 0.03 * (1 - 0.5*0) = 24 -> 376.
    assert np.allclose(sim.net, 376.0)


def test_tier_no_show_override_is_its_own_dimension(hand_raw, today):
    hand_raw["ticket_tiers"][0].update(no_show_low=0.3, no_show_mean=0.4, no_show_high=0.5)
    _, sim = _sim(hand_raw, today)
    assert any("General" in d for d in sim.dimensions)
    assert any("General" in t.name for t in sim.tornado)


def test_uncertain_fixed_row_sampled(hand_raw, today):
    hand_raw["fixed_costs"][0].update(uncertain=True, low=300, mode=400, high=800)
    hand_raw["attendance"].update(low=40, likely=40, high=40)
    _, sim = _sim(hand_raw, today)
    assert sim.net.max() <= 556.8 - 300 + 1e-6 and sim.net.min() >= 556.8 - 800 - 1e-6
    assert sim.mean == pytest.approx(556.8 - 500, abs=5)


def test_tornado_sorted_and_weather_labeled(today):
    plan, sim = _sim(load_demo("scenario_a", today), today)
    ranges = [t.impact_range for t in sim.tornado]
    assert ranges == sorted(ranges, reverse=True)
    weather = [t for t in sim.tornado if t.kind == "weather"]
    assert len(weather) == 1 and weather[0].low_input == 0 and weather[0].high_input == 1


def test_minimum_runs_enforced(hand_raw, today):
    plan = validate_plan(hand_raw, today)
    with pytest.raises(ValueError):
        simulate(plan, calculate_staffing(plan), runs=500)


def test_percentiles_and_tolerance(hand_raw, today):
    hand_raw["fixed_costs"][0]["amount"] = 556.8  # exactly break-even at 40 registrations
    hand_raw["attendance"].update(low=40, likely=40, high=40)
    _, sim = _sim(hand_raw, today)
    assert sim.probability_break_even == 1.0  # float residues treated as zero
    assert sim.p10 == sim.p50 == sim.p90 == 0.0


def test_ten_thousand_runs_under_five_seconds_end_to_end(today):
    for key in ("scenario_a", "scenario_b", "scenario_c"):
        plan = validate_plan(load_demo(key, today), today)
        start = time.perf_counter()
        r = build_plan(plan, today=today)
        sim = run_simulation(r)
        assert time.perf_counter() - start < 5.0
        assert sim.runs >= 10_000 and sim.fingerprint == r.input_fingerprint
