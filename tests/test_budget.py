import copy
from decimal import Decimal

import numpy as np
import pytest

from wellnesspop import fmt
from wellnesspop.budget import build_model, calculate_break_even, calculate_budget, evaluate
from wellnesspop.staffing import calculate_staffing
from wellnesspop.validation import PlanValidationError, validate_plan


def _run(raw, today):
    plan = validate_plan(raw, today)
    staff = calculate_staffing(plan)
    return plan, staff, calculate_budget(plan, staff), calculate_break_even(plan, staff)


@pytest.mark.parametrize("scenario,regs,att,gross,fees,cost,net", [
    ("low", 25, 20, "400.00", "12.00", "440.00", "-52.00"),
    ("likely", 40, 32, "640.00", "19.20", "464.00", "156.80"),
    ("high", 55, 44, "880.00", "26.40", "488.00", "365.60"),
])
def test_hand_fixture_to_the_cent(hand_raw, today, scenario, regs, att, gross, fees, cost, net):
    _, _, budget, _ = _run(hand_raw, today)
    s = budget.scenarios[scenario]
    assert s.registrations == regs
    assert s.attendees == pytest.approx(att)
    assert fmt.to_cents(s.ticket_gross) == Decimal(gross)
    assert fmt.to_cents(s.processing_fees) == Decimal(fees)
    assert fmt.to_cents(s.total_cost) == Decimal(cost)
    assert fmt.to_cents(s.net) == Decimal(net)


def test_hand_fixture_break_even(hand_raw, today):
    _, _, _, be = _run(hand_raw, today)
    assert be.registrations == 29
    assert be.onsite_attendance == 23
    assert be.attendees_at_registrations == pytest.approx(23.2)
    assert be.raw_required_price == pytest.approx(464 / (32 * 0.97))
    assert fmt.money(be.required_price) == "$14.95"
    assert be.simple["break_even_attendance"] == 23
    assert be.simple["break_even_registrations"] == 29
    assert "29 registrations" in be.sentence


def test_staffing_cost_flows_into_every_scenario(hand_raw, today):
    _, _, base, _ = _run(hand_raw, today)
    hand_raw["staffing"] = [{"id": "s1", "role": "Instructor", "count": 1, "rate": 100,
                             "pay_basis": "flat"}]
    _, staff, with_staff, _ = _run(hand_raw, today)
    assert staff.total_cost == 100
    for k in ("low", "likely", "high"):
        assert with_staff.scenarios[k].net == pytest.approx(base.scenarios[k].net - 100)


def test_not_achievable_within_capacity(hand_raw, today):
    hand_raw["fixed_costs"][0]["amount"] = 100_000
    _, _, _, be = _run(hand_raw, today)
    assert be.status == "not_achievable" and be.registrations is None
    assert "Not achievable within venue capacity" in be.sentence


def test_zero_and_negative_contribution(hand_raw, today):
    hand_raw["ticket_tiers"][0]["price"] = 2
    hand_raw["processing"]["ticket_fee_rate"] = 0
    _, _, _, be = _run(hand_raw, today)
    assert be.status == "not_achievable"
    assert "adds no net money" in be.sentence


def test_zero_cost_event_breaks_even_at_zero(hand_raw, today):
    hand_raw["fixed_costs"][0]["amount"] = 0
    _, _, _, be = _run(hand_raw, today)
    assert be.registrations == 0 and be.onsite_attendance == 0


def test_all_free_event_price_not_applicable(hand_raw, today):
    hand_raw["ticket_tiers"][0]["price"] = 0
    _, _, budget, be = _run(hand_raw, today)
    assert be.status == "not_achievable"
    assert be.price_status == "not_applicable"
    assert budget.likely.ticket_gross == 0


def test_full_no_show_and_full_fees(hand_raw, today):
    hand_raw["no_show"].update(low=1, mean=1, high=1)
    _, _, budget, be = _run(hand_raw, today)
    assert budget.likely.attendees == 0 and be.status == "not_achievable"
    assert be.price_status == "not_applicable"
    hand_raw["no_show"].update(low=0.2, mean=0.2, high=0.2)
    hand_raw["processing"]["ticket_fee_rate"] = 1
    _, _, budget, be = _run(hand_raw, today)
    assert budget.likely.ticket_net == 0 and be.price_status == "not_applicable"


def test_free_quota_filled_first_and_tier_weights(hand_raw, today):
    hand_raw["ticket_tiers"] = [
        {"id": "g", "label": "General", "price": 15, "weight": 0.6},
        {"id": "e", "label": "Early", "preset": "early_bird", "price": 10, "weight": 0.4},
        {"id": "f", "label": "Free", "preset": "free", "price": 0, "allocation": "free_quota",
         "free_quota": 10, "weight": 0},
    ]
    plan, staff, budget, _ = _run(hand_raw, today)
    lines = {l.label: l for l in budget.likely.lines}
    assert lines["Free"].registrations == 10
    assert lines["General"].registrations == pytest.approx(18)
    assert lines["Early"].registrations == pytest.approx(12)
    # Below the quota, all registrations go to free places.
    model = build_model(plan, staff)
    e = evaluate(model, 5, 0.2, 2)
    assert float(e.ticket_gross) == 0 and float(e.attendees) == pytest.approx(4)


def test_registered_billing_keeps_revenue_from_no_shows(hand_raw, today):
    hand_raw["ticket_tiers"][0]["billing_basis"] = "registered"
    _, _, budget, _ = _run(hand_raw, today)
    assert budget.likely.ticket_gross == pytest.approx(800)  # 40 x $20
    assert budget.likely.variable_expense == pytest.approx(64)  # only 32 attend


def test_additional_revenue_and_addon_price_target(hand_raw, today):
    hand_raw["ticket_tiers"][0]["price"] = 0
    hand_raw["additional_revenue"] = [
        {"id": "pass", "label": "Class pass", "unit_price": 10, "quantity_basis": "per_attendee",
         "uptake_rate": 0.5, "units_per_buyer": 2},
        {"id": "vendor", "label": "Vendor fee", "unit_price": 50, "quantity": 6, "prepaid": True},
    ]
    _, _, budget, be = _run(hand_raw, today)
    assert budget.likely.addl_gross == pytest.approx(32 * 0.5 * 2 * 10 + 300)
    assert be.price_target == "required Class pass price"
    # (400 + 64 - 300) / 32 units
    assert be.raw_required_price == pytest.approx(164 / 32)


def test_deposit_is_cash_not_expense(hand_raw, today):
    hand_raw["venue"].update(security_deposit=200, rental_total=100, rental_advance=50)
    _, _, budget, _ = _run(hand_raw, today)
    assert budget.fixed_total == pytest.approx(500)
    assert budget.cash_required_upfront == pytest.approx(250)
    hand_raw["venue"]["security_deposit_forfeit_fraction"] = 0.5
    _, _, budget, _ = _run(hand_raw, today)
    assert budget.fixed_total == pytest.approx(600)


def test_permit_insurance_marketing_counted_once(hand_raw, today):
    hand_raw["venue"].update(permit_required=True, permit_cost=75, insurance_required=True,
                             insurance_cost=125)
    hand_raw["marketing"]["budget"] = 50
    _, _, budget, _ = _run(hand_raw, today)
    sources = [i.source for i in budget.ledger]
    assert sources.count("permit") == 1 and sources.count("insurance") == 1
    assert sources.count("marketing") == 1
    assert budget.fixed_total == pytest.approx(650)


def test_uncertain_fixed_cost_uses_triangular_mean(hand_raw, today):
    hand_raw["fixed_costs"][0].update(uncertain=True, low=300, mode=400, high=800)
    _, _, budget, _ = _run(hand_raw, today)
    assert budget.fixed_total == pytest.approx(500)


def test_vectorized_evaluation_matches_scalar(hand_raw, today):
    plan, staff, budget, _ = _run(hand_raw, today)
    model = build_model(plan, staff)
    e = evaluate(model, np.array([25.0, 40.0, 55.0]), 0.2, 2.0)
    assert np.allclose(e.ordinary_net, [-52, 156.8, 365.6])


def test_invalid_inputs_rejected(hand_raw, today):
    bad = copy.deepcopy(hand_raw)
    bad["attendance"]["high"] = 500
    with pytest.raises(PlanValidationError):
        validate_plan(bad, today)
    bad = copy.deepcopy(hand_raw)
    bad["processing"]["ticket_fee_rate"] = float("nan")
    with pytest.raises(PlanValidationError):
        validate_plan(bad, today)
    bad = copy.deepcopy(hand_raw)
    bad["fixed_costs"][0]["amount"] = -1
    with pytest.raises(PlanValidationError):
        validate_plan(bad, today)
    bad = copy.deepcopy(hand_raw)
    bad["currency"] = "EUR"
    with pytest.raises(PlanValidationError):
        validate_plan(bad, today)
