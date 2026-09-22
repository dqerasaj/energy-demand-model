"""
Default scenario configuration for the Other Oil Consumption model.

Parses input_data/other_oil_default_schema.csv into the shape
other_oil_forecast_model.run_model takes. The file is one row per
(sector, lever, case), with the anchor years as columns:

    Sector,Level,Change Category,Change Application Type,Case,2025,...,2050
    Shipping,Activity,Total Change,YoY,Base,2,2,2,2,2
    Shipping,Oil,Efficiency,PA,Base,-0.5,-0.5,-0.5,-0.5,-0.5
    Shipping,Oil,Low-emission Fuel,Penetration,Base,2,10,20,35,50

"Change Application Type" is what the model dispatches on, not the lever's
name - see APPLICATION_TYPES. That matters for Penetration in particular: a
sector's deductions are every Penetration row it has, whatever they're called,
so the electrification lever can be "E-shipping" for one sector and "E-plane"
for another, and a fourth lever is a schema edit rather than a code change.

Values in the file are bare percentages and the model works in fractions, so
they're divided by 100 on the way in - the same convention as
hdv_scenario_config.py.
"""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache

import pandas as pd

from forecast_model import ANCHOR_YEARS, SCENARIOS

# The schema's own case names, mapped onto the names used everywhere else in
# the app. The file says "Base"; the app says "Base Case".
CASE_NAMES = {
    "Slower Transition": "Slower Transition",
    "Base": "Base Case",
    "Faster Transition": "Faster Transition",
}
assert sorted(CASE_NAMES.values()) == sorted(SCENARIOS)

# Display order for the four sectors - the order they appear in the schema.
SECTOR_ORDER = ["Petrochemicals", "Shipping", "Aviation", "Buildings/Power/Other"]

# The two sectors modelled through an activity base and an oil intensity.
# The others are projected as a bare YoY on their own prior-year oil.
ACTIVITY_SECTORS = ["Shipping", "Aviation"]

# How each lever is applied. The Change Application Type column carries these.
YOY = "YoY"                    # compounded onto the prior year's own value
PA = "PA"                      # compounded onto the prior year's own value
PENETRATION = "Penetration"    # a share, interpolated, deducted from activity
APPLICATION_TYPES = {YOY, PA, PENETRATION}

# Which Change Category each of the two compounding levers must carry. Both are
# stepped schedules, but they drive different quantities, so they're looked up
# by name rather than by application type alone.
TOTAL_CHANGE = "Total Change"
EFFICIENCY = "Efficiency"

REQUIRED_COLS = {
    "Sector",
    "Level",
    "Change Category",
    "Change Application Type",
    "Case",
    *(str(y) for y in ANCHOR_YEARS),
}


# The identifier column of the per-sector tables built below.
LEVER_COLUMN = "Lever"


def _anchors(row: pd.Series) -> dict[int, float]:
    """One row's anchor-year percentages as {year: fraction}."""
    return {year: float(row[str(year)]) / 100 for year in ANCHOR_YEARS}


def lever_labels(sector: str, sector_config: dict) -> list[tuple[str, dict[int, float]]]:
    """(label, anchors) for one sector's levers, in a fixed order.

    Each label carries how the lever is applied, because the numbers mean
    different things: YoY and PA are rates compounded onto the prior year,
    while Penetration is a level the year's activity is multiplied by. Without
    it, a 2 in one row and a 2 in another look like the same assumption.

    The growth lever is named for what it drives - activity for the sectors
    modelled through a physical base, oil directly for the other two.
    """
    growth = "Activity growth" if sector in ACTIVITY_SECTORS else "Oil growth"
    levers = [(f"{growth} ({YOY})", sector_config["total_change"])]
    if sector_config["efficiency"] is not None:
        levers.append((f"{EFFICIENCY} ({PA})", sector_config["efficiency"]))
    levers += [
        (f"{name} ({PENETRATION})", anchors)
        for name, anchors in sector_config["penetration"].items()
    ]
    return levers


def apply_config_table(sector_config: dict, sector: str, table: pd.DataFrame) -> dict:
    """The inverse of config_table: one sector's config rebuilt from an edited
    table, back in the fractions the model works in.

    Matched by row position rather than by the label text, since lever_labels
    fixes that order and the editor runs with num_rows="fixed" and the label
    column disabled - so the rows that come back are the rows that went out.

    Raises ValueError on a row-count mismatch or a blank cell; the caller
    decides what to do about it, because mid-edit a blank cell is a normal
    thing for a user to be looking at rather than an error worth crashing on.
    """
    labels = lever_labels(sector, sector_config)
    if len(table) != len(labels):
        raise ValueError(
            f"{sector}: expected {len(labels)} lever rows, got {len(table)}."
        )

    rows = []
    for i in range(len(table)):
        values = {}
        for year in ANCHOR_YEARS:
            value = table.iloc[i][str(year)]
            if pd.isna(value):
                raise ValueError(
                    f"{sector}: {labels[i][0]} has no value for {year}."
                )
            values[year] = float(value) / 100
        rows.append(values)

    rebuilt: dict = {"total_change": rows[0], "efficiency": None, "penetration": {}}
    index = 1
    if sector_config["efficiency"] is not None:
        rebuilt["efficiency"] = rows[index]
        index += 1
    for name in sector_config["penetration"]:
        rebuilt["penetration"][name] = rows[index]
        index += 1
    return rebuilt


def config_table(sector_config: dict, sector: str) -> pd.DataFrame:
    """One sector's levers as rows and anchor years as columns, carrying the
    bare percentages the schema file holds rather than the fractions the model
    works in. Shared by the Forecasts page's read-only panel and the editor."""
    # Rounded because these values are a percentage that was divided by 100 on
    # load and is being multiplied back here: 3.5 returns as 3.5000000000000004
    # otherwise, which the display format hides but an equality check against
    # the stored baseline would not.
    return pd.DataFrame(
        [
            {
                LEVER_COLUMN: label,
                **{str(y): round(anchors[y] * 100, 6) for y in ANCHOR_YEARS},
            }
            for label, anchors in lever_labels(sector, sector_config)
        ]
    )


@lru_cache(maxsize=None)
def default_scenarios(schema_path: str | None = None) -> dict:
    """{case: {sector: {"total_change": anchors,
                        "efficiency": anchors,
                        "penetration": {lever name: anchors}}}}

    Cached: the file is small, but this is called on every page run and its
    values never change within a session. schema_path=None resolves it through
    data_loader (the normal case); an explicit path is for tests and this
    module's own __main__.
    """
    if schema_path is None:
        from data_loader import get_other_oil_schema_path

        schema_path = get_other_oil_schema_path()

    raw = pd.read_csv(schema_path, encoding="utf-8-sig")
    missing_cols = REQUIRED_COLS - set(raw.columns)
    if missing_cols:
        raise ValueError(f"{schema_path}: missing columns {sorted(missing_cols)}.")

    for col in ("Sector", "Level", "Change Category", "Change Application Type", "Case"):
        raw[col] = raw[col].str.strip()
    raw["case"] = raw["Case"].map(CASE_NAMES)

    unknown = raw.loc[raw["case"].isna() | ~raw["Sector"].isin(SECTOR_ORDER)]
    if not unknown.empty:
        raise ValueError(
            f"{schema_path}: unrecognised case or sector in rows {list(unknown.index)}. "
            f"Expected cases {sorted(CASE_NAMES)} and sectors {SECTOR_ORDER}."
        )

    # A mistyped application type would otherwise drop a lever silently - the
    # row stays visible in the CSV while contributing nothing to the numbers.
    bad_type = raw.loc[~raw["Change Application Type"].isin(APPLICATION_TYPES)]
    if not bad_type.empty:
        raise ValueError(
            f"{schema_path}: unrecognised Change Application Type "
            f"{sorted(set(bad_type['Change Application Type']))}. "
            f"Expected one of {sorted(APPLICATION_TYPES)}."
        )

    scenarios: dict = {
        case: defaultdict(lambda: {"total_change": None, "efficiency": None, "penetration": {}})
        for case in SCENARIOS
    }
    for _, row in raw.iterrows():
        sector = scenarios[row["case"]][row["Sector"]]
        applied, category = row["Change Application Type"], row["Change Category"]

        if applied == PENETRATION:
            sector["penetration"][category] = _anchors(row)
        elif category == TOTAL_CHANGE:
            sector["total_change"] = _anchors(row)
        elif category == EFFICIENCY:
            sector["efficiency"] = _anchors(row)
        else:
            raise ValueError(
                f"{schema_path}: {applied} row with unrecognised Change Category "
                f"{category!r}. Expected {TOTAL_CHANGE!r} or {EFFICIENCY!r}."
            )

    scenarios = {case: dict(sectors) for case, sectors in scenarios.items()}
    _check_complete(scenarios, schema_path)
    return scenarios


def _check_complete(scenarios: dict, schema_path: str) -> None:
    """A lever missing from one case would surface much later as a silently
    null forecast, so it's worth failing loudly here instead.

    Every sector needs a Total Change. The activity sectors additionally need
    an Efficiency and at least one Penetration row - without those, step 4 has
    no intensity to apply and no deduction to make.
    """
    missing = []
    for case in SCENARIOS:
        for name in SECTOR_ORDER:
            sector = scenarios[case].get(name)
            if sector is None:
                missing.append(f"{case}/{name}: no rows at all")
                continue
            if sector["total_change"] is None:
                missing.append(f"{case}/{name}: no {TOTAL_CHANGE} row")
            if name in ACTIVITY_SECTORS:
                if sector["efficiency"] is None:
                    missing.append(f"{case}/{name}: no {EFFICIENCY} row")
                if not sector["penetration"]:
                    missing.append(f"{case}/{name}: no {PENETRATION} rows")
    if missing:
        raise ValueError(f"{schema_path}: incomplete schema - {missing}.")


if __name__ == "__main__":
    import sys

    config = default_scenarios(sys.argv[1] if len(sys.argv) > 1 else None)
    for case in SCENARIOS:
        print(f"\n== {case} ==")
        for name in SECTOR_ORDER:
            sector = config[case][name]
            print(f"  {name}")
            print(f"    total change: {sector['total_change']}")
            if sector["efficiency"] is not None:
                print(f"    efficiency:   {sector['efficiency']}")
            for lever, anchors in sector["penetration"].items():
                print(f"    {lever}: {anchors}")
