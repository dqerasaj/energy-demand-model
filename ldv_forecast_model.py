"""
LDV sales scenario forecasting model.

Only the LDV-specific bits live here - which raw columns carry region and
powertrain, and how their values bucket. The forecasting itself is in
forecast_model.py, shared with the HDV model; see that module's docstring for
how the scenario schedules are applied.

Only BEV, PHEV and IC Only powertrains are modelled. Other values - FHEV, and
anything blank or unrecognised - get no powertrain of their own, but they are
still light duty vehicles, so they count towards the all-LDV region totals.
That means the powertrain breakdown sums to less than the all-LDV total in
actual years; from the first forecast year the IC Only residual absorbs the
difference.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from forecast_model import DataSpec, ForecastResults, to_wide
from forecast_model import run_model as _run_model
from ldv_scenario_config import (
    BASE_POWERTRAIN_AND_REGION_SCENARIOS,
    BASE_REGION_SCENARIOS,
)

RAW_REGION_COL = "REGION"
RAW_POWERTRAIN_COL = "HYBRID & EV TYPE"

REGION_ORDER = ["North America", "Europe", "APAC", "RoW"]
POWERTRAIN_ORDER = ["PHEV", "BEV", "IC Only"]

# Maps the file's HYBRID & EV TYPE onto the three modelled powertrains.
# Anything that drives on grid electricity is BEV (range-extenders and fuel
# cell included); mild hybrids are engine-driven, so they sit with IC Only;
# PHEV stands alone because it has its own scenario.
#
# FHEV is deliberately absent. A full hybrid is neither scenario-driven nor
# really "IC Only", so it gets no powertrain of its own - but it is still a
# light duty vehicle, so it counts towards the all-LDV totals (see
# TOTALS_INCLUDE_UNMAPPED). It's ~7% of 2024 sales.
POWERTRAIN_BUCKETS = {
    "IC Only": "IC Only",
    "MHEV": "IC Only",
    "MHEV (48V)": "IC Only",
    "BEV": "BEV",
    "EREV": "BEV",
    "FCEV": "BEV",
    "PFCEV": "BEV",
    "PHEV": "PHEV",
}

# "Sales by region (all LDV)" means every LDV in the file, not just the three
# powertrains broken out above.
TOTALS_INCLUDE_UNMAPPED = True

# FHEV is shown as its own series using the source file's published figures -
# actuals and its forward years alike - rather than being folded into IC Only.
# The source stops at 2032; from 2033 there is nothing to show and the IC Only
# residual covers the remainder again.
OTHER_POWERTRAINS = (("FHEV", "FHEV"),)


def bucket_region(raw: pd.Series) -> pd.Series:
    return pd.Series(
        np.select(
            [
                raw.eq("North America"),
                raw.str.contains("Europe", na=False),
                raw.eq("Asia-Pacific"),
            ],
            ["North America", "Europe", "APAC"],
            default="RoW",
        ),
        index=raw.index,
    )


DATA_SPEC = DataSpec(
    region_col=RAW_REGION_COL,
    powertrain_col=RAW_POWERTRAIN_COL,
    bucket_region=bucket_region,
    powertrain_buckets=POWERTRAIN_BUCKETS,
    modelled_powertrains=("BEV", "PHEV"),
    residual_powertrain="IC Only",
    totals_include_unmapped=TOTALS_INCLUDE_UNMAPPED,
    other_powertrains=OTHER_POWERTRAINS,
)


def run_model(
    csv_path: str,
    *,
    region_scenarios: dict | None = None,
    region_powertrain_scenarios: dict | None = None,
) -> ForecastResults:
    """`region_scenarios`/`region_powertrain_scenarios` default to the
    scenario_config.py constants, but can be overridden with a custom
    scenario dict of the same shape (e.g. for a what-if sandbox)."""
    return _run_model(
        csv_path,
        DATA_SPEC,
        region_scenarios if region_scenarios is not None else BASE_REGION_SCENARIOS,
        region_powertrain_scenarios
        if region_powertrain_scenarios is not None
        else BASE_POWERTRAIN_AND_REGION_SCENARIOS,
    )


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    results = run_model(sys.argv[1] if len(sys.argv) > 1 else "ldv_sales.csv")

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 250)

    print("\n== Sales by region & powertrain (all scenarios) ==")
    print(to_wide(results.region_and_powertrain_sales).round(0).to_string(index=False))
    print("\n== Sales by region, all LDVs (all scenarios) ==")
    print(to_wide(results.region_sales).round(0).to_string(index=False))
    print("\n== Global sales by powertrain (all scenarios) ==")
    print(to_wide(results.powertrain_sales).round(0).to_string(index=False))
    print("\n== Global all-LDV total (all scenarios) ==")
    print(to_wide(results.total_sales).round(0).to_string(index=False))
