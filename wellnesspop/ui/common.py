"""Shared Streamlit helpers. All user data lives in ``st.session_state`` only."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from wellnesspop import schema as S
from wellnesspop import state
from wellnesspop.validation import Issue

FLAG_TEXT = {"overdue": "Overdue", "late_start": "Start date passed",
             "conflict": "Date conflict", "pinned": "Pinned date", "infeasible":
             "Before earliest start", "compressed": "Compressed"}


def esc(text) -> str:
    """Escape dollar signs so Streamlit markdown does not render money as LaTeX."""
    return str(text).replace(r"\$", "$").replace("$", r"\$")


class _Markdown:
    """Drop-in for st.write/markdown/caption/alerts that escapes dollar signs in text."""

    def __getattr__(self, name):
        fn = getattr(st, name)

        def call(body, *args, **kwargs):
            return fn(esc(body) if isinstance(body, str) else body, *args, **kwargs)

        return call


md = _Markdown()


def store():
    return st.session_state


def wkey(name: str) -> str:
    """Widget key tied to this session's nonce and revision, so commits/clears reset widgets."""
    s = st.session_state[state.KEY]
    return f"wp_{name}_{s['nonce']}_{s['revision']}"


def today() -> dt.date:
    return S.today_in(state.plan(store()).event.timezone)


def humanize(path: str) -> str:
    parts = path.replace("_", " ").split(".")
    return " › ".join(p[:1].upper() + p[1:] for p in parts)


def flash(kind: str, message: str, issues: list[Issue] | None = None) -> None:
    st.session_state["wp_flash"] = (kind, message, issues or [])


def show_flash() -> None:
    item = st.session_state.pop("wp_flash", None)
    if not item:
        return
    kind, message, issues = item
    show_issues(issues, message if kind == "error" else None)
    if kind == "success":
        md.success(message, icon=":material/check_circle:")
        warnings = [i for i in issues if i.severity == "warning"]
        if warnings:
            show_issues(warnings)


def show_issues(issues: list[Issue], heading: str | None = None) -> None:
    errors = [i for i in issues if i.severity == "error"]
    warns = [i for i in issues if i.severity == "warning"]
    if errors or heading:
        lines = "\n".join(f"- **{humanize(i.path)}**: {i.message}" for i in errors)
        md.error(f"{heading or 'Please fix these fields:'}\n\n{lines}", icon=":material/error:")
    if warns:
        lines = "\n".join(f"- **{humanize(i.path)}**: {i.message}" for i in warns)
        md.warning(lines, icon=":material/warning:")


def commit(new_raw: dict, success: str = "Changes applied.") -> None:
    issues = state.commit_plan(store(), new_raw, today())
    if any(i.severity == "error" for i in issues):
        flash("error", "Changes were not applied. Your plan is unchanged.", issues)
    else:
        flash("success", success, issues)
    st.rerun()


def records_to_df(rows: list[dict], columns: list[str], pct_cols: tuple = (),
                  list_cols: tuple = ()) -> pd.DataFrame:
    data = []
    for r in rows:
        row = {}
        for c in columns:
            v = r.get(c)
            if c in pct_cols and v is not None:
                v = round(v * 100, 6)
            if c in list_cols:
                v = ", ".join(v or [])
            row[c] = v
        data.append(row)
    df = pd.DataFrame(data, columns=columns)
    return df.astype(object).where(df.notna(), None) if not df.empty else df


def df_to_records(df: pd.DataFrame, pct_cols: tuple = ()) -> list[dict]:
    out = []
    for rec in df.to_dict("records"):
        row = {}
        for k, v in rec.items():
            if v is None or (isinstance(v, float) and v != v) or v is pd.NaT:
                v = None
            elif k in pct_cols:
                try:
                    v = float(v) / 100
                except (TypeError, ValueError):
                    pass  # validation reports the bad value
            if isinstance(v, str) and k != "label":
                v = v.strip()
            row[k] = v
        if any(v not in (None, "") for k, v in row.items() if k != "id"):
            out.append(row)
    return out


def flags_text(flags) -> str:
    return " · ".join(FLAG_TEXT.get(f, f) for f in flags) or "On track"
