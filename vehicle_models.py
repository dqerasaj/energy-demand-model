"""
One VehicleModel per vehicle class - the object every shared page, store and
helper is parameterised by.

The LDV and HDV dashboards are the same app twice over: same pages, same
tables, same charts. What actually differs is small and entirely captured
here - the regions, the powertrains, where the data and defaults come from, and
the labels and key prefixes that keep the two sets of pages apart. Adding a
third vehicle class means adding a third VehicleModel below and listing it in
VEHICLE_MODELS; nothing else needs to know it exists.

Widget keys and URLs are namespaced per model on purpose. Streamlit keys are
global, so two dashboards sharing a key would share the widget - and a region
filter holding "Europe" would be meaningless the moment the HDV page, which has
no Europe, tried to render it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import hdv_forecast_model
import ldv_forecast_model
from data_loader import get_hdv_csv_path, get_ldv_csv_path
from forecast_model import DataSpec
from hdv_scenario_config import default_scenarios as hdv_default_scenarios
from ldv_scenario_config import (
    BASE_POWERTRAIN_AND_REGION_SCENARIOS,
    BASE_REGION_SCENARIOS,
)


@dataclass(frozen=True)
class VehicleModel:
    """Everything that distinguishes one vehicle class's dashboard from
    another's.

    `powertrains` is the full display order, residual included.
    `modelled_powertrains` is just the scenario-driven ones, in the order the
    saved-scenario pages list them; `edit_powertrain_order` is the same set in
    the order the editor puts them (BEV leads there).

    `load_defaults` returns the (region_powertrain, region) pair for the default
    scenario. It's a callable rather than a pair of dicts because the HDV
    defaults are parsed from a CSV that may still need downloading.
    """

    key: str
    label: str
    data_spec: DataSpec
    regions: list[str]
    powertrains: list[str]
    modelled_powertrains: list[str]
    edit_powertrain_order: list[str]
    residual_powertrain: str
    get_csv_path: Callable[[], str]
    load_defaults: Callable[[], tuple[dict, dict]]

    # -- naming -----------------------------------------------------------

    @property
    def nav_label(self) -> str:
        """The sidebar section header."""
        return f"{self.label} Model"

    @property
    def title(self) -> str:
        """The Forecasts page title."""
        return f"{self.label} Sales Forecast"

    @property
    def total_label(self) -> str:
        """The all-vehicle row/table name: "Total LDVs" / "Total HDVs"."""
        return f"Total {self.label}s"

    @property
    def techs(self) -> list[str]:
        """The scenario-config tables in canonical order: one per modelled
        powertrain, then the all-vehicle totals."""
        return [*self.modelled_powertrains, self.total_label]

    @property
    def edit_techs(self) -> list[str]:
        """The same tables in the order the Edit Scenario Configs page shows
        them."""
        return [*self.edit_powertrain_order, self.total_label]

    def table_caption(self, tech: str) -> str:
        """What a scenario-config table's numbers actually mean - penetration
        share for a powertrain, YoY growth for the totals."""
        if tech == self.total_label:
            return f"{tech} - YoY sales growth (%)"
        return f"{tech} - penetration share of all-{self.label} sales (%)"

    # -- namespacing ------------------------------------------------------

    def wkey(self, name: str) -> str:
        """A widget key scoped to this model, so the two dashboards' controls
        stay independent."""
        return f"{self.key}_{name}"

    def url(self, suffix: str) -> str:
        """A page URL scoped to this model. st.Page URLs are a single flat
        segment, so the prefix is what namespaces them."""
        return f"{self.key}-model-{suffix}"

    @property
    def other_powertrains(self) -> dict[str, str]:
        """{raw source value: display label} for powertrains carried from the
        source rather than forecast. Defined on the DataSpec, since that's what
        the engine reads."""
        return dict(self.data_spec.other_powertrains)

    @property
    def other_powertrain_labels(self) -> list[str]:
        """Display names of the non-forecast powertrains, in source order."""
        return list(self.other_powertrains.values())

    @property
    def store_path(self) -> Path:
        """Where this model's saved scenarios live. One file per model - a
        scenario's regions and powertrains only make sense for its own."""
        return Path(__file__).parent / f"saved_scenarios_{self.key}.json"


LDV = VehicleModel(
    key="ldv",
    label="LDV",
    data_spec=ldv_forecast_model.DATA_SPEC,
    regions=ldv_forecast_model.REGION_ORDER,
    powertrains=ldv_forecast_model.POWERTRAIN_ORDER,
    modelled_powertrains=["PHEV", "BEV"],
    edit_powertrain_order=["BEV", "PHEV"],
    residual_powertrain="IC Only",
    get_csv_path=get_ldv_csv_path,
    load_defaults=lambda: (BASE_POWERTRAIN_AND_REGION_SCENARIOS, BASE_REGION_SCENARIOS),
)

HDV = VehicleModel(
    key="hdv",
    label="HDV",
    data_spec=hdv_forecast_model.DATA_SPEC,
    regions=hdv_forecast_model.REGION_ORDER,
    powertrains=hdv_forecast_model.POWERTRAIN_ORDER,
    modelled_powertrains=["BEV"],
    edit_powertrain_order=["BEV"],
    residual_powertrain="IC Only",
    get_csv_path=get_hdv_csv_path,
    load_defaults=hdv_default_scenarios,
)

VEHICLE_MODELS = {model.key: model for model in (LDV, HDV)}


def get_model(key: str) -> VehicleModel:
    """Look a model up by key - how the cached model run gets back to a
    VehicleModel from the plain string it was cached on."""
    return VEHICLE_MODELS[key]
