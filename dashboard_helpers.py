"""Shared render helpers used by every model's dashboard and scenario editor
pages.

Everything here takes the VehicleModel it is rendering for: it supplies the
regions, the powertrains, the table names and the widget-key prefix that keeps
the LDV and HDV copies of a control apart.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.express as px
import streamlit as st

from chart_marks import mark_forecast_start

from forecast_model import (
    ANCHOR_YEARS,
    BASE_CASE,
    SCENARIOS,
    ForecastResults,
    aggregate_powertrain_sales,
    aggregate_total_sales,
    to_wide,
)
from vehicle_models import VehicleModel

# ANCHOR_YEARS, BASE_CASE and SCENARIOS are imported above purely so pages can keep
# getting the scenario vocabulary from here rather than reaching into the
# engine themselves.

# The synthetic region the filtered rollups are stacked under - "sum of what's
# currently shown", not necessarily the true worldwide figure.
GLOBAL_ROW = "Global"

# Chart type labels, on the same grammar as the Other Oil page:
# "<what varies inside a panel> <form> per <what each panel is>", where "trend"
# is lines and "split" is stacked bars. The "per ..." suffix means the chart is
# faceted, so its absence marks the single-panel charts - which is why each
# pair below has an all-cases twin.
#
# The "Global ..." charts are named for powertrain, not region, because that is
# what they actually break down: their input is the rollup across every region
# shown, which has no region column left at all.
PT_TREND_PER_REGION = "Powertrain trend per region"
GLOBAL_PT_TREND = "Global powertrain trend"
GLOBAL_PT_SPLIT = "Global powertrain split"

PT_SCENARIO_TREND_PER_REGION = "Powertrain and scenario trend per region"
GLOBAL_PT_TREND_PER_SCENARIO = "Global powertrain trend per scenario"
GLOBAL_PT_SPLIT_PER_SCENARIO = "Global powertrain split per scenario"

REGIONAL_TREND = "Regional trend"
REGIONAL_SPLIT = "Regional split"
REGIONAL_TREND_PER_SCENARIO = "Regional trend per scenario"
REGIONAL_SPLIT_PER_SCENARIO = "Regional split per scenario"

# The stacked-bar members of the above, so the chart builder can tell which
# form it is being asked for without re-deriving it from the label text.
_SPLIT_CHARTS = {GLOBAL_PT_SPLIT, GLOBAL_PT_SPLIT_PER_SCENARIO}


def build_editable_tech_tables(
    model: VehicleModel,
    region_powertrain_scenarios: dict,
    region_scenarios: dict,
) -> dict[str, dict[str, pd.DataFrame]]:
    """Anchor-year values as bare percentages, nested {tech: {case: DataFrame}} -
    one simple Region x Year table per (tech, scenario case), meant to be shown
    3-at-a-time (one per case) side by side under each tech's heading. No
    computed Global row here (unlike build_tech_tables) - these are the raw
    values, editable on the Edit Scenario Configs page and read-only on a saved
    scenario's page.

    The values passed in are also the baseline the editor diffs against, so
    they must be the stored values, never already-edited ones."""
    tables: dict[str, dict[str, pd.DataFrame]] = {}
    for powertrain in model.modelled_powertrains:
        tables[powertrain] = {
            scenario: pd.DataFrame(
                [
                    {
                        "Region": region,
                        **{
                            str(y): round(
                                region_powertrain_scenarios[scenario][(region, powertrain)][y] * 100, 1
                            )
                            for y in ANCHOR_YEARS
                        },
                    }
                    for region in model.regions
                ]
            )
            for scenario in SCENARIOS
        }
    tables[model.total_label] = {
        scenario: pd.DataFrame(
            [
                {
                    "Region": region,
                    **{str(y): round(region_scenarios[scenario][region][y] * 100, 1) for y in ANCHOR_YEARS},
                }
                for region in model.regions
            ]
        )
        for scenario in SCENARIOS
    }
    return tables


def render_region_filter(model: VehicleModel, key_suffix: str = "") -> list[str]:
    """Region multiselect. `key_suffix` scopes it to one section, so each
    section of the Forecasts page filters independently. An empty selection
    falls back to "all"."""
    return (
        st.multiselect(
            "Region", model.regions, default=model.regions,
            key=model.wkey(f"region_filter{key_suffix}"),
        )
        or model.regions
    )


def render_powertrain_filter(
    model: VehicleModel, key_suffix: str = "", options: list[str] | None = None
) -> list[str]:
    """Powertrain multiselect. `options` defaults to the modelled powertrains.
    An empty selection falls back to all of them."""
    if options is None:
        options = model.powertrains
    return (
        st.multiselect(
            "Powertrain", options, default=options,
            key=model.wkey(f"powertrain_filter{key_suffix}"),
        )
        or options
    )


def render_filters(
    model: VehicleModel, key_suffix: str = "", powertrain_options: list[str] | None = None
) -> tuple[list[str], list[str]]:
    """Region + Powertrain multiselects side by side."""
    col1, col2 = st.columns(2)
    with col1:
        regions = render_region_filter(model, key_suffix)
    with col2:
        powertrains = render_powertrain_filter(model, key_suffix, powertrain_options)
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
    agnostic, so only the region filter applies to them.

    The rollups need "scenario" present to group by (aggregate_powertrain_sales/
    aggregate_total_sales both group on it), so it's dropped only afterward,
    from all 4 stored frames - once filtered to a single scenario, keeping
    that column around would just be a redundant constant value in every
    downstream table."""
    detail_rp = results.region_and_powertrain_sales.loc[
        results.region_and_powertrain_sales["scenario"].eq(scenario)
        & results.region_and_powertrain_sales["region"].isin(regions)
        & results.region_and_powertrain_sales["powertrain"].isin(powertrains)
    ]
    detail_region = results.region_sales.loc[
        results.region_sales["scenario"].eq(scenario) & results.region_sales["region"].isin(regions)
    ]
    rollup_pt = aggregate_powertrain_sales(detail_rp)
    rollup_total = aggregate_total_sales(detail_region)
    return FilteredView(
        detail_rp=detail_rp.drop(columns="scenario"),
        rollup_pt=rollup_pt.drop(columns="scenario"),
        detail_region=detail_region.drop(columns="scenario"),
        rollup_total=rollup_total.drop(columns="scenario"),
    )


def build_tech_tables(
    model: VehicleModel,
    scenario: str,
    view: FilteredView,
    region_powertrain_scenarios: dict,
    region_scenarios: dict,
    regions: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """One table per tech, matching the Excel scenario-config layout: a
    penetration table per modelled powertrain, then the all-vehicle totals.
    Each has one row per region (raw anchor-year config values, as bare
    percentages) plus one or two rows pulled from the model's actual results
    (scoped to whatever `view` was filtered to), NOT a naive average/sum of the
    region rows above them:

    - Powertrain tables: region rows are penetration share (% of that
      region's all-vehicle sales). "Global Penetration" is the true global
      ratio (global powertrain sales / global all-vehicle sales) - it does NOT
      equal any average of the region rows, since penetration is a ratio of
      sums, not a sum of ratios.
    - Totals table: region rows are YoY sales growth %. "Global Growth"
      is the sales-share-weighted average of the region growth rates (this
      one IS a weighted average, unlike penetration above). "Global Sales
      (m)" is the actual global sales volume that year, in millions of
      vehicles - a different unit entirely (absolute, not a rate).

    `scenario` must be a case present in both scenario dicts.
    """
    if regions is None:
        regions = model.regions

    available_powertrains = set(view.rollup_pt["powertrain"])

    tables = {}
    for powertrain in model.modelled_powertrains:
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
    tables[model.total_label] = pd.DataFrame(total_rows)

    return tables


def append_global_rollup(detail: pd.DataFrame, rollup: pd.DataFrame) -> pd.DataFrame:
    """Stack the region-less rollup rows under a synthetic region="Global"
    so both frames share the same columns for to_wide(). `detail`/`rollup`
    are expected to already be filtered to one scenario."""
    rollup = rollup.copy()
    rollup.insert(0, "region", GLOBAL_ROW)
    return pd.concat([detail, rollup], ignore_index=True)


def order_sales_table(model: VehicleModel, wide: pd.DataFrame) -> pd.DataFrame:
    """Row/column order for the wide sales tables: Powertrain first (if
    present), then Region, then Scenario (if present) - all using the model's
    canonical ordering, with "Global" always sorted last within its group
    rather than wherever it'd otherwise fall."""
    wide = wide.copy()
    region_order = [*model.regions, GLOBAL_ROW]
    wide["region"] = pd.Categorical(wide["region"], categories=region_order, ordered=True)

    sort_cols: list[str] = []
    lead_cols: list[str] = []
    if "powertrain" in wide.columns:
        # Any non-forecast powertrain shown via "include ... not forecast by
        # this model" sorts after the modelled ones.
        seen = list(dict.fromkeys(wide["powertrain"].dropna()))
        pt_order = [*model.powertrains, *[p for p in seen if p not in model.powertrains]]
        wide["powertrain"] = pd.Categorical(
            wide["powertrain"], categories=pt_order, ordered=True
        )
        sort_cols.append("powertrain")
        lead_cols.append("powertrain")
    sort_cols.append("region")
    lead_cols.append("region")
    if "scenario" in wide.columns:
        wide["scenario"] = pd.Categorical(wide["scenario"], categories=SCENARIOS, ordered=True)
        sort_cols.append("scenario")
        lead_cols.append("scenario")

    wide = wide.sort_values(sort_cols)
    remaining = [c for c in wide.columns if c not in lead_cols]
    return wide[[*lead_cols, *remaining]].reset_index(drop=True)


def render_sales_table(wide: pd.DataFrame) -> None:
    """Draw a wide sales table with the year columns at 1dp. The model carries
    full float precision, which for million-vehicle figures is far more digits
    than it's meaningful to; formatting on the Styler rather than rounding the
    frame keeps the underlying values intact for sorting and download."""
    year_cols = wide.select_dtypes("number").columns
    st.dataframe(wide.style.format("{:.1f}", subset=year_cols), hide_index=True)


def by_region_chart(
    model: VehicleModel, detail_rp: pd.DataFrame, dash_col: str | None = None,
    powertrain_order: list[str] | None = None,
):
    """Facet-by-region, color-by-powertrain line chart. `dash_col` (e.g.
    "scenario") adds a 3rd dimension via line dash pattern - used only by
    the all-scenarios PT_SCENARIO_TREND_PER_REGION view."""
    category_orders = {
        "region": model.regions,
        "powertrain": powertrain_order or model.powertrains,
    }
    if dash_col:
        category_orders[dash_col] = SCENARIOS
    fig = px.line(
        detail_rp,
        x="year",
        y="sales",
        color="powertrain",
        line_dash=dash_col,
        facet_col="region",
        facet_col_wrap=2,
        category_orders=category_orders,
        labels={"sales": "Sales (million vehicles)", "year": "Year"},
    )
    fig.update_yaxes(matches=None, showticklabels=True)
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    return mark_forecast_start(fig)


def chart_type_control(options: list[str], key: str) -> str:
    """The chart-type picker, defaulting to the first of `options`.

    Each section's single-case and all-cases views share one key but offer
    different chart types, so toggling "Show all scenario cases" leaves the
    stored selection outside the new options. A keyed segmented_control keeps
    its identity when its options change, so it would render with nothing
    highlighted. Writing the default through session_state is what resets it
    in the browser, and since that happens before every render the widget
    takes no `default=` - it would be ignored, and Streamlit warns about it.
    """
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]
    return st.segmented_control("Chart type", options, key=key)


def global_powertrain_chart(
    model: VehicleModel, rollup_pt: pd.DataFrame, chart_type: str,
    powertrain_order: list[str] | None = None,
    facet_col: str | None = None,
):
    """Global powertrain trend/split - the rollup across every region shown.

    `chart_type` is one of the GLOBAL_PT_* labels; only its form (line vs
    stacked bar) is read here.

    `facet_col` ("scenario") puts the three cases side by side as panels of one
    figure rather than as three separate figures. That draws the powertrain
    legend once for the whole figure instead of repeating it per case, and
    shares one y-axis across the panels, so the cases are comparable by eye -
    three independent figures each autoscale, which flattens the difference
    between a high case and a low one.
    """
    plot_fn = px.bar if chart_type in _SPLIT_CHARTS else px.line
    fig = plot_fn(
        rollup_pt,
        x="year",
        y="sales",
        color="powertrain",
        facet_col=facet_col,
        category_orders={
            "powertrain": powertrain_order or model.powertrains,
            "scenario": SCENARIOS,
        },
        labels={"sales": "Sales (million vehicles)", "year": "Year"},
    )
    if chart_type in _SPLIT_CHARTS:
        fig.update_layout(barmode="stack")
    if facet_col:
        # px titles facets "scenario=Base Case"; only the value is wanted.
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    return mark_forecast_start(fig, bars=chart_type in _SPLIT_CHARTS)


def region_trend_chart(model: VehicleModel, combined: pd.DataFrame):
    """Region totals line chart (REGIONAL_TREND), region + Global rollup."""
    fig = px.line(
        combined,
        x="year",
        y="sales",
        color="region",
        category_orders={"region": [*model.regions, GLOBAL_ROW]},
        labels={"sales": "Sales (million vehicles)", "year": "Year"},
    )
    fig.update_traces(selector={"name": GLOBAL_ROW}, line=dict(dash="dash", width=4))
    return mark_forecast_start(fig)


def region_split_chart(model: VehicleModel, detail_region: pd.DataFrame):
    """Region totals stacked bar chart (REGIONAL_SPLIT), for one scenario."""
    fig = px.bar(
        detail_region,
        x="year",
        y="sales",
        color="region",
        category_orders={"region": model.regions},
        labels={"sales": "Sales (million vehicles)", "year": "Year"},
    )
    fig.update_layout(barmode="stack")
    return mark_forecast_start(fig, bars=True)


OTHER_POWERTRAIN_NOTE = (
    "{names} are not forecast by this model. Those figures come straight from "
    "the source data's own published projections, unchanged, and stop when the "
    "source data does."
)


def render_other_powertrain_toggle(model: VehicleModel, key_suffix: str = "") -> bool:
    """The opt-in for powertrains this model doesn't forecast. Off by default -
    supplementary context rather than part of the forecast."""
    if not model.other_powertrains:
        return False
    names = " and ".join(model.other_powertrain_labels)
    shown = st.checkbox(
        f"Include {names} (not forecast by this model)",
        value=False,
        key=model.wkey(f"show_other_powertrains{key_suffix}"),
    )
    if shown:
        st.caption(OTHER_POWERTRAIN_NOTE.format(names=names))
    return shown


def region_totals_from_powertrains(detail_rp: pd.DataFrame) -> pd.DataFrame:
    """All-vehicle sales per region, summed over whichever powertrains are
    selected. With every powertrain selected this reproduces region_sales
    exactly, since the powertrains reconcile to it."""
    out = (
        detail_rp.groupby(["region", "year", "data_type"])["sales"]
        .sum()
        .reset_index()
        .sort_values(["region", "year"], ignore_index=True)
    )
    out["yoy_pct"] = out.groupby("region")["sales"].pct_change(fill_method=None)
    return out


def render_region_powertrain_section(
    model: VehicleModel,
    results: ForecastResults,
    scenario: str,
    regions: list[str],
    powertrains: list[str],
) -> None:
    """Sales split by region and powertrain. Owns its own view controls and the
    opt-in for the non-forecast powertrains, so the filters above it only ever
    decide what is displayed."""
    view_mode = st.segmented_control(
        "View", ["Chart", "Table"], default="Chart", key=model.wkey("s1_view")
    )
    chart_type = None
    if view_mode != "Table":
        chart_type = chart_type_control(
            [PT_TREND_PER_REGION, GLOBAL_PT_TREND, GLOBAL_PT_SPLIT],
            key=model.wkey("s1_chart_type"),
        )

    # Below the view and chart-type controls, per the page layout.
    show_other = render_other_powertrain_toggle(model)

    shown = list(powertrains)
    if show_other:
        shown += [p for p in model.other_powertrain_labels if p not in shown]
    view = compute_filtered_view(results, scenario, regions, shown)

    if view_mode == "Table":
        combined = append_global_rollup(view.detail_rp, view.rollup_pt)
        render_sales_table(order_sales_table(model, to_wide(combined)))
        return

    if chart_type == PT_TREND_PER_REGION:
        fig = by_region_chart(model, view.detail_rp, powertrain_order=shown)
    else:
        fig = global_powertrain_chart(model, view.rollup_pt, chart_type, powertrain_order=shown)
        fig.update_layout(height=600)

    st.plotly_chart(fig, use_container_width=True, key=model.wkey("s1_chart"))


def render_region_totals_section(
    model: VehicleModel,
    results: ForecastResults,
    scenario: str,
    regions: list[str],
    powertrains: list[str],
) -> None:
    """All-vehicle sales by region. The powertrain filter decides which
    powertrains make up the total; with every one selected - the default - it
    is the true all-vehicle figure."""
    view = compute_filtered_view(results, scenario, regions, powertrains)
    detail_region = region_totals_from_powertrains(view.detail_rp)
    rollup_total = aggregate_total_sales(detail_region.assign(scenario=scenario)).drop(
        columns="scenario"
    )
    combined = append_global_rollup(detail_region, rollup_total)

    view_mode = st.segmented_control(
        "View", ["Chart", "Table"], default="Chart", key=model.wkey("s2_view")
    )
    if view_mode == "Table":
        render_sales_table(order_sales_table(model, to_wide(combined)))
        return

    chart_type = chart_type_control(
        [REGIONAL_TREND, REGIONAL_SPLIT], key=model.wkey("s2_chart_type")
    )

    if chart_type == REGIONAL_TREND:
        fig = region_trend_chart(model, combined)
    else:
        fig = region_split_chart(model, detail_region)
    fig.update_layout(height=600)

    st.plotly_chart(fig, use_container_width=True, key=model.wkey("s2_chart"))


# ---------------------------------------------------------------------------
# Per-tech scenario sales outputs (Edit Scenario Configs page)
# ---------------------------------------------------------------------------


def scenario_output_data(model: VehicleModel, results: ForecastResults, tech: str) -> pd.DataFrame:
    """One tech's sales across every region and scenario case.

    tech=<the model's total label> is the all-vehicle regional total;
    otherwise it's that powertrain's own sales. The powertrain column is
    dropped - the caller already knows which tech this is, so repeating it in
    every row would just be a constant column.

    Returns: region | scenario | year | sales | data_type (+ metric columns)
    """
    if tech == model.total_label:
        return results.region_sales
    detail = results.region_and_powertrain_sales
    return detail.loc[detail["powertrain"].eq(tech)].drop(columns="powertrain")


# A scenario case keeps one colour whether it's the saved line or the edited
# overlay, so the pair reads as one series in two states.
CASE_COLOURS = dict(zip(SCENARIOS, px.colors.qualitative.Plotly))

UPDATED_SUFFIX = " - Updated"


def scenario_overlay_chart(
    model: VehicleModel, original: pd.DataFrame, updated: pd.DataFrame | None, split_by: str
):
    """Saved values as solid lines, with any edited series overlaid dashed.

    split_by="Region" gives one panel per region coloured by scenario case;
    split_by="Scenario case" flips it - one panel per case coloured by region.
    Either way the edited overlay takes the same colour as the line it
    replaces and is named "<series> - Updated", so the legend pairs them.
    """
    region_colours = dict(zip(model.regions, px.colors.qualitative.Plotly))
    if split_by == "Scenario case":
        facet, colour_col = "scenario", "region"
        facet_order, colour_order, palette = SCENARIOS, model.regions, region_colours
    else:
        facet, colour_col = "region", "scenario"
        facet_order, colour_order, palette = model.regions, SCENARIOS, CASE_COLOURS

    frames = [original.assign(series=original[colour_col])]
    if updated is not None and not updated.empty:
        frames.append(updated.assign(series=updated[colour_col] + UPDATED_SUFFIX))
    data = pd.concat(frames, ignore_index=True)

    colour_map = {
        **palette,
        **{f"{name}{UPDATED_SUFFIX}": colour for name, colour in palette.items()},
    }
    series_order = [*colour_order, *[f"{n}{UPDATED_SUFFIX}" for n in colour_order]]

    fig = px.line(
        data,
        x="year",
        y="sales",
        color="series",
        facet_col=facet,
        facet_col_wrap=2,
        color_discrete_map=colour_map,
        category_orders={facet: facet_order, "series": series_order},
        labels={"sales": "Sales (million vehicles)", "year": "Year", "series": ""},
    )
    fig.for_each_trace(
        lambda t: t.update(line=dict(dash="dash")) if t.name.endswith(UPDATED_SUFFIX) else None
    )
    fig.update_yaxes(matches=None, showticklabels=True)
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    return mark_forecast_start(fig)
