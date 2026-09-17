"""
HDV sales scenario forecasting model - heavy duty trucks and buses.

The mirror of ldv_forecast_model.py. Only the HDV-specific bits live here; the
forecasting itself is in forecast_model.py, shared with the LDV model.

Three things differ from LDV:

* Regions. Three buckets - China, the USA, and everything else as RoW. These
  come from the COUNTRY column, not the file's own REGION column: REGION holds
  only continent-level values (Asia-Pacific, Western Europe, ...) with no China
  or USA of its own, so COUNTRY is the only column that can produce the split.
* Powertrains. Two buckets - BEV and IC Only - taken from just the "Electric"
  and "ICE" rows. There is no PHEV case, so BEV is the only scenario-driven
  powertrain, and IC Only is the reconciliation residual, calculated exactly as
  for LDV. The file's "ICE-Hybrid" and "H2 ICE" rows are left out of that
  breakdown but still count towards the all-HDV region totals.
* Encoding. The extract is Windows-1252 rather than UTF-8.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from forecast_model import DataSpec, ForecastResults, to_wide
from forecast_model import run_model as _run_model
from hdv_scenario_config import REGION_ORDER, default_scenarios

RAW_REGION_COL = "COUNTRY"
RAW_POWERTRAIN_COL = "POWERTRAIN TYPE"

POWERTRAIN_ORDER = ["BEV", "IC Only"]

# Only these two POWERTRAIN TYPE values appear in the powertrain breakdown.
# "Electric" covers both battery electric and fuel cell (matching LDV, where
# FCEV also buckets into BEV).
#
# The file's other two values - "ICE-Hybrid" (its HEV and PHEV variants) and
# "H2 ICE" - are deliberately absent, so they never show up as a powertrain.
# They do still count towards the all-HDV region totals though (see
# TOTALS_INCLUDE_UNMAPPED), because those totals mean every HDV regardless of
# powertrain.
POWERTRAIN_BUCKETS = {
    "Electric": "BEV",
    "ICE": "IC Only",
}

# "Sales by region (all HDVs)" means exactly that - every row in the file, not
# just the two powertrains broken out above. The two are separate filters: the
# breakdown is filtered, the totals are not.
TOTALS_INCLUDE_UNMAPPED = True

# Shown as their own series from the source file's published figures, forward
# years included, rather than folded into IC Only. The source stops at 2037.
OTHER_POWERTRAINS = (("ICE-Hybrid", "ICE Hybrids"), ("H2 ICE", "H2 Hybrids"))

# A stray non-breaking space in the plant names is enough to make a plain
# utf-8 read of this file fail.
ENCODING = "cp1252"


def bucket_region(raw: pd.Series) -> pd.Series:
    return pd.Series(
        np.select(
            [raw.eq("China"), raw.eq("USA")],
            ["China", "USA"],
            default="RoW",
        ),
        index=raw.index,
    )


DATA_SPEC = DataSpec(
    region_col=RAW_REGION_COL,
    powertrain_col=RAW_POWERTRAIN_COL,
    bucket_region=bucket_region,
    powertrain_buckets=POWERTRAIN_BUCKETS,
    modelled_powertrains=("BEV",),
    residual_powertrain="IC Only",
    encoding=ENCODING,
    totals_include_unmapped=TOTALS_INCLUDE_UNMAPPED,
    other_powertrains=OTHER_POWERTRAINS,
)


def run_model(
    csv_path: str,
    *,
    schema_path: str | None = None,
    region_scenarios: dict | None = None,
    region_powertrain_scenarios: dict | None = None,
) -> ForecastResults:
    """`region_scenarios`/`region_powertrain_scenarios` default to the values
    parsed from the HDV schema CSV, but can be overridden with a custom
    scenario dict of the same shape (e.g. for a what-if sandbox).

    `schema_path` is only read when a default is actually needed."""
    if region_scenarios is None or region_powertrain_scenarios is None:
        default_rp, default_region = default_scenarios(schema_path)
        if region_scenarios is None:
            region_scenarios = default_region
        if region_powertrain_scenarios is None:
            region_powertrain_scenarios = default_rp

    return _run_model(csv_path, DATA_SPEC, region_scenarios, region_powertrain_scenarios)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    results = run_model(sys.argv[1] if len(sys.argv) > 1 else "hdv_sales.csv")

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 250)

    print("\n== Sales by region & powertrain (all scenarios) ==")
    print(to_wide(results.region_and_powertrain_sales).round(0).to_string(index=False))
    print("\n== Sales by region, all HDVs (all scenarios) ==")
    print(to_wide(results.region_sales).round(0).to_string(index=False))
    print("\n== Global sales by powertrain (all scenarios) ==")
    print(to_wide(results.powertrain_sales).round(0).to_string(index=False))
    print("\n== Global all-HDV total (all scenarios) ==")
    print(to_wide(results.total_sales).round(0).to_string(index=False))
