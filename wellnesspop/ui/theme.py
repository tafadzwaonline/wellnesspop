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
.stTabs [data-baseweb="tab-list"] {gap: .25rem;}
.stTabs [data-baseweb="tab"] {padding: .5rem .9rem; font-weight: 550;}
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

@media (max-width: 640px) {
  .block-container {padding-top: 4rem;}
  .wp-title {font-size: 1.45rem;}
  .wp-card {min-height: 0;}
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
