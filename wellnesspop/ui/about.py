"""About & privacy page."""

from __future__ import annotations

import streamlit as st

from wellnesspop import schema as S
from wellnesspop.ui import theme
from wellnesspop.ui.common import md

PRIVACY = (
    "Your inputs are processed in server memory for this browser session only. WellnessPop has "
    "no accounts and no database, and it does not call outside services. Refreshing the page or "
    "disconnecting can lose your work, so download the Excel workbook to keep it. "
    "**Clear plan** (sidebar › Reset plan) removes your inputs, results, uploads and downloads "
    "from this session."
)


def render() -> None:
    theme.page_header("About & privacy", "A free planning tool for community wellness "
                      "organizers: turn event assumptions into a budget, break-even point, task "
                      "plan, schedule, risk register, staffing and marketing plan, and a "
                      "simulation of financial risk.", eyebrow="WellnessPop")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        with st.container(border=True):
            st.subheader("Privacy", anchor=False)
            md.markdown(PRIVACY)
            md.markdown(
                "- The app runs on a server, not entirely in your browser.\n"
                "- Application code never logs, stores or shares your plan.\n"
                "- On Streamlit Community Cloud, the platform collects usage statistics that the "
                "app cannot switch off, and keeps platform logs. Self-hosting avoids the usage "
                "statistics.\n"
                "- No ticket sales, payments, emails, posts or scraping happen here.")
    with c2:
        with st.container(border=True):
            st.subheader("Model limits", anchor=False)
            md.markdown(
                "- Forecasts come from your assumptions and are not guarantees.\n"
                "- Default amounts marked *illustrative* are invented examples, not researched "
                "Chicago rates.\n"
                "- Hybrid events use a whole-event weather cancellation approximation.\n"
                "- Simulated inputs are sampled independently of each other.")
        with st.container(border=True):
            st.subheader("Accessibility", anchor=False)
            md.markdown(
                "- Every chart has a table alternative.\n"
                "- Status is shown with words, not colour alone.\n"
                "- Light and dark themes are available from the ⋮ menu › Settings.")
    st.caption(f"Schema {S.SCHEMA_VERSION} · engine {S.ENGINE_VERSION}")
