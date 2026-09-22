"""A saved Other Oil scenario's own page: its anchor-year values, read-only,
plus the controls that act on the scenario as a whole - make it the main
scenario, or rename it.

Same tables as the Edit Scenario Configs page, without the editing, the save
and revert buttons, or the forecast charts (there is nothing to diff against
here - these values are the saved state).
"""

from __future__ import annotations

import streamlit as st

from forecast_model import SCENARIOS
from other_oil_scenario_config import SECTOR_ORDER, config_table
from other_oil_scenario_store import (
    get_main_scenario_name,
    get_scenario,
    name_is_available,
    rename_scenario,
    set_main_scenario,
)

WKEY = "other_oil_saved"


def _render_rename(name: str) -> None:
    """Rename control. A scenario's page URL is derived from its name, so a
    rename moves the page - the sidebar link follows on the next run."""
    with st.expander("Rename scenario"):
        with st.form(f"{WKEY}_rename_{name}", clear_on_submit=False):
            new_name = st.text_input("New name", value=name)
            submitted = st.form_submit_button("Save name")

        if not submitted:
            return
        if new_name.strip() == name:
            st.info("That's already the name.")
            return
        if not name_is_available(new_name):
            st.error(
                "Enter a name that isn't already in use."
                if new_name.strip()
                else "Enter a name for the scenario."
            )
            return

        rename_scenario(name, new_name)
        st.success(f"Renamed to {new_name.strip()!r}.")
        st.rerun()


def render(name: str) -> None:
    scenario = get_scenario(name)
    is_main = get_main_scenario_name() == scenario.name

    st.title(scenario.name)
    st.caption("Other Oil Consumption scenario")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button(
            "Set as main Other Oil scenario",
            width="stretch",
            disabled=is_main,
            key=f"{WKEY}_set_main_{scenario.url_slug}",
            help=(
                "Already the main scenario."
                if is_main
                else "Apply this scenario across every Other Oil page."
            ),
        ):
            set_main_scenario(scenario.name)
            st.rerun()
    with col2:
        if is_main:
            st.success(
                "This is the main Other Oil scenario.", icon=":material/check_circle:"
            )

    if scenario.is_default:
        st.caption(
            "The default scenario is a read-only baseline, so it can't be renamed or "
            "overwritten - save a copy from the Edit Scenario Configs page to make "
            "your own version."
        )
    else:
        _render_rename(scenario.name)

    st.divider()

    for sector in SECTOR_ORDER:
        st.subheader(sector)
        for case, col in zip(SCENARIOS, st.columns(3)):
            with col:
                st.caption(case)
                st.dataframe(
                    config_table(scenario.scenarios[case][sector], sector),
                    hide_index=True,
                    width="stretch",
                )
