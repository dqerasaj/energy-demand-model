"""Forecasts page: pick a scenario, filter by region/powertrain, and view the
scenario config and resulting sales forecasts as charts or tables. Reflects a
saved scenario override from the Edit Scenario Configs page, if one exists.
"Show all scenario cases" switches the scenario config tables and both sales
sections into a Base/Faster/Slower side-by-side view.

Rendered once per vehicle model - the VehicleModel passed to render() supplies
the regions, powertrains, data and widget-key prefix.
"""

import pandas as pd
import streamlit as st

from dashboard_helpers import (
    GLOBAL_PT_SPLIT_PER_SCENARIO,
    GLOBAL_PT_TREND_PER_SCENARIO,
    PT_SCENARIO_TREND_PER_REGION,
    REGIONAL_SPLIT_PER_SCENARIO,
    REGIONAL_TREND_PER_SCENARIO,
    BASE_CASE,
    SCENARIOS,
    region_totals_from_powertrains,
    append_global_rollup,
    build_tech_tables,
    by_region_chart,
    chart_type_control,
    compute_filtered_view,
    global_powertrain_chart,
    order_sales_table,
    region_split_chart,
    region_trend_chart,
    render_filters,
    render_region_powertrain_section,
    render_region_totals_section,
    render_sales_table,
)
from forecast_model import ForecastResults, aggregate_total_sales, to_wide
from model_cache import get_active_results, get_active_scenario_dicts
from scenario_store import get_main_scenario_name, scenario_names, set_main_scenario
from vehicle_models import VehicleModel


def render_main_scenario_picker(model: VehicleModel) -> None:
    """Which saved scenario drives this model. Choosing one here applies it
    across every one of the model's pages, so it writes straight through to the
    store. Locked while the default scenario is the only one saved."""
    names = scenario_names(model)
    current = get_main_scenario_name(model)
    selected = st.selectbox(
        "Scenario",
        names,
        index=names.index(current),
        disabled=len(names) == 1,
        key=model.wkey("main_scenario_picker"),
        help=(
            "Only the default scenario exists so far - save one from Edit "
            "Scenario Configs to enable this."
            if len(names) == 1
            else f"Applied across every {model.label} page."
        ),
    )
    if selected != current:
        set_main_scenario(model, selected)
        st.rerun()


def render_region_powertrain_section_all_scenarios(
    model: VehicleModel, results: ForecastResults, regions: list[str], powertrains: list[str]
) -> None:
    """Same content as render_region_powertrain_section, but showing all 3
    scenario cases at once - used while "Show all scenario cases" is ticked."""
    view_mode = st.segmented_control(
        "View", ["Chart", "Table"], default="Chart", key=model.wkey("s1_view")
    )

    if view_mode == "Table":
        frames = []
        for s in SCENARIOS:
            v = compute_filtered_view(results, s, regions, powertrains)
            combined = append_global_rollup(v.detail_rp, v.rollup_pt).copy()
            combined["scenario"] = s
            frames.append(combined)
        render_sales_table(
            order_sales_table(model, to_wide(pd.concat(frames, ignore_index=True)))
        )
        return

    chart_type = chart_type_control(
        [
            PT_SCENARIO_TREND_PER_REGION,
            GLOBAL_PT_TREND_PER_SCENARIO,
            GLOBAL_PT_SPLIT_PER_SCENARIO,
        ],
        key=model.wkey("s1_chart_type"),
    )
    scenario_choice = st.selectbox(
        "Scenario case", ["All", *SCENARIOS], key=model.wkey("s1_chart_scenario")
    )

    if scenario_choice != "All":
        view = compute_filtered_view(results, scenario_choice, regions, powertrains)
        if chart_type == PT_SCENARIO_TREND_PER_REGION:
            fig = by_region_chart(model, view.detail_rp)
        else:
            fig = global_powertrain_chart(model, view.rollup_pt, chart_type)
            fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True, key=model.wkey("s1_chart_one"))
        return

    if chart_type == PT_SCENARIO_TREND_PER_REGION:
        detail_all = pd.concat(
            [
                compute_filtered_view(results, s, regions, powertrains).detail_rp.assign(scenario=s)
                for s in SCENARIOS
            ],
            ignore_index=True,
        )
        fig = by_region_chart(model, detail_all, dash_col="scenario")
        st.plotly_chart(fig, use_container_width=True, key=model.wkey("s1_chart_all"))
    else:
        rollup_all = pd.concat(
            [
                compute_filtered_view(results, s, regions, powertrains).rollup_pt.assign(scenario=s)
                for s in SCENARIOS
            ],
            ignore_index=True,
        )
        fig = global_powertrain_chart(model, rollup_all, chart_type, facet_col="scenario")
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True, key=model.wkey("s1_chart_all_global"))


def render_region_totals_section_all_scenarios(
    model: VehicleModel, results: ForecastResults, regions: list[str], powertrains: list[str]
) -> None:
    """Same content as render_region_totals_section, but showing all 3
    scenario cases at once - used while "Show all scenario cases" is ticked."""
    view_mode = st.segmented_control(
        "View", ["Chart", "Table"], default="Chart", key=model.wkey("s2_view")
    )

    if view_mode == "Table":
        frames = []
        for s in SCENARIOS:
            v = compute_filtered_view(results, s, regions, powertrains)
            detail = region_totals_from_powertrains(v.detail_rp)
            rollup = aggregate_total_sales(detail.assign(scenario=s)).drop(columns="scenario")
            combined = append_global_rollup(detail, rollup).copy()
            combined["scenario"] = s
            frames.append(combined)
        render_sales_table(
            order_sales_table(model, to_wide(pd.concat(frames, ignore_index=True)))
        )
        return

    chart_type = chart_type_control(
        [REGIONAL_TREND_PER_SCENARIO, REGIONAL_SPLIT_PER_SCENARIO],
        key=model.wkey("s2_chart_type"),
    )
    scenario_choice = st.selectbox(
        "Scenario case", ["All", *SCENARIOS], key=model.wkey("s2_chart_scenario")
    )

    def totals_for(case: str):
        v = compute_filtered_view(results, case, regions, powertrains)
        detail = region_totals_from_powertrains(v.detail_rp)
        rollup = aggregate_total_sales(detail.assign(scenario=case)).drop(columns="scenario")
        return detail, append_global_rollup(detail, rollup)

    if scenario_choice != "All":
        detail, combined = totals_for(scenario_choice)
        fig = (
            region_trend_chart(model, combined)
            if chart_type == REGIONAL_TREND_PER_SCENARIO
            else region_split_chart(model, detail)
        )
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True, key=model.wkey("s2_chart_one"))
        return

    for s, col in zip(SCENARIOS, st.columns(3)):
        with col:
            st.caption(s)
            detail, combined = totals_for(s)
            fig = (
                region_trend_chart(model, combined)
                if chart_type == REGIONAL_TREND_PER_SCENARIO
                else region_split_chart(model, detail)
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True, key=model.wkey(f"s2_chart_{s}"))


def render(model: VehicleModel) -> None:
    rp_scenarios, r_scenarios = get_active_scenario_dicts(model)
    results = get_active_results(model)

    st.title(model.title)

    render_main_scenario_picker(model)

    # Streamlit forgets a keyed widget's value once it's skipped for a run (e.g.
    # while the "All" placeholder is shown instead), so the last real choice is
    # tracked explicitly here rather than relying on the "scenario" widget key
    # to survive being hidden. Likewise, the "show all" checkbox is read from
    # session_state before it's instantiated below so the scenario selectbox
    # above it can react to the same run's toggle.
    last_key = model.wkey("last_single_scenario")
    show_all_key = model.wkey("show_all_scenario_configs")
    last_scenario = st.session_state.get(last_key, BASE_CASE)
    show_all_scenarios = st.session_state.get(show_all_key, False)

    if show_all_scenarios:
        st.selectbox("Scenario case", ["All"], disabled=True, key=model.wkey("scenario_all"))
        scenario = last_scenario
    else:
        scenario = st.selectbox(
            "Scenario case", SCENARIOS, index=SCENARIOS.index(last_scenario),
            key=model.wkey("scenario"),
        )
        st.session_state[last_key] = scenario

    show_all_scenarios = st.checkbox("Show all scenario cases", key=show_all_key)

    # The scenario configuration is shown here for reference only, always at
    # full scope - it deliberately ignores the per-section filters below, since
    # a scenario's anchor values are a property of the scenario rather than of
    # whatever the viewer is currently looking at. Edit Scenario Configs is
    # where they're explored properly.
    with st.expander("Scenario configuration"):
        if show_all_scenarios:
            tables_by_scenario = {
                s: build_tech_tables(
                    model, s,
                    compute_filtered_view(results, s, model.regions, model.powertrains),
                    rp_scenarios, r_scenarios, model.regions,
                )
                for s in SCENARIOS
            }
            for tech in tables_by_scenario[SCENARIOS[0]]:
                st.caption(model.table_caption(tech))
                for s, col in zip(SCENARIOS, st.columns(3)):
                    with col:
                        st.caption(s)
                        st.dataframe(tables_by_scenario[s][tech], hide_index=True)
        else:
            config_view = compute_filtered_view(
                results, scenario, model.regions, model.powertrains
            )
            tables = build_tech_tables(
                model, scenario, config_view, rp_scenarios, r_scenarios, model.regions
            )
            for name, df in tables.items():
                st.caption(model.table_caption(name))
                st.dataframe(df, hide_index=True)

    st.divider()
    st.subheader("Sales by region & powertrain")
    s1_regions, s1_powertrains = render_filters(model, key_suffix="_s1")
    if show_all_scenarios:
        render_region_powertrain_section_all_scenarios(
            model, results, s1_regions, s1_powertrains
        )
    else:
        render_region_powertrain_section(
            model, results, scenario, s1_regions, s1_powertrains
        )

    st.divider()
    st.subheader(f"Sales by region (all {model.label})")
    # Every powertrain is an option here, the non-forecast ones included, since
    # they are part of the all-vehicle total. All selected by default.
    totals_powertrains = [*model.powertrains, *model.other_powertrain_labels]
    s2_regions, s2_powertrains = render_filters(
        model, key_suffix="_s2", powertrain_options=totals_powertrains
    )
    if show_all_scenarios:
        render_region_totals_section_all_scenarios(
            model, results, s2_regions, s2_powertrains
        )
    else:
        render_region_totals_section(
            model, results, scenario, s2_regions, s2_powertrains
        )
