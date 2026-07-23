"""Main dashboard page: pick a scenario (built-in or a saved Custom one),
filter by region/powertrain, and view the scenario config and resulting
sales forecasts as tables or charts."""

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
from ldv_forecast_model import run_model
from model_cache import get_forecast_results


def render() -> None:
    results = get_forecast_results(get_csv_path())

    st.title("LDV Sales Forecast")

    has_custom = "custom_scenario_config" in st.session_state
    scenario_options = [*SCENARIOS, "Custom"] if has_custom else SCENARIOS
    scenario = st.selectbox("Scenario", scenario_options, key="scenario")

    if scenario == "Custom":
        rp_scenarios, r_scenarios = st.session_state["custom_scenario_config"]
        results = run_model(
            get_csv_path(), region_scenarios=r_scenarios, region_powertrain_scenarios=rp_scenarios
        )
    else:
        rp_scenarios, r_scenarios = None, None

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
