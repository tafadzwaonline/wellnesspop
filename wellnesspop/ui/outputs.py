"""The ten output pages. Every page reads the same ``PlanResult`` snapshot."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from wellnesspop import export, fmt
from wellnesspop import schema as S
from wellnesspop import state
from wellnesspop.budget import evaluate_baseline, normalize_zero
from wellnesspop.dashboard import build_dashboard
from wellnesspop.demos import DEMO_KEYS, demo_titles
from wellnesspop.planner import PlanResult
from wellnesspop.risk import apply_risk_table, risk_table_rows
from wellnesspop.schedule import apply_task_table, task_table_rows
from wellnesspop.ui import charts, theme
from wellnesspop.ui.common import flags_text, flash, md, show_issues, store, today, wkey

CC = st.column_config
HOW_TO_READ = Path(__file__).resolve().parent.parent / "templates" / "how_to_read.md"
MONEY = CC.NumberColumn(format="dollar")


def _header(r: PlanResult, title: str, subtitle: str, sim_chip: bool = False) -> None:
    from wellnesspop.ui.shell import eyebrow, sim_chip as chip

    chips = [chip(r.simulation_status)] if sim_chip else []
    theme.page_header(title, subtitle, eyebrow=eyebrow(), chips=chips)


def _chart(fig, **kw) -> None:
    """Plotly chart without the floating toolbar (cleaner on touch screens)."""
    st.plotly_chart(fig, config={"displayModeBar": False, "scrollZoom": False,
                                 "responsive": True}, **kw)


def _table(df: pd.DataFrame, **kw) -> None:
    st.dataframe(df, hide_index=True, width="stretch", **kw)


def _sim_banner(r: PlanResult) -> None:
    if r.simulation_status == "stale":
        md.warning("Results out of date: inputs changed since the last simulation. Run it again "
                   "on the Simulation page.", icon=":material/update:")
    elif r.simulation_status == "not_run":
        md.info("Simulation not run yet for these inputs. Open the Simulation page to run it.",
                icon=":material/info:")


# -------------------------------------------------------------------------- dashboard


def dashboard(r: PlanResult) -> None:
    d = build_dashboard(r)
    s = st.session_state[state.KEY]
    _header(r, "Dashboard", "Everything that matters for this event on one screen. All figures "
            "come from the same input revision.", sim_chip=True)
    if s["source"] == "blank" and s["revision"] == 1:
        theme.hero(
            "Plan your wellness event in about 15 minutes",
            "Start from a realistic demonstration or enter your own details. WellnessPop turns "
            "your assumptions into a budget, a task plan and a clear view of financial risk.",
            [("1 · Enter assumptions", "Event, venue, costs, pricing, staff and marketing."),
             ("2 · Check the numbers", "Budget, break-even and a 10,000-run simulation."),
             ("3 · Run the project", "Tasks, timeline, risks and marketing checklist."),
             ("4 · Share", "Download an Excel workbook and a one-page PDF.")])
        titles = demo_titles()
        demo = st.segmented_control("Try a demonstration scenario", DEMO_KEYS,
                                    format_func=titles.get, default=DEMO_KEYS[0],
                                    key=wkey("hero_demo"))
        c1, c2, _ = st.columns([1, 1, 2])
        with c1:
            if st.button("Load this demo", type="primary", icon=":material/play_circle:",
                         key=wkey("hero_load"), width="stretch"):
                from wellnesspop.ui.shell import load_demo
                load_demo(demo or DEMO_KEYS[0])
        with c2:
            if st.button("Enter my event", icon=":material/edit_note:", key=wkey("hero_inputs"),
                         width="stretch"):
                from wellnesspop.ui.shell import INPUTS_PAGE
                st.switch_page(INPUTS_PAGE)
        st.space("small")
    _sim_banner(r)
    cards = []
    for k in d.kpis:
        if k.key == "risks":
            items = tuple(f"{x.title} ({x.band.lower()}, {x.score})" for x in r.risks
                          if x.status != "closed")[:3]
            cards.append(theme.Card(k.label, k.value.replace(" shown", " open"), "",
                                    k.status, items))
        else:
            cards.append(theme.Card(k.label, k.value, k.detail, k.status))
    theme.card_grid(cards)
    c1, c2 = st.columns([1, 1.4], gap="large")
    with c1:
        with st.container(border=True):
            st.subheader("Key figures", anchor=False)
            _table(pd.DataFrame(d.supporting, columns=["Measure", "Value"]))
    with c2:
        with st.container(border=True):
            st.subheader("Next tasks", anchor=False)
            if r.schedule:
                upcoming = sorted((x for x in r.schedule.tasks
                                   if not x.task.is_group and x.task.status != "complete"),
                                  key=lambda x: (x.start, x.wbs_code))[:6]
                _table(pd.DataFrame([{"Start": x.start, "Task": x.task.name,
                                      "Owner": x.task.owner_role, "Status": flags_text(x.flags)}
                                     for x in upcoming]),
                       column_config={"Start": CC.DateColumn(format="ddd D MMM")})
            else:
                md.write("Fix task errors on the Tasks page to see the schedule.")
    st.caption(f"Input revision {d.revision} · financial fingerprint {r.input_fingerprint}")


# ----------------------------------------------------------------------------- budget


def budget(r: PlanResult) -> None:
    b = r.budget
    _header(r, "Budget", "What the event earns and costs at your low, likely and high "
            "registration estimates, assuming it goes ahead. Weather risk is in the Simulation.")
    sc = [b.scenarios[k] for k in ("low", "likely", "high")]
    cols = st.container(key="wp_metrics_budget").columns(4)
    for col, s in zip(cols, sc):
        col.metric(f"Net income · {s.name}", fmt.money(s.net), border=True,
                   help=f"{fmt.num(s.registrations)} registrations, about "
                        f"{fmt.num(s.attendees)} people on site")
    cols[3].metric("Total fixed costs", fmt.money(b.fixed_total), border=True,
                   help="Venue, permit, insurance, fixed items, staffing and marketing")
    tab1, tab2, tab3 = st.tabs(["Summary", "Fixed-cost ledger", "Cash & notes"])
    with tab1:
        _table(pd.DataFrame(
            [["Registrations", *[s.registrations for s in sc]],
             ["Expected attendees (on site)", *[s.attendees for s in sc]]],
            columns=["Attendance", "Low", "Likely", "High"]),
            column_config={c: CC.NumberColumn(format="%.1f") for c in ("Low", "Likely", "High")})
        rows = []
        for i, line in enumerate(sc[0].lines):
            kind = "Tickets" if line.kind == "ticket" else "Other revenue"
            rows.append([f"{kind}: {line.label} @ {fmt.money(line.price)}",
                         *[s.lines[i].gross for s in sc]])
        rows += [["Processing fees", *[-s.processing_fees for s in sc]],
                 ["Net revenue", *[s.revenue_net for s in sc]],
                 ["Fixed costs", *[-s.fixed_total for s in sc]],
                 ["Variable costs", *[-s.variable_expense for s in sc]],
                 ["Total cost (fixed + variable)", *[s.total_cost for s in sc]],
                 ["Net income", *[s.net for s in sc]]]
        _table(pd.DataFrame(rows, columns=["Line", "Low", "Likely", "High"]),
               column_config={c: MONEY for c in ("Low", "Likely", "High")})
    with tab2:
        _table(pd.DataFrame([{
            "Cost": i.label, "Source": i.source.replace("_", " ").capitalize(),
            "Budget amount": i.mean,
            "Range (low / likely / high)": (
                f"{fmt.money(i.low)} / {fmt.money(i.mode)} / {fmt.money(i.high)}"
                if i.uncertain else "Known"),
            "Lost if cancelled": i.retained_fraction} for i in b.ledger],
            columns=["Cost", "Source", "Budget amount", "Range (low / likely / high)",
                     "Lost if cancelled"]),
            column_config={"Budget amount": MONEY,
                           "Lost if cancelled": CC.NumberColumn(format="percent")})
        md.caption(f"Variable cost per attendee: {fmt.money(b.variable_cost_per_attendee)} (mean "
                   "of the summed rows).")
    with tab3:
        lim = b.spending_limit
        within = lim is None or b.likely.total_cost <= lim + 1e-9
        theme.card_grid([
            theme.Card("Cash needed up front", fmt.money(b.cash_required_upfront),
                       f"Rental advance {fmt.money(b.rental_advance)} + refundable deposit "
                       f"{fmt.money(b.security_deposit)}", "info"),
            theme.Card("Spending limit", fmt.money(lim),
                       "No limit supplied" if lim is None else
                       f"Likely total cost {fmt.money(b.likely.total_cost)}",
                       "info" if lim is None else ("good" if within else "bad")),
            theme.Card("Target net income", fmt.money(b.target_net_income),
                       f"Likely net {fmt.money(b.likely.net)}",
                       "good" if b.likely.net >= b.target_net_income - 1e-9 else "bad"),
        ])
        for n in b.notes:
            md.markdown(f"- {n}")


# ------------------------------------------------------------------------- break-even


def break_even(r: PlanResult) -> None:
    be = r.break_even
    _header(r, "Break-even", "How many people you need, and what they need to pay, for income "
            "to cover costs if the event goes ahead.")
    c1, c2, c3 = st.container(key="wp_metrics_be").columns(3)
    c1.metric("Registrations needed",
              str(be.registrations) if be.registrations is not None else "Not achievable",
              border=True, help="Sign-ups before no-shows")
    c2.metric("On-site attendance needed",
              str(be.onsite_attendance) if be.onsite_attendance is not None else "—",
              border=True, help="Expected number who actually arrive")
    c3.metric(be.price_target.capitalize(),
              fmt.money(be.required_price) if be.required_price is not None else "Not applicable",
              border=True, help="At likely registrations, holding everything else constant")
    with st.container(border=True):
        md.markdown(f"**{be.sentence}**")
        md.write(be.price_sentence)
        grid = np.arange(0, r.plan.venue.capacity + 1, dtype=float)
        net = normalize_zero(evaluate_baseline(r.model, grid).ordinary_net)
        _chart(charts.break_even_curve(grid, net, be.registrations), width="stretch",
                        key=wkey("be_chart"))
    with st.expander("Table: net income by registrations"):
        step = max(1, len(grid) // 20)
        _table(pd.DataFrame({"Registrations": grid[::step].astype(int), "Net income": net[::step]}),
               column_config={"Net income": MONEY})
    if be.simple:
        with st.expander("Simple formula check"):
            s = be.simple
            md.write(f"Blended ticket price {fmt.money(s['blended_price'])}; contribution per "
                     f"attendee {fmt.money(s['contribution_per_attendee'])}; fixed costs "
                     f"{fmt.money(s['fixed'])}.")
            if "break_even_attendance" in s:
                md.write(f"Closed form: {s['break_even_attendance']} on-site attendees, "
                         f"{s['break_even_registrations']} registrations.")
    st.caption("The price holds attendance, costs, free places and other revenue constant and "
               "applies one common price to paid units.")


# ------------------------------------------------------------------------- simulation


def simulation(r: PlanResult) -> None:
    _header(r, "Simulation", "Thousands of plausible versions of your event, drawn from your "
            "ranges, show how likely it is to cover its costs.", sim_chip=True)
    p = r.plan.simulation
    with st.container(border=True):
        c1, c2 = st.columns([4, 1], vertical_alignment="center")
        with c1:
            md.markdown(f"**{p.runs:,} runs · seed {p.seed}** — the same inputs and seed always "
                        "give the same results. Change both under Plan inputs › Risk assumptions.")
        with c2:
            run = st.button("Run simulation", type="primary", icon=":material/play_arrow:",
                            key=wkey("run_sim"), width="stretch")
    if run:
        with st.spinner("Simulating…"):
            state.simulate(store(), today())
        st.rerun()
    _sim_banner(r)
    sim = r.current_simulation
    if sim is None:
        with st.container(border=True):
            md.markdown(HOW_TO_READ.read_text(encoding="utf-8"))
        return
    c = st.container(key="wp_metrics_sim").columns(4)
    c[0].metric("Probability of breaking even", fmt.pct(sim.probability_break_even), border=True)
    c[1].metric("P10 (bad case)", fmt.money(sim.p10), border=True,
                help="Only 1 in 10 outcomes were worse")
    c[2].metric("P50 (typical)", fmt.money(sim.p50), border=True)
    c[3].metric("P90 (good case)", fmt.money(sim.p90), border=True,
                help="Only 1 in 10 outcomes were better")
    tab1, tab2, tab3 = st.tabs(["Distribution", "What moves the result", "How to read this"])
    with tab1:
        for line in sim.explainer:
            md.markdown(f"- {line}")
        _chart(charts.histogram(sim), width="stretch", key=wkey("hist"))
        with st.expander("Table: histogram bins"):
            e = sim.histogram_edges
            _table(pd.DataFrame({"From": e[:-1], "To": e[1:], "Runs": sim.histogram_counts}),
                   column_config={"From": MONEY, "To": MONEY})
    with tab2:
        if sim.tornado:
            _chart(charts.tornado(sim), width="stretch", key=wkey("tornado"))
            _table(pd.DataFrame([{
                "Input": t.name, "Low input": t.low_input, "High input": t.high_input,
                "Expected net at low": t.net_at_low, "Expected net at high": t.net_at_high,
                "Impact range": t.impact_range} for t in sim.tornado]),
                column_config={"Low input": CC.NumberColumn(format="%.3f"),
                               "High input": CC.NumberColumn(format="%.3f"),
                               "Expected net at low": MONEY, "Expected net at high": MONEY,
                               "Impact range": MONEY})
            st.caption("One input at a time, others held at baseline. Continuous inputs swing to "
                       "P10 and P90; the weather row swings cancellation probability from 0 to "
                       "1. This is sensitivity, not cause and effect.")
        else:
            md.write("No uncertain inputs: every run gives the same result.")
    with tab3:
        md.markdown(HOW_TO_READ.read_text(encoding="utf-8"))
    st.caption(f"{sim.runs:,} runs in {sim.elapsed_seconds:.2f} s · seed {sim.seed} · engine "
               f"{sim.engine_version} · sampled: "
               + ("; ".join(sim.dimensions) or "nothing (deterministic)"))


# -------------------------------------------------------------------------------- WBS


def wbs(r: PlanResult) -> None:
    _header(r, "Tasks (WBS)", "Tasks generated from your inputs in three phases. Edit, add or "
            "delete rows, then apply. Your edits survive date and input changes.")
    show_issues([i for i in r.issues if i.path.startswith("task")])
    codes = {s.task.id: s.wbs_code for s in r.schedule.tasks} if r.schedule else {}
    rows = task_table_rows(list(r.tasks))
    for row in rows:
        row["wbs"] = codes.get(row["id"], "")
    rows.sort(key=lambda x: [int(p) for p in x["wbs"].split(".") if p.isdigit()] or [999])
    df = pd.DataFrame(rows, columns=["wbs", "name", "status", "owner_role", "duration_days",
                                     "offset_days", "predecessor_ids", "manual_start", "phase",
                                     "parent_id", "id"])
    with st.form(wkey("wbs_form"), border=False):
        edited = st.data_editor(
            df, num_rows="dynamic", hide_index=True, width="stretch", key=wkey("wbs_editor"),
            height=560,
            column_config={
                "wbs": CC.TextColumn("WBS", disabled=True, width="small"),
                "id": CC.TextColumn("Task ID", disabled=True, help="Generated for new rows"),
                "name": CC.TextColumn("Task", required=True, width="large", pinned=True),
                "phase": CC.SelectboxColumn("Phase", options=list(S.PHASES)),
                "parent_id": CC.TextColumn("Parent ID", help="phase.pre_event, phase.event_day, "
                                           "phase.post_event, or another task ID"),
                "duration_days": CC.NumberColumn("Days", min_value=0, step=1),
                "offset_days": CC.NumberColumn("Anchor (days from event)", step=1,
                                               help="Pre-event: latest finish. Event day: start. "
                                                    "Post-event: earliest start."),
                "owner_role": CC.TextColumn("Owner role"),
                "status": CC.SelectboxColumn("Status", options=list(S.TASK_STATUSES)),
                "predecessor_ids": CC.TextColumn("Depends on", help="Task IDs, comma-separated"),
                "manual_start": CC.DateColumn("Pinned start", format="YYYY-MM-DD"),
            })
        submitted = st.form_submit_button("Apply task changes", type="primary",
                                          icon=":material/check:")
    if submitted:
        records = edited.drop(columns=["wbs"]).to_dict("records")
        new, issues = apply_task_table(r.plan, r.staffing, r.edits["tasks"], records)
        if new is None:
            flash("error", "Task changes were not applied.", issues)
        else:
            state.commit_edits(store(), "tasks", new)
            flash("success", "Task changes applied.", issues)
        st.rerun()
    if st.button("Reset tasks to templates", icon=":material/restart_alt:", key=wkey("wbs_reset"),
                 help="Discards all task edits, additions and deletions."):
        state.reset_edits(store(), "tasks")
        flash("success", "Tasks reset to the generated templates.")
        st.rerun()


# ------------------------------------------------------------------------------ Gantt


def gantt(r: PlanResult) -> None:
    _header(r, "Timeline (Gantt)", "Scheduled backward from the event date. Bars are coloured by "
            "phase; ◆ marks a milestone; the dotted line is today.")
    if r.schedule is None:
        md.error("The timeline cannot be drawn until task errors on the Tasks page are fixed.")
        show_issues(list(r.issues))
        return
    sch = r.schedule
    if sch.problems:
        md.warning(f"{len(sch.problems)} task(s) need attention: overdue, past their latest "
                   "start, or in conflict with a pinned date. Dates are never moved silently.",
                   icon=":material/warning:")
    with st.container(border=True, key="wp_desktop_only_gantt"):
        _chart(charts.gantt(sch, r.today), width="stretch", key=wkey("gantt_chart"))
    with st.container(key="wp_mobile_only_gantt"):
        theme.agenda(sch)
    tab1, tab2 = st.tabs(["Schedule table", "Dependencies"])
    with tab1:
        _table(pd.DataFrame([{
            "WBS": s.wbs_code, "Task": s.task.name, "Phase": S.label(s.task.phase),
            "Start": s.start, "Due (exclusive finish)": s.finish, "Owner": s.task.owner_role,
            "Status": "Summary" if s.task.is_group else S.label(s.task.status),
            "Lead-time rule": s.task.lead_rule,
            "Flags": "" if s.task.is_group else flags_text(s.flags)} for s in sch.tasks]),
            column_config={"Start": CC.DateColumn(format="YYYY-MM-DD"),
                           "Due (exclusive finish)": CC.DateColumn(format="YYYY-MM-DD")})
    with tab2:
        names = {s.task.id: s.task.name for s in sch.tasks}
        deps = [{"Task": s.task.name,
                 "Starts after": "; ".join(names.get(p, p) for p in s.task.predecessor_ids),
                 "Waiting period (days)": s.task.lag_days or None}
                for s in sch.tasks if s.task.predecessor_ids]
        _table(pd.DataFrame(deps, columns=["Task", "Starts after", "Waiting period (days)"]))


# ------------------------------------------------------------------------------ risks


def risks(r: PlanResult) -> None:
    _header(r, "Risks", "Score = likelihood × impact (1–5 each). Scores set priorities only; "
            "they never change simulation inputs.")
    show_issues([i for i in r.issues if i.path.startswith("risk")])
    open_risks = [x for x in r.risks if x.status != "closed"]
    c = st.container(key="wp_metrics_risks").columns(4)
    for col, band in zip(c, ("Critical", "High", "Medium", "Low")):
        col.metric(f"{band} risks", sum(x.band == band for x in open_risks), border=True,
                   help={"Critical": "Score 17-25", "High": "Score 10-16", "Medium": "Score 5-9",
                         "Low": "Score 1-4"}[band])
    tab1, tab2 = st.tabs(["Register", "Edit risks"])
    with tab1:
        _table(pd.DataFrame([{"Risk": x.title, "Score": x.score, "Band": x.band,
                              "Response": S.label(x.response), "Plan": x.response_note,
                              "Owner": x.owner_role, "Status": S.label(x.status)}
                             for x in r.risks]),
               column_config={"Score": CC.ProgressColumn("Score", min_value=0, max_value=25,
                                                         format="%d"),
                              "Plan": CC.TextColumn(width="large")})
    with tab2:
        df = pd.DataFrame(risk_table_rows(list(r.risks)),
                          columns=["title", "likelihood", "impact", "status", "owner_role",
                                   "response", "response_note", "assumption_refs", "id"])
        with st.form(wkey("risk_form"), border=False):
            edited = st.data_editor(
                df, num_rows="dynamic", hide_index=True, width="stretch",
                key=wkey("risk_editor"),
                column_config={
                    "id": CC.TextColumn("ID", disabled=True),
                    "title": CC.TextColumn("Risk", required=True, width="large", pinned=True),
                    "likelihood": CC.NumberColumn("Likelihood", min_value=1, max_value=5, step=1),
                    "impact": CC.NumberColumn("Impact", min_value=1, max_value=5, step=1),
                    "owner_role": CC.TextColumn("Owner role"),
                    "response": CC.SelectboxColumn("Response", options=list(S.RISK_RESPONSES)),
                    "response_note": CC.TextColumn("Response plan", width="large"),
                    "status": CC.SelectboxColumn("Status", options=list(S.RISK_STATUSES)),
                    "assumption_refs": CC.TextColumn("Linked assumptions"),
                })
            submitted = st.form_submit_button("Apply risk changes", type="primary",
                                              icon=":material/check:")
        if submitted:
            new, issues = apply_risk_table(r.plan, r.edits["risks"], edited.to_dict("records"))
            if new is None:
                flash("error", "Risk changes were not applied.", issues)
            else:
                state.commit_edits(store(), "risks", new)
                flash("success", "Risk register updated.", issues)
            st.rerun()
        if st.button("Reset risks to library", icon=":material/restart_alt:",
                     key=wkey("risk_reset")):
            state.reset_edits(store(), "risks")
            st.rerun()


# --------------------------------------------------------------------------- staffing


def staffing(r: PlanResult) -> None:
    s = r.staffing
    _header(r, "Staffing", "Role costs, coverage and credentials. Staff costs feed the budget "
            "and simulation automatically. Edit roles under Plan inputs › Staffing.")
    c = st.container(key="wp_metrics_staff").columns(4)
    c[0].metric("Staffing cost", fmt.money(s.total_cost), border=True)
    c[1].metric("People planned", sum(x.count for x in s.rows), border=True)
    c[2].metric("Coverage gap", f"{s.total_gap} short" if s.total_gap else "Covered",
                border=True, help=f"Planned peak {fmt.num(s.planned_peak)} people "
                                  f"({s.peak_source})")
    c[3].metric("Credentials to confirm", len(s.missing_credentials), border=True)
    _table(pd.DataFrame([{
        "Role": x.role, "Count": x.count,
        "Recommended": x.recommended_count, "Gap": x.gap or None,
        "Pay": "Volunteer" if x.volunteer else f"{S.label(x.pay_basis)} {fmt.money(x.rate)}",
        "Hours": x.hours, "Cost": x.cost,
        "Credentials missing": ", ".join(S.label(c) for c in x.missing_certifications) or "None",
        "Note": "Unconfirmed $0 rate" if x.unconfirmed_rate else ""} for x in s.rows],
        columns=["Role", "Count", "Recommended", "Gap", "Pay", "Hours", "Cost",
                 "Credentials missing", "Note"]),
        column_config={"Cost": MONEY, "Hours": CC.NumberColumn(format="%.2f")})
    if s.missing_credentials:
        md.warning("Credentials to confirm: " + "; ".join(s.missing_credentials),
                   icon=":material/badge:")
    st.caption("Recommended count = planned peak ÷ attendees per person, rounded up. Role "
               "templates and ratios are planning suggestions, not regulations.")


# -------------------------------------------------------------------------- marketing


def marketing(r: PlanResult) -> None:
    m = r.marketing
    _header(r, "Marketing", "A dated checklist per channel, counted back from the event. "
            "Marking items complete never sends anything.")
    soon = sum(1 for x in m.rows if x.status != "complete"
               and 0 <= (x.due_date - r.today).days <= 14)
    c = st.container(key="wp_metrics_mkt").columns(3)
    c[0].metric("Complete", f"{m.complete} / {m.total}", border=True)
    c[1].metric("Due in the next 14 days", soon, border=True)
    c[2].metric("Before earliest start", m.infeasible_count, border=True)
    if m.infeasible_count:
        md.error(f"{m.infeasible_count} activity date(s) fall before your earliest marketing "
                 f"start ({m.earliest_start:%d %b %Y}), so the plan is not feasible as scheduled.",
                 icon=":material/event_busy:")
    if m.infeasible_count or m.compressed:
        label = ("Undo compression" if m.compressed else
                 "Compress: move early activities to the earliest start date")
        if st.button(label, icon=":material/compress:", key=wkey("mkt_compress")):
            new = dict(r.edits["marketing"])
            new["compress"] = not m.compressed
            state.commit_edits(store(), "marketing", new)
            st.rerun()
    df = pd.DataFrame([{"id": x.id, "activity": x.activity, "due": x.due_date,
                        "channel": S.label(x.channel), "owner": x.owner_role,
                        "status": x.status, "flags": flags_text(x.flags)} for x in m.rows],
                      columns=["id", "activity", "due", "status", "channel", "owner", "flags"])
    with st.form(wkey("mkt_form"), border=False):
        edited = st.data_editor(
            df, hide_index=True, width="stretch", key=wkey("mkt_editor"),
            disabled=["id", "due", "activity", "channel", "owner", "flags"],
            column_config={"id": None, "due": CC.DateColumn("Due", format="ddd D MMM YYYY"),
                           "activity": CC.TextColumn("Activity", width="large", pinned=True),
                           "channel": "Channel", "owner": "Owner", "flags": "Flags",
                           "status": CC.SelectboxColumn("Status", options=list(S.TASK_STATUSES),
                                                        required=True)})
        c1, c2 = st.columns([1, 3])
        with c1:
            submitted = st.form_submit_button("Save checklist", type="primary",
                                              icon=":material/check:")
    if submitted:
        statuses = {row["id"]: row["status"] for row in edited.to_dict("records")
                    if row["status"] in S.TASK_STATUSES}
        state.commit_edits(store(), "marketing", {**r.edits["marketing"], "status": statuses})
        flash("success", "Marketing checklist saved. Nothing was sent.")
        st.rerun()
    st.download_button("Download schedule (CSV)", export.export_marketing_csv(m),
                       "wellnesspop_marketing.csv", "text/csv", icon=":material/download:",
                       key=wkey("mkt_csv"))
    md.caption(m.budget_note)


# ---------------------------------------------------------------------------- exports


def exports(r: PlanResult) -> None:
    _header(r, "Exports", "Files are generated in memory from the current plan revision and are "
            "not stored anywhere.", sim_chip=True)
    _sim_banner(r)
    sim = r.current_simulation
    key = f"{r.revision_fingerprint}:{sim.fingerprint if sim else 'nosim'}"
    xlsx = state.cached_export(store(), key, "xlsx", lambda: export.export_xlsx(r))
    pdf = state.cached_export(store(), key, "pdf", lambda: export.export_pdf(r))
    slug = "".join(c if c.isalnum() else "_" for c in r.plan.event.name.lower()).strip("_")[:40]
    slug = slug or "plan"
    items = [
        ("Excel workbook", ":material/table_view:",
         "Eight sheets: " + ", ".join(export.SHEETS) + ". Opens in Excel, Google Sheets or "
         "LibreOffice.", xlsx, f"{slug}.xlsx",
         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "primary"),
        ("One-page PDF summary" + ("" if sim else " (incomplete)"), ":material/picture_as_pdf:",
         "Budget, break-even, simulation, top risks, readiness and next tasks on one page."
         + ("" if sim else " Run the simulation for a complete summary."),
         pdf, f"{slug}_summary.pdf", "application/pdf", "secondary"),
        ("Marketing schedule", ":material/csv:",
         "One row per activity and channel, with due dates and status.",
         export.export_marketing_csv(r.marketing), f"{slug}_marketing.csv", "text/csv",
         "secondary"),
    ]
    cols = st.columns(3)
    for col, (title, icon, desc, data, name, mime, kind) in zip(cols, items):
        with col:
            with st.container(border=True, height="stretch"):
                st.subheader(title, anchor=False)
                md.write(desc)
                st.download_button(f"Download {name.rsplit('.', 1)[1].upper()}", data, name, mime,
                                   type=kind, icon=icon,
                                   key=wkey(f"dl_{name}"), width="stretch")
    if sim is None:
        st.caption("Without a current simulation, the PDF is labelled incomplete and the "
                   "workbook's Simulation sheet says it was not run. Old results are never reused.")
