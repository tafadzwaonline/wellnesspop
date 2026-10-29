import csv
import io

import pytest
from openpyxl import load_workbook

from wellnesspop.demos import DEMO_KEYS, load_demo
from wellnesspop.export import (SHEETS, csv_bytes, export_marketing_csv, export_pdf,
                                export_xlsx)
from wellnesspop.planner import build_plan, run_simulation
from wellnesspop.validation import validate_plan


def _result(key, today, sim=True):
    r = build_plan(validate_plan(load_demo(key, today), today), today=today)
    return r.with_simulation(run_simulation(r)) if sim else r


def _pages(pdf: bytes) -> int:
    return pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages")


@pytest.mark.parametrize("key", DEMO_KEYS)
def test_workbook_sheets_and_reconciliation(key, today):
    r = _result(key, today)
    wb = load_workbook(io.BytesIO(export_xlsx(r)))
    assert tuple(wb.sheetnames) == SHEETS
    budget = {row[1]: row[2:5] for row in wb["Budget"].iter_rows(min_row=2, values_only=True)
              if row[1]}
    nets = budget["Net income"]
    assert nets == pytest.approx([r.budget.scenarios[k].net for k in ("low", "likely", "high")])
    assert budget["Registrations needed"][0] == r.break_even.registrations
    sim = {row[0]: row[1] for row in wb["Simulation"].iter_rows(min_row=2, values_only=True)}
    assert sim["Probability of break-even"] == pytest.approx(r.simulation.probability_break_even)
    assert sim["Seed"] == r.plan.simulation.seed and sim["Runs"] == r.plan.simulation.runs
    assumptions = [row[0] for row in wb["Assumptions"].iter_rows(min_row=2, values_only=True)]
    assert "meta.revision_fingerprint" in assumptions and "simulation.seed" in assumptions
    staff_total = [row for row in wb["Staffing"].iter_rows(values_only=True)
                   if row[0] == "Total staffing cost"][0]
    assert staff_total[12] == pytest.approx(r.staffing.total_cost)
    assert wb["Budget"].freeze_panes == "A2"


@pytest.mark.parametrize("key", DEMO_KEYS)
def test_pdf_is_exactly_one_page(key, today):
    pdf = export_pdf(_result(key, today))
    assert pdf.startswith(b"%PDF") and _pages(pdf) == 1


def test_stale_or_missing_simulation_is_labeled(today):
    r = _result("scenario_c", today, sim=False)
    pdf = export_pdf(r)
    assert _pages(pdf) == 1
    wb = load_workbook(io.BytesIO(export_xlsx(r)))
    assert "not run" in str(wb["Simulation"]["B2"].value)
    full = _result("scenario_c", today)
    raw = load_demo("scenario_c", today)
    raw["attendance"]["likely"] = 100
    stale = build_plan(validate_plan(raw, today), today=today, simulation=full.simulation)
    wb = load_workbook(io.BytesIO(export_xlsx(stale)))
    assert "out of date" in str(wb["Simulation"]["B2"].value)


def test_formula_injection_neutralised_and_unicode(today):
    raw = load_demo("scenario_b", today)
    raw["event"]["name"] = "=HYPERLINK(\"http://x\") Café ☀"
    raw["fixed_costs"][0]["label"] = "+cmd|' /C calc'!A0"
    r = build_plan(validate_plan(raw, today), today=today)
    wb = load_workbook(io.BytesIO(export_xlsx(r)))
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                assert cell.data_type != "f", (ws.title, cell.coordinate, cell.value)
    assert _pages(export_pdf(r)) == 1
    rows = list(csv.reader(io.StringIO(csv_bytes([["=1+1", "-5", -5, "@SUM", "ok"]]).decode("utf-8-sig"))))
    assert rows[0] == ["'=1+1", "'-5", "-5", "'@SUM", "ok"]


def test_marketing_csv_one_row_per_activity_channel(today):
    r = _result("scenario_a", today, sim=False)
    text = export_marketing_csv(r.marketing).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == r.marketing.total
    assert {"activity", "channel", "due_date", "status", "owner_role"} <= set(rows[0])
