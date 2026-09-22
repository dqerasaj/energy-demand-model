"""Saved scenarios for the Other Oil Consumption model.

The counterpart to scenario_store.py. Same behaviour - a synthesised read-only
"Default Scenario", named saves in a JSON file beside the app, and one of them
marked as the main scenario driving every Other Oil page - but a different
payload, because an Other Oil scenario is one nested dict rather than the two
region/powertrain dicts a VehicleModel carries:

    {case: {sector: {"total_change": {year: fraction},
                     "efficiency":   {year: fraction} | None,
                     "penetration":  {lever: {year: fraction}}}}}

That is exactly what other_oil_forecast_model.run_model takes as `scenarios`,
so a scenario can be handed straight to it.

There is no model argument anywhere here: there is one Other Oil model, so the
store is a single file rather than one per model.

Terminology matches the vehicle models: a *scenario case* is Slower Transition /
Base Case / Faster Transition, and a *scenario* is a complete named set
of all three cases' anchor values.

saved_scenarios_other_oil.json survives a browser refresh and an app restart
locally; on Streamlit Community Cloud the filesystem is ephemeral, so a
redeploy or container restart clears it. There is a single shared login, so the
file is shared by everyone using the app - including the choice of main
scenario.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from other_oil_forecast_model import OtherOilResults
from other_oil_forecast_model import run_model as _run_model
from scenario_store import DEFAULT_SCENARIO_NAME, slugify

STORE_PATH = Path(__file__).parent / "saved_scenarios_other_oil.json"


@dataclass(frozen=True)
class OtherOilScenario:
    """A complete named set of anchor values - all three scenario cases."""

    name: str
    scenarios: dict  # {case: {sector: {total_change, efficiency, penetration}}}

    @property
    def is_default(self) -> bool:
        """The default is a read-only baseline: it can't be renamed, and
        "Save updates to scenario" can't overwrite it."""
        return self.name == DEFAULT_SCENARIO_NAME

    @property
    def url_slug(self) -> str:
        return slugify(self.name)


def default_scenario() -> OtherOilScenario:
    """Built fresh from the schema CSV every time, never from the store.

    Deep-copied because default_scenarios is lru_cached: handing out the cached
    dict would let one caller's edit leak into every later read of the default.
    """
    from data_loader import get_other_oil_schema_path
    from other_oil_scenario_config import default_scenarios

    return OtherOilScenario(
        name=DEFAULT_SCENARIO_NAME,
        scenarios=copy.deepcopy(default_scenarios(get_other_oil_schema_path())),
    )


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def _encode_anchors(anchors: dict | None) -> dict | None:
    """Anchor years are ints; JSON object keys have to be strings."""
    return None if anchors is None else {str(y): v for y, v in anchors.items()}


def _decode_anchors(raw: dict | None) -> dict | None:
    return None if raw is None else {int(y): v for y, v in raw.items()}


def _encode(scenario: OtherOilScenario) -> dict:
    return {
        "name": scenario.name,
        "scenarios": {
            case: {
                sector: {
                    "total_change": _encode_anchors(config["total_change"]),
                    "efficiency": _encode_anchors(config["efficiency"]),
                    "penetration": {
                        lever: _encode_anchors(anchors)
                        for lever, anchors in config["penetration"].items()
                    },
                }
                for sector, config in sectors.items()
            }
            for case, sectors in scenario.scenarios.items()
        },
    }


def _decode(raw: dict) -> OtherOilScenario:
    return OtherOilScenario(
        name=raw["name"],
        scenarios={
            case: {
                sector: {
                    "total_change": _decode_anchors(config["total_change"]),
                    "efficiency": _decode_anchors(config["efficiency"]),
                    "penetration": {
                        lever: _decode_anchors(anchors)
                        for lever, anchors in config["penetration"].items()
                    },
                }
                for sector, config in sectors.items()
            }
            for case, sectors in raw["scenarios"].items()
        },
    )


def _read_store() -> dict:
    if not STORE_PATH.exists():
        return {"scenarios": [], "main_scenario": DEFAULT_SCENARIO_NAME}
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A corrupt or unreadable store shouldn't take the whole app down -
        # fall back to just the default scenario.
        return {"scenarios": [], "main_scenario": DEFAULT_SCENARIO_NAME}


def _write_store(store: dict) -> None:
    tmp = STORE_PATH.with_suffix(".json.part")
    tmp.write_text(json.dumps(store, indent=2), encoding="utf-8")
    tmp.replace(STORE_PATH)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_scenarios() -> list[OtherOilScenario]:
    """Every scenario, default first, then saved ones in creation order."""
    return [default_scenario(), *(_decode(raw) for raw in _read_store()["scenarios"])]


def scenario_names() -> list[str]:
    return [s.name for s in list_scenarios()]


def get_scenario(name: str) -> OtherOilScenario:
    """The named scenario, falling back to the default if it's gone (e.g. the
    store was cleared while a page still referenced it)."""
    for scenario in list_scenarios():
        if scenario.name == name:
            return scenario
    return default_scenario()


def name_is_available(name: str) -> bool:
    return name.strip() != "" and name.strip() not in scenario_names()


def add_scenario(name: str, scenarios: dict) -> OtherOilScenario:
    """Save a new named scenario. Raises if the name is taken or empty."""
    name = name.strip()
    if not name_is_available(name):
        raise ValueError(f"Scenario name {name!r} is empty or already in use.")

    scenario = OtherOilScenario(name, scenarios)
    store = _read_store()
    store["scenarios"].append(_encode(scenario))
    _write_store(store)
    return scenario


def update_scenario(name: str, scenarios: dict) -> None:
    """Overwrite an existing scenario's values in place. The default scenario
    is a read-only baseline and can't be updated."""
    if name == DEFAULT_SCENARIO_NAME:
        raise ValueError("The default scenario can't be overwritten.")

    store = _read_store()
    updated = _encode(OtherOilScenario(name, scenarios))
    for i, raw in enumerate(store["scenarios"]):
        if raw["name"] == name:
            store["scenarios"][i] = updated
            _write_store(store)
            return
    raise ValueError(f"No saved scenario named {name!r}.")


def rename_scenario(old_name: str, new_name: str) -> None:
    """Rename a saved scenario. Its page URL is derived from the name, so this
    changes the URL too. The default scenario can't be renamed."""
    new_name = new_name.strip()
    if old_name == DEFAULT_SCENARIO_NAME:
        raise ValueError("The default scenario can't be renamed.")
    if new_name != old_name and not name_is_available(new_name):
        raise ValueError(f"Scenario name {new_name!r} is empty or already in use.")

    store = _read_store()
    for raw in store["scenarios"]:
        if raw["name"] == old_name:
            raw["name"] = new_name
            if store.get("main_scenario") == old_name:
                store["main_scenario"] = new_name
            _write_store(store)
            return
    raise ValueError(f"No saved scenario named {old_name!r}.")


def get_main_scenario_name() -> str:
    """The scenario currently driving the Other Oil pages. Falls back to the
    default if the stored choice no longer exists."""
    name = _read_store().get("main_scenario", DEFAULT_SCENARIO_NAME)
    return name if name in scenario_names() else DEFAULT_SCENARIO_NAME


def set_main_scenario(name: str) -> None:
    store = _read_store()
    store["main_scenario"] = name
    _write_store(store)


def get_main_scenario() -> OtherOilScenario:
    return get_scenario(get_main_scenario_name())


# ---------------------------------------------------------------------------
# Running a scenario
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Running Other Oil forecast...")
def _run_encoded(csv_path: str, payload: str) -> OtherOilResults:
    """Cached by the scenario's serialised values rather than its name, so two
    scenarios with identical numbers share a run and an edited scenario always
    re-runs."""
    return _run_model(csv_path, scenarios=_decode(json.loads(payload)).scenarios)


def run_scenario(csv_path: str, scenario: OtherOilScenario) -> OtherOilResults:
    return _run_encoded(csv_path, json.dumps(_encode(scenario), sort_keys=True))
