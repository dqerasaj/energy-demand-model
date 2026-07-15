"""
Baseline web dashboard for the LDV sales scenario model. Lets users switch
between the Base/Faster/Slower scenarios and view the scenario config plus
the resulting sales forecasts, as either tables or charts.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from auth import check_password
from data_loader import get_csv_path
from ldv_forecast_model import ForecastResults, run_model, to_wide
from scenario_config import BASE_POWERTRAIN_AND_REGION_SCENARIOS, BASE_REGION_SCENARIOS

REGION_ORDER = ["North America", "Europe", "APAC", "RoW"]
POWERTRAIN_ORDER = ["PHEV", "BEV", "IC Only"]
ANCHOR_YEARS = [2025, 2030, 2035, 2040, 2050]
SCENARIOS = ["Base Case", "Faster Transition", "Slower Transition"]


def build_scenario_config_table(scenario: str) -> pd.DataFrame:
    """Pure anchor-year values straight from scenario_config.py - PHEV rows,
    then BEV rows, then region-level "Total LDV" rows, as bare percentages."""
    rows = []
    for powertrain in ["PHEV", "BEV"]:
        for region in REGION_ORDER:
            anchors = BASE_POWERTRAIN_AND_REGION_SCENARIOS[scenario][(region, powertrain)]
            rows.append(
                {
                    "Region": region,
                    "Powertrain": powertrain,
                    **{str(y): round(anchors[y] * 100, 1) for y in ANCHOR_YEARS},
                }
            )
    for region in REGION_ORDER:
        anchors = BASE_REGION_SCENARIOS[scenario][region]
        rows.append(
            {
                "Region": region,
                "Powertrain": "Total LDV",
                **{str(y): round(anchors[y] * 100, 1) for y in ANCHOR_YEARS},
            }
        )
    return pd.DataFrame(rows)


def _append_global_rollup(
    detail: pd.DataFrame, rollup: pd.DataFrame, scenario: str
) -> pd.DataFrame:
    """Filter both frames to one scenario, drop the now-constant scenario
    column, and stack the region-less rollup rows under a synthetic
    region="Global" so both frames share the same columns for to_wide()."""
    detail_f = detail.loc[detail["scenario"].eq(scenario)].drop(columns="scenario")
    rollup_f = rollup.loc[rollup["scenario"].eq(scenario)].drop(columns="scenario").copy()
    rollup_f.insert(0, "region", "Global")
    return pd.concat([detail_f, rollup_f], ignore_index=True)


def render_region_powertrain_section(results: ForecastResults, scenario: str) -> None:
    combined = _append_global_rollup(
        results.region_and_powertrain_sales, results.powertrain_sales, scenario
    )
    view = st.segmented_control(
        "View", ["Table", "Chart"], default="Table", key="s1_view"
    )
    if view == "Chart":
        detail = results.region_and_powertrain_sales.loc[
            results.region_and_powertrain_sales["scenario"].eq(scenario)
        ]
        fig = px.line(
            detail,
            x="year",
            y="sales",
            color="powertrain",
            facet_col="region",
            facet_col_wrap=2,
            category_orders={"region": REGION_ORDER, "powertrain": POWERTRAIN_ORDER},
            labels={"sales": "Sales (million vehicles)", "year": "Year"},
        )
        fig.update_yaxes(matches=None, showticklabels=True)
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.dataframe(to_wide(combined), hide_index=True)


def render_region_totals_section(results: ForecastResults, scenario: str) -> None:
    combined = _append_global_rollup(results.region_sales, results.total_sales, scenario)
    view = st.segmented_control(
        "View", ["Table", "Chart"], default="Table", key="s2_view"
    )
    if view == "Chart":
        fig = px.line(
            combined,
            x="year",
            y="sales",
            color="region",
            category_orders={"region": [*REGION_ORDER, "Global"]},
            labels={"sales": "Sales (million vehicles)", "year": "Year"},
        )
        fig.update_traces(selector={"name": "Global"}, line=dict(dash="dash", width=4))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.dataframe(to_wide(combined), hide_index=True)


@st.cache_data(show_spinner="Running forecast model...")
def get_forecast_results(csv_path: str) -> ForecastResults:
    return run_model(csv_path)


if __name__ == "__main__":
    st.set_page_config(page_title="LDV Sales Forecast", layout="wide")

    if not check_password():
        st.stop()

    results = get_forecast_results(get_csv_path())

    st.title("LDV Sales Forecast")
    scenario = st.selectbox("Scenario", SCENARIOS, key="scenario")

    st.subheader("Scenario configuration")
    st.caption("Sales Growth (%)")
    st.dataframe(build_scenario_config_table(scenario), hide_index=True)

    st.divider()
    st.subheader("Sales by region & powertrain")
    render_region_powertrain_section(results, scenario)

    st.divider()
    st.subheader("Sales by region (all LDV)")
    render_region_totals_section(results, scenario)
