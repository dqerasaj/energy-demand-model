"""
Default scenario configuration for the HDV forecasting model.

The LDV defaults are hard-coded constants in scenario_config.py; the HDV ones
are supplied as a CSV instead (input_data/hdv_default_schema.csv), so this
module parses that file into the same two dict shapes the model takes:

    case,pt,region,2025,2030,2035,2040,2050
    base,bev,china,20,40,80,90,100
    base,total,china,7,3,2.5,2.5,2.5

pt="bev"   -> penetration share of the region's all-HDV sales
pt="total" -> YoY sales-change rate for the region's all-HDV sales

Values in the file are bare percentages; the model works in fractions, so they
are divided by 100 on the way in - the same convention the Edit Scenario
Configs page uses when it writes edited tables back.

This module owns the HDV region vocabulary (rather than hdv_forecast_model,
which imports it from here) because the schema file is what decides which
regions exist in the first place.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from forecast_model import ANCHOR_YEARS, SCENARIOS

# The schema file's own short names, mapped onto the names used everywhere else
# in the app. REGION_ORDER is the display order that follows from it.
CASE_NAMES = dict(zip(["base", "faster", "slower"], SCENARIOS))
REGION_NAMES = {"china": "China", "usa": "USA", "row": "RoW"}
REGION_ORDER = list(REGION_NAMES.values())

# Which pt value drives which of the two scenario dicts.
PENETRATION_PT = "bev"
TOTAL_PT = "total"

# The one scenario-driven HDV powertrain - there is no PHEV case here.
PENETRATION_POWERTRAIN = "BEV"


def _anchors(row: pd.Series) -> dict[int, float]:
    """One row's anchor-year percentages as {year: fraction}."""
    return {year: float(row[str(year)]) / 100 for year in ANCHOR_YEARS}


@lru_cache(maxsize=None)
def default_scenarios(schema_path: str | None = None) -> tuple[dict, dict]:
    """(region_powertrain, region) - the two dicts run_model takes.

    Cached: the file is small, but this is called on every page run and its
    values never change within a session. schema_path=None resolves it through
    data_loader (the normal case); an explicit path is for tests and this
    module's own __main__.
    """
    if schema_path is None:
        from data_loader import get_hdv_schema_path

        schema_path = get_hdv_schema_path()

    raw = pd.read_csv(schema_path)
    missing_cols = {"case", "pt", "region", *(str(y) for y in ANCHOR_YEARS)} - set(raw.columns)
    if missing_cols:
        raise ValueError(f"{schema_path}: missing columns {sorted(missing_cols)}.")

    raw["case"] = raw["case"].str.strip().str.lower().map(CASE_NAMES)
    raw["pt"] = raw["pt"].str.strip().str.lower()
    raw["region"] = raw["region"].str.strip().str.lower().map(REGION_NAMES)

    unknown = raw.loc[raw["case"].isna() | raw["region"].isna()]
    if not unknown.empty:
        raise ValueError(
            f"{schema_path}: unrecognised case or region in rows {list(unknown.index)}. "
            f"Expected cases {sorted(CASE_NAMES)} and regions {sorted(REGION_NAMES)}."
        )

    region_powertrain: dict = {case: {} for case in SCENARIOS}
    region: dict = {case: {} for case in SCENARIOS}
    for _, row in raw.iterrows():
        if row["pt"] == TOTAL_PT:
            region[row["case"]][row["region"]] = _anchors(row)
        elif row["pt"] == PENETRATION_PT:
            key = (row["region"], PENETRATION_POWERTRAIN)
            region_powertrain[row["case"]][key] = _anchors(row)
        else:
            raise ValueError(
                f"{schema_path}: unrecognised pt {row['pt']!r}. "
                f"Expected {PENETRATION_PT!r} or {TOTAL_PT!r}."
            )

    # A region missing from one case would otherwise surface much later as a
    # silently null forecast, so it's worth failing loudly here instead.
    missing = [
        f"{case}/{pt}/{name}"
        for case in SCENARIOS
        for name in REGION_ORDER
        for pt, group, key in (
            (TOTAL_PT, region, name),
            (PENETRATION_PT, region_powertrain, (name, PENETRATION_POWERTRAIN)),
        )
        if key not in group[case]
    ]
    if missing:
        raise ValueError(f"{schema_path}: no values for {missing}.")

    return region_powertrain, region


if __name__ == "__main__":
    import sys

    rp, r = default_scenarios(sys.argv[1] if len(sys.argv) > 1 else None)
    for case in SCENARIOS:
        print(f"\n== {case} ==")
        print("  all-HDV YoY growth:")
        for name, anchors in r[case].items():
            print(f"    {name}: {anchors}")
        print("  BEV penetration:")
        for key, anchors in rp[case].items():
            print(f"    {key}: {anchors}")
