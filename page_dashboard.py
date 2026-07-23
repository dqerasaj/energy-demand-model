"""Main dashboard page: pick a scenario, filter by region/powertrain, and
view the scenario config and resulting sales forecasts as tables or
charts. Reflects a saved scenario override from the Edit Scenario Configs
page, if one exists."""

import streamlit as st

from dashboard_helpers import (
    SCENARIOS,
    build_tech_tables,
    compute_filtered_view,
    render_filters,
    render_region_powertrain_section,
    render_region_totals_section,
)
from data_loader import get_csv_path
from model_cache import get_active_results, get_active_scenario_dicts


def render() -> None:
    rp_scenarios, r_scenarios = get_active_scenario_dicts()
    results = get_active_results(get_csv_path())

    st.title("LDV Sales Forecast")
    scenario = st.selectbox("Scenario", SCENARIOS, key="scenario")

    regions, powertrains = render_filters()
    view = compute_filtered_view(results, scenario, regions, powertrains)

    with st.expander("Scenario configuration"):
        table_captions = {
            "PHEV": "PHEV - penetration share of all-LDV sales (%)",
            "BEV": "BEV - penetration share of all-LDV sales (%)",
            "Total LDVs": "Total LDVs - YoY sales growth (%)",
        }
        tables = build_tech_tables(scenario, view, rp_scenarios, r_scenarios, regions)
        for name, df in tables.items():
            st.caption(table_captions[name])
            st.dataframe(df, hide_index=True)

    st.divider()
    st.subheader("Sales by region & powertrain")
    render_region_powertrain_section(view)

    st.divider()
    st.subheader("Sales by region (all LDV)")
    render_region_totals_section(view)
