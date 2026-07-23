"""What-if scenario sandbox: start from a built-in scenario, edit its
anchor-year values, and see the resulting sales forecast recompute live.
Edits are session-only unless explicitly saved - Save makes the edited
values selectable as "Custom" on the main Dashboard page; Reset discards
any saved Custom scenario and reverts the editable tables."""

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard_helpers import (
    ANCHOR_YEARS,
    SCENARIOS,
    build_editable_tech_tables,
    compute_filtered_view,
    render_filters,
    render_region_powertrain_section,
    render_region_totals_section,
)
from ldv_forecast_model import ForecastResults, run_model
from model_cache import get_forecast_results

CUSTOM_SCENARIO_NAME = "Custom"
TECHS = ["PHEV", "BEV", "Total LDVs"]


def _tables_to_scenario_dicts(edited_tables: dict[str, pd.DataFrame]) -> tuple[dict, dict]:
    """Split the edited 3-table dict back into the two scenario-dict shapes
    run_model expects, converting bare percentages back to fractions."""
    region_powertrain: dict = {}
    region_only: dict = {}
    for powertrain in ["PHEV", "BEV"]:
        for _, row in edited_tables[powertrain].iterrows():
            region_powertrain[(row["Region"], powertrain)] = {
                y: row[str(y)] / 100 for y in ANCHOR_YEARS
            }
    for _, row in edited_tables["Total LDVs"].iterrows():
        region_only[row["Region"]] = {y: row[str(y)] / 100 for y in ANCHOR_YEARS}
    return {CUSTOM_SCENARIO_NAME: region_powertrain}, {CUSTOM_SCENARIO_NAME: region_only}


def _changed_configs(
    starting_tables: dict[str, pd.DataFrame], edited_tables: dict[str, pd.DataFrame]
) -> list[tuple[str, str]]:
    """(region, tech) pairs where any year value differs between the
    starting and edited tables. Both are already rounded to 1dp, so this is
    an exact comparison, not float-fuzzy."""
    year_cols = [str(y) for y in ANCHOR_YEARS]
    changed = []
    for tech in TECHS:
        starting = starting_tables[tech].set_index("Region")
        edited = edited_tables[tech].set_index("Region")
        for region in starting.index:
            if not starting.loc[region, year_cols].equals(edited.loc[region, year_cols]):
                changed.append((region, tech))
    return changed


def render_change_charts(
    starting_point: str,
    original_results: ForecastResults,
    custom_results: ForecastResults,
    changed_configs: list[tuple[str, str]],
) -> None:
    if not changed_configs:
        st.caption("No changes yet - edit a value above to see it here.")
        return

    for region, tech in changed_configs:
        if tech == "Total LDVs":
            original = original_results.region_sales.loc[
                original_results.region_sales["scenario"].eq(starting_point)
                & original_results.region_sales["region"].eq(region)
            ].assign(series="Original")
            edited = custom_results.region_sales.loc[
                custom_results.region_sales["region"].eq(region)
            ].assign(series="Edited")
        else:
            original = original_results.region_and_powertrain_sales.loc[
                original_results.region_and_powertrain_sales["scenario"].eq(starting_point)
                & original_results.region_and_powertrain_sales["region"].eq(region)
                & original_results.region_and_powertrain_sales["powertrain"].eq(tech)
            ].assign(series="Original")
            edited = custom_results.region_and_powertrain_sales.loc[
                custom_results.region_and_powertrain_sales["region"].eq(region)
                & custom_results.region_and_powertrain_sales["powertrain"].eq(tech)
            ].assign(series="Edited")

        combined = pd.concat([original, edited], ignore_index=True)
        fig = px.line(
            combined,
            x="year",
            y="sales",
            color="series",
            title=f"{region} - {tech}",
            labels={"sales": "Sales (million vehicles)", "year": "Year"},
        )
        st.plotly_chart(fig, use_container_width=True)


def render(csv_path: str) -> None:
    st.title("Edit Scenario")
    st.write(
        "Start from one of the built-in scenarios, tweak the anchor-year "
        "values below, and see the resulting sales forecast update live. "
        "Nothing here is saved unless you click Save."
    )

    starting_point = st.selectbox("Start from", SCENARIOS, key="edit_starting_point")
    starting_tables = build_editable_tech_tables(starting_point)

    edited_tables = {}
    for tech in TECHS:
        st.caption(tech)
        edited_tables[tech] = st.data_editor(
            starting_tables[tech],
            hide_index=True,
            disabled=["Region"],
            num_rows="fixed",
            key=f"edit_{tech}_table",
        )

    region_powertrain_scenarios, region_scenarios = _tables_to_scenario_dicts(edited_tables)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save as Custom scenario"):
            st.session_state["custom_scenario_config"] = (region_powertrain_scenarios, region_scenarios)
            st.success("Saved - select 'Custom' on the Dashboard page to view it there.")
    with col2:
        if st.button("Reset to defaults"):
            st.session_state.pop("custom_scenario_config", None)
            for tech in TECHS:
                st.session_state.pop(f"edit_{tech}_table", None)
            st.rerun()

    custom_results = run_model(
        csv_path,
        region_scenarios=region_scenarios,
        region_powertrain_scenarios=region_powertrain_scenarios,
    )

    st.divider()
    with st.expander("See changes as charts"):
        changed = _changed_configs(starting_tables, edited_tables)
        render_change_charts(
            starting_point, get_forecast_results(csv_path), custom_results, changed
        )

    regions, powertrains = render_filters()
    view = compute_filtered_view(custom_results, CUSTOM_SCENARIO_NAME, regions, powertrains)

    st.divider()
    st.subheader("Sales by region & powertrain")
    render_region_powertrain_section(view)

    st.divider()
    st.subheader("Sales by region (all LDV)")
    render_region_totals_section(view)
