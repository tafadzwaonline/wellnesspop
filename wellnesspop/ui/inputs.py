"""Input forms. Each form validates the whole plan before anything is committed."""

from __future__ import annotations

import copy
import datetime as dt

import streamlit as st

from wellnesspop import imports
from wellnesspop import schema as S
from wellnesspop import state
from wellnesspop.staffing import role_templates
from wellnesspop.ui import theme
from wellnesspop.ui.common import (md, commit, df_to_records, records_to_df, show_issues, store,
                                   today, wkey)

ILLUSTRATIVE = "Illustrative default, not researched. Replace with your own figure."


def _pct(label: str, value: float, key: str, help: str | None = None) -> float:
    v = st.number_input(f"{label} (%)", min_value=0.0, max_value=100.0, step=1.0,
                        value=round(float(value) * 100, 4), key=wkey(key), help=help)
    return v / 100


def _money(label: str, value: float | None, key: str, help: str | None = None,
           allow_none: bool = False, allow_negative: bool = False):
    return st.number_input(f"{label} ($)", min_value=None if allow_negative else 0.0,
                           step=5.0, value=None if value is None else float(value),
                           key=wkey(key), help=help,
                           placeholder="Not supplied" if allow_none else None, format="%.2f")


def _enum(label: str, choices, value, key: str, help: str | None = None):
    choices = list(choices)
    return st.selectbox(label, choices, index=choices.index(value), format_func=S.label,
                        key=wkey(key), help=help)


def render() -> None:
    raw = state.raw(store())
    from wellnesspop.ui.shell import eyebrow

    theme.page_header("Plan inputs", "Defaults appear immediately. Apply each section with its "
                      "own button: the whole plan is checked first, and nothing changes if a "
                      "field is invalid. Rates are entered as percentages.", eyebrow=eyebrow())
    tabs = st.tabs(["Event & goals", "Venue", "Costs", "Pricing & attendance", "Staffing",
                    "Marketing", "Risk assumptions", "Import"])
    with tabs[0]:
        _event(raw)
    with tabs[1]:
        _venue(raw)
    with tabs[2]:
        _costs(raw)
    with tabs[3]:
        _pricing(raw)
    with tabs[4]:
        _staffing(raw)
    with tabs[5]:
        _marketing(raw)
    with tabs[6]:
        _risk_assumptions(raw)
    with tabs[7]:
        _import(raw)


def _event(raw: dict) -> None:
    ev, goals = raw["event"], raw["goals"]
    with st.form(wkey("form_event")):
        st.subheader("Event")
        name = st.text_input("Event name", ev["name"], max_chars=120, key=wkey("ev_name"),
                             help="No contact details are needed anywhere in WellnessPop.")
        c1, c2, c3 = st.columns(3)
        with c1:
            etype = _enum("Event type", S.EVENT_TYPES, ev["event_type"], "ev_type")
        with c2:
            setting = _enum("Setting", S.SETTINGS, ev["setting"], "ev_setting",
                            help="Outdoor and hybrid events get weather risk and rain-plan tasks.")
        with c3:
            sessions = st.number_input("Number of sessions", 1, 100, int(ev["session_count"]),
                                       key=wkey("ev_sessions"))
        c1, c2, c3 = st.columns(3)
        with c1:
            date = st.date_input("Event date", dt.date.fromisoformat(ev["date"]),
                                 key=wkey("ev_date"), format="YYYY-MM-DD")
        with c2:
            start = st.time_input("Start time", dt.time.fromisoformat(ev["start_time"]),
                                  key=wkey("ev_start"), step=900)
        with c3:
            end = st.time_input("End time", dt.time.fromisoformat(ev["end_time"]),
                                key=wkey("ev_end"), step=900)
        tz = st.text_input("Timezone (IANA name)", ev["timezone"], key=wkey("ev_tz"),
                           help="Dates and 'days to event' use this timezone, not your computer's.")
        hist = st.checkbox("This is a historical plan (allow dates in the past)",
                           ev["historical_ack"], key=wkey("ev_hist"))
        st.subheader("Goals")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            goal = _enum("Primary goal", S.GOALS, goals["primary_goal"], "g_goal")
        with c2:
            target_att = st.number_input("Target on-site attendance", 0, S.MAX_CAPACITY,
                                         int(goals["target_attendance"]), key=wkey("g_att"))
        with c3:
            target_net = _money("Target net income", goals["target_net_income"], "g_net",
                                help="May be negative for a subsidized event.",
                                allow_negative=True)
        with c4:
            limit = _money("Spending limit, optional", goals["spending_limit"], "g_limit",
                           allow_none=True, help="Leave empty if you have no limit.")
        if st.form_submit_button("Apply event & goals", type="primary"):
            new = copy.deepcopy(raw)
            new["event"].update(name=name, event_type=etype, setting=setting, session_count=sessions,
                                date=date.isoformat(), start_time=start.strftime("%H:%M"),
                                end_time=end.strftime("%H:%M"), timezone=tz, historical_ack=hist)
            if setting != ev["setting"]:
                new["weather"]["cancellation_probability"] = S.WEATHER_DEFAULTS[setting]
            new["goals"].update(primary_goal=goal, target_attendance=target_att,
                                target_net_income=target_net, spending_limit=limit)
            commit(new, "Event and goals updated.")


def _venue(raw: dict) -> None:
    v = raw["venue"]
    with st.form(wkey("form_venue")):
        c1, c2 = st.columns([3, 1])
        with c1:
            name = st.text_input("Venue name", v["name"], max_chars=120, key=wkey("v_name"))
        with c2:
            cap = st.number_input("Capacity", 1, S.MAX_CAPACITY, int(v["capacity"]),
                                  key=wkey("v_cap"), help="Registrations cannot exceed this.")
        md.markdown("**Rental and deposit**")
        c1, c2, c3 = st.columns(3)
        with c1:
            rental = _money("Rental total", v["rental_total"], "v_rent",
                            help="Total rental expense, including any advance payment.")
        with c2:
            adv = _money("Advance paid toward rental", v["rental_advance"], "v_adv",
                         help="Part of the rental total; shown only as cash timing.")
        with c3:
            rent_ret = _pct("Rental lost if cancelled", v["rental_retained_fraction"], "v_rent_ret")
        c1, c2 = st.columns(2)
        with c1:
            dep = _money("Refundable security deposit", v["security_deposit"], "v_dep",
                         help="Cash you need up front. Not counted as an expense.")
        with c2:
            forfeit = _pct("Share of deposit expected to be forfeited",
                           v["security_deposit_forfeit_fraction"], "v_forfeit")
        md.markdown("**Permit**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            preq = st.checkbox("Permit required", v["permit_required"], key=wkey("v_preq"))
        with c2:
            pcost = _money("Permit cost", v["permit_cost"], "v_pcost")
        with c3:
            plead = st.number_input("Permit lead time (days)", 0, 365, int(v["permit_lead_days"]),
                                    key=wkey("v_plead"), help=ILLUSTRATIVE)
        with c4:
            pret = _pct("Permit cost lost if cancelled", v["permit_retained_fraction"], "v_pret")
        md.markdown("**Insurance**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            ireq = st.checkbox("Insurance required", v["insurance_required"], key=wkey("v_ireq"))
        with c2:
            icost = _money("Insurance cost", v["insurance_cost"], "v_icost")
        with c3:
            ilead = st.number_input("Insurance lead time (days)", 0, 365,
                                    int(v["insurance_lead_days"]), key=wkey("v_ilead"),
                                    help=ILLUSTRATIVE)
        with c4:
            iret = _pct("Insurance lost if cancelled", v["insurance_retained_fraction"], "v_iret")
        md.caption("Venue rental, permit, insurance, staffing and marketing each enter the cost "
                   "ledger once from these fields. Do not repeat them as miscellaneous costs.")
        if st.form_submit_button("Apply venue", type="primary"):
            new = copy.deepcopy(raw)
            new["venue"].update(name=name, capacity=cap, rental_total=rental, rental_advance=adv,
                                rental_retained_fraction=rent_ret, security_deposit=dep,
                                security_deposit_forfeit_fraction=forfeit, permit_required=preq,
                                permit_cost=pcost, permit_lead_days=plead,
                                permit_retained_fraction=pret, insurance_required=ireq,
                                insurance_cost=icost, insurance_lead_days=ilead,
                                insurance_retained_fraction=iret)
            commit(new, "Venue updated.")


FIXED_COLS = ["id", "label", "category", "amount", "uncertain", "low", "mode", "high",
              "retained_fraction"]
VAR_COLS = ["id", "label", "low", "mode", "high", "retained_fraction"]
CC = st.column_config


def _money_col(label, help=None):
    return CC.NumberColumn(label, min_value=0.0, format="$%.2f", help=help)


def _pct_col(label, help=None):
    return CC.NumberColumn(label, min_value=0.0, max_value=100.0, format="%.1f%%", help=help)


def _costs(raw: dict) -> None:
    md.caption("Fixed costs stay the same however many people come. Variable costs are per "
               "attendee. Tick *Uncertain* to give a fixed cost a low / most likely / high range "
               "for the simulation; its budget value is then the average of the three.")
    with st.form(wkey("form_costs")):
        st.subheader("Fixed costs")
        fixed = st.data_editor(
            records_to_df(raw["fixed_costs"], FIXED_COLS, pct_cols=("retained_fraction",)),
            num_rows="dynamic", width="stretch", key=wkey("fixed_editor"), hide_index=True,
            column_config={
                "id": CC.TextColumn("ID", disabled=True, help="Generated automatically"),
                "label": CC.TextColumn("Cost", required=True),
                "category": CC.SelectboxColumn("Category", options=list(S.COST_CATEGORIES)),
                "amount": _money_col("Amount"),
                "uncertain": CC.CheckboxColumn("Uncertain"),
                "low": _money_col("Low"), "mode": _money_col("Most likely"),
                "high": _money_col("High"),
                "retained_fraction": _pct_col("Lost if cancelled",
                                              "Share of this cost you still pay if cancelled"),
            })
        st.subheader("Variable costs per attendee")
        var = st.data_editor(
            records_to_df(raw["variable_costs"], VAR_COLS, pct_cols=("retained_fraction",)),
            num_rows="dynamic", width="stretch", key=wkey("var_editor"), hide_index=True,
            column_config={
                "id": CC.TextColumn("ID", disabled=True),
                "label": CC.TextColumn("Item", required=True),
                "low": _money_col("Low"), "mode": _money_col("Most likely"),
                "high": _money_col("High"),
                "retained_fraction": _pct_col("Lost if cancelled"),
            })
        md.caption("Variable rows are added together and move as one in the simulation.")
        if st.form_submit_button("Apply costs", type="primary"):
            new = copy.deepcopy(raw)
            new["fixed_costs"] = df_to_records(fixed, ("retained_fraction",))
            new["variable_costs"] = df_to_records(var, ("retained_fraction",))
            commit(new, "Costs updated.")


TIER_COLS = ["id", "label", "preset", "price", "allocation", "weight", "free_quota",
             "billing_basis", "no_show_low", "no_show_mean", "no_show_high", "refund_fraction",
             "fee_refund_fraction"]
TIER_PCT = ("weight", "no_show_low", "no_show_mean", "no_show_high", "refund_fraction",
            "fee_refund_fraction")
REV_COLS = ["id", "label", "unit_price", "quantity_basis", "quantity", "uptake_rate",
            "units_per_buyer", "fee_rate", "prepaid", "refund_fraction", "fee_refund_fraction"]
REV_PCT = ("uptake_rate", "fee_rate", "refund_fraction", "fee_refund_fraction")


def _pricing(raw: dict) -> None:
    att, ns = raw["attendance"], raw["no_show"]
    c1, c2, c3, c4 = st.columns(4)
    for col, preset in zip((c1, c2, c3), ("early_bird", "sliding_scale", "free")):
        with col:
            if st.button(f"Add {S.label(preset).lower()} tier", icon=":material/add:",
                         key=wkey(f"add_{preset}"), width="stretch"):
                new = copy.deepcopy(raw)
                new["ticket_tiers"].append(S.tier_from_preset(preset))
                commit(new, f"{S.label(preset)} tier added with a 0% share. Rebalance shares "
                            "so weighted tiers total 100%.")
    with st.form(wkey("form_pricing")):
        st.subheader("Registrations (before no-shows)")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            low = st.number_input("Low", 0.0, value=float(att["low"]), key=wkey("a_low"))
        with c2:
            likely = st.number_input("Likely", 0.0, value=float(att["likely"]), key=wkey("a_lik"))
        with c3:
            high = st.number_input("High", 0.0, value=float(att["high"]), key=wkey("a_high"))
        with c4:
            peak = st.number_input("Staffing peak (optional)", 0.0, value=att["planned_peak"],
                                   key=wkey("a_peak"), placeholder="Use high estimate",
                                   help="Leave empty to staff for the high registration estimate.")
        st.subheader("No-shows")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            ns_low = _pct("Low", ns["low"], "ns_low")
        with c2:
            ns_mean = _pct("Mean", ns["mean"], "ns_mean",
                           help="Must sit strictly between low and high, or set all three equal.")
        with c3:
            ns_high = _pct("High", ns["high"], "ns_high")
        with c4:
            conc = st.number_input("Concentration", 0.1, 1000.0, float(ns["concentration"]),
                                   key=wkey("ns_k"), help="Model-shape assumption (default 6). "
                                   "Higher values cluster no-show rates closer to the mean.")
        fee = _pct("Ticket processing fee", raw["processing"]["ticket_fee_rate"], "fee",
                   help="Entered by you; WellnessPop does not process payments.")
        st.subheader("Ticket tiers")
        md.caption("Weighted shares of weighted tiers must total 100%. *Fixed free places* are "
                   "filled first (price $0). *Prepaid* tiers are billed per registration, so "
                   "no-shows still pay. Leave the no-show override blank to use the event rates.")
        tiers = st.data_editor(
            records_to_df(raw["ticket_tiers"], TIER_COLS, pct_cols=TIER_PCT), num_rows="dynamic",
            width="stretch", key=wkey("tier_editor"), hide_index=True,
            column_config={
                "id": CC.TextColumn("ID", disabled=True),
                "label": CC.TextColumn("Tier", required=True),
                "preset": CC.SelectboxColumn("Preset", options=list(S.TIER_PRESETS)),
                "price": _money_col("Price"),
                "allocation": CC.SelectboxColumn("Allocation", options=list(S.ALLOCATIONS)),
                "weight": _pct_col("Share"),
                "free_quota": CC.NumberColumn("Free places", min_value=0, step=1),
                "billing_basis": CC.SelectboxColumn("Billing", options=list(S.BILLING_BASES)),
                "no_show_low": _pct_col("No-show low"), "no_show_mean": _pct_col("No-show mean"),
                "no_show_high": _pct_col("No-show high"),
                "refund_fraction": _pct_col("Refunded if cancelled"),
                "fee_refund_fraction": _pct_col("Fee refunded with refund"),
            })
        st.subheader("Additional revenue")
        md.caption("Class passes, vendor fees and similar. *Per attendee* lines scale with "
                   "attendance; prepaid lines must use a fixed quantity.")
        rev = st.data_editor(
            records_to_df(raw["additional_revenue"], REV_COLS, pct_cols=REV_PCT),
            num_rows="dynamic", width="stretch", key=wkey("rev_editor"), hide_index=True,
            column_config={
                "id": CC.TextColumn("ID", disabled=True),
                "label": CC.TextColumn("Revenue line", required=True),
                "unit_price": _money_col("Unit price"),
                "quantity_basis": CC.SelectboxColumn("Basis", options=list(S.QUANTITY_BASES)),
                "quantity": CC.NumberColumn("Fixed quantity", min_value=0.0),
                "uptake_rate": _pct_col("Uptake"),
                "units_per_buyer": CC.NumberColumn("Units per buyer", min_value=0.0),
                "fee_rate": _pct_col("Fee"), "prepaid": CC.CheckboxColumn("Prepaid"),
                "refund_fraction": _pct_col("Refunded if cancelled"),
                "fee_refund_fraction": _pct_col("Fee refunded with refund"),
            })
        if st.form_submit_button("Apply pricing & attendance", type="primary"):
            new = copy.deepcopy(raw)
            new["attendance"].update(low=low, likely=likely, high=high, planned_peak=peak)
            new["no_show"].update(low=ns_low, mean=ns_mean, high=ns_high, concentration=conc)
            new["processing"]["ticket_fee_rate"] = fee
            new["ticket_tiers"] = df_to_records(tiers, TIER_PCT)
            new["additional_revenue"] = df_to_records(rev, REV_PCT)
            commit(new, "Pricing and attendance updated.")


STAFF_COLS = ["id", "role", "count", "hours", "pay_basis", "rate", "volunteer",
              "required_certifications", "confirmed_certifications", "coverage_ratio",
              "retained_fraction"]


def _staffing(raw: dict) -> None:
    md.caption("Use role labels, not names or contact details. Credentials: "
               + ", ".join(S.CERTIFICATIONS) + " (comma-separated). A paid role with a $0 rate is "
               "shown as an unconfirmed estimate.")
    tmpl = {t["key"]: t for t in role_templates()}
    c1, c2 = st.columns([3, 1])
    with c1:
        choice = st.selectbox("Suggested roles", list(tmpl), format_func=lambda k: tmpl[k]["role"],
                              key=wkey("role_tmpl"), help="Planning suggestions, not regulations.")
    with c2:
        md.write("")
        if st.button("Add role", icon=":material/person_add:", key=wkey("add_role"),
                     width="stretch"):
            t = tmpl[choice]
            new = copy.deepcopy(raw)
            ev = state.plan(store()).event
            row = S.record_defaults("staffing", duration_hours=ev.duration_hours)
            row.update(role=t["role"], pay_basis=t["pay_basis"], volunteer=t["volunteer"],
                       coverage_ratio=t["coverage_ratio"],
                       required_certifications=t["required_certifications"])
            new["staffing"].append(row)
            commit(new, f"{t['role']} added. {t['note']}")
    with st.form(wkey("form_staff")):
        staff = st.data_editor(
            records_to_df(raw["staffing"], STAFF_COLS, pct_cols=("retained_fraction",),
                          list_cols=("required_certifications", "confirmed_certifications")),
            num_rows="dynamic", width="stretch", key=wkey("staff_editor"), hide_index=True,
            column_config={
                "id": CC.TextColumn("ID", disabled=True),
                "role": CC.TextColumn("Role", required=True),
                "count": CC.NumberColumn("Count", min_value=0, step=1),
                "hours": CC.NumberColumn("Hours", min_value=0.0),
                "pay_basis": CC.SelectboxColumn("Pay basis", options=list(S.PAY_BASES)),
                "rate": _money_col("Rate", "Flat fee per person, or hourly rate"),
                "volunteer": CC.CheckboxColumn("Volunteer"),
                "required_certifications": CC.TextColumn("Credentials required"),
                "confirmed_certifications": CC.TextColumn("Credentials confirmed"),
                "coverage_ratio": CC.NumberColumn("Attendees per person", min_value=0.0,
                                                  help="Leave blank if not ratio-based"),
                "retained_fraction": _pct_col("Pay owed if cancelled"),
            })
        if st.form_submit_button("Apply staffing", type="primary"):
            new = copy.deepcopy(raw)
            new["staffing"] = df_to_records(staff, ("retained_fraction",))
            commit(new, "Staffing updated. Budget and simulation inputs now include it.")


def _marketing(raw: dict) -> None:
    m = raw["marketing"]
    with st.form(wkey("form_mkt")):
        c1, c2 = st.columns(2)
        with c1:
            start = st.date_input("Earliest marketing start", dt.date.fromisoformat(m["earliest_start"]),
                                  key=wkey("m_start"), format="YYYY-MM-DD")
        with c2:
            budget = _money("Marketing budget", m["budget"], "m_budget",
                            help="Added once to fixed costs.")
        channels = st.multiselect("Channels", list(S.CHANNELS), default=m["channels"],
                                  format_func=S.label, key=wkey("m_channels"))
        ret = _pct("Marketing spend lost if cancelled", m["budget_retained_fraction"], "m_ret")
        md.caption("WellnessPop schedules marketing activities; it never sends emails or posts.")
        if st.form_submit_button("Apply marketing", type="primary"):
            new = copy.deepcopy(raw)
            new["marketing"].update(earliest_start=start.isoformat(), budget=budget,
                                    channels=channels, budget_retained_fraction=ret)
            commit(new, "Marketing settings updated.")
    if raw.get("marketing_activities") is not None:
        md.info("This plan uses an imported list of marketing activities instead of the "
                "generated schedule.")
        if st.button("Use generated marketing schedule instead", key=wkey("m_regen")):
            new = copy.deepcopy(raw)
            new["marketing_activities"] = None
            commit(new, "Generated marketing schedule restored.")


def _risk_assumptions(raw: dict) -> None:
    rain, sim = raw["rain"], raw["simulation"]
    setting = raw["event"]["setting"]
    with st.form(wkey("form_risk")):
        st.subheader("Weather")
        p = _pct("Weather cancellation probability", raw["weather"]["cancellation_probability"],
                 "w_p", help="Forced to 0 for indoor events. Outdoor 25% and hybrid 20% defaults "
                 "are illustrative. Rainfall frequency is not the same as cancellation risk.")
        if setting == "hybrid":
            md.caption("Hybrid events are modeled as a whole-event cancellation (MVP approximation).")
        has = st.checkbox("We have a rain plan", rain["has_rain_plan"], key=wkey("r_has"))
        c1, c2 = st.columns(2)
        with c1:
            alt_date = st.date_input(
                "Alternate date", dt.date.fromisoformat(rain["alternate_date"])
                if rain["alternate_date"] else None, key=wkey("r_date"), format="YYYY-MM-DD")
        with c2:
            alt_venue = st.text_input("Alternate venue (description)", rain["alternate_venue"] or "",
                                      max_chars=120, key=wkey("r_venue"))
        md.caption("The alternate date is recorded in tasks and risks; the simulation does not "
                   "model a second event date.")
        st.subheader("Simulation settings")
        c1, c2 = st.columns(2)
        with c1:
            seed = st.number_input("Random seed", 0, 2**53 - 1, int(sim["seed"]), key=wkey("s_seed"),
                                   help="The same inputs and seed always reproduce the same results.")
        with c2:
            runs = st.number_input("Runs", S.MIN_RUNS, S.MAX_RUNS, int(sim["runs"]), step=1000,
                                   key=wkey("s_runs"))
        md.caption("Costs lost if cancelled are set beside each cost (Venue, Costs, Staffing, "
                   "Marketing). Refund settings are on the ticket tier and revenue tables.")
        if st.form_submit_button("Apply risk assumptions", type="primary"):
            new = copy.deepcopy(raw)
            new["weather"]["cancellation_probability"] = p
            new["rain"].update(has_rain_plan=has,
                               alternate_date=alt_date.isoformat() if alt_date else None,
                               alternate_venue=alt_venue or None)
            new["simulation"].update(seed=seed, runs=runs)
            commit(new, "Risk assumptions updated.")


def _import(raw: dict) -> None:
    s = st.session_state[state.KEY]
    md.write("Upload a filled-in template to replace parts of your plan. Files are read in "
             "memory only; nothing is saved. Formulas, macros and external links are rejected; "
             "limit 5 MB and 5,000 rows per table.")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Download XLSX input template (current plan)",
                           imports.import_template_xlsx(raw), "wellnesspop_input_template.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key=wkey("tmpl_xlsx"))
    with c2:
        csv_t = st.selectbox("CSV template", list(imports.CSV_TARGETS), key=wkey("tmpl_csv_t"))
        st.download_button(f"Download {csv_t} CSV template", imports.csv_template(csv_t, raw),
                           f"wellnesspop_{csv_t.lower()}.csv", "text/csv", key=wkey("tmpl_csv"))
    up = st.file_uploader("Upload .xlsx or .csv", type=["xlsx", "csv"],
                          key=f"wp_upload_{s['nonce']}")
    target = None
    if up is not None and up.name.lower().endswith(".csv"):
        target = st.selectbox("This CSV replaces which table?", list(imports.CSV_TARGETS),
                              key=wkey("csv_target"))
    if up is not None and st.button("Preview import", key=wkey("preview")):
        s["import_preview"] = imports.parse_upload(up.getvalue(), up.name, target, raw, today())
    preview = s.get("import_preview")
    if preview is None:
        return
    md.markdown(f"**Preview: {preview.filename}** ({preview.target})")
    for line in preview.summary:
        md.write("• " + line)
    if not preview.ok:
        show_issues(preview.errors, "Import rejected. Your current plan is unchanged.")
        return
    if preview.warnings:
        show_issues(preview.warnings)
    md.success("The file is valid. Apply it to replace the listed parts of your plan.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Apply import", type="primary", key=wkey("apply_import")):
            proposed = preview.proposed_raw
            s["import_preview"] = None
            commit(proposed, "Import applied.")
    with c2:
        if st.button("Discard preview", key=wkey("discard_import")):
            s["import_preview"] = None
            st.rerun()
