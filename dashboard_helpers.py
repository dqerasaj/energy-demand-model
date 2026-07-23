"""Shared constants and render helpers used by both the main dashboard page
and the what-if scenario editor page."""

from dataclasses import dataclass

import pandas as pd
import plotly.express as px
import streamlit as st

from ldv_forecast_model import (
    ForecastResults,
    aggregate_powertrain_sales,
    aggregate_total_sales,
    to_wide,
)
from scenario_config import BASE_POWERTRAIN_AND_REGION_SCENARIOS, BASE_REGION_SCENARIOS

REGION_ORDER = ["North America", "Europe", "APAC", "RoW"]
POWERTRAIN_ORDER = ["PHEV", "BEV", "IC Only"]
ANCHOR_YEARS = [2025, 2030, 2035, 2040, 2050]
SCENARIOS = ["Base Case", "Faster Transition", "Slower Transition"]


def build_editable_tech_tables() -> dict[str, dict[str, pd.DataFrame]]:
    """Pure anchor-year values straight from scenario_config.py. Nested:
    {tech: {scenario: DataFrame}} - one simple Region x Year table per
    (tech, scenario) combination, meant to be shown 3-at-a-time (one per
    scenario) side by side under each tech's heading. No computed Global row
    here (unlike build_tech_tables) - these are purely the editable starting
    values for the Edit Scenario Configs page, and editing a computed rollup
    wouldn't make sense. Always built straight from the scenario_config.py
    constants (never from a saved override), since this is also the
    pristine reference Reset needs to revert back to."""
    tables: dict[str, dict[str, pd.DataFrame]] = {}
    for powertrain in ["PHEV", "BEV"]:
        tables[powertrain] = {
            scenario: pd.DataFrame(
                [
                    {
                        "Region": region,
                        **{
                            str(y): round(
                                BASE_POWERTRAIN_AND_REGION_SCENARIOS[scenario][(region, powertrain)][y] * 100, 1
                            )
                            for y in ANCHOR_YEARS
                        },
                    }
                    for region in REGION_ORDER
                ]
            )
            for scenario in SCENARIOS
        }
    tables["Total LDVs"] = {
        scenario: pd.DataFrame(
            [
                {
                    "Region": region,
                    **{str(y): round(BASE_REGION_SCENARIOS[scenario][region][y] * 100, 1) for y in ANCHOR_YEARS},
                }
                for region in REGION_ORDER
            ]
        )
        for scenario in SCENARIOS
    }
    return tables


def combo_series_data(results: ForecastResults, region: str, series_type: str) -> pd.DataFrame:
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


def render_region_filter() -> list[str]:
    """Region multiselect, shared widget key so the selection persists
    across pages. An empty selection falls back to "all"."""
    return (
        st.multiselect("Region", REGION_ORDER, default=REGION_ORDER, key="region_filter")
        or REGION_ORDER
    )


def render_powertrain_filter() -> list[str]:
    """Powertrain multiselect, shared widget key so the selection persists
    across pages. An empty selection falls back to "all"."""
    return (
        st.multiselect(
            "Powertrain", ["PHEV", "BEV", "IC Only"],
            default=["PHEV", "BEV", "IC Only"], key="powertrain_filter",
        )
        or ["PHEV", "BEV", "IC Only"]
    )


def render_filters() -> tuple[list[str], list[str]]:
    """Region + Powertrain multiselects side by side."""
    col1, col2 = st.columns(2)
    with col1:
        regions = render_region_filter()
    with col2:
        powertrains = render_powertrain_filter()
    return regions, powertrains


@dataclass
class FilteredView:
    detail_rp: pd.DataFrame       # region_and_powertrain_sales, filtered to one scenario + regions/powertrains
    rollup_pt: pd.DataFrame       # aggregate_powertrain_sales(detail_rp) - "Global" per powertrain, scoped to the filter
    detail_region: pd.DataFrame   # region_sales, filtered to one scenario + regions
    rollup_total: pd.DataFrame    # aggregate_total_sales(detail_region) - "Global" total, scoped to the filter


def compute_filtered_view(
    results: ForecastResults, scenario: str, regions: list[str], powertrains: list[str]
) -> FilteredView:
    """Filter results to one scenario + the selected regions/powertrains, and
    recompute the "Global" rollups from that filtered subset - so Global
    always means "sum of what's currently shown", not the true unfiltered
    worldwide figure. The powertrain filter only applies to the region+
    powertrain data; region_sales/total_sales are inherently powertrain-
    agnostic, so only the region filter applies to them."""
    detail_rp = results.region_and_powertrain_sales.loc[
        results.region_and_powertrain_sales["scenario"].eq(scenario)
        & results.region_and_powertrain_sales["region"].isin(regions)
        & results.region_and_powertrain_sales["powertrain"].isin(powertrains)
    ]
    detail_region = results.region_sales.loc[
        results.region_sales["scenario"].eq(scenario) & results.region_sales["region"].isin(regions)
    ]
    return FilteredView(
        detail_rp=detail_rp,
        rollup_pt=aggregate_powertrain_sales(detail_rp),
        detail_region=detail_region,
        rollup_total=aggregate_total_sales(detail_region),
    )


def build_tech_tables(
    scenario: str,
    view: FilteredView,
    region_powertrain_scenarios: dict | None = None,
    region_scenarios: dict | None = None,
    regions: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """3 tables matching the Excel scenario-config layout: PHEV, BEV, Total
    LDVs. Each has one row per region (raw anchor-year config values, as
    bare percentages) plus one or two rows pulled from the model's actual
    results (scoped to whatever `view` was filtered to), NOT a naive
    average/sum of the region rows above them:

    - PHEV/BEV tables: region rows are penetration share (% of that
      region's all-LDV sales). "Global Penetration" is the true global
      ratio (global powertrain sales / global all-LDV sales) - it does NOT
      equal any average of the region rows, since penetration is a ratio of
      sums, not a sum of ratios.
    - Total LDVs table: region rows are YoY sales growth %. "Global Growth"
      is the sales-share-weighted average of the region growth rates (this
      one IS a weighted average, unlike penetration above). "Global Sales
      (m)" is the actual global sales volume that year, in millions of
      vehicles - a different unit entirely (absolute, not a rate).

    `region_powertrain_scenarios`/`region_scenarios` default to the
    scenario_config.py constants, but can be a custom scenario dict of the
    same shape (e.g. the saved "Custom" scenario) - `scenario` must be a key
    present in both.
    """
    if region_powertrain_scenarios is None:
        region_powertrain_scenarios = BASE_POWERTRAIN_AND_REGION_SCENARIOS
    if region_scenarios is None:
        region_scenarios = BASE_REGION_SCENARIOS
    if regions is None:
        regions = REGION_ORDER

    available_powertrains = set(view.rollup_pt["powertrain"])

    tables = {}
    for powertrain in ["PHEV", "BEV"]:
        if powertrain not in available_powertrains:
            continue  # filtered out by the powertrain filter - nothing to show
        rows = [
            {
                "Region": region,
                **{
                    str(y): round(region_powertrain_scenarios[scenario][(region, powertrain)][y] * 100, 1)
                    for y in ANCHOR_YEARS
                },
            }
            for region in regions
        ]
        global_pen = view.rollup_pt.loc[
            view.rollup_pt["powertrain"].eq(powertrain) & view.rollup_pt["year"].isin(ANCHOR_YEARS)
        ]
        rows.append(
            {
                "Region": "Global Penetration",
                **{
                    str(y): round(global_pen.loc[global_pen["year"].eq(y), "penetration"].iloc[0] * 100, 1)
                    for y in ANCHOR_YEARS
                },
            }
        )
        tables[powertrain] = pd.DataFrame(rows)

    total_rows = [
        {
            "Region": region,
            **{str(y): round(region_scenarios[scenario][region][y] * 100, 1) for y in ANCHOR_YEARS},
        }
        for region in regions
    ]
    global_total = view.rollup_total.loc[view.rollup_total["year"].isin(ANCHOR_YEARS)]
    total_rows.append(
        {
            "Region": "Global Growth",
            **{
                str(y): round(global_total.loc[global_total["year"].eq(y), "yoy_pct"].iloc[0] * 100, 1)
                for y in ANCHOR_YEARS
            },
        }
    )
    total_rows.append(
        {
            "Region": "Global Sales (m)",
            **{
                str(y): round(global_total.loc[global_total["year"].eq(y), "sales"].iloc[0], 1)
                for y in ANCHOR_YEARS
            },
        }
    )
    tables["Total LDVs"] = pd.DataFrame(total_rows)

    return tables


def _append_global_rollup(detail: pd.DataFrame, rollup: pd.DataFrame) -> pd.DataFrame:
    """Stack the region-less rollup rows under a synthetic region="Global"
    so both frames share the same columns for to_wide(). `detail`/`rollup`
    are expected to already be filtered to one scenario."""
    rollup = rollup.copy()
    rollup.insert(0, "region", "Global")
    return pd.concat([detail, rollup], ignore_index=True)


def render_region_powertrain_section(view: FilteredView) -> None:
    combined = _append_global_rollup(view.detail_rp, view.rollup_pt)
    view_mode = st.segmented_control(
        "View", ["Table", "Chart"], default="Table", key="s1_view"
    )
    if view_mode != "Chart":
        st.dataframe(to_wide(combined), hide_index=True)
        return

    chart_type = st.segmented_control(
        "Chart type",
        ["By region", "Global trend", "Global split"],
        default="By region",
        key="s1_chart_type",
    )

    if chart_type == "By region":
        fig = px.line(
            view.detail_rp,
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
    else:
        plot_fn = px.line if chart_type == "Global trend" else px.bar
        fig = plot_fn(
            view.rollup_pt,
            x="year",
            y="sales",
            color="powertrain",
            category_orders={"powertrain": POWERTRAIN_ORDER},
            labels={"sales": "Sales (million vehicles)", "year": "Year"},
        )
        if chart_type == "Global split":
            fig.update_layout(barmode="stack")
        fig.update_layout(height=600)

    st.plotly_chart(fig, use_container_width=True)


def render_region_totals_section(view: FilteredView) -> None:
    combined = _append_global_rollup(view.detail_region, view.rollup_total)
    view_mode = st.segmented_control(
        "View", ["Table", "Chart"], default="Table", key="s2_view"
    )
    if view_mode != "Chart":
        st.dataframe(to_wide(combined), hide_index=True)
        return

    chart_type = st.segmented_control(
        "Chart type", ["Trend", "Split by region"], default="Trend", key="s2_chart_type"
    )

    if chart_type == "Trend":
        fig = px.line(
            combined,
            x="year",
            y="sales",
            color="region",
            category_orders={"region": [*REGION_ORDER, "Global"]},
            labels={"sales": "Sales (million vehicles)", "year": "Year"},
        )
        fig.update_traces(selector={"name": "Global"}, line=dict(dash="dash", width=4))
    else:
        fig = px.bar(
            view.detail_region,
            x="year",
            y="sales",
            color="region",
            category_orders={"region": REGION_ORDER},
            labels={"sales": "Sales (million vehicles)", "year": "Year"},
        )
        fig.update_layout(barmode="stack", height=600)

    st.plotly_chart(fig, use_container_width=True)
