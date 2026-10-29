"""WellnessPop Streamlit entry point: `streamlit run app.py`."""

from __future__ import annotations

import streamlit as st

from wellnesspop import state
from wellnesspop.ui import shell, theme
from wellnesspop.ui.common import show_flash, store

st.set_page_config(page_title="WellnessPop", page_icon=shell.ICON, layout="wide",
                   initial_sidebar_state="auto")
theme.inject_css()
state.init(store())
st.logo(shell.LOGO, icon_image=shell.ICON, size="large")
page = shell.navigation()
shell.sidebar()
show_flash()
page.run()
