"""Main dashboard page: pick a scenario, filter by region/powertrain, and
view the scenario config and resulting sales forecasts as tables or
charts. Reflects a saved scenario override from the Edit Scenario Configs
page, if one exists. "Show all scenarios" switches the scenario config
tables and both sales sections into a Base/Faster/Slower side-by-side view."""

import pandas as pd
import streamlit as st

from dashboard_helpers import (
    SCENARIOS,
    append_global_rollup,
    build_tech_tables,
    by_region_chart,
    compute_filtered_view,
    global_powertrain_chart,
    order_sales_table,
    region_split_chart,
    region_trend_chart,
    render_filters,
    render_region_powertrain_section,
    render_region_totals_section,
)
from data_loader import get_csv_path
from ldv_forecast_model import ForecastResults, to_wide
from model_cache import get_active_results, get_active_scenario_dicts


def render_region_powertrain_section_all_scenarios(
    results: ForecastResults, regions: list[str], powertrains: list[str]
) -> None:
    """Same content as render_region_powertrain_section, but showing all 3
    scenarios at once - Main Dashboard only, used while "Show all scenarios"
    is ticked."""
    view_mode = st.segmented_control(
        "View", ["Table", "Chart"], default="Table", key="s1_view"
    )

    if view_mode != "Chart":
        frames = []
        for s in SCENARIOS:
            v = compute_filtered_view(results, s, regions, powertrains)
            combined = append_global_rollup(v.detail_rp, v.rollup_pt).copy()
            combined["scenario"] = s
            frames.append(combined)
        st.dataframe(order_sales_table(to_wide(pd.concat(frames, ignore_index=True))), hide_index=True)
        return

    chart_type = st.segmented_control(
        "Chart type",
        ["By region", "Global trend", "Global split"],
        default="By region",
        key="s1_chart_type",
    )
    scenario_choice = st.selectbox("Scenario", ["All", *SCENARIOS], key="s1_chart_scenario")

    if scenario_choice != "All":
        view = compute_filtered_view(results, scenario_choice, regions, powertrains)
        if chart_type == "By region":
            fig = by_region_chart(view.detail_rp)
        else:
            fig = global_powertrain_chart(view.rollup_pt, chart_type)
            fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)
        return

    if chart_type == "By region":
        detail_all = pd.concat(
            [
                compute_filtered_view(results, s, regions, powertrains).detail_rp.assign(scenario=s)
                for s in SCENARIOS
            ],
            ignore_index=True,
        )
        fig = by_region_chart(detail_all, dash_col="scenario")
        st.plotly_chart(fig, use_container_width=True)
    else:
        for s, col in zip(SCENARIOS, st.columns(3)):
            with col:
                st.caption(s)
                view = compute_filtered_view(results, s, regions, powertrains)
                fig = global_powertrain_chart(view.rollup_pt, chart_type)
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True, key=f"s1_chart_{s}")


def render_region_totals_section_all_scenarios(
    results: ForecastResults, regions: list[str], powertrains: list[str]
) -> None:
    """Same content as render_region_totals_section, but showing all 3
    scenarios at once - Main Dashboard only, used while "Show all scenarios"
    is ticked."""
    view_mode = st.segmented_control(
        "View", ["Table", "Chart"], default="Table", key="s2_view"
    )

    if view_mode != "Chart":
        frames = []
        for s in SCENARIOS:
            v = compute_filtered_view(results, s, regions, powertrains)
            combined = append_global_rollup(v.detail_region, v.rollup_total).copy()
            combined["scenario"] = s
            frames.append(combined)
        st.dataframe(order_sales_table(to_wide(pd.concat(frames, ignore_index=True))), hide_index=True)
        return

    chart_type = st.segmented_control(
        "Chart type", ["Trend", "Split by region"], default="Trend", key="s2_chart_type"
    )
    scenario_choice = st.selectbox("Scenario", ["All", *SCENARIOS], key="s2_chart_scenario")

    if scenario_choice != "All":
        view = compute_filtered_view(results, scenario_choice, regions, powertrains)
        if chart_type == "Trend":
            combined = append_global_rollup(view.detail_region, view.rollup_total)
            fig = region_trend_chart(combined)
        else:
            fig = region_split_chart(view.detail_region)
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)
        return

    for s, col in zip(SCENARIOS, st.columns(3)):
        with col:
            st.caption(s)
            view = compute_filtered_view(results, s, regions, powertrains)
            if chart_type == "Trend":
                combined = append_global_rollup(view.detail_region, view.rollup_total)
                fig = region_trend_chart(combined)
            else:
                fig = region_split_chart(view.detail_region)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True, key=f"s2_chart_{s}")


def render() -> None:
    rp_scenarios, r_scenarios = get_active_scenario_dicts()
    results = get_active_results(get_csv_path())

    st.title("LDV Sales Forecast")

    # Streamlit forgets a keyed widget's value once it's skipped for a run (e.g.
    # while the "All" placeholder is shown instead), so the last real choice is
    # tracked explicitly here rather than relying on the "scenario" widget key
    # to survive being hidden. Likewise, the "show all" checkbox is read from
    # session_state before it's instantiated below so the scenario selectbox
    # above it can react to the same run's toggle.
    last_scenario = st.session_state.get("last_single_scenario", SCENARIOS[0])
    show_all_scenarios = st.session_state.get("show_all_scenario_configs", False)

    if show_all_scenarios:
        st.selectbox("Scenario", ["All"], disabled=True)
        scenario = last_scenario
    else:
        scenario = st.selectbox(
            "Scenario", SCENARIOS, index=SCENARIOS.index(last_scenario), key="scenario"
        )
        st.session_state["last_single_scenario"] = scenario

    regions, powertrains = render_filters()

    show_all_scenarios = st.checkbox("Show all scenarios", key="show_all_scenario_configs")

    view = compute_filtered_view(results, scenario, regions, powertrains)

    table_captions = {
        "PHEV": "PHEV - penetration share of all-LDV sales (%)",
        "BEV": "BEV - penetration share of all-LDV sales (%)",
        "Total LDVs": "Total LDVs - YoY sales growth (%)",
    }

    with st.expander("Scenario configuration"):
        if show_all_scenarios:
            tables_by_scenario = {
                s: build_tech_tables(
                    s, compute_filtered_view(results, s, regions, powertrains),
                    rp_scenarios, r_scenarios, regions,
                )
                for s in SCENARIOS
            }
            for tech in tables_by_scenario[SCENARIOS[0]]:
                st.caption(table_captions[tech])
                for s, col in zip(SCENARIOS, st.columns(3)):
                    with col:
                        st.caption(s)
                        st.dataframe(tables_by_scenario[s][tech], hide_index=True)
        else:
            tables = build_tech_tables(scenario, view, rp_scenarios, r_scenarios, regions)
            for name, df in tables.items():
                st.caption(table_captions[name])
                st.dataframe(df, hide_index=True)

    st.divider()
    st.subheader("Sales by region & powertrain")
    if show_all_scenarios:
        render_region_powertrain_section_all_scenarios(results, regions, powertrains)
    else:
        render_region_powertrain_section(view)

    st.divider()
    st.subheader("Sales by region (all LDV)")
    if show_all_scenarios:
        render_region_totals_section_all_scenarios(results, regions, powertrains)
    else:
        render_region_totals_section(view)
