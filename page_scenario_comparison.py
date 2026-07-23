"""Scenario Comparison page: Base Case vs Faster Transition vs Slower
Transition, side by side, for every region + powertrain combination (plus
Global across regions and Total across powertrains)."""

import plotly.express as px
import streamlit as st

from dashboard_helpers import REGION_ORDER, SCENARIOS, combo_series_data, render_powertrain_filter
from data_loader import get_csv_path
from ldv_forecast_model import to_wide
from model_cache import get_active_results


def render() -> None:
    st.title("Scenario Comparison")
    st.write("Base Case vs Faster Transition vs Slower Transition, side by side.")

    results = get_active_results(get_csv_path())
    powertrains = render_powertrain_filter()
    combo_regions = [*REGION_ORDER, "Global"]
    combo_series = [*powertrains, "Total"]

    view = st.segmented_control("View", ["Chart", "Table"], default="Chart", key="comparison_view")
    chart_type = None
    if view == "Chart":
        chart_type = st.segmented_control(
            "Chart type", ["Line", "Grouped Bar"], default="Line", key="comparison_chart_type"
        )

    for region, tab in zip(combo_regions, st.tabs(combo_regions)):
        with tab:
            for series_type in combo_series:
                data = combo_series_data(results, region, series_type)
                st.caption(f"{region} - {series_type}")

                if view == "Table":
                    st.dataframe(to_wide(data), hide_index=True)
                    continue

                plot_fn = px.line if chart_type == "Line" else px.bar
                fig = plot_fn(
                    data,
                    x="year",
                    y="sales",
                    color="scenario",
                    category_orders={"scenario": SCENARIOS},
                    labels={"sales": "Sales (million vehicles)", "year": "Year"},
                )
                if chart_type == "Grouped Bar":
                    fig.update_layout(barmode="group")
                st.plotly_chart(fig, use_container_width=True)
