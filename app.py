"""
Baseline web dashboard for the LDV sales scenario model. Entry point: wires
up auth and page navigation. The actual page content lives in
page_dashboard.py and page_edit_scenario.py.
"""

import streamlit as st

from auth import check_password
from data_loader import get_csv_path
import page_dashboard
import page_edit_scenario

if __name__ == "__main__":
    st.set_page_config(page_title="LDV Sales Forecast", layout="wide")

    if not check_password():
        st.stop()

    pg = st.navigation(
        [
            st.Page(page_dashboard.render, title="Dashboard", default=True),
            st.Page(lambda: page_edit_scenario.render(get_csv_path()), title="Edit Scenario"),
        ]
    )
    pg.run()
