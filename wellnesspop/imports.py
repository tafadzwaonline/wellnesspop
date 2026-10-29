"""CSV/XLSX import contract: parse in memory, validate everything, preview, then apply.

Uploaded formulas are never evaluated; macros, external links, embedded objects, unknown
sheets or columns, and oversized files are rejected. A failed import never changes the plan.
"""

from __future__ import annotations

import copy
import csv
import datetime as dt
import io
import re
import zipfile
from dataclasses import dataclass, field

from openpyxl import Workbook, load_workbook

from wellnesspop import schema as S
from wellnesspop.validation import Issue, check_plan

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5_000
MAX_SHEETS = 20
MAX_UNCOMPRESSED = 50 * 1024 * 1024
MAX_ZIP_MEMBERS = 500

FIELD_VALUE_SHEETS = {
    "Event": ("schema_version", "currency", "event.", "rain.", "goals.", "venue.", "processing.",
              "weather.", "simulation.", "marketing."),
    "Attendance": ("attendance.", "no_show."),
}
RECORD_SHEETS = {
    "Pricing": "ticket_tiers",
    "Staffing": "staffing",
    "Marketing": "marketing_activities",
    "Revenue": "additional_revenue",
}
COST_COLUMNS = ("cost_kind", "id", "label", "category", "amount", "retained_fraction", "uncertain",
                "low", "mode", "high")
FIXED_ONLY = {"category", "amount", "uncertain"}
INPUT_SHEETS = ("Event", "Costs", "Pricing", "Attendance", "Staffing", "Marketing", "Revenue")
IGNORED_SHEETS = ("README",)
CSV_TARGETS = {"Costs": "Costs", "Pricing": "Pricing", "Staffing": "Staffing",
               "Marketing": "Marketing", "Revenue": "Revenue"}
_NUMERIC = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


class ImportRejected(ValueError):
    pass


@dataclass
class ImportPreview:
    filename: str
    target: str
    ok: bool
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    proposed_raw: dict | None = None
    summary: list[str] = field(default_factory=list)


def _scalar_paths_for(sheet: str) -> set[str]:
    prefixes = FIELD_VALUE_SHEETS[sheet]
    return {s.path for s in S.SCALAR_SPECS
            if any(s.path == p or (p.endswith(".") and s.path.startswith(p)) for p in prefixes)
            and not (sheet == "Event" and s.path.split(".")[0] in ("attendance", "no_show"))}


def _check_text_cell(value, where: str) -> None:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith(("=", "@")):
            raise ImportRejected(f"{where}: formulas are not accepted in input cells")
        if text.startswith(("+", "-")) and not _NUMERIC.match(text.replace(",", "")):
            raise ImportRejected(f"{where}: cells starting with + or - must be numbers")


# ----------------------------------------------------------------------- readers


def _read_csv(content: bytes) -> list[list]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportRejected("CSV files must be UTF-8 encoded") from exc
    if "\x00" in text:
        raise ImportRejected("file contains binary data")
    rows = list(csv.reader(io.StringIO(text)))
    return rows


def _inspect_zip(content: bytes) -> None:
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ImportRejected("not a valid .xlsx workbook") from exc
    infos = zf.infolist()
    if len(infos) > MAX_ZIP_MEMBERS:
        raise ImportRejected("workbook has too many internal parts")
    if sum(i.file_size for i in infos) > MAX_UNCOMPRESSED:
        raise ImportRejected("workbook expands beyond the 50 MB safety limit")
    for i in infos:
        name = i.filename.lower()
        if (name.endswith(".bin") or "vbaproject" in name or "externallink" in name
                or "/embeddings/" in name or "macrosheet" in name or name.endswith(".exe")):
            raise ImportRejected("workbook contains macros, external links, or embedded objects")


def _read_xlsx(content: bytes) -> dict[str, list[list]]:
    _inspect_zip(content)
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=False,
                           keep_links=False)
    except Exception as exc:  # openpyxl raises many types for malformed files
        raise ImportRejected("the workbook could not be read") from exc
    try:
        if len(wb.sheetnames) > MAX_SHEETS:
            raise ImportRejected(f"workbook has more than {MAX_SHEETS} sheets")
        sheets: dict[str, list[list]] = {}
        for ws in wb.worksheets:
            if ws.title in IGNORED_SHEETS:
                continue
            if ws.title not in INPUT_SHEETS:
                raise ImportRejected(f"unknown sheet '{ws.title}'; expected "
                                     f"{', '.join(INPUT_SHEETS)}")
            rows = []
            for r_idx, row in enumerate(ws.iter_rows(), 1):
                if r_idx > MAX_ROWS + 1:
                    raise ImportRejected(f"sheet {ws.title} has more than {MAX_ROWS} rows")
                values = []
                for cell in row:
                    if getattr(cell, "data_type", None) == "f":
                        raise ImportRejected(f"sheet {ws.title} row {r_idx}: formulas are not "
                                             "accepted in input cells")
                    values.append(cell.value)
                rows.append(values)
            sheets[ws.title] = rows
        return sheets
    finally:
        wb.close()


# ----------------------------------------------------------------------- mapping


def _table(rows: list[list], sheet: str) -> tuple[list[str], list[tuple[int, dict]]]:
    rows = [r for r in rows if any(v not in (None, "") for v in r)]
    if not rows:
        return [], []
    header = [str(h).strip().lower() if h is not None else "" for h in rows[0]]
    while header and header[-1] == "":
        header.pop()
    if len(rows) - 1 > MAX_ROWS:
        raise ImportRejected(f"{sheet} has more than {MAX_ROWS} rows")
    out = []
    for n, r in enumerate(rows[1:], 2):
        rec = {}
        for i, h in enumerate(header):
            v = r[i] if i < len(r) else None
            _check_text_cell(v, f"{sheet} row {n}, column {h}")
            if isinstance(v, str):
                v = v.strip()
            rec[h] = v
        if any(v not in (None, "") for v in rec.values()):
            if any(i >= len(header) and v not in (None, "") for i, v in enumerate(r)):
                raise ImportRejected(f"{sheet} row {n}: values found outside named columns")
            out.append((n, rec))
    return header, out


def _field_values(rows, sheet: str, errors: list[Issue]) -> dict[str, object]:
    header, recs = _table(rows, sheet)
    if header[:2] != ["field", "value"]:
        raise ImportRejected(f"{sheet} must have columns 'field' and 'value'")
    allowed = _scalar_paths_for(sheet)
    out = {}
    for n, rec in recs:
        key = str(rec.get("field") or "").strip()
        if key not in allowed:
            errors.append(Issue(f"{sheet} row {n}", f"unknown field '{key}'"))
            continue
        out[key] = rec.get("value")
    return out


def _records(rows, sheet: str, group: str, errors: list[Issue]) -> tuple[list[dict], list[int]]:
    header, recs = _table(rows, sheet)
    allowed = {s.path for s in S.RECORD_SPECS[group]}
    unknown = [h for h in header if h and h not in allowed]
    if unknown:
        raise ImportRejected(f"{sheet}: unknown column(s) {', '.join(unknown)}")
    return [{k: v for k, v in rec.items() if k and v not in (None, "")} for _, rec in recs], \
        [n for n, _ in recs]


def _costs(rows, sheet: str, errors: list[Issue]):
    header, recs = _table(rows, sheet)
    unknown = [h for h in header if h and h not in COST_COLUMNS]
    if unknown:
        raise ImportRejected(f"{sheet}: unknown column(s) {', '.join(unknown)}")
    if "cost_kind" not in header:
        raise ImportRejected(f"{sheet}: a cost_kind column (fixed or variable) is required")
    fixed, variable, fixed_rows, var_rows = [], [], [], []
    for n, rec in recs:
        kind = str(rec.get("cost_kind") or "").strip().lower()
        data = {k: v for k, v in rec.items() if k != "cost_kind" and v not in (None, "")}
        if kind == "fixed":
            fixed.append(data)
            fixed_rows.append(n)
        elif kind == "variable":
            extra = FIXED_ONLY & set(data)
            if extra:
                errors.append(Issue(f"{sheet} row {n}",
                                    f"column(s) {', '.join(sorted(extra))} apply to fixed costs only"))
            variable.append({k: v for k, v in data.items() if k not in FIXED_ONLY})
            var_rows.append(n)
        else:
            errors.append(Issue(f"{sheet} row {n}", "cost_kind must be 'fixed' or 'variable'"))
    return fixed, variable, fixed_rows, var_rows


def parse_upload(content: bytes, filename: str, target: str | None, current_raw: dict,
                 today: dt.date | None = None) -> ImportPreview:
    """Parse and validate an upload against the current plan without changing it.

    target: for CSV, one of Costs/Pricing/Staffing/Marketing/Revenue. Ignored for XLSX.
    """
    name = (filename or "").lower()
    preview = ImportPreview(filename=filename, target=target or "", ok=False)
    try:
        if len(content) > MAX_BYTES:
            raise ImportRejected("files are limited to 5 MB")
        if name.endswith(".xlsx"):
            sheets = _read_xlsx(content)
            preview.target = "Workbook: " + ", ".join(sheets) if sheets else "Workbook"
        elif name.endswith(".csv"):
            if target not in CSV_TARGETS:
                raise ImportRejected("choose which table this CSV replaces")
            sheets = {target: _read_csv(content)}
        else:
            raise ImportRejected("only .csv and .xlsx files are accepted")
        if not sheets:
            raise ImportRejected("no input sheets found")
        proposed = copy.deepcopy(current_raw)
        row_map: dict[str, tuple[str, list[int]]] = {}
        errors: list[Issue] = []
        for sheet, rows in sheets.items():
            if sheet in FIELD_VALUE_SHEETS:
                values = _field_values(rows, sheet, errors)
                for path, value in values.items():
                    S.set_path(proposed, path, value)
                preview.summary.append(f"{sheet}: {len(values)} field(s) updated")
            elif sheet == "Costs":
                fixed, variable, fr, vr = _costs(rows, sheet, errors)
                proposed["fixed_costs"], proposed["variable_costs"] = fixed, variable
                row_map["fixed_costs"] = (sheet, fr)
                row_map["variable_costs"] = (sheet, vr)
                preview.summary.append(f"Costs: {len(fixed)} fixed and {len(variable)} variable "
                                       "row(s) will replace the current cost tables")
            else:
                group = RECORD_SHEETS[sheet]
                recs, nums = _records(rows, sheet, group, errors)
                row_map[group] = (sheet, nums)
                if group == "marketing_activities" and not recs:
                    proposed[group] = None  # empty sheet: keep the generated schedule
                    preview.summary.append("Marketing: no rows, so the generated marketing "
                                           "schedule is used")
                    continue
                proposed[group] = recs
                preview.summary.append(f"{sheet}: {len(recs)} row(s) will replace the current "
                                       "table")
        if errors:
            preview.errors = errors
            return preview
        plan, issues = check_plan(proposed, today)
        preview.errors = [_relabel(i, row_map) for i in issues if i.severity == "error"]
        preview.warnings = [_relabel(i, row_map) for i in issues if i.severity == "warning"]
        if plan is not None:
            preview.ok = True
            preview.proposed_raw = plan.to_dict()
            preview.proposed_raw["provenance"] = proposed.get("provenance", {})
    except ImportRejected as exc:
        preview.errors = [Issue(filename or "upload", str(exc))]
    return preview


def _relabel(issue: Issue, row_map: dict) -> Issue:
    m = re.match(r"^(\w+)\[(\d+)\]\.?(.*)$", issue.path)
    if m and m.group(1) in row_map:
        sheet, nums = row_map[m.group(1)]
        idx = int(m.group(2)) - 1
        if idx < len(nums):
            col = f", field {m.group(3)}" if m.group(3) else ""
            return Issue(f"{sheet} row {nums[idx]}{col}", issue.message, issue.severity)
    return issue


# ------------------------------------------------------------------- templates


def _cell(v):
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v)
    return v


def import_template_xlsx(current_raw: dict) -> bytes:
    """Downloadable input template prefilled with the current plan (values only)."""
    wb = Workbook()
    readme = wb.active
    readme.title = "README"
    for line in (
        ["WellnessPop input template, schema version 1.0"],
        ["Dates use ISO format (YYYY-MM-DD); money is decimal USD; rates are fractions (0.2 = 20%)."],
        ["Event and Attendance sheets use field / value rows. Other sheets use one row per record."],
        ["Leave id blank for new rows. Uploading replaces each included table atomically."],
        ["Leave the Marketing sheet empty (header only) to use the generated marketing schedule."],
        ["Formulas, macros and external links are rejected. This README sheet is ignored on import."],
    ):
        readme.append(line)
    for sheet in ("Event", "Attendance"):
        ws = wb.create_sheet(sheet)
        ws.append(["field", "value"])
        for path in [s.path for s in S.SCALAR_SPECS if s.path in _scalar_paths_for(sheet)]:
            v = S.get_path(current_raw, path)
            ws.append([path, _cell(v)])
    ws = wb.create_sheet("Costs")
    ws.append(list(COST_COLUMNS))
    for r in current_raw.get("fixed_costs") or []:
        ws.append(["fixed"] + [_cell(r.get(c)) for c in COST_COLUMNS[1:]])
    for r in current_raw.get("variable_costs") or []:
        ws.append(["variable"] + [_cell(r.get(c)) if c not in FIXED_ONLY else None
                                  for c in COST_COLUMNS[1:]])
    for sheet, group in RECORD_SHEETS.items():
        ws = wb.create_sheet(sheet)
        cols = [s.path for s in S.RECORD_SPECS[group]]
        ws.append(cols)
        for r in current_raw.get(group) or []:
            ws.append([_cell(r.get(c)) for c in cols])
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def csv_template(target: str, current_raw: dict) -> bytes:
    from wellnesspop.export import csv_bytes  # local import to avoid a cycle

    if target == "Costs":
        rows = [list(COST_COLUMNS)]
        rows += [["fixed"] + [_cell(r.get(c)) for c in COST_COLUMNS[1:]]
                 for r in current_raw.get("fixed_costs") or []]
        rows += [["variable"] + [_cell(r.get(c)) if c not in FIXED_ONLY else None
                                 for c in COST_COLUMNS[1:]]
                 for r in current_raw.get("variable_costs") or []]
    else:
        group = RECORD_SHEETS[target]
        cols = [s.path for s in S.RECORD_SPECS[group]]
        rows = [cols] + [[_cell(r.get(c)) for c in cols] for r in current_raw.get(group) or []]
    return csv_bytes(rows)
