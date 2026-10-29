import io
import zipfile

from openpyxl import Workbook, load_workbook

from wellnesspop.demos import load_demo
from wellnesspop.export import csv_bytes
from wellnesspop.imports import csv_template, import_template_xlsx, parse_upload
from wellnesspop.validation import validate_plan


def _current(today):
    return validate_plan(load_demo("scenario_a", today), today).to_dict()


def test_xlsx_template_round_trip_reproduces_plan(today):
    raw = _current(today)
    preview = parse_upload(import_template_xlsx(raw), "plan.xlsx", None, raw, today)
    assert preview.ok, preview.errors
    a = validate_plan(raw, today).to_dict()
    b = validate_plan(preview.proposed_raw, today).to_dict()
    a.pop("provenance"), b.pop("provenance")
    assert a == b


def test_xlsx_import_covers_every_input_sheet(today):
    raw = _current(today)
    wb = load_workbook(io.BytesIO(import_template_xlsx(raw)))
    assert set(wb.sheetnames) == {"README", "Event", "Costs", "Pricing", "Attendance",
                                  "Staffing", "Marketing", "Revenue"}
    event = {r[0]: r[1] for r in wb["Event"].iter_rows(min_row=2, values_only=True)}
    for path in ("event.name", "venue.capacity", "goals.spending_limit", "rain.has_rain_plan",
                 "processing.ticket_fee_rate", "simulation.seed", "marketing.budget"):
        assert path in event
    att = {r[0] for r in wb["Attendance"].iter_rows(min_row=2, values_only=True)}
    assert {"attendance.low", "no_show.concentration"} <= att


def test_csv_import_replaces_one_group(today):
    raw = _current(today)
    content = csv_bytes([["cost_kind", "id", "label", "category", "amount", "low", "mode", "high"],
                         ["fixed", "", "Banner", "signage", "75", "", "", ""],
                         ["variable", "", "Water", "", "", "1", "1.5", "2"]])
    preview = parse_upload(content, "costs.csv", "Costs", raw, today)
    assert preview.ok, preview.errors
    assert [r["label"] for r in preview.proposed_raw["fixed_costs"]] == ["Banner"]
    assert preview.proposed_raw["variable_costs"][0]["mode"] == 1.5
    assert raw["fixed_costs"][0]["label"] == "Signage"  # current plan untouched


def test_invalid_values_reported_by_sheet_row_and_field(today):
    raw = _current(today)
    content = csv_bytes([["id", "label", "price", "allocation", "weight"],
                         ["", "General", "15", "weighted", "60"]])  # 60 is not a fraction
    preview = parse_upload(content, "pricing.csv", "Pricing", raw, today)
    assert not preview.ok
    assert any(i.path == "Pricing row 2, field weight" and "fraction" in i.message
               for i in preview.errors)
    content = csv_bytes([["cost_kind", "label", "amount"], ["fixed", "Tent", "abc"]])
    assert not parse_upload(content, "c.csv", "Costs", raw, today).ok


def test_malformed_dates_and_unknown_columns(today):
    raw = _current(today)
    content = csv_bytes([["name", "offset_days", "channels", "status", "colour"],
                         ["Poster", "-10", "flyers", "not_started", "red"]])
    p = parse_upload(content, "m.csv", "Marketing", raw, today)
    assert not p.ok and "unknown column" in p.errors[0].message
    wb = Workbook()
    wb.active.title = "Event"
    wb["Event"].append(["field", "value"])
    wb["Event"].append(["event.date", "31/12/2026"])
    buf = io.BytesIO()
    wb.save(buf)
    p = parse_upload(buf.getvalue(), "e.xlsx", None, raw, today)
    assert not p.ok and any("event.date" in i.path for i in p.errors)


def test_formula_cells_rejected(today):
    raw = _current(today)
    wb = Workbook()
    wb.active.title = "Costs"
    ws = wb["Costs"]
    ws.append(["cost_kind", "label", "amount"])
    ws.append(["fixed", "Tent", "=1+1"])
    buf = io.BytesIO()
    wb.save(buf)
    p = parse_upload(buf.getvalue(), "f.xlsx", None, raw, today)
    assert not p.ok and "formula" in p.errors[0].message
    p = parse_upload(csv_bytes([["cost_kind", "label", "amount"]]) + b'fixed,"=HYPERLINK(1)",5\r\n',
                     "c.csv", "Costs", raw, today)
    assert not p.ok and "formula" in p.errors[0].message


def test_unknown_sheet_macros_and_size_limits(today):
    raw = _current(today)
    wb = Workbook()
    wb.active.title = "Secrets"
    buf = io.BytesIO()
    wb.save(buf)
    assert "unknown sheet" in parse_upload(buf.getvalue(), "x.xlsx", None, raw, today).errors[0].message
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as z:
        z.writestr("xl/vbaProject.bin", b"macro")
        z.writestr("[Content_Types].xml", "<x/>")
    assert "macros" in parse_upload(zbuf.getvalue(), "m.xlsx", None, raw, today).errors[0].message
    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/big.xml", b"0" * (60 * 1024 * 1024))
    assert "50 MB" in parse_upload(bomb.getvalue(), "b.xlsx", None, raw, today).errors[0].message
    big = b"a" * (5 * 1024 * 1024 + 1)
    assert "5 MB" in parse_upload(big, "big.csv", "Costs", raw, today).errors[0].message
    assert not parse_upload(b"data", "plan.json", None, raw, today).ok
    rows = [["cost_kind", "label", "amount"]] + [["fixed", f"c{i}", "1"] for i in range(5001)]
    assert "5000" in parse_upload(csv_bytes(rows), "c.csv", "Costs", raw, today).errors[0].message


def test_cross_field_failure_is_atomic(today):
    raw = _current(today)
    # Free places are valid alone but the weighted tiers no longer sum to 100%.
    content = csv_bytes([["label", "price", "allocation", "weight", "free_quota"],
                         ["General", "15", "weighted", "0.5", ""],
                         ["Free", "0", "free_quota", "0", "10"]])
    p = parse_upload(content, "p.csv", "Pricing", raw, today)
    assert not p.ok and p.proposed_raw is None


def test_csv_templates_parse_back(today):
    raw = _current(today)
    for target in ("Costs", "Pricing", "Staffing", "Revenue"):
        p = parse_upload(csv_template(target, raw), f"{target}.csv", target, raw, today)
        assert p.ok, (target, p.errors)
