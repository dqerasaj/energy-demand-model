"""
Baseline web dashboard for the LDV sales scenario model. Entry point: wires
up auth and page navigation. The actual page content lives in
page_dashboard.py, page_edit_scenario.py, and page_scenario_comparison.py.
"""

import streamlit as st

from auth import check_password
from data_loader import get_csv_path
import page_dashboard
import page_edit_scenario
import page_scenario_comparison

if __name__ == "__main__":
    st.set_page_config(page_title="LDV Sales Forecast", layout="wide")

    if not check_password():
        st.stop()

    pg = st.navigation(
        [
            st.Page(page_dashboard.render, title="Main Dashboard", url_path="dashboard", default=True),
            st.Page(
                lambda: page_edit_scenario.render(get_csv_path()),
                title="Edit Scenario Configs",
                url_path="edit-scenario",
            ),
            st.Page(
                page_scenario_comparison.render,
                title="Scenario Comparison",
                url_path="scenario-comparison",
            ),
        ]
    )
    pg.run()
