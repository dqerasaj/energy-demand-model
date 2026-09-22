"""Resolves whichever saved scenario is currently driving the Other Oil pages,
and runs the forecast for it.

The counterpart to model_cache.py. The run itself is cached in
other_oil_scenario_store.run_scenario, keyed on the scenario's values rather
than its name - so switching the main scenario back and forth is free, and
editing one always re-runs.
"""

from data_loader import get_other_oil_csv_path
from other_oil_forecast_model import OtherOilResults
from other_oil_scenario_store import get_main_scenario, run_scenario


def get_other_oil_results() -> OtherOilResults:
    """Results for the scenario currently set as the main Other Oil scenario."""
    return run_scenario(get_other_oil_csv_path(), get_main_scenario())


def get_other_oil_scenarios() -> dict:
    """The main scenario's anchor values, for the Forecasts page's Scenario
    configuration panel - so the panel describes the run above it rather than
    always the schema defaults."""
    return get_main_scenario().scenarios
