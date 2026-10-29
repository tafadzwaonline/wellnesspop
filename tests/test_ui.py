"""End-to-end UI checks with Streamlit's AppTest harness (no browser)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PAGES = ["dashboard", "plan_inputs", "budget", "break_even", "simulation", "wbs", "gantt",
         "risks", "staffing", "marketing", "exports", "about"]


def _app():
    return AppTest.from_file(APP, default_timeout=60).run()


def _button(at, label, sidebar=False):
    buttons = at.sidebar.button if sidebar else at.button
    return next(b for b in buttons if b.label.startswith(label))


def _load(at, key):
    at.sidebar.selectbox[0].set_value(key).run()
    _button(at, "Load demo", sidebar=True).click().run()


def _goto(at, page):
    at.switch_page(f"views/{page}.py").run()


def _plan_name(at):
    return at.session_state["wellnesspop"]["plan"].event.name


@pytest.mark.parametrize("key", ["scenario_a", "scenario_b", "scenario_c"])
def test_demo_renders_every_page_with_simulation(key):
    at = _app()
    _load(at, key)
    _goto(at, "simulation")
    _button(at, "Run simulation").click().run()
    assert any(m.label == "Probability of breaking even" for m in at.metric)
    for page in PAGES:
        _goto(at, page)
        assert not at.exception, (page, [e.value for e in at.exception])
        assert not at.error, (page, [e.value for e in at.error])


def test_invalid_input_is_rejected_and_plan_unchanged():
    at = _app()
    _load(at, "scenario_a")
    _goto(at, "plan_inputs")
    cap = next(n for n in at.number_input if n.label == "Capacity")
    cap.set_value(10)
    _button(at, "Apply venue").click().run()
    assert at.error and "unchanged" in at.error[0].value
    _goto(at, "budget")
    assert at.metric[1].value == "-$65.03"  # scenario A likely net unchanged


def test_stale_simulation_banner_and_clear_plan():
    at = _app()
    _load(at, "scenario_b")
    _goto(at, "simulation")
    _button(at, "Run simulation").click().run()
    _goto(at, "plan_inputs")
    likely = next(n for n in at.number_input if n.label == "Likely")
    likely.set_value(30.0)
    _button(at, "Apply pricing").click().run()
    _goto(at, "dashboard")
    assert any("Results out of date" in w.value or "not run" in w.value.lower()
               for w in list(at.warning) + list(at.info))
    next(c for c in at.sidebar.checkbox if c.label.startswith("I want to clear")).check().run()
    _button(at, "Clear plan", sidebar=True).click().run()
    assert any("cleared" in s.value for s in at.success)
    _goto(at, "budget")
    assert _plan_name(at) == "My wellness event"


def test_two_sessions_are_isolated():
    a, b = _app(), _app()
    _load(a, "scenario_c")
    b.run()
    assert _plan_name(a) == "One-Day Wellness Fair"
    assert _plan_name(b) == "My wellness event"
