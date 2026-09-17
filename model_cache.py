"""Resolves whichever saved scenario is currently driving a model's pages, and
runs the forecast for it.

The run itself is cached in scenario_store.run_scenario, keyed on the model and
the scenario's values rather than its name - so switching the main scenario
back and forth is free, and editing one always re-runs.
"""

from forecast_model import ForecastResults
from scenario_store import get_main_scenario, run_scenario
from vehicle_models import VehicleModel


def get_active_scenario_dicts(model: VehicleModel) -> tuple[dict, dict]:
    """The main scenario's two dicts, in the order build_tech_tables wants
    them: (region+powertrain penetration, region YoY)."""
    scenario = get_main_scenario(model)
    return scenario.region_powertrain, scenario.region


def get_active_results(model: VehicleModel) -> ForecastResults:
    """Results for the scenario currently set as this model's main scenario."""
    return run_scenario(model, model.get_csv_path(), get_main_scenario(model))
