"""Scenario Comparison page: Base Case vs Faster Transition vs Slower
Transition, side by side, for every region + powertrain combination (plus
Global across regions and Total across powertrains)."""

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard_helpers import SCENARIOS, render_filters
from data_loader import get_csv_path
from ldv_forecast_model import ForecastResults, to_wide
from model_cache import get_forecast_results


def _combo_data(results: ForecastResults, region: str, series_type: str) -> pd.DataFrame:
    """All 3 scenarios' full actual+forecast series for one combination.
    region="Global" = summed across regions; series_type="Total" = summed
    across powertrains (all-LDV)."""
    if series_type == "Total":
        df = (
            results.total_sales
            if region == "Global"
            else results.region_sales.loc[results.region_sales["region"].eq(region)]
        )
    else:
        df = (
            results.powertrain_sales.loc[results.powertrain_sales["powertrain"].eq(series_type)]
            if region == "Global"
            else results.region_and_powertrain_sales.loc[
                results.region_and_powertrain_sales["region"].eq(region)
                & results.region_and_powertrain_sales["powertrain"].eq(series_type)
            ]
        )
    return df.drop(columns=[c for c in ("region", "powertrain") if c in df.columns])


def render() -> None:
    st.title("Scenario Comparison")
    st.write("Base Case vs Faster Transition vs Slower Transition, side by side.")

    results = get_forecast_results(get_csv_path())
    regions, powertrains = render_filters()
    combo_regions = [*regions, "Global"]
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
                data = _combo_data(results, region, series_type)
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
