"""Workbook, PDF, and CSV exports built in memory from one ``PlanResult`` snapshot.

Exports only read values already computed in the snapshot. No temporary files are written.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from wellnesspop import fmt
from wellnesspop import schema as S
from wellnesspop.marketing import MarketingResult
from wellnesspop.planner import PlanResult

SHEETS = ("Assumptions", "Budget", "WBS", "Schedule", "Risks", "Staffing", "Marketing",
          "Simulation")
FONT_DIR = Path(__file__).parent / "fonts"
MONEY_FMT = '"$"#,##0.00;-"$"#,##0.00'
PCT_FMT = "0.0%"
DATE_FMT = "yyyy-mm-dd"
_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


# ------------------------------------------------------------------------------ CSV


def safe_csv_value(v):
    """Neutralise spreadsheet formula injection in text cells (numbers pass unchanged)."""
    if isinstance(v, str) and v.startswith(_DANGEROUS):
        return "'" + v
    return v


def csv_bytes(rows: list[list]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    for row in rows:
        w.writerow(["" if v is None else safe_csv_value(v) for v in row])
    return buf.getvalue().encode("utf-8-sig")


def marketing_rows(m: MarketingResult) -> list[list]:
    rows = [["activity_id", "activity", "channel", "offset_days", "planned_date", "due_date",
             "owner_role", "status", "flags"]]
    for r in m.rows:
        rows.append([r.activity_id, r.activity, S.label(r.channel), r.offset_days,
                     r.planned_due.isoformat(), r.due_date.isoformat(), r.owner_role,
                     S.label(r.status), ", ".join(r.flags)])
    return rows


def export_marketing_csv(m: MarketingResult) -> bytes:
    return csv_bytes(marketing_rows(m))


# ----------------------------------------------------------------------------- XLSX

HEADER_FILL = PatternFill("solid", fgColor="1F5F5B")
HEADER_FONT = Font(bold=True, color="FFFFFF")


def _put(ws, row: int, col: int, value, number_format: str | None = None):
    cell = ws.cell(row=row, column=col)
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(v) for v in value)
    cell.value = value
    if isinstance(value, str):
        cell.data_type = "s"  # never let user text become a formula
        if value.startswith(_DANGEROUS):
            cell.quotePrefix = True
    if number_format and isinstance(value, (int, float)) and not isinstance(value, bool):
        cell.number_format = number_format
    return cell


def _table(ws, header: list[str], rows: list[list], formats: dict[int, str] | None = None,
           start_row: int = 1, freeze: bool = True) -> int:
    formats = formats or {}
    for c, h in enumerate(header, 1):
        cell = _put(ws, start_row, c, h)
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for r, row in enumerate(rows, start_row + 1):
        for c, v in enumerate(row, 1):
            _put(ws, r, c, v, formats.get(c - 1))
    if freeze and start_row == 1:
        ws.freeze_panes = ws.cell(row=2, column=1)
        ws.auto_filter.ref = f"A1:{get_column_letter(len(header))}{max(len(rows) + 1, 1)}"
    return start_row + len(rows) + 1


def _widths(ws, maximum: int = 60) -> None:
    widths: dict[int, int] = {}
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                n = len(str(cell.value)) if not isinstance(cell.value, float) else 12
                widths[cell.column] = max(widths.get(cell.column, 8), min(n + 2, maximum))
    for col, w in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = w


def _d(v):
    return v.isoformat() if v is not None and hasattr(v, "isoformat") else v


def export_xlsx(result: PlanResult) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    plan, b, be = result.plan, result.budget, result.break_even
    sim = result.current_simulation

    ws = wb.create_sheet("Assumptions")
    meta = [
        ["meta.revision_fingerprint", result.revision_fingerprint, "-", "derived", "", "", "", ""],
        ["meta.input_fingerprint", result.input_fingerprint, "-", "derived", "", "", "", ""],
        ["meta.generated_at", result.generated_at.isoformat(timespec="seconds"), "-", "derived",
         "", "", "", ""],
        ["meta.schema_version", S.SCHEMA_VERSION, "-", "derived", "", "", "", ""],
        ["meta.engine_version", S.ENGINE_VERSION, "-", "derived", "", "", "", ""],
        ["meta.simulation_status", result.simulation_status, "-", "derived", "", "", "", ""],
    ]
    rows = meta + [[a["field_path"], a["value"], a["unit"], a["source_kind"], a["source_reference"],
                    a["as_of_date"], a["note"], a["original_source_kind"]] for a in result.assumptions]
    _table(ws, ["Field", "Value", "Unit", "Source kind", "Source / formula", "As of", "Note",
                "Original source kind"], rows)
    _widths(ws)

    ws = wb.create_sheet("Budget")
    sc = [b.scenarios[k] for k in ("low", "likely", "high")]
    rows = [["Attendance", "Registrations", *[s.registrations for s in sc], ""],
            ["Attendance", "Expected attendees (on site)", *[s.attendees for s in sc],
             "Averages; may be fractional"]]
    for i, line in enumerate(sc[0].lines):
        kind = "Ticket" if line.kind == "ticket" else "Additional revenue"
        rows.append(["Revenue", f"{kind}: {line.label} (gross)", *[s.lines[i].gross for s in sc],
                     f"Price {fmt.money(line.price)}"])
    rows += [["Revenue", "Ticket revenue (gross)", *[s.ticket_gross for s in sc], ""],
             ["Revenue", "Additional revenue (gross)", *[s.addl_gross for s in sc], ""],
             ["Revenue", "Processing fees", *[-s.processing_fees for s in sc], "Deducted"],
             ["Revenue", "Net revenue", *[s.revenue_net for s in sc], ""]]
    for item in b.ledger:
        note = f"{item.source}; retained if cancelled {item.retained_fraction:.0%}"
        if item.uncertain:
            note += f"; triangular {fmt.money(item.low)}/{fmt.money(item.mode)}/{fmt.money(item.high)}"
        rows.append(["Fixed costs", item.label, item.mean, item.mean, item.mean, note])
    rows += [["Fixed costs", "Total fixed costs", *[s.fixed_total for s in sc], ""],
             ["Variable costs", "Variable cost per attendee", b.variable_cost_per_attendee,
              b.variable_cost_per_attendee, b.variable_cost_per_attendee, "Mean of summed rows"],
             ["Variable costs", "Total variable costs", *[s.variable_expense for s in sc], ""],
             ["Costs", "Total cost (fixed + variable)", *[s.total_cost for s in sc], ""],
             ["Result", "Net income", *[s.net for s in sc], "Assumes the event goes ahead"],
             ["Break-even", "Registrations needed", be.registrations, None, None, be.sentence],
             ["Break-even", "On-site attendance needed", be.onsite_attendance, None, None, ""],
             ["Break-even", be.price_target.capitalize(), None, be.required_price, None,
              be.price_sentence],
             ["Cash", "Rental advance (part of rental total)", b.rental_advance, None, None,
              "Cash timing only"],
             ["Cash", "Refundable security deposit", b.security_deposit, None, None,
              "Cash required, not an expense"],
             ["Goals", "Target net income", b.target_net_income, None, None, ""],
             ["Goals", "Spending limit", b.spending_limit, None, None,
              "" if b.spending_limit is not None else "Not supplied"]]
    end = _table(ws, ["Section", "Item", "Low", "Likely", "High", "Note"], rows,
                 {2: MONEY_FMT, 3: MONEY_FMT, 4: MONEY_FMT})
    for r in (2, 3):  # registrations and attendees are counts
        for c in (3, 4, 5):
            ws.cell(row=r, column=c).number_format = "0.0"
    for r in range(2, end):
        if ws.cell(row=r, column=2).value in ("Registrations needed", "On-site attendance needed"):
            ws.cell(row=r, column=3).number_format = "0"
    for i, note in enumerate(b.notes, end + 1):
        _put(ws, i, 1, "Note")
        _put(ws, i, 2, note)
    _widths(ws)

    sched = result.schedule.by_id() if result.schedule else {}
    ws = wb.create_sheet("WBS")
    rows = []
    for t in (sorted(result.tasks, key=lambda t: _code_key(sched.get(t.id))) if sched else result.tasks):
        s = sched.get(t.id)
        rows.append([s.wbs_code if s else "", t.id, t.parent_id or "", S.label(t.phase), t.name,
                     t.owner_role, t.duration_days, ", ".join(t.predecessor_ids),
                     "Summary" if t.is_group else S.label(t.status), t.source])
    _table(ws, ["WBS code", "Task ID", "Parent ID", "Phase", "Task", "Owner role",
                "Duration (days)", "Depends on", "Status", "Source"], rows)
    _widths(ws)

    ws = wb.create_sheet("Schedule")
    rows = []
    if result.schedule:
        for s in result.schedule.tasks:
            t = s.task
            rows.append([s.wbs_code, t.id, t.name, s.start, s.finish, t.duration_days,
                         s.deadline, f"Event {t.offset_days:+d} days", t.lead_rule,
                         "Milestone" if s.is_milestone else "", ", ".join(s.flags),
                         t.manual_start])
    else:
        rows.append(["", "", "Schedule unavailable: fix task dependency errors", None, None,
                     None, None, "", "", "", "", None])
    _table(ws, ["WBS code", "Task ID", "Task", "Start", "Finish (exclusive)", "Duration",
                "Deadline / earliest start", "Anchor", "Lead-time rule", "Milestone", "Flags",
                "Pinned start"], rows, {3: DATE_FMT, 4: DATE_FMT, 6: DATE_FMT, 11: DATE_FMT})
    _widths(ws)

    ws = wb.create_sheet("Risks")
    rows = [[r.id, r.title, r.likelihood, r.impact, r.score, r.band, r.owner_role,
             S.label(r.response), r.response_note, S.label(r.status), ", ".join(r.assumption_refs)]
            for r in result.risks]
    _table(ws, ["Risk ID", "Risk", "Likelihood (1-5)", "Impact (1-5)", "Score", "Band",
                "Owner role", "Response", "Response plan", "Status", "Linked assumptions"], rows)
    _widths(ws)

    ws = wb.create_sheet("Staffing")
    st = result.staffing
    rows = [[r.role, r.count, r.hours, S.label(r.pay_basis), r.rate,
             "Yes" if r.volunteer else "No", ", ".join(S.label(c) for c in r.required_certifications),
             ", ".join(S.label(c) for c in r.confirmed_certifications),
             ", ".join(S.label(c) for c in r.missing_certifications), r.coverage_ratio,
             r.recommended_count, r.gap, r.cost, "Unconfirmed estimate" if r.unconfirmed_rate else ""]
            for r in st.rows]
    end = _table(ws, ["Role", "Count", "Hours", "Pay basis", "Rate", "Volunteer",
                      "Required credentials", "Confirmed credentials", "Missing credentials",
                      "Attendees per person", "Recommended count", "Gap", "Total cost", "Note"],
                 rows, {4: MONEY_FMT, 12: MONEY_FMT})
    _put(ws, end + 1, 1, "Total staffing cost")
    _put(ws, end + 1, 13, st.total_cost, MONEY_FMT)
    _put(ws, end + 2, 1, f"Planned peak attendees: {fmt.num(st.planned_peak)} ({st.peak_source})")
    _widths(ws)

    ws = wb.create_sheet("Marketing")
    m = result.marketing
    rows = [[r.activity, S.label(r.channel), r.due_date, r.planned_due, r.offset_days,
             r.owner_role, S.label(r.status), ", ".join(r.flags)] for r in m.rows]
    end = _table(ws, ["Activity", "Channel", "Due date", "Planned date", "Days from event",
                      "Owner role", "Status", "Flags"], rows, {2: DATE_FMT, 3: DATE_FMT})
    _put(ws, end + 1, 1, m.budget_note)
    _widths(ws)

    ws = wb.create_sheet("Simulation")
    if sim is None:
        _table(ws, ["Item", "Value"], [
            ["Status", "Simulation not run for this revision" if result.simulation_status ==
             "not_run" else "Simulation results are out of date for these inputs"],
            ["Required", "Run the simulation in the app, then export again"]])
    else:
        rows = [["Input fingerprint", sim.fingerprint], ["Seed", sim.seed], ["Runs", sim.runs],
                ["Engine version", sim.engine_version],
                ["Elapsed seconds", round(sim.elapsed_seconds, 4)],
                ["Probability of break-even", sim.probability_break_even],
                ["P10 net income", sim.p10], ["P50 net income", sim.p50],
                ["P90 net income", sim.p90], ["Mean net income", sim.mean],
                ["Share of runs cancelled by weather", sim.cancelled_share],
                ["Quantile method", "linear"],
                ["Sampled dimensions", "; ".join(sim.dimensions) or "none (deterministic)"],
                ["Independence", "Sampled dimensions are independent; variable-cost rows move "
                                 "together; tiers inherit the event no-show draw unless overridden"]]
        end = _table(ws, ["Item", "Value"], rows)
        for r in range(2, end):
            label_ = ws.cell(row=r, column=1).value
            cell = ws.cell(row=r, column=2)
            if "net income" in label_:
                cell.number_format = MONEY_FMT
            elif label_.startswith(("Probability", "Share")):
                cell.number_format = PCT_FMT
        end = _table(ws, ["Sensitivity input", "Kind", "Unit", "Low input (P10 or 0)",
                          "High input (P90 or 1)", "Expected net at low", "Expected net at high",
                          "Impact range", "Baseline expected net"],
                     [[t.name, t.kind, t.unit, t.low_input, t.high_input, t.net_at_low,
                       t.net_at_high, t.impact_range, t.baseline_net] for t in sim.tornado],
                     {5: MONEY_FMT, 6: MONEY_FMT, 7: MONEY_FMT, 8: MONEY_FMT},
                     start_row=end + 2, freeze=False)
        edges = sim.histogram_edges
        _table(ws, ["Histogram bin from", "Bin to", "Runs"],
               [[edges[i], edges[i + 1], c] for i, c in enumerate(sim.histogram_counts)],
               {0: MONEY_FMT, 1: MONEY_FMT}, start_row=end + 2, freeze=False)
        for i, line in enumerate(sim.explainer):
            _put(ws, i + 1, 4, line)
    _widths(ws, 70)

    assert tuple(wb.sheetnames) == SHEETS
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _code_key(s):
    if s is None:
        return [9999]
    return [int(x) for x in s.wbs_code.split(".") if x.isdigit()]


# ------------------------------------------------------------------------------ PDF


class _SummaryPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="Letter")
        self.add_font("DejaVu", "", str(FONT_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(False)
        self.set_margins(12, 12, 12)
        self.set_title("WellnessPop plan summary")
        self.set_creator("WellnessPop")


def _fit(pdf: FPDF, text: str, width: float) -> str:
    text = " ".join(str(text).split())
    if pdf.get_string_width(text) <= width:
        return text
    while text and pdf.get_string_width(text + "…") > width:
        text = text[:-1]
    return text.rstrip() + "…"


def export_pdf(result: PlanResult) -> bytes:
    plan, b, be = result.plan, result.budget, result.break_even
    sim = result.current_simulation
    pdf = _SummaryPDF()
    pdf.add_page()
    W = pdf.w - pdf.l_margin - pdf.r_margin
    col_w = (W - 6) / 2

    pdf.set_font("DejaVu", "B", 15)
    pdf.cell(W, 7, _fit(pdf, plan.event.name, W), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 8.5)
    ev = plan.event
    line = (f"{ev.date:%A %d %B %Y}, {ev.start_time:%H:%M}-{ev.end_time:%H:%M} ({ev.timezone}) · "
            f"{S.label(ev.event_type)} · {S.label(ev.setting)} · {plan.venue.name} · capacity "
            f"{plan.venue.capacity}")
    pdf.cell(W, 4.5, _fit(pdf, line, W), new_x="LMARGIN", new_y="NEXT")
    goal = (f"Goal: {S.label(plan.goals.primary_goal)} · target {plan.goals.target_attendance} on "
            f"site · target net {fmt.money(plan.goals.target_net_income)} · spending limit "
            f"{fmt.money(b.spending_limit)}")
    pdf.cell(W, 4.5, _fit(pdf, goal, W), new_x="LMARGIN", new_y="NEXT")
    if sim is None:
        pdf.set_font("DejaVu", "B", 8.5)
        pdf.set_text_color(160, 40, 40)
        pdf.cell(W, 4.5, "INCOMPLETE SUMMARY: simulation has not been run for these inputs.",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
    pdf.ln(1.5)
    top = pdf.get_y()

    def heading(x, text):
        pdf.set_x(x)
        pdf.set_font("DejaVu", "B", 10)
        pdf.set_text_color(31, 95, 91)
        pdf.cell(col_w, 5.5, text, new_x="LEFT", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("DejaVu", "", 8)

    def row(x, label_, value, bold=False, split=0.62):
        pdf.set_x(x)
        pdf.set_font("DejaVu", "B" if bold else "", 8)
        pdf.cell(col_w * split, 4.1, _fit(pdf, label_, col_w * split - 1))
        pdf.cell(col_w * (1 - split), 4.1, _fit(pdf, value, col_w * (1 - split)), align="R",
                 new_x="LEFT", new_y="NEXT")
        pdf.set_x(x)

    def para(x, text, lines=2):
        pdf.set_x(x)
        pdf.set_font("DejaVu", "", 7.5)
        words, cur, out = str(text).split(), "", []
        for w in words:
            trial = (cur + " " + w).strip()
            if pdf.get_string_width(trial) <= col_w:
                cur = trial
            else:
                out.append(cur)
                cur = w
        out.append(cur)
        if len(out) > lines:
            out = out[:lines]
            out[-1] = _fit(pdf, out[-1] + " …", col_w)
        for o in out:
            pdf.set_x(x)
            pdf.cell(col_w, 3.6, o, new_x="LEFT", new_y="NEXT")

    left, right = pdf.l_margin, pdf.l_margin + col_w + 6
    att, ns = plan.attendance, plan.no_show
    heading(left, "Assumptions")
    row(left, "Registrations low / likely / high",
        f"{fmt.num(att.low)} / {fmt.num(att.likely)} / {fmt.num(att.high)}")
    row(left, "No-show rate low / mean / high",
        f"{fmt.pct(ns.low)} / {fmt.pct(ns.mean)} / {fmt.pct(ns.high)}")
    row(left, "Weather cancellation probability", fmt.pct(plan.weather.cancellation_probability))
    row(left, "Variable cost per attendee (mean)", fmt.money(b.variable_cost_per_attendee))
    tiers = ", ".join(f"{t.label} {fmt.money(t.price)}" for t in plan.ticket_tiers)
    extra = ", ".join(f"{a.label} {fmt.money(a.unit_price)}" for a in plan.additional_revenue)
    para(left, "Pricing: " + tiers + (f"; other revenue: {extra}" if extra else ""), 2)
    pdf.ln(1)
    heading(left, "Likely budget")
    lk = b.likely
    row(left, "Expected attendees", fmt.num(lk.attendees))
    row(left, "Net revenue (after fees)", fmt.money(lk.revenue_net))
    row(left, "Fixed costs", fmt.money(lk.fixed_total))
    row(left, "Variable costs", fmt.money(lk.variable_expense))
    row(left, "Net income (likely)", fmt.money(lk.net), bold=True)
    row(left, "Net income low / high", f"{fmt.money(b.scenarios['low'].net)} / "
                                       f"{fmt.money(b.scenarios['high'].net)}")
    if b.cash_required_upfront:
        row(left, "Cash needed up front (advance + deposit)", fmt.money(b.cash_required_upfront))
    pdf.ln(1)
    heading(left, "Break-even")
    row(left, "Registrations needed",
        str(be.registrations) if be.registrations is not None else "Not achievable")
    if be.onsite_attendance is not None:
        row(left, "On-site attendance needed", str(be.onsite_attendance))
    row(left, be.price_target.capitalize(),
        fmt.money(be.required_price) if be.required_price is not None else "Not applicable")
    para(left, be.sentence, 2)
    pdf.ln(1)
    heading(left, "Next tasks")
    upcoming = []
    if result.schedule:
        upcoming = sorted((s for s in result.schedule.tasks
                           if not s.task.is_group and s.task.status != "complete"),
                          key=lambda s: (s.start, s.wbs_code))[:6]
    for s in upcoming:
        flag = " (overdue)" if "overdue" in s.flags else ""
        row(left, f"{s.start:%d %b} · {s.task.name}{flag}", s.task.owner_role, split=0.7)
    if not upcoming:
        row(left, "No open tasks", "")
    left_end = pdf.get_y()

    pdf.set_y(top)
    heading(right, "Financial risk (simulation)")
    if sim is not None:
        row(right, "Probability of breaking even", fmt.pct(sim.probability_break_even), bold=True)
        row(right, "Net income P10 (bad case)", fmt.money(sim.p10))
        row(right, "Net income P50 (typical)", fmt.money(sim.p50))
        row(right, "Net income P90 (good case)", fmt.money(sim.p90))
        main = next((t for t in sim.tornado if t.kind == "continuous"), None)
        if main:
            row(right, "Most influential assumption", main.name)
        para(right, sim.explainer[1], 3)
    else:
        row(right, "Probability of breaking even", "Not run")
        row(right, "Net income P10 / P50 / P90", "Not run")
        para(right, "Run the simulation in the app and export again for a complete summary.", 2)
    pdf.ln(1)
    heading(right, "Top risks")
    open_risks = [r for r in result.risks if r.status != "closed"][:3]
    for r in open_risks:
        row(right, r.title, f"{r.band} ({r.score})", split=0.78)
        pdf.set_x(right)
        pdf.set_font("DejaVu", "", 7)
        pdf.cell(col_w, 3.5, _fit(pdf, f"{S.label(r.response)}: {r.response_note}", col_w),
                 new_x="LEFT", new_y="NEXT")
    pdf.ln(1)
    heading(right, "Readiness")
    st, m = result.staffing, result.marketing
    row(right, "Staffing cost", fmt.money(st.total_cost))
    row(right, "Staffing coverage", "Covered" if st.coverage_ok else
        f"{st.total_gap} short; {len(st.missing_credentials)} credential open")
    row(right, "Marketing activities complete", f"{m.complete} / {m.total}")
    if m.infeasible_count:
        row(right, "Marketing before earliest start", str(m.infeasible_count))
    if result.schedule:
        row(right, "Schedule problems (overdue / conflicts)", str(len(result.schedule.problems)))
    right_end = pdf.get_y()

    pdf.set_y(max(left_end, right_end) + 3)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + W, pdf.get_y())
    pdf.ln(1.5)
    pdf.set_font("DejaVu", "", 7)
    meta = (f"Generated {result.generated_at:%Y-%m-%d %H:%M %Z} · revision "
            f"{result.revision_fingerprint} · engine {S.ENGINE_VERSION} · ")
    meta += (f"seed {sim.seed}, {sim.runs:,} runs" if sim else "simulation not run")
    pdf.cell(W, 3.6, _fit(pdf, meta, W), new_x="LMARGIN", new_y="NEXT")
    caveat = ("Forecast from the organizer's assumptions, not a guarantee. Illustrative values are "
              "not researched rates; see the Excel export for full detail.")
    pdf.cell(W, 3.6, _fit(pdf, caveat, W), new_x="LMARGIN", new_y="NEXT")
    if pdf.get_y() > pdf.h - 8 or pdf.page_no() != 1:
        raise RuntimeError("PDF summary overflowed one page")
    return bytes(pdf.output())
