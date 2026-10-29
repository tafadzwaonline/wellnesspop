"""Visual system: global CSS, page headers, KPI cards, and status pills.

Colours adapt to the light and dark themes in ``.streamlit/config.toml``: components use
``currentColor`` and translucent fills rather than fixed backgrounds. Status is always
shown as words plus a dot, never colour alone. All user text is HTML-escaped.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

import streamlit as st

STATUS = {
    "good": ("On track", "#12946B"),
    "warn": ("Needs attention", "#C98500"),
    "bad": ("At risk", "#D9483B"),
    "info": ("Info", "#7A8A87"),
    "neutral": ("", "#7A8A87"),
}

CSS = """
<style>
/* Layout rhythm */
.block-container {padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1280px;}
[data-testid="stDecoration"] {display: none;}
[data-testid="stSidebarNav"] {padding-top: .25rem;}
[data-testid="stSidebarNavSeparator"] {margin: .35rem 0;}
h1, h2, h3 {letter-spacing: -0.015em;}
[data-testid="stMetric"] {padding: .85rem 1rem;}
[data-testid="stMetricLabel"] p {font-size: .82rem; opacity: .78; font-weight: 550;}
[data-testid="stExpander"] details summary p {font-weight: 600;}
.stTabs [role="tablist"] {gap: .25rem;}
.stTabs [role="tab"] {padding: .5rem .9rem; font-weight: 550;}
[data-testid="stForm"] {padding: 1.25rem 1.25rem .75rem;}

/* Page header */
.wp-header {display: flex; justify-content: space-between; align-items: flex-end;
  gap: 1rem; flex-wrap: wrap; margin: 0 0 1.25rem; padding-bottom: 1rem;
  border-bottom: 1px solid rgba(127,127,127,.18);}
.wp-eyebrow {font-size: .75rem; font-weight: 650; letter-spacing: .08em;
  text-transform: uppercase; opacity: .6; margin-bottom: .3rem;}
.wp-title {font-size: 1.85rem; font-weight: 700; letter-spacing: -.02em; line-height: 1.15;
  margin: 0;}
.wp-sub {opacity: .72; margin-top: .35rem; max-width: 62ch; line-height: 1.5;}
.wp-chips {display: flex; gap: .4rem; flex-wrap: wrap;}

/* Pills */
.wp-pill {display: inline-flex; align-items: center; gap: .4rem; font-size: .76rem;
  font-weight: 600; padding: .22rem .6rem; border-radius: 999px; white-space: nowrap;
  border: 1px solid rgba(127,127,127,.25); background: rgba(127,127,127,.06);}
.wp-dot {width: .5rem; height: .5rem; border-radius: 50%; flex: none;}

/* KPI cards */
.wp-grid {display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: .9rem; margin: .25rem 0 1.25rem;}
.wp-card {border: 1px solid rgba(127,127,127,.2); border-radius: .8rem; padding: 1rem 1.1rem;
  background: rgba(127,127,127,.035); display: flex; flex-direction: column; gap: .35rem;
  min-height: 9.5rem;}
.wp-card-label {font-size: .8rem; font-weight: 600; opacity: .7;}
.wp-card-value {font-size: 1.65rem; font-weight: 700; letter-spacing: -.02em; line-height: 1.2;}
.wp-card-detail {font-size: .85rem; opacity: .75; line-height: 1.45; flex: 1;}
.wp-card .wp-pill {align-self: flex-start;}
.wp-list {margin: .1rem 0 0; padding-left: 1rem; font-size: .85rem; line-height: 1.45;}

/* Hero / empty state */
.wp-hero {border: 1px solid rgba(127,127,127,.2); border-radius: 1rem; padding: 1.6rem 1.75rem;
  background: linear-gradient(135deg, rgba(15,118,110,.10), rgba(43,179,163,.03));
  margin-bottom: 1.25rem;}
.wp-hero h2 {margin: 0 0 .4rem; font-size: 1.4rem;}
.wp-hero p {margin: 0; opacity: .8; max-width: 70ch; line-height: 1.55;}
.wp-steps {display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: .75rem; margin-top: 1.1rem;}
.wp-step {font-size: .86rem; line-height: 1.45; opacity: .85;}
.wp-step b {display: block; font-size: .9rem; margin-bottom: .15rem; opacity: 1;}

/* Sidebar plan card */
.wp-plan {border: 1px solid rgba(127,127,127,.2); border-radius: .7rem; padding: .7rem .8rem;
  font-size: .82rem; line-height: 1.45;}
.wp-plan b {font-size: .9rem;}
.wp-muted {opacity: .65;}

/* Metric rows wrap instead of truncating: as many per row as fit, two on a phone */
[class*="st-key-wp_metrics"] [data-testid="stHorizontalBlock"] {flex-wrap: wrap; gap: .75rem;}
[class*="st-key-wp_metrics"] [data-testid="stColumn"] {flex: 1 1 165px !important;
  min-width: 165px; width: auto !important;}

/* Agenda list (phone timeline) */
.wp-agenda-phase {font-size: .75rem; font-weight: 650; letter-spacing: .08em;
  text-transform: uppercase; opacity: .6; margin: 1rem 0 .4rem;}
.wp-agenda-item {display: grid; grid-template-columns: 4.6rem 1fr; gap: .75rem;
  padding: .65rem 0; border-bottom: 1px solid rgba(127,127,127,.15);}
.wp-agenda-date {font-size: .8rem; font-weight: 650; line-height: 1.3;}
.wp-agenda-date span {display: block; font-weight: 400; opacity: .65;}
.wp-agenda-task {font-size: .9rem; font-weight: 600; line-height: 1.35;}
.wp-agenda-meta {font-size: .8rem; opacity: .7; margin: .2rem 0 .3rem;}

/* Page pager */
[class*="st-key-wp_pager"] {margin-top: 2rem; padding-top: 1rem;
  border-top: 1px solid rgba(127,127,127,.18);}

/* Responsive visibility helpers: keyed containers */
[class*="st-key-wp_mobile_only"] {display: none !important;}

@media (max-width: 640px) {
  .block-container {padding: 4rem 1rem 3rem;}
  .wp-title {font-size: 1.45rem;}
  .wp-header {margin-bottom: .9rem;}
  .wp-card {min-height: 0; padding: .85rem .95rem;}
  .wp-card-value {font-size: 1.4rem;}
  .wp-hero {padding: 1.15rem 1.1rem;}
  [data-testid="stMetric"] {padding: .6rem .75rem;}
  [data-testid="stMetricValue"] {font-size: 1.3rem;}
  [data-testid="stForm"] {padding: .9rem .8rem .5rem;}
  .stTabs [role="tablist"] {flex-wrap: wrap !important; overflow: visible !important;
    height: auto !important; row-gap: .15rem;}
  .stTabs [role="tablist"] ~ button, .stTabs button[aria-label*="scroll" i] {display: none !important;}
  .stTabs [role="tab"] {padding: .4rem .6rem;}
  .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {display: none;}
  .stTabs [aria-selected="true"] {background: rgba(15,118,110,.12); border-radius: .5rem;}
  [class*="st-key-wp_desktop_only"] {display: none !important;}
  [class*="st-key-wp_mobile_only"] {display: block !important;}
  button, [role="tab"], a[data-testid="stPageLink-NavLink"] {min-height: 2.6rem;}
}
</style>
"""


def inject_css() -> None:
    st.html(CSS)


def pill(status: str, text: str | None = None) -> str:
    label, colour = STATUS.get(status, STATUS["info"])
    text = label if text is None else text
    return (f'<span class="wp-pill"><span class="wp-dot" style="background:{colour}"></span>'
            f"{escape(text)}</span>")


def page_header(title: str, subtitle: str = "", eyebrow: str = "",
                chips: list[str] | None = None) -> None:
    """Consistent page header. ``chips`` are pre-rendered pill HTML strings."""
    eb = f'<div class="wp-eyebrow">{escape(eyebrow)}</div>' if eyebrow else ""
    sub = f'<div class="wp-sub">{escape(subtitle)}</div>' if subtitle else ""
    ch = f'<div class="wp-chips">{"".join(chips or [])}</div>' if chips else ""
    st.html(f'<div class="wp-header"><div>{eb}<h1 class="wp-title">{escape(title)}</h1>'
            f"{sub}</div>{ch}</div>")


@dataclass(frozen=True)
class Card:
    label: str
    value: str
    detail: str = ""
    status: str | None = None
    items: tuple[str, ...] = ()


def card_grid(cards: list[Card]) -> None:
    parts = []
    for c in cards:
        items = ""
        if c.items:
            items = '<ul class="wp-list">' + "".join(f"<li>{escape(i)}</li>" for i in c.items) + "</ul>"
        detail = f'<div class="wp-card-detail">{escape(c.detail)}{items}</div>'
        parts.append(
            f'<div class="wp-card"><div class="wp-card-label">{escape(c.label)}</div>'
            f'<div class="wp-card-value">{escape(c.value)}</div>{detail}'
            f'{pill(c.status) if c.status else ""}</div>')
    st.html(f'<div class="wp-grid">{"".join(parts)}</div>')


def hero(title: str, body: str, steps: list[tuple[str, str]]) -> None:
    s = "".join(f'<div class="wp-step"><b>{escape(a)}</b>{escape(b)}</div>' for a, b in steps)
    st.html(f'<div class="wp-hero"><h2>{escape(title)}</h2><p>{escape(body)}</p>'
            f'<div class="wp-steps">{s}</div></div>')


def agenda(schedule) -> None:
    """Phone-friendly timeline: tasks grouped by phase as a dated list."""
    from wellnesspop import schema as S

    flag_status = {"overdue": ("bad", "Overdue"), "conflict": ("bad", "Date conflict"),
                   "late_start": ("warn", "Start date passed")}
    parts = []
    for phase in S.PHASES:
        items = [t for t in schedule.tasks if not t.task.is_group and t.task.phase == phase]
        if not items:
            continue
        parts.append(f'<div class="wp-agenda-phase">{escape(S.label(phase))}</div>')
        for t in sorted(items, key=lambda x: (x.start, x.wbs_code)):
            last = t.finish if t.is_milestone else t.finish - _one_day()
            when = (f"{t.start:%d %b}" if last <= t.start
                    else f"{t.start:%d %b}<span>to {last:%d %b}</span>")
            flags = [flag_status[f] for f in t.flags if f in flag_status]
            pills = "".join(pill(k, v) for k, v in flags) or (
                pill("good", "Done") if t.task.status == "complete" else "")
            kind = "Milestone · " if t.is_milestone else ""
            parts.append(
                f'<div class="wp-agenda-item"><div class="wp-agenda-date">{when}</div><div>'
                f'<div class="wp-agenda-task">{escape(t.task.name)}</div>'
                f'<div class="wp-agenda-meta">{kind}{escape(t.task.owner_role)} · '
                f'{escape(S.label(t.task.status))}</div>{pills}</div></div>')
    st.html("".join(parts))


def _one_day():
    import datetime as dt

    return dt.timedelta(days=1)
