"""Other Oil Consumption forecasts page.

The non-road sectors - Petrochemicals, Shipping, Aviation and
Buildings/Power/Other. Reflects whichever saved scenario is currently the main
one, as chosen here or from a saved scenario's own page.

Two metrics are shown. Oil consumption covers all four sectors; activity covers
only Shipping and Aviation, which are the two modelled through a physical base.
Intensity is computed by the model but deliberately not surfaced here.

Total liquids never appears, as input or as forecast. It is used once, inside
the model, to seed the 2024 intensity - see other_oil_forecast_model.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from forecast_model import ANCHOR_YEARS, BASE_CASE, SCENARIOS
from other_oil_forecast_model import OtherOilResults, to_wide
from other_oil_model_cache import get_other_oil_results, get_other_oil_scenarios
from other_oil_scenario_store import (
    get_main_scenario_name,
    scenario_names,
    set_main_scenario,
)
from other_oil_scenario_config import (
    ACTIVITY_SECTORS,
    LEVER_COLUMN,
    SECTOR_ORDER,
    config_table,
)

TITLE = "Other Oil Consumption Forecast"

# The two metrics the page shows, with the axis label each is quoted in.
# Activity's unit differs by sector - tonne-km for shipping, passenger-km for
# aviation - so the label names both rather than picking one sector's unit.
OIL = "Oil consumption"
ACTIVITY = "Activity"
METRIC_LABELS = {
    OIL: "Oil consumption (mb/d)",
    ACTIVITY: "Activity (bn tonne-km / bn passenger-km)",
}

# The chart types, named "<what varies inside a panel> <form> per <what each
# panel is>". "trend" is lines, "split" is stacked bars, and the "per ..."
# suffix means the chart is faceted - so its absence marks the single-panel
# charts, which are the only ones offered while a single case is on screen.
SECTOR_TREND = "Sector trend"                              # lines, one panel
SECTOR_SPLIT = "Sector split"                              # bars, one panel
SCENARIO_TREND_PER_SECTOR = "Scenario trend per sector"    # lines, panel per sector
SECTOR_TREND_PER_SCENARIO = "Sector trend per scenario"    # lines, panel per scenario
SECTOR_SPLIT_PER_SCENARIO = "Sector split per scenario"    # bars,  panel per scenario

WKEY = "other_oil"

# Fixed column geometry for the scenario-config tables. Without it each table
# is sized to its own contents, so a one-lever sector like Petrochemicals comes
# out visibly narrower than Shipping and the year columns stop lining up down
# the page. Semantic widths rather than pixels, so the three case columns still
# scale with the window.
_CONFIG_COLUMNS = {
    LEVER_COLUMN: st.column_config.TextColumn(LEVER_COLUMN, width="medium"),
    **{
        str(year): st.column_config.NumberColumn(str(year), width="small", format="%.1f")
        for year in ANCHOR_YEARS
    },
}


def _frame(results: OtherOilResults, metric: str):
    return results.consumption if metric == OIL else results.activity


def _sector_filter(metric: str) -> list[str]:
    """Which sectors to show. Activity only exists for the two sectors modelled
    through a physical base, so the options narrow with the metric rather than
    offering sectors that would come back empty."""
    options = SECTOR_ORDER if metric == OIL else ACTIVITY_SECTORS
    selected = st.multiselect(
        "Sector", options, default=options, key=f"{WKEY}_sectors_{metric}"
    )
    return [s for s in options if s in selected]


def _trend_chart(data, metric: str, facet_col: str | None = None):
    """Colour by sector, one line per sector.

    `facet_col` ("scenario") gives each case its own panel - how the all-cases
    view is drawn. Faceting draws the sector legend once for the whole figure
    and shares one y-axis across the panels, so the cases stay comparable by
    eye.
    """
    fig = px.line(
        data,
        x="year",
        y="value",
        color="sector",
        facet_col=facet_col,
        category_orders={"sector": SECTOR_ORDER, "scenario": SCENARIOS},
        labels={"value": METRIC_LABELS[metric], "year": "Year"},
    )
    if facet_col:
        # px titles facets "scenario=Base Case"; only the value is wanted.
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    return fig


def _trend_by_sector_chart(data, metric: str):
    """One panel per sector, wrapped two to a row, coloured by scenario case.

    Whether the panels share a y-axis follows the same rule as the stacked
    split: share one only where the sectors share a unit.

      oil      - all four sectors are mb/d and within about 4x of each other,
                 so a shared axis holds and is worth having. It keeps "which
                 sector is biggest" readable, which is most of the point of
                 splitting oil demand out by sector.
      activity - Shipping runs ~112,000 bn tonne-km against Aviation's ~9,600
                 bn passenger-km. Different units as well as different
                 magnitudes, so the panels get their own axes; a shared one
                 would flatten aviation onto the baseline and imply a
                 comparison that isn't there.

    Colour carries the scenario rather than the sector: with one sector per
    panel, colouring by sector would repeat the panel title and leave the cases
    indistinguishable.
    """
    # Only the sectors actually present, in SECTOR_ORDER. The sector column is
    # a Categorical carrying all four, and a facet order naming a sector with
    # no rows still draws its title - so the unfiltered activity frame would
    # get four headings above two panels.
    sectors = [s for s in SECTOR_ORDER if s in set(data["sector"])]

    fig = px.line(
        data,
        x="year",
        y="value",
        color="scenario",
        facet_col="sector",
        facet_col_wrap=2,
        category_orders={"sector": sectors, "scenario": SCENARIOS},
        labels={"value": METRIC_LABELS[metric], "year": "Year"},
    )
    if metric != OIL:
        fig.update_yaxes(matches=None, showticklabels=True)
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    return fig


def _split_chart(data, metric: str, facet_col: str | None = None):
    """Stacked bar, one band per sector - oil only.

    Every oil sector is mb/d, so the bar height is genuine combined demand.
    Activity has no equivalent: its two sectors are bn tonne-km and bn
    passenger-km, and a stack of those sums two different units into a height
    that means nothing, so the activity section doesn't offer this chart.

    `facet_col` ("scenario") puts the three cases side by side as panels of one
    figure rather than as three separate figures. That earns two things: the
    sector legend is drawn once for the whole figure instead of repeating per
    case, and the panels share a y-axis, so the cases are actually comparable
    by eye - three independent figures each autoscale, which makes a 28 mb/d
    case and a 73 mb/d case look the same height.
    """
    fig = px.bar(
        data,
        x="year",
        y="value",
        color="sector",
        facet_col=facet_col,
        category_orders={"sector": SECTOR_ORDER, "scenario": SCENARIOS},
        labels={"value": METRIC_LABELS[metric], "year": "Year"},
    )
    fig.update_layout(barmode="stack")
    if facet_col:
        # px titles facets "scenario=Base Case"; only the value is wanted.
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    return fig


def _chart_type_control(metric: str, show_all: bool) -> str:
    """The chart-type picker, whose options depend on what's on screen.

    With one case on screen there is nothing to facet by, so only the
    single-panel charts are offered and SECTOR_TREND is the default. With all
    cases shown they are replaced by their faceted counterparts - three cases
    on one set of axes is what the facets exist to avoid - and
    SCENARIO_TREND_PER_SECTOR leads.

    The stacked split is oil-only throughout. Stacking activity would sum bn
    tonne-km onto bn passenger-km, so the bar height would mean nothing.
    """
    if show_all:
        chart_types = [SCENARIO_TREND_PER_SECTOR, SECTOR_TREND_PER_SCENARIO]
        split = SECTOR_SPLIT_PER_SCENARIO
    else:
        chart_types = [SECTOR_TREND]
        split = SECTOR_SPLIT
    if metric == OIL:
        chart_types.append(split)

    # Toggling "Show all scenario cases" changes which chart types exist, so
    # the stored selection can stop being an option. Assigning the default
    # rather than clearing the key matters: with the key merely absent,
    # Streamlit sends the new default but leaves set_value False, so a widget
    # already mounted in the browser keeps its stale selection and renders with
    # nothing highlighted. Writing the value through session_state is what
    # actually pushes it to the frontend. That seeding runs before every
    # render, so the widget takes no `default=`: it would always be ignored,
    # and Streamlit warns when a keyed widget gets both.
    key = f"{WKEY}_chart_{metric}"
    if st.session_state.get(key) not in chart_types:
        st.session_state[key] = chart_types[0]

    return st.segmented_control("Chart type", chart_types, key=key)


def _render_table(data) -> None:
    """Years as columns. Oil is quoted to 2dp; activity runs to five figures,
    so it gets none. Formatting on the Styler rather than rounding the frame
    keeps the underlying values intact for sorting and download."""
    wide = to_wide(data.drop(columns="metric"))
    year_cols = wide.select_dtypes("number").columns
    decimals = "{:.2f}" if data["metric"].iloc[0] == "oil" else "{:,.0f}"
    st.dataframe(wide.style.format(decimals, subset=year_cols), hide_index=True)


def _render_section(results: OtherOilResults, metric: str, show_all: bool, scenario: str) -> None:
    sectors = _sector_filter(metric)
    if not sectors:
        st.info("Select at least one sector.")
        return

    data = _frame(results, metric)
    data = data.loc[data["sector"].isin(sectors)]

    view = st.segmented_control(
        "View", ["Chart", "Table"], default="Chart", key=f"{WKEY}_view_{metric}"
    )

    if view == "Table":
        _render_table(data if show_all else data.loc[data["scenario"].eq(scenario)])
        return

    chart_type = _chart_type_control(metric, show_all)

    shown = data if show_all else data.loc[data["scenario"].eq(scenario)]

    # Faceting by case is what makes the all-cases views legible: three cases
    # can't share one set of axes without twelve lines landing in one frame.
    # Faceting by sector is a property of the chart type instead, so it applies
    # whether one case is shown or all three.
    # Only the "per scenario" variants are offered while all cases are shown, so
    # show_all is what decides whether the scenario dimension becomes facets.
    facet = "scenario" if show_all else None
    if chart_type == SCENARIO_TREND_PER_SECTOR:
        fig = _trend_by_sector_chart(shown, metric)
    elif chart_type in (SECTOR_SPLIT, SECTOR_SPLIT_PER_SCENARIO):
        fig = _split_chart(shown, metric, facet_col=facet)
    else:
        fig = _trend_chart(shown, metric, facet_col=facet)

    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True, key=f"{WKEY}_fig_{metric}")


def _render_case_config(case_config: dict) -> None:
    """One case's levers - a table per sector, in schema order."""
    for sector in SECTOR_ORDER:
        st.caption(sector)
        st.dataframe(
            config_table(case_config[sector], sector),
            column_config=_CONFIG_COLUMNS,
            hide_index=True,
            width="stretch",
        )


def _render_scenario_config(show_all: bool, scenario: str) -> None:
    """Follows the scenario picker, as the LDV and HDV panels do: the chosen
    case alone at full width, or all three side by side once "Show all scenario
    cases" is ticked.

    It ignores the per-section sector filters, though - a scenario's anchor
    values are a property of the scenario rather than of whichever sectors the
    viewer currently has on screen.
    """
    scenarios = get_other_oil_scenarios()
    if not show_all:
        _render_case_config(scenarios[scenario])
        return

    for case, col in zip(SCENARIOS, st.columns(3)):
        with col:
            st.markdown(f"**{case}**")
            _render_case_config(scenarios[case])


def _render_main_scenario_picker() -> None:
    """Which saved scenario drives the Other Oil pages. Choosing one here
    applies it across all of them, so it writes straight through to the store.
    Locked while the default scenario is the only one saved."""
    names = scenario_names()
    current = get_main_scenario_name()
    selected = st.selectbox(
        "Scenario",
        names,
        index=names.index(current),
        disabled=len(names) == 1,
        key=f"{WKEY}_main_scenario_picker",
        help=(
            "Only the default scenario exists so far - save one from Edit "
            "Scenario Configs to enable this."
            if len(names) == 1
            else "Applied across every Other Oil page."
        ),
    )
    if selected != current:
        set_main_scenario(selected)
        st.rerun()


def render() -> None:
    results = get_other_oil_results()

    st.title(TITLE)

    _render_main_scenario_picker()

    # Mirrors the Forecasts page: Streamlit forgets a keyed widget's value once
    # it's skipped for a run, so the last real choice is tracked explicitly
    # rather than relying on the hidden selectbox's key to survive.
    last_key, show_all_key = f"{WKEY}_last_case", f"{WKEY}_show_all"
    last_case = st.session_state.get(last_key, BASE_CASE)

    if st.session_state.get(show_all_key, False):
        st.selectbox("Scenario case", ["All"], disabled=True, key=f"{WKEY}_case_all")
        scenario = last_case
    else:
        scenario = st.selectbox(
            "Scenario case", SCENARIOS, index=SCENARIOS.index(last_case), key=f"{WKEY}_case"
        )
        st.session_state[last_key] = scenario

    show_all = st.checkbox("Show all scenario cases", key=show_all_key)

    with st.expander("Scenario configuration"):
        _render_scenario_config(show_all, scenario)

    st.divider()
    st.subheader(METRIC_LABELS[OIL])
    _render_section(results, OIL, show_all, scenario)

    st.divider()
    st.subheader(METRIC_LABELS[ACTIVITY])
    st.caption(
        f"{' and '.join(ACTIVITY_SECTORS)} only - the other sectors are forecast "
        "directly on their oil, with no activity base."
    )
    _render_section(results, ACTIVITY, show_all, scenario)
