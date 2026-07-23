"""What-if scenario sandbox: edit Base/Faster/Slower's anchor-year values
side by side and see the resulting sales forecasts recompute live. Nothing
is saved unless you click Save, which replaces Base Case/Faster
Transition/Slower Transition app-wide for the rest of the session (Main
Dashboard and Scenario Comparison both pick it up). Reset reverts
everything back to the scenario_config.py defaults."""

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard_helpers import (
    ANCHOR_YEARS,
    REGION_ORDER,
    SCENARIOS,
    build_editable_tech_tables,
    combo_series_data,
    compute_filtered_view,
    render_filters,
    render_region_powertrain_section,
    render_region_totals_section,
)
from ldv_forecast_model import ForecastResults, run_model
from model_cache import get_forecast_results

TECHS = ["PHEV", "BEV", "Total LDVs"]


def _tables_to_scenario_dicts(
    edited_tables: dict[str, dict[str, pd.DataFrame]]
) -> tuple[dict, dict]:
    """Split the edited {tech: {scenario: DataFrame}} dict back into the two
    scenario-dict shapes run_model expects, converting bare percentages back
    to fractions."""
    region_powertrain: dict = {s: {} for s in SCENARIOS}
    region_only: dict = {s: {} for s in SCENARIOS}
    for powertrain in ["PHEV", "BEV"]:
        for scenario in SCENARIOS:
            for _, row in edited_tables[powertrain][scenario].iterrows():
                region_powertrain[scenario][(row["Region"], powertrain)] = {
                    y: row[str(y)] / 100 for y in ANCHOR_YEARS
                }
    for scenario in SCENARIOS:
        for _, row in edited_tables["Total LDVs"][scenario].iterrows():
            region_only[scenario][row["Region"]] = {y: row[str(y)] / 100 for y in ANCHOR_YEARS}
    return region_powertrain, region_only


def _changed_scenarios(
    pristine_tables: dict[str, dict[str, pd.DataFrame]],
    edited_tables: dict[str, dict[str, pd.DataFrame]],
) -> dict[tuple[str, str], list[str]]:
    """{(region, tech): [scenario, ...]} for every region+tech with at least
    one edited scenario - the list names exactly which scenario(s) changed,
    so the chart can decide between an Original-vs-Edited diff (1 scenario
    changed) or a scenario comparison (more than 1). Both tables are already
    rounded to 1dp, so this is an exact comparison, not float-fuzzy."""
    year_cols = [str(y) for y in ANCHOR_YEARS]
    changed: dict[tuple[str, str], list[str]] = {}
    for tech in TECHS:
        pristine_by_scenario = {s: pristine_tables[tech][s].set_index("Region") for s in SCENARIOS}
        edited_by_scenario = {s: edited_tables[tech][s].set_index("Region") for s in SCENARIOS}
        for region in REGION_ORDER:
            changed_here = [
                s
                for s in SCENARIOS
                if not pristine_by_scenario[s].loc[region, year_cols].equals(
                    edited_by_scenario[s].loc[region, year_cols]
                )
            ]
            if changed_here:
                changed[(region, tech)] = changed_here
    return changed


def render_change_charts(
    original_results: ForecastResults,
    custom_results: ForecastResults,
    changed: dict[tuple[str, str], list[str]],
    selected_scenarios: list[str],
) -> None:
    """One chart per changed (region, tech): Original (dashed) vs Edited
    (solid) lines, colored by scenario - but only for the scenario(s) that
    were both actually edited and currently selected in the scenario filter.
    Unchanged scenarios aren't shown, since their Original and Edited lines
    would be identical anyway."""
    if not changed:
        st.caption("No changes yet - edit a value above to see it here.")
        return

    any_shown = False
    for (region, tech), changed_scenarios in changed.items():
        scenarios_to_show = [s for s in changed_scenarios if s in selected_scenarios]
        if not scenarios_to_show:
            continue
        any_shown = True

        series_type = "Total" if tech == "Total LDVs" else tech

        original = combo_series_data(original_results, region, series_type)
        original = original.loc[original["scenario"].isin(scenarios_to_show)].assign(series="Original")
        edited = combo_series_data(custom_results, region, series_type)
        edited = edited.loc[edited["scenario"].isin(scenarios_to_show)].assign(series="Edited")
        data = pd.concat([original, edited], ignore_index=True)

        fig = px.line(
            data,
            x="year",
            y="sales",
            color="scenario",
            line_dash="series",
            line_dash_map={"Original": "dash", "Edited": "solid"},
            category_orders={"scenario": SCENARIOS},
            title=f"{region} - {tech}",
            labels={"sales": "Sales (million vehicles)", "year": "Year"},
        )
        st.plotly_chart(fig, use_container_width=True)

    if not any_shown:
        st.caption("No changes for the selected scenario(s).")


def render(csv_path: str) -> None:
    st.title("Edit Scenario Configs")
    st.write(
        "Tweak the anchor-year values for Base Case, Faster Transition and "
        "Slower Transition below, and see the resulting sales forecasts "
        "update live. Nothing here is saved unless you click Save."
    )

    pristine_tables = build_editable_tech_tables()

    edited_tables: dict[str, dict[str, pd.DataFrame]] = {}
    for tech in TECHS:
        st.subheader(tech)
        edited_tables[tech] = {}
        for scenario, col in zip(SCENARIOS, st.columns(3)):
            with col:
                st.caption(scenario)
                edited_tables[tech][scenario] = st.data_editor(
                    pristine_tables[tech][scenario],
                    hide_index=True,
                    disabled=["Region"],
                    num_rows="fixed",
                    key=f"edit_{tech}_{scenario}_table",
                )

    region_powertrain_scenarios, region_scenarios = _tables_to_scenario_dicts(edited_tables)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save (replaces Base/Faster/Slower app-wide)"):
            st.session_state["scenario_override"] = (region_powertrain_scenarios, region_scenarios)
            st.success("Saved - Main Dashboard and Scenario Comparison now reflect these edits.")
    with col2:
        if st.button("Reset to defaults"):
            st.session_state.pop("scenario_override", None)
            for tech in TECHS:
                for scenario in SCENARIOS:
                    st.session_state.pop(f"edit_{tech}_{scenario}_table", None)
            st.rerun()

    custom_results = run_model(
        csv_path,
        region_scenarios=region_scenarios,
        region_powertrain_scenarios=region_powertrain_scenarios,
    )

    st.divider()
    with st.expander("See changes as charts", expanded=True):
        changed = _changed_scenarios(pristine_tables, edited_tables)
        selected_scenarios = (
            st.multiselect(
                "Show scenario(s)", SCENARIOS, default=SCENARIOS, key="change_chart_scenario_filter"
            )
            or SCENARIOS
        )
        render_change_charts(get_forecast_results(csv_path), custom_results, changed, selected_scenarios)

    st.divider()
    st.subheader("Sales by region & powertrain")
    scenario_to_view = st.selectbox("Scenario", SCENARIOS, key="edit_page_scenario_view")
    regions, powertrains = render_filters()
    view = compute_filtered_view(custom_results, scenario_to_view, regions, powertrains)
    render_region_powertrain_section(view)

    st.divider()
    st.subheader("Sales by region (all LDV)")
    render_region_totals_section(view)
