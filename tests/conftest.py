import copy
import datetime as dt

import pytest

from wellnesspop.schema import default_plan

TODAY = dt.date(2026, 10, 29)


def fixture_raw() -> dict:
    """Synthetic hand-calculated fixture from guide Section 6 (not a researched demo)."""
    raw = default_plan(TODAY)
    raw["event"]["date"] = (TODAY + dt.timedelta(days=42)).isoformat()
    raw["venue"]["capacity"] = 100
    raw["attendance"].update(low=25, likely=40, high=55)
    raw["no_show"].update(low=0.2, mean=0.2, high=0.2)
    raw["processing"]["ticket_fee_rate"] = 0.03
    raw["fixed_costs"] = [{"id": "fc-fixed", "label": "Fixed costs", "category": "other",
                           "amount": 400}]
    raw["variable_costs"] = [{"id": "vc", "label": "Supplies", "low": 2, "mode": 2, "high": 2}]
    raw["ticket_tiers"] = [{"id": "tier", "label": "General", "price": 20, "weight": 1}]
    raw["staffing"] = []
    raw["additional_revenue"] = []
    return raw


@pytest.fixture
def today():
    return TODAY


@pytest.fixture
def hand_raw():
    return copy.deepcopy(fixture_raw())
