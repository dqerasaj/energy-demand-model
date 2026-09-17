"""Edit Scenario Configs: pick a saved scenario, edit the anchor-year values
for all three scenario cases side by side, and watch the charts move.

Edits are live - every change re-runs the model and redraws the charts, where
each edited series appears as a dashed "<case> - Updated" line alongside the
saved one it replaces. A run is well under a second, so there's nothing worth
gating behind a button.

Nothing reaches the rest of the app until you explicitly save, as either a new
scenario or an update to the selected one.

The editors are always handed the *stored* values of the selected scenario,
never already-edited ones: st.data_editor keeps its edits in widget state and
replays them onto whatever frame it's given, so re-feeding edited values would
apply them twice. That also makes the stored values the natural baseline for
"has anything changed?", which is what gates the save and revert buttons.

Rendered once per vehicle model - the VehicleModel passed to render() supplies
the regions, the techs to edit, and the widget-key prefix.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard_helpers import (
    ANCHOR_YEARS,
    SCENARIOS,
    build_editable_tech_tables,
    scenario_output_data,
    scenario_overlay_chart,
)
from scenario_store import (
    SavedScenario,
    add_scenario,
    get_main_scenario_name,
    get_scenario,
    name_is_available,
    run_scenario,
    scenario_names,
    set_main_scenario,
    update_scenario,
)
from vehicle_models import VehicleModel

PAGE_DESCRIPTION = (
    "Edit the anchor-year values for each scenario case of the selected "
    "scenario below. Expand a section's charts to see how the edited values "
    "change its sales forecast. Nothing is kept until you save the edits - "
    "either as a new scenario, or as an update to the one you're editing."
)

# Six columns share a third of the page. The year headers take priority over
# the region names: a clipped "North Ameri..." is still readable in a fixed row
# order, whereas a header clipped to "203" can't be told from 2030 or 2035.
_REGION_WIDTH = 76
_YEAR_WIDTH = 58


def _selected_key(model: VehicleModel) -> str:
    return model.wkey("edit_selected_scenario")


def _editor_key(model: VehicleModel, tech: str, scenario: str) -> str:
    return model.wkey(f"edit_{tech}_{scenario}_table")


def _clear_editor_state(model: VehicleModel) -> None:
    """Drop every editor's stored edits. Needed whenever the baseline moves
    underneath them - switching scenario, saving, or reverting - otherwise the
    old edits get replayed onto the new values."""
    for tech in model.edit_techs:
        for scenario in SCENARIOS:
            st.session_state.pop(_editor_key(model, tech, scenario), None)


def _column_config() -> dict:
    """Explicit pixel widths - six columns in a third of the page don't fit
    unless they're told to."""
    return {
        "Region": st.column_config.TextColumn("Region", width=_REGION_WIDTH),
        **{
            str(y): st.column_config.NumberColumn(str(y), width=_YEAR_WIDTH)
            for y in ANCHOR_YEARS
        },
    }


def _tables_to_scenario_dicts(
    model: VehicleModel, edited_tables: dict[str, dict[str, pd.DataFrame]]
) -> tuple[dict, dict]:
    """Split the edited {tech: {case: DataFrame}} dict back into the two
    scenario-dict shapes run_model expects, converting bare percentages back
    to fractions."""
    region_powertrain: dict = {s: {} for s in SCENARIOS}
    region_only: dict = {s: {} for s in SCENARIOS}
    for powertrain in model.modelled_powertrains:
        for scenario in SCENARIOS:
            for _, row in edited_tables[powertrain][scenario].iterrows():
                region_powertrain[scenario][(row["Region"], powertrain)] = {
                    y: row[str(y)] / 100 for y in ANCHOR_YEARS
                }
    for scenario in SCENARIOS:
        for _, row in edited_tables[model.total_label][scenario].iterrows():
            region_only[scenario][row["Region"]] = {y: row[str(y)] / 100 for y in ANCHOR_YEARS}
    return region_powertrain, region_only


def _changed_scenarios(
    model: VehicleModel,
    pristine_tables: dict[str, dict[str, pd.DataFrame]],
    edited_tables: dict[str, dict[str, pd.DataFrame]],
) -> dict[tuple[str, str], list[str]]:
    """{(region, tech): [case, ...]} for every region+tech with at least one
    edited case - which is exactly the set of series needing a dashed
    "Updated" overlay. Both tables are already rounded to 1dp, so this is an
    exact comparison, not float-fuzzy."""
    year_cols = [str(y) for y in ANCHOR_YEARS]
    changed: dict[tuple[str, str], list[str]] = {}
    for tech in model.edit_techs:
        pristine_by_scenario = {s: pristine_tables[tech][s].set_index("Region") for s in SCENARIOS}
        edited_by_scenario = {s: edited_tables[tech][s].set_index("Region") for s in SCENARIOS}
        for region in model.regions:
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


def _updated_series(
    edited_data: pd.DataFrame, changed: dict[tuple[str, str], list[str]], tech: str
) -> pd.DataFrame:
    """The edited rows worth overlaying: only the (region, case) pairs that
    actually changed for this tech. Anything else would redraw the saved line
    on top of itself.

    Note this is per-tech by design: editing a BEV value moves the totals
    residual too, but only the series the user actually touched are marked as
    updated."""
    pairs = {
        (region, case)
        for (region, changed_tech), cases in changed.items()
        if changed_tech == tech
        for case in cases
    }
    if not pairs:
        return edited_data.iloc[0:0]
    keep = [
        (region, case) in pairs
        for region, case in zip(edited_data["region"], edited_data["scenario"])
    ]
    return edited_data.loc[keep]


def _render_charts(
    model: VehicleModel, tech: str, saved_results, edited_results, changed: dict
) -> None:
    with st.expander(f"View {tech} sales charts", expanded=False):
        split_by = (
            st.segmented_control(
                "Split by",
                ["Region", "Scenario case"],
                default="Region",
                key=model.wkey(f"edit_{tech}_split"),
            )
            or "Region"
        )
        original = scenario_output_data(model, saved_results, tech)
        updated = _updated_series(
            scenario_output_data(model, edited_results, tech), changed, tech
        )

        fig = scenario_overlay_chart(model, original, updated, split_by)
        fig.update_layout(height=650)
        st.plotly_chart(fig, use_container_width=True, key=model.wkey(f"edit_{tech}_chart"))


def _render_scenario_picker(model: VehicleModel) -> str:
    """Which saved scenario to edit. Defaults to whichever is currently this
    model's main scenario, and is locked when the default is the only one."""
    selected_key = _selected_key(model)
    names = scenario_names(model)
    st.session_state.setdefault(selected_key, get_main_scenario_name(model))
    if st.session_state[selected_key] not in names:
        st.session_state[selected_key] = names[0]

    previous = st.session_state[selected_key]
    selected = st.selectbox(
        "Scenario",
        names,
        index=names.index(previous),
        disabled=len(names) == 1,
        key=model.wkey("edit_scenario_picker"),
        help=(
            "Only the default scenario exists so far - save one to enable this."
            if len(names) == 1
            else "Which saved scenario to edit."
        ),
    )
    if selected != previous:
        # The baseline just moved; stale edits would be replayed onto it.
        st.session_state[selected_key] = selected
        _clear_editor_state(model)
        st.rerun()
    return selected


def _render_save_dialog(model: VehicleModel, region_powertrain: dict, region: dict) -> None:
    """Name-and-save prompt for "Save new scenario to dashboard". Kept in a
    form so the name isn't submitted on every keystroke."""
    with st.form(model.wkey("save_scenario_form"), clear_on_submit=False):
        name = st.text_input("Scenario name", placeholder="e.g. High EV uptake")
        submitted = st.form_submit_button("Save scenario")

    if not submitted:
        return
    if not name_is_available(model, name):
        st.error(
            "Enter a name that isn't already in use."
            if name.strip()
            else "Enter a name for the scenario."
        )
        return

    scenario = add_scenario(model, name, region_powertrain, region)
    set_main_scenario(model, scenario.name)
    st.session_state[_selected_key(model)] = scenario.name
    st.session_state[model.wkey("show_save_dialog")] = False
    _clear_editor_state(model)
    st.success(f"Saved {scenario.name!r} and applied it across the {model.label} model.")
    st.rerun()


def render(model: VehicleModel) -> None:
    st.title("Edit Scenario Configs")
    st.write(PAGE_DESCRIPTION)

    csv_path = model.get_csv_path()

    selected_name = _render_scenario_picker(model)
    scenario = get_scenario(model, selected_name)

    # Always the stored values - see the module docstring for why.
    pristine_tables = build_editable_tech_tables(
        model, scenario.region_powertrain, scenario.region
    )

    # Each tech's charts belong directly under its own tables, but they can't be
    # drawn yet: the edited model run needs every tech's editors to have
    # returned first. So each section reserves a container now and fills it
    # below, once the results exist.
    edited_tables: dict[str, dict[str, pd.DataFrame]] = {}
    chart_slots: dict[str, "st.delta_generator.DeltaGenerator"] = {}
    for tech in model.edit_techs:
        st.subheader(tech)
        st.caption(model.table_caption(tech))
        edited_tables[tech] = {}
        for case, col in zip(SCENARIOS, st.columns(3)):
            with col:
                st.caption(case)
                edited_tables[tech][case] = st.data_editor(
                    pristine_tables[tech][case],
                    hide_index=True,
                    disabled=["Region"],
                    num_rows="fixed",
                    column_config=_column_config(),
                    key=_editor_key(model, tech, case),
                )
        chart_slots[tech] = st.container()

    region_powertrain_scenarios, region_scenarios = _tables_to_scenario_dicts(
        model, edited_tables
    )
    changed = _changed_scenarios(model, pristine_tables, edited_tables)
    has_changes = bool(changed)

    saved_results = run_scenario(model, csv_path, scenario)
    edited_results = (
        run_scenario(
            model,
            csv_path,
            SavedScenario("(edited)", region_powertrain_scenarios, region_scenarios),
        )
        if has_changes
        else saved_results
    )

    for tech in model.edit_techs:
        with chart_slots[tech]:
            _render_charts(model, tech, saved_results, edited_results, changed)

    st.divider()
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
            "Save new scenario to dashboard",
            width="stretch",
            disabled=not has_changes,
            key=model.wkey("save_new_scenario"),
            help=f"Save these edits as a new named scenario and apply it across the {model.label} model.",
        ):
            st.session_state[model.wkey("show_save_dialog")] = True

    with col2:
        if st.button(
            "Save updates to scenario",
            width="stretch",
            disabled=not has_changes or scenario.is_default,
            key=model.wkey("save_updates"),
            help=(
                "The default scenario is a read-only baseline - use "
                '"Save new scenario to dashboard" to save a copy.'
                if scenario.is_default
                else "Overwrite this scenario with the edits above."
            ),
        ):
            update_scenario(
                model, selected_name, region_powertrain_scenarios, region_scenarios
            )
            _clear_editor_state(model)
            st.success(f"Updated {selected_name!r}.")
            st.rerun()

    with col3:
        if st.button(
            "Revert unsaved changes",
            width="stretch",
            disabled=not has_changes,
            key=model.wkey("revert_changes"),
            help="Discard every edit and go back to this scenario's saved values.",
        ):
            _clear_editor_state(model)
            st.rerun()

    if st.session_state.get(model.wkey("show_save_dialog")):
        _render_save_dialog(model, region_powertrain_scenarios, region_scenarios)
