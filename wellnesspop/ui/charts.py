"""Plotly figures. Colors follow the validated reference palette (categorical slots 1-3).

Every chart has a tabular alternative on its page; identity is never color-only
(legends and direct labels accompany colored marks).
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from wellnesspop import fmt
from wellnesspop import schema as S
from wellnesspop.schedule import ScheduleResult
from wellnesspop.simulation import SimulationResult

SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # slots 1-3: all-pairs CVD-validated
NEUTRAL = "#8a8985"
INK = "#7A8A87"
FONT = "Inter, Segoe UI, -apple-system, Roboto, Helvetica Neue, Arial, sans-serif"
PHASE_COLORS = {S.label(p): c for p, c in zip(S.PHASES, SERIES)}


def _layout(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=36, b=8),
                      font=dict(size=13, family=FONT), hoverlabel=dict(font_size=13),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    fig.update_xaxes(showgrid=True, gridwidth=1, zeroline=False)
    fig.update_yaxes(showgrid=False)
    return fig


def gantt(schedule: ScheduleResult, today: dt.date) -> go.Figure:
    rows = []
    for s in schedule.tasks:
        if s.task.is_group:
            continue
        finish = s.finish if s.finish > s.start else s.start + dt.timedelta(hours=8)
        flag = ", ".join(s.flags) or "on track"
        rows.append({"Task": f"{s.wbs_code} {s.task.name}" + (" ◆" if s.is_milestone else ""),
                     "Start": s.start, "Finish": finish, "Phase": S.label(s.task.phase),
                     "Owner": s.task.owner_role, "Status": S.label(s.task.status),
                     "Flags": flag, "Due": (s.finish.isoformat())})
    df = pd.DataFrame(rows)
    fig = px.timeline(df, x_start="Start", x_end="Finish", y="Task", color="Phase",
                      color_discrete_map=PHASE_COLORS,
                      hover_data={"Owner": True, "Status": True, "Flags": True, "Due": True,
                                  "Start": "|%Y-%m-%d", "Finish": False, "Phase": False})
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_traces(marker_line_color="white", marker_line_width=2)
    for x, label, dash in ((today, "Today", "dot"), (schedule.event_date, "Event", "solid")):
        fig.add_shape(type="line", x0=x, x1=x, y0=0, y1=1, yref="paper",
                      line=dict(color=INK, width=2, dash=dash))
        fig.add_annotation(x=x, y=1, yref="paper", text=label, showarrow=False,
                           yanchor="bottom", font=dict(color=INK))
    return _layout(fig, height=max(320, 26 * len(rows) + 80))


def histogram(sim: SimulationResult) -> go.Figure:
    edges = np.array(sim.histogram_edges)
    mids = (edges[:-1] + edges[1:]) / 2
    widths = np.diff(edges)
    labels = [f"{fmt.money(a)} to {fmt.money(b)}" for a, b in zip(edges[:-1], edges[1:])]
    fig = go.Figure(go.Bar(x=mids, y=sim.histogram_counts, width=widths * 0.92,
                           marker_color=SERIES[0], customdata=labels, name="Simulated runs",
                           hovertemplate="%{customdata}<br>%{y:,} runs<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=INK, width=2))
    fig.add_annotation(x=0, y=1.09, yref="paper", text="Break-even ($0)", showarrow=False,
                       yanchor="bottom", font=dict(color=INK))
    for v, name in ((sim.p10, "P10"), (sim.p50, "P50"), (sim.p90, "P90")):
        fig.add_vline(x=v, line=dict(color=NEUTRAL, width=1, dash="dot"))
        fig.add_annotation(x=v, y=1.0, yref="paper", text=name, showarrow=False,
                           yanchor="bottom", font=dict(color=INK, size=11))
    fig.update_xaxes(title="Net income (USD)", tickprefix="$", tickformat=",.0f")
    fig.update_yaxes(title="Number of runs", showgrid=True)
    fig.update_layout(bargap=0, showlegend=False)
    fig = _layout(fig, height=400)
    fig.update_layout(margin=dict(t=64))
    return fig


def tornado(sim: SimulationResult) -> go.Figure:
    rows = list(reversed(sim.tornado))
    base = sim.baseline_expected_net
    names = [r.name for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=names, x=[r.net_at_low - base for r in rows], base=base, orientation="h",
        name="Input at low end (P10, or probability 0)", marker_color=SERIES[0],
        customdata=[[fmt.money(r.net_at_low), fmt.num(r.low_input, 3)] for r in rows],
        hovertemplate="%{y}<br>Input %{customdata[1]} → expected net %{customdata[0]}<extra></extra>"))
    fig.add_trace(go.Bar(
        y=names, x=[r.net_at_high - base for r in rows], base=base, orientation="h",
        name="Input at high end (P90, or probability 1)", marker_color=SERIES[1],
        customdata=[[fmt.money(r.net_at_high), fmt.num(r.high_input, 3)] for r in rows],
        hovertemplate="%{y}<br>Input %{customdata[1]} → expected net %{customdata[0]}<extra></extra>"))
    fig.add_vline(x=base, line=dict(color=INK, width=2))
    fig.update_layout(barmode="overlay")
    fig.update_traces(marker_line_color="white", marker_line_width=1)
    fig.update_xaxes(title="Expected net income (USD)", tickprefix="$", tickformat=",.0f")
    return _layout(fig, height=max(260, 48 * len(rows) + 110))


def break_even_curve(registrations: np.ndarray, net: np.ndarray, be: int | None) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=registrations, y=net, mode="lines", line=dict(color=SERIES[0], width=2),
        name="Net income", hovertemplate="%{x:.0f} registrations<br>Net %{y:$,.2f}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=INK, width=2))
    if be is not None:
        fig.add_vline(x=be, line=dict(color=NEUTRAL, width=1, dash="dot"))
        fig.add_annotation(x=be, y=1, yref="paper", text=f"Break-even: {be}", showarrow=False,
                           yanchor="bottom", font=dict(color=INK))
    fig.update_xaxes(title="Registrations")
    fig.update_yaxes(title="Net income (USD, event goes ahead)", tickprefix="$",
                     tickformat=",.0f", showgrid=True)
    fig.update_layout(showlegend=False)
    return _layout(fig, height=320)
