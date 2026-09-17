"""Saved scenarios: the named sets of anchor-year values users build on the
Edit Scenario Configs page, plus which one is currently driving each model's
pages.

Every function here takes the VehicleModel it applies to. The LDV and HDV
models keep entirely separate stores - a scenario's regions and powertrains
only mean anything for the model it was built for.

Terminology, which is easy to trip over: a *scenario case* is Base Case /
Faster Transition / Slower Transition - the three columns that have always
existed. A *scenario* is a complete named set of all three cases' anchor
values. One scenario contains three cases.

"Default Scenario" is synthesised from the model's own defaults rather than
stored, so it is always a pristine baseline - it can't be renamed or
overwritten. For LDV those defaults are the scenario_config.py constants; for
HDV they're parsed from the schema CSV.

Everything else lives in saved_scenarios_<model>.json beside the app. That
survives a browser refresh and an app restart locally; on Streamlit Community
Cloud the filesystem is ephemeral, so a redeploy or container restart clears
it. There is a single shared login, so the file is shared by everyone using the
app - including the choice of main scenario.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import streamlit as st

from forecast_model import ForecastResults
from forecast_model import run_model as _run_model
from vehicle_models import VehicleModel, get_model

DEFAULT_SCENARIO_NAME = "Default Scenario"

# (region, powertrain) tuples can't be JSON object keys, so they're joined on
# this separator for storage and split again on load.
_KEY_SEP = "|"


@dataclass(frozen=True)
class SavedScenario:
    """A complete named set of anchor values - all three scenario cases.

    `region_powertrain` and `region` are exactly the two dicts run_model takes,
    so a scenario can be handed straight to it.
    """

    name: str
    region_powertrain: dict  # {case: {(region, powertrain): {year: fraction}}}
    region: dict  # {case: {region: {year: fraction}}}

    @property
    def is_default(self) -> bool:
        """The default is a read-only baseline: it can't be renamed, and
        "Save updates to scenario" can't overwrite it."""
        return self.name == DEFAULT_SCENARIO_NAME

    @property
    def url_slug(self) -> str:
        return slugify(self.name)


def slugify(name: str) -> str:
    """A url_path-safe slug. st.Page URLs are a single flat segment, so this
    has to survive as one - no slashes, no spaces."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "scenario"


def default_scenario(model: VehicleModel) -> SavedScenario:
    """Built fresh from the model's own defaults every time, never from the
    store."""
    region_powertrain, region = model.load_defaults()
    return SavedScenario(
        name=DEFAULT_SCENARIO_NAME,
        region_powertrain=region_powertrain,
        region=region,
    )


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def _encode(scenario: SavedScenario) -> dict:
    return {
        "name": scenario.name,
        "region_powertrain": {
            case: {
                f"{region}{_KEY_SEP}{powertrain}": {str(y): v for y, v in anchors.items()}
                for (region, powertrain), anchors in groups.items()
            }
            for case, groups in scenario.region_powertrain.items()
        },
        "region": {
            case: {
                region: {str(y): v for y, v in anchors.items()}
                for region, anchors in groups.items()
            }
            for case, groups in scenario.region.items()
        },
    }


def _decode(raw: dict) -> SavedScenario:
    return SavedScenario(
        name=raw["name"],
        region_powertrain={
            case: {
                tuple(key.split(_KEY_SEP, 1)): {int(y): v for y, v in anchors.items()}
                for key, anchors in groups.items()
            }
            for case, groups in raw["region_powertrain"].items()
        },
        region={
            case: {
                region: {int(y): v for y, v in anchors.items()}
                for region, anchors in groups.items()
            }
            for case, groups in raw["region"].items()
        },
    )


def _read_store(model: VehicleModel) -> dict:
    if not model.store_path.exists():
        return {"scenarios": [], "main_scenario": DEFAULT_SCENARIO_NAME}
    try:
        return json.loads(model.store_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A corrupt or unreadable store shouldn't take the whole app down -
        # fall back to just the default scenario.
        return {"scenarios": [], "main_scenario": DEFAULT_SCENARIO_NAME}


def _write_store(model: VehicleModel, store: dict) -> None:
    tmp = model.store_path.with_suffix(".json.part")
    tmp.write_text(json.dumps(store, indent=2), encoding="utf-8")
    tmp.replace(model.store_path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_scenarios(model: VehicleModel) -> list[SavedScenario]:
    """Every scenario, default first, then saved ones in creation order."""
    store = _read_store(model)
    return [default_scenario(model), *(_decode(raw) for raw in store["scenarios"])]


def scenario_names(model: VehicleModel) -> list[str]:
    return [s.name for s in list_scenarios(model)]


def get_scenario(model: VehicleModel, name: str) -> SavedScenario:
    """The named scenario, falling back to the default if it's gone (e.g. the
    store was cleared while a page still referenced it)."""
    for scenario in list_scenarios(model):
        if scenario.name == name:
            return scenario
    return default_scenario(model)


def name_is_available(model: VehicleModel, name: str) -> bool:
    return name.strip() != "" and name.strip() not in scenario_names(model)


def add_scenario(
    model: VehicleModel, name: str, region_powertrain: dict, region: dict
) -> SavedScenario:
    """Save a new named scenario. Raises if the name is taken or empty."""
    name = name.strip()
    if not name_is_available(model, name):
        raise ValueError(f"Scenario name {name!r} is empty or already in use.")

    scenario = SavedScenario(name, region_powertrain, region)
    store = _read_store(model)
    store["scenarios"].append(_encode(scenario))
    _write_store(model, store)
    return scenario


def update_scenario(
    model: VehicleModel, name: str, region_powertrain: dict, region: dict
) -> None:
    """Overwrite an existing scenario's values in place. The default scenario
    is a read-only baseline and can't be updated."""
    if name == DEFAULT_SCENARIO_NAME:
        raise ValueError("The default scenario can't be overwritten.")

    store = _read_store(model)
    updated = _encode(SavedScenario(name, region_powertrain, region))
    for i, raw in enumerate(store["scenarios"]):
        if raw["name"] == name:
            store["scenarios"][i] = updated
            _write_store(model, store)
            return
    raise ValueError(f"No saved scenario named {name!r}.")


def rename_scenario(model: VehicleModel, old_name: str, new_name: str) -> None:
    """Rename a saved scenario. Its page URL is derived from the name, so this
    changes the URL too. The default scenario can't be renamed."""
    new_name = new_name.strip()
    if old_name == DEFAULT_SCENARIO_NAME:
        raise ValueError("The default scenario can't be renamed.")
    if new_name != old_name and not name_is_available(model, new_name):
        raise ValueError(f"Scenario name {new_name!r} is empty or already in use.")

    store = _read_store(model)
    for raw in store["scenarios"]:
        if raw["name"] == old_name:
            raw["name"] = new_name
            if store.get("main_scenario") == old_name:
                store["main_scenario"] = new_name
            _write_store(model, store)
            return
    raise ValueError(f"No saved scenario named {old_name!r}.")


def get_main_scenario_name(model: VehicleModel) -> str:
    """The scenario currently driving this model's pages. Falls back to the
    default if the stored choice no longer exists."""
    name = _read_store(model).get("main_scenario", DEFAULT_SCENARIO_NAME)
    return name if name in scenario_names(model) else DEFAULT_SCENARIO_NAME


def set_main_scenario(model: VehicleModel, name: str) -> None:
    store = _read_store(model)
    store["main_scenario"] = name
    _write_store(model, store)


def get_main_scenario(model: VehicleModel) -> SavedScenario:
    return get_scenario(model, get_main_scenario_name(model))


# ---------------------------------------------------------------------------
# Running a scenario
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Running forecast model...")
def _run_encoded(model_key: str, csv_path: str, payload: str) -> ForecastResults:
    """Cached by the scenario's serialised values rather than its name, so two
    scenarios with identical numbers share a run and an edited scenario always
    re-runs. The model arrives as its key because a VehicleModel isn't a
    cache-key-friendly argument."""
    model = get_model(model_key)
    scenario = _decode(json.loads(payload))
    return _run_model(
        csv_path,
        model.data_spec,
        scenario.region,
        scenario.region_powertrain,
    )


def run_scenario(
    model: VehicleModel, csv_path: str, scenario: SavedScenario
) -> ForecastResults:
    return _run_encoded(
        model.key, csv_path, json.dumps(_encode(scenario), sort_keys=True)
    )
