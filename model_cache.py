"""Process-wide cache for the (expensive-ish) default model run, shared by
every page so it's only computed once per running app. Also resolves
whichever scenario data is currently "active" - the scenario_config.py
defaults, or a saved override from the Edit Scenario Configs page's Save button."""

import streamlit as st

from ldv_forecast_model import ForecastResults, run_model


@st.cache_data(show_spinner="Running forecast model...")
def get_forecast_results(csv_path: str) -> ForecastResults:
    return run_model(csv_path)


def get_active_scenario_dicts() -> tuple[dict | None, dict | None]:
    """The saved override from the Edit Scenario Configs page's Save button, if one
    exists, else (None, None) meaning "use scenario_config.py's defaults"."""
    return st.session_state.get("scenario_override", (None, None))


def get_active_results(csv_path: str) -> ForecastResults:
    """The currently active results - the saved override if one exists
    (uncached, since it can change any time Save is clicked), otherwise the
    cached default run."""
    region_powertrain_scenarios, region_scenarios = get_active_scenario_dicts()
    if region_powertrain_scenarios is None:
        return get_forecast_results(csv_path)
    return run_model(
        csv_path,
        region_scenarios=region_scenarios,
        region_powertrain_scenarios=region_powertrain_scenarios,
    )
