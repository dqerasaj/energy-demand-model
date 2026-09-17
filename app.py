"""
Web dashboard for the energy demand scenario models. Entry point: wires up
auth and page navigation. The actual page content lives in the page_* modules.

The sidebar is rendered by nav.py rather than st.navigation, which is why
navigation is created with position="hidden" - see nav.py for why.

Each vehicle model (LDV, HDV, ...) gets one NavSection, built by
_model_section from its VehicleModel. The pages themselves are shared - the
same modules render both models, parameterised by the model they're given -
so adding a third vehicle class means adding it to vehicle_models.VEHICLE_MODELS
and nothing here changes. Page URLs are prefixed with the model, since st.Page
URLs are a single flat segment and the prefix is what namespaces them.

The Saved Scenarios pages are built fresh each run from each model's scenario
store, so saving or renaming a scenario changes the sidebar on the next rerun.
"""

import streamlit as st

from auth import check_password
from nav import NavSection, all_pages, render_sidebar
import page_dashboard
import page_edit_scenario
import page_main_dashboard
import page_saved_scenario
from scenario_store import list_scenarios
from vehicle_models import VEHICLE_MODELS, VehicleModel


def _saved_scenario_pages(model: VehicleModel) -> list[st.Page]:
    """One page per saved scenario of this model. The default arguments bind
    the model and name per iteration - a bare closure over the loop variable
    would give every page the last scenario's name."""
    return [
        st.Page(
            lambda m=model, name=scenario.name: page_saved_scenario.render(m, name),
            title=scenario.name,
            url_path=model.url(f"scenario-{scenario.url_slug}"),
        )
        for scenario in list_scenarios(model)
    ]


def _model_section(model: VehicleModel) -> NavSection:
    """One vehicle model's whole sidebar section: its two pages, plus a
    nested Saved Scenarios subsection."""
    return NavSection(
        label=model.nav_label,
        key=f"{model.key}_model",
        pages=[
            st.Page(
                lambda m=model: page_dashboard.render(m),
                title="Forecasts",
                url_path=model.url("forecasts"),
            ),
            st.Page(
                lambda m=model: page_edit_scenario.render(m),
                title="Edit Scenario Configs",
                url_path=model.url("edit-scenarios"),
            ),
        ],
        subsections=[
            NavSection(
                label="Saved Scenarios",
                key=f"{model.key}_saved_scenarios",
                pages=_saved_scenario_pages(model),
                start_expanded=False,
            ),
        ],
    )


if __name__ == "__main__":
    st.set_page_config(page_title="Energy Demand Model", layout="wide")

    if not check_password():
        st.stop()

    landing = st.Page(
        page_main_dashboard.render,
        title="Model Dashboard Overview",
        # No url_path: the default page is always served at "/" and url_path is ignored.
        default=True,
    )

    sections = [_model_section(model) for model in VEHICLE_MODELS.values()]

    pg = st.navigation([landing, *all_pages(sections)], position="hidden")
    render_sidebar(landing, sections, pg)
    pg.run()
