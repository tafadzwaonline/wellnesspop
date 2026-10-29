"""App shell: navigation structure, sidebar controls, and page dispatch."""

from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

from wellnesspop import schema as S
from wellnesspop import state
from wellnesspop.demos import DEMO_KEYS, demo_summary, demo_titles
from wellnesspop.ui import theme
from wellnesspop.ui.common import flash, store, today, wkey

ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS = ROOT / "wellnesspop" / "assets"
LOGO = str(ASSETS / "logo.svg")
ICON = str(ASSETS / "icon.svg")

# (section, script, title, icon, url_path)
PAGES = [
    ("Overview", "views/dashboard.py", "Dashboard", ":material/space_dashboard:", "dashboard"),
    ("Plan", "views/plan_inputs.py", "Plan inputs", ":material/edit_note:", "inputs"),
    ("Finances", "views/budget.py", "Budget", ":material/account_balance_wallet:", "budget"),
    ("Finances", "views/break_even.py", "Break-even", ":material/balance:", "break-even"),
    ("Finances", "views/simulation.py", "Simulation", ":material/query_stats:", "simulation"),
    ("Project", "views/wbs.py", "Tasks (WBS)", ":material/account_tree:", "wbs"),
    ("Project", "views/gantt.py", "Timeline (Gantt)", ":material/view_timeline:", "gantt"),
    ("Project", "views/risks.py", "Risks", ":material/shield:", "risks"),
    ("Project", "views/staffing.py", "Staffing", ":material/groups:", "staffing"),
    ("Project", "views/marketing.py", "Marketing", ":material/campaign:", "marketing"),
    ("Share", "views/exports.py", "Exports", ":material/download:", "exports"),
    ("Share", "views/about.py", "About & privacy", ":material/info:", "about"),
]
INPUTS_PAGE = "views/plan_inputs.py"


def navigation():
    sections: dict[str, list] = {}
    for i, (section, script, title, icon, url) in enumerate(PAGES):
        sections.setdefault(section, []).append(
            st.Page(str(ROOT / script), title=title, icon=icon, url_path=url, default=i == 0))
    return st.navigation(sections, position="sidebar")


def sim_chip(status: str) -> str:
    return {"current": theme.pill("good", "Simulation current"),
            "stale": theme.pill("warn", "Simulation out of date"),
            "not_run": theme.pill("info", "Simulation not run")}[status]


def eyebrow() -> str:
    p = state.plan(store())
    return f"{p.event.name} · {p.event.date:%a %d %b %Y}"


def sidebar() -> None:
    s = st.session_state[state.KEY]
    plan = s["plan"]
    with st.sidebar:
        days = (plan.event.date - today()).days
        when = f"in {days} days" if days > 0 else ("today" if days == 0 else f"{-days} days ago")
        st.html(
            f'<div class="wp-plan"><div class="wp-muted">Current plan</div>'
            f"<b>{escape(plan.event.name)}</b><br>"
            f"{plan.event.date:%a %d %b %Y} · {escape(when)}<br>"
            f'<span class="wp-muted">{escape(S.label(plan.event.setting))} · capacity '
            f"{plan.venue.capacity} · revision {s['revision']}</span></div>")
        st.caption("DEMONSTRATION SCENARIOS")
        titles = demo_titles()
        choice = st.selectbox("Demonstration scenario", DEMO_KEYS, format_func=titles.get,
                              key=wkey("demo_choice"), label_visibility="collapsed")
        st.caption(demo_summary(choice))
        if st.button("Load demo", icon=":material/play_circle:", key=wkey("load_demo"),
                     width="stretch", help="Replaces the current plan"):
            load_demo(choice)
        with st.expander("Reset plan", icon=":material/restart_alt:"):
            st.caption("Removes your inputs, results, uploads and downloads from this session.")
            confirm = st.checkbox("I want to clear this plan", key=wkey("clear_confirm"))
            if st.button("Clear plan", disabled=not confirm, key=wkey("clear"), type="primary",
                         width="stretch"):
                state.clear(store())
                flash("success", "Plan cleared. You are starting from the blank defaults.")
                st.rerun()
        st.caption("Session-only · no accounts · no database. "
                   "Details on the About & privacy page.")


def load_demo(key: str) -> None:
    issues = state.load_demo_into(store(), key, today())
    flash("success", f"Loaded {demo_titles()[key]}. Values are illustrative unless marked as "
                     "from the brief.", issues)
    st.rerun()


def run_page(name: str) -> None:
    from wellnesspop.ui import about, inputs, outputs

    if name == "inputs":
        inputs.render()
    elif name == "about":
        about.render()
    else:
        getattr(outputs, name)(state.result(store(), today()))
