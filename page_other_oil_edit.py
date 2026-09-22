"""Edit Scenario Configs for Other Oil Consumption: pick a saved scenario, edit
the anchor-year values for all three scenario cases side by side, and watch
each sector's forecast move.

Edits are live - every change re-runs the model and redraws the charts, where
each edited case appears as a dashed "<case> - Updated" line alongside the
saved one it replaces. A run is trivial here (four sectors over 26 years), so
there is nothing worth gating behind a button.

Nothing reaches the rest of the app until you explicitly save, as either a new
scenario or an update to the selected one.

The editors are always handed the *stored* values of the selected scenario,
never already-edited ones: st.data_editor keeps its edits in widget state and
replays them onto whatever frame it's given, so re-feeding edited values would
apply them twice. That also makes the stored values the natural baseline for
"has anything changed?", which is what gates the save and revert buttons.

Unlike the LDV and HDV editor this page takes no model argument: there is one
Other Oil model, so its widget keys need no prefix beyond this page's own.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from data_loader import get_other_oil_csv_path
from forecast_model import ANCHOR_YEARS, SCENARIOS
from other_oil_forecast_model import OtherOilResults, to_wide
from other_oil_scenario_config import (
    LEVER_COLUMN,
    SECTOR_ORDER,
    apply_config_table,
    config_table,
)
from other_oil_scenario_store import (
    OtherOilScenario,
    add_scenario,
    get_main_scenario_name,
    get_scenario,
    name_is_available,
    run_scenario,
    scenario_names,
    set_main_scenario,
    update_scenario,
)
from page_other_oil import METRIC_LABELS, OIL

TITLE = "Edit Scenario Configs"
WKEY = "other_oil_edit"

PAGE_DESCRIPTION = (
    "Edit the anchor-year values for each scenario case of the selected "
    "scenario below. Expand a sector's forecast to see how the edited values "
    "change it. Nothing is kept until you save the edits - either as a new "
    "scenario, or as an update to the one you're editing."
)

# Explicit pixel widths - six columns in a third of the page don't fit unless
# they're told to. The lever names are long ("Low-emission Fuel
# (Penetration)"), so they get the room the year columns don't need.
_LEVER_WIDTH = 160
_YEAR_WIDTH = 52

# A scenario case keeps one colour whether it's the saved line or the edited
# overlay, so the pair reads as one series in two states.
CASE_COLOURS = dict(zip(SCENARIOS, px.colors.qualitative.Plotly))
UPDATED_SUFFIX = " - Updated"


# ---------------------------------------------------------------------------
# Widget state
# ---------------------------------------------------------------------------

def _slug(name: str) -> str:
    """Sector names carry a slash (Buildings/Power/Other) and spaces, so they
    are squashed before going into a widget key."""
    return name.replace("/", "-").replace(" ", "-").lower()


def _editor_key(sector: str, case: str) -> str:
    return f"{WKEY}_{_slug(sector)}_{case.split()[0].lower()}_table"


def _selected_key() -> str:
    return f"{WKEY}_selected_scenario"


def _picker_key() -> str:
    return f"{WKEY}_scenario_picker"


def _set_selected(name: str) -> None:
    """Move the picker to `name` from code.

    Both keys have to move. The tracking key is what render() reads, but the
    selectbox has its own widget key, and a widget's stored value wins over the
    `index` argument - so setting the tracking key alone leaves the picker
    sitting on the previous scenario after a save.
    """
    st.session_state[_selected_key()] = name
    st.session_state.pop(_picker_key(), None)


def _clear_editor_state() -> None:
    """Drop every editor's stored edits. Needed whenever the baseline moves
    underneath them - switching scenario, saving, or reverting - otherwise the
    old edits get replayed onto the new values."""
    for sector in SECTOR_ORDER:
        for case in SCENARIOS:
            st.session_state.pop(_editor_key(sector, case), None)


def _column_config() -> dict:
    return {
        LEVER_COLUMN: st.column_config.TextColumn(LEVER_COLUMN, width=_LEVER_WIDTH),
        **{
            str(year): st.column_config.NumberColumn(
                str(year), width=_YEAR_WIDTH, format="%.1f"
            )
            for year in ANCHOR_YEARS
        },
    }


# ---------------------------------------------------------------------------
# Tables <-> scenario values
# ---------------------------------------------------------------------------

def _edited_scenarios(
    stored: dict, tables: dict[str, dict[str, pd.DataFrame]]
) -> tuple[dict, list[str]]:
    """The stored scenario with every edited table folded in.

    A sector whose table can't be read - a cleared cell, most likely - keeps
    its stored values and is named in the returned problem list, so one blank
    cell costs that sector its edits rather than breaking the page while the
    user is still typing.
    """
    edited: dict = {}
    problems: list[str] = []
    for case, sectors in stored.items():
        edited[case] = {}
        for sector, sector_config in sectors.items():
            try:
                edited[case][sector] = apply_config_table(
                    sector_config, sector, tables[sector][case]
                )
            except ValueError as exc:
                edited[case][sector] = sector_config
                problems.append(str(exc))
    return edited, problems


def _changed_cases(
    pristine: dict[str, dict[str, pd.DataFrame]],
    edited: dict[str, dict[str, pd.DataFrame]],
) -> dict[str, list[str]]:
    """{sector: [case, ...]} for every sector with at least one edited case -
    exactly the set of series needing a dashed "Updated" overlay. Both tables
    come from config_table, which rounds, so this is an exact comparison rather
    than float-fuzzy."""
    year_cols = [str(y) for y in ANCHOR_YEARS]
    changed: dict[str, list[str]] = {}
    for sector in SECTOR_ORDER:
        cases = [
            case
            for case in SCENARIOS
            if not pristine[sector][case][year_cols].equals(edited[sector][case][year_cols])
        ]
        if cases:
            changed[sector] = cases
    return changed


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_scenario_picker() -> str:
    """Which saved scenario to edit. Defaults to whichever is currently the
    main scenario, and is locked when the default is the only one."""
    selected_key = _selected_key()
    names = scenario_names()
    st.session_state.setdefault(selected_key, get_main_scenario_name())
    if st.session_state[selected_key] not in names:
        _set_selected(names[0])

    previous = st.session_state[selected_key]
    selected = st.selectbox(
        "Scenario",
        names,
        index=names.index(previous),
        disabled=len(names) == 1,
        key=_picker_key(),
        help=(
            "Only the default scenario exists so far - save one to enable this."
            if len(names) == 1
            else "Which saved scenario to edit."
        ),
    )
    if selected != previous:
        # The baseline just moved; stale edits would be replayed onto it.
        st.session_state[selected_key] = selected
        _clear_editor_state()
        st.rerun()
    return selected


def _sector_series(results: OtherOilResults, sector: str) -> pd.DataFrame:
    data = results.consumption
    return data.loc[data["sector"].eq(sector)].drop(columns=["sector", "metric"])


def _overlay_chart(saved: pd.DataFrame, updated: pd.DataFrame | None):
    """Saved values as solid lines, with any edited case overlaid dashed and
    named "<case> - Updated", so the legend pairs them by colour."""
    frames = [saved.assign(series=saved["scenario"])]
    if updated is not None and not updated.empty:
        frames.append(updated.assign(series=updated["scenario"] + UPDATED_SUFFIX))
    data = pd.concat(frames, ignore_index=True)

    colours = {
        **CASE_COLOURS,
        **{f"{case}{UPDATED_SUFFIX}": colour for case, colour in CASE_COLOURS.items()},
    }
    order = [
        *SCENARIOS,
        *[f"{case}{UPDATED_SUFFIX}" for case in SCENARIOS],
    ]

    fig = px.line(
        data,
        x="year",
        y="value",
        color="series",
        color_discrete_map=colours,
        category_orders={"series": order},
        labels={"value": METRIC_LABELS[OIL], "year": "Year"},
    )
    fig.for_each_trace(
        lambda t: t.update(line=dict(dash="dash"))
        if t.name.endswith(UPDATED_SUFFIX)
        else None
    )
    return fig


def _render_sector_charts(
    sector: str,
    saved_results: OtherOilResults,
    edited_results: OtherOilResults,
    changed: dict[str, list[str]],
) -> None:
    """One sector's forecast under its own tables - a line per scenario case.

    Faceting would be pointless here: the section is already one sector, so the
    cases are the only thing left to tell apart, and they read better overlaid
    on shared axes than split across three panels.
    """
    with st.expander(f"View {sector} forecast", expanded=False):
        view = st.segmented_control(
            "View", ["Chart", "Table"], default="Chart",
            key=f"{WKEY}_{_slug(sector)}_view",
        )
        saved = _sector_series(saved_results, sector)

        # Only the cases actually edited get an overlay; an untouched case
        # would just draw a dashed line on top of its own solid one.
        cases = changed.get(sector, [])
        updated = None
        if cases:
            edited = _sector_series(edited_results, sector)
            updated = edited.loc[edited["scenario"].isin(cases)]

        if view == "Table":
            frames = [saved.assign(series=saved["scenario"])]
            if updated is not None and not updated.empty:
                frames.append(updated.assign(series=updated["scenario"] + UPDATED_SUFFIX))
            wide = to_wide(
                pd.concat(frames, ignore_index=True).drop(columns="scenario")
            )
            year_cols = wide.select_dtypes("number").columns
            st.dataframe(
                wide.style.format("{:.2f}", subset=year_cols),
                hide_index=True,
                width="stretch",
            )
            return

        fig = _overlay_chart(saved, updated)
        fig.update_layout(height=450)
        st.plotly_chart(fig, width="stretch", key=f"{WKEY}_{_slug(sector)}_chart")


def _render_save_dialog(scenarios: dict) -> None:
    """Name-and-save prompt for "Save new scenario to dashboard". Kept in a
    form so the name isn't submitted on every keystroke."""
    with st.form(f"{WKEY}_save_form", clear_on_submit=False):
        name = st.text_input("Scenario name", placeholder="e.g. Faster shipping shift")
        submitted = st.form_submit_button("Save scenario")

    if not submitted:
        return
    if not name_is_available(name):
        st.error(
            "Enter a name that isn't already in use."
            if name.strip()
            else "Enter a name for the scenario."
        )
        return

    scenario = add_scenario(name, scenarios)
    set_main_scenario(scenario.name)
    _set_selected(scenario.name)
    st.session_state[f"{WKEY}_show_save_dialog"] = False
    _clear_editor_state()
    st.success(f"Saved {scenario.name!r} and applied it across the Other Oil model.")
    st.rerun()


def render() -> None:
    st.title(TITLE)
    st.write(PAGE_DESCRIPTION)

    csv_path = get_other_oil_csv_path()

    selected_name = _render_scenario_picker()
    scenario = get_scenario(selected_name)

    # Always the stored values - see the module docstring for why.
    pristine: dict[str, dict[str, pd.DataFrame]] = {
        sector: {
            case: config_table(scenario.scenarios[case][sector], sector)
            for case in SCENARIOS
        }
        for sector in SECTOR_ORDER
    }

    # Each sector's charts belong directly under its own tables, but they can't
    # be drawn yet: the edited model run needs every editor to have returned
    # first. So each section reserves a container now and fills it below, once
    # the results exist.
    tables: dict[str, dict[str, pd.DataFrame]] = {}
    chart_slots: dict[str, "st.delta_generator.DeltaGenerator"] = {}

    for sector in SECTOR_ORDER:
        st.subheader(sector)
        tables[sector] = {}
        for case, col in zip(SCENARIOS, st.columns(3)):
            with col:
                st.caption(case)
                tables[sector][case] = st.data_editor(
                    pristine[sector][case],
                    hide_index=True,
                    disabled=[LEVER_COLUMN],
                    num_rows="fixed",
                    column_config=_column_config(),
                    key=_editor_key(sector, case),
                )
        chart_slots[sector] = st.container()

    edited_scenarios, problems = _edited_scenarios(scenario.scenarios, tables)
    for problem in problems:
        st.warning(f"{problem} Showing the unedited values for that sector.")

    changed = _changed_cases(pristine, tables)
    has_changes = bool(changed)

    saved_results = run_scenario(csv_path, scenario)
    edited_results = (
        run_scenario(csv_path, OtherOilScenario("(edited)", edited_scenarios))
        if has_changes
        else saved_results
    )

    for sector in SECTOR_ORDER:
        with chart_slots[sector]:
            _render_sector_charts(sector, saved_results, edited_results, changed)

    st.divider()
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
            "Save new scenario to dashboard",
            width="stretch",
            disabled=not has_changes,
            key=f"{WKEY}_save_new",
            help="Save these edits as a new named scenario and apply it across the Other Oil model.",
        ):
            st.session_state[f"{WKEY}_show_save_dialog"] = True

    with col2:
        if st.button(
            "Save updates to scenario",
            width="stretch",
            disabled=not has_changes or scenario.is_default,
            key=f"{WKEY}_save_updates",
            help=(
                "The default scenario is a read-only baseline - use "
                '"Save new scenario to dashboard" to save a copy.'
                if scenario.is_default
                else "Overwrite this scenario with the edits above."
            ),
        ):
            update_scenario(selected_name, edited_scenarios)
            _clear_editor_state()
            st.success(f"Updated {selected_name!r}.")
            st.rerun()

    with col3:
        if st.button(
            "Revert unsaved changes",
            width="stretch",
            disabled=not has_changes,
            key=f"{WKEY}_revert",
            help="Discard every edit and go back to this scenario's saved values.",
        ):
            _clear_editor_state()
            st.rerun()

    if st.session_state.get(f"{WKEY}_show_save_dialog"):
        _render_save_dialog(edited_scenarios)
