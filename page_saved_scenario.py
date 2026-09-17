"""A saved scenario's own page: its anchor-year values, read-only, plus the
controls that act on the scenario as a whole - make it the main scenario for
its model, or rename it.

Same tables as the Edit Scenario Configs page, without the editing, the save
and revert buttons, or the change charts (there is nothing to diff against
here - these values are the saved state).
"""

from __future__ import annotations

import streamlit as st

from dashboard_helpers import SCENARIOS, build_editable_tech_tables
from scenario_store import (
    get_main_scenario_name,
    get_scenario,
    name_is_available,
    rename_scenario,
    set_main_scenario,
)
from vehicle_models import VehicleModel


def _render_rename(model: VehicleModel, name: str) -> None:
    """Rename control. A scenario's page URL is derived from its name, so a
    rename moves the page - the sidebar link follows on the next run."""
    with st.expander("Rename scenario"):
        with st.form(model.wkey(f"rename_{name}"), clear_on_submit=False):
            new_name = st.text_input("New name", value=name)
            submitted = st.form_submit_button("Save name")

        if not submitted:
            return
        if new_name.strip() == name:
            st.info("That's already the name.")
            return
        if not name_is_available(model, new_name):
            st.error(
                "Enter a name that isn't already in use."
                if new_name.strip()
                else "Enter a name for the scenario."
            )
            return

        rename_scenario(model, name, new_name)
        st.success(f"Renamed to {new_name.strip()!r}.")
        st.rerun()


def render(model: VehicleModel, name: str) -> None:
    scenario = get_scenario(model, name)
    is_main = get_main_scenario_name(model) == scenario.name

    st.title(scenario.name)
    st.caption(f"{model.label} model scenario")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button(
            f"Set as main {model.label} scenario",
            width="stretch",
            disabled=is_main,
            key=model.wkey(f"set_main_{scenario.url_slug}"),
            help=(
                "Already the main scenario."
                if is_main
                else f"Apply this scenario across every {model.label} page."
            ),
        ):
            set_main_scenario(model, scenario.name)
            st.rerun()
    with col2:
        if is_main:
            st.success(
                f"This is the main {model.label} scenario.", icon=":material/check_circle:"
            )

    if scenario.is_default:
        st.caption(
            "The default scenario is a read-only baseline, so it can't be renamed or "
            "overwritten - save a copy from the Edit Scenario Configs page to make "
            "your own version."
        )
    else:
        _render_rename(model, scenario.name)

    st.divider()

    tables = build_editable_tech_tables(model, scenario.region_powertrain, scenario.region)
    for tech in model.techs:
        st.subheader(tech)
        st.caption(model.table_caption(tech))
        for case, col in zip(SCENARIOS, st.columns(3)):
            with col:
                st.caption(case)
                st.dataframe(tables[tech][case], hide_index=True)
