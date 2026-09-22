"""
Other Oil Consumption scenario forecasting model - the non-road sectors.

Sibling to the LDV and HDV models, but not built on forecast_model.py: the
shape is genuinely different. There are no regions and no powertrains, no
residual to reconcile against a total, and three lever types rather than two.
What is shared is the horizon (2025-2050), the three scenario cases, and the
anchor-year expansion rules - stepped for compounding levers, linearly
interpolated for penetration shares.

Four sectors, in two kinds:

* Shipping and Aviation are modelled through a physical activity base (tonne-km
  and passenger-km respectively) and an oil intensity per unit of that activity.
  Activity grows on its own YoY rate; intensity improves on an efficiency rate;
  and a share of the activity is taken to be served by something other than oil.
* Petrochemicals and Buildings/Power/Other have no activity measure. Their oil
  is compounded straight off its own prior-year value at the sector's YoY rate.

The five steps, for an activity sector:

    1. intensity[2024] = total liquids[2024] x share x 365000 / activity[2024]
    2. intensity[y]    = intensity[y-1] x (1 + efficiency)
    3. activity[y]     = activity[y-1] x (1 + YoY)
    4. oil[y]          = intensity[y] x activity[y] x (1 - sum penetration) / 365000
    5. oil[y]          = oil[y-1] x (1 + YoY)          - the other two sectors

Step 1 is the only place total liquids is used, and SECTOR_SHARE is the only
place the 7%/8% lives. Both exist purely to set the 2024 intensity; from 2025
intensity moves on efficiency alone. The 365000 converts between mb/d and the
per-unit-activity basis the intensity is quoted on, and step 4 divides it back
out, so steps 1 and 4 are exact inverses and 2024 round-trips unchanged.

Results are long dataframes, matching the LDV/HDV convention:
    sector | scenario | year | metric | value | data_type
`metric` is "oil" (mb/d), "activity" (bn tonne-km or bn passenger-km) or
"intensity".
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from forecast_model import ANCHOR_YEARS, FORECAST_START, FORECAST_YEARS, SCENARIOS
from other_oil_scenario_config import (
    ACTIVITY_SECTORS,
    SECTOR_ORDER,
    default_scenarios,
)

# The 2024 oil figures for Shipping and Aviation are fixed shares of total
# liquids - exactly 7% and 8% in every published year. That split is applied
# upstream, when the dataset is built, so these are here only to reproduce the
# same 2024 number inside step 1. Nothing downstream of step 1 uses them.
#
# Deliberately a constant rather than a schema input: it isn't a scenario
# lever, and it doesn't vary by case. If it ever needs to flex, it belongs in
# weo_other_oil_consumption.csv as its own Level, not here.
SECTOR_SHARE = {"Shipping": 0.07, "Aviation": 0.08}

# Converts a per-day oil figure onto the per-unit-activity basis the intensity
# is quoted on: 365 days, and the activity columns being in billions while the
# intensity is per thousand.
DAYS_PER_YEAR = 365
ACTIVITY_SCALE = DAYS_PER_YEAR * 1000

# The rows the model reads out of the source file. "Total"/"Oil" is total
# liquids - used once, for step 1, and never shown.
TOTAL_SECTOR = "Total"
OIL = "Oil"
ACTIVITY = "Activity"

# History earlier than this is dropped. Every sector has both oil and activity
# from 2022; before that the coverage is ragged (aviation oil starts 2019,
# activity 2022) and the charts would start at four different years.
HISTORY_START = 2022

_ANNUAL_COL = re.compile(r"^\d{4}$")


@dataclass
class OtherOilResults:
    """Long frames, one row per sector-scenario-year-metric.

    `consumption` is the headline oil series for all four sectors, in mb/d.
    `activity` is the physical base for Shipping and Aviation only.
    `intensity` is oil per unit of activity - computed because step 4 needs it,
    and carried here so it can be charted, though the page doesn't show it yet.
    """

    consumption: pd.DataFrame
    activity: pd.DataFrame
    intensity: pd.DataFrame

    @property
    def all_metrics(self) -> pd.DataFrame:
        """The three frames stacked - the shape the page filters and charts."""
        return pd.concat(
            [self.consumption, self.activity, self.intensity], ignore_index=True
        )


# ---------------------------------------------------------------------------
# Data load
# ---------------------------------------------------------------------------

def load_actuals(csv_path: str) -> pd.DataFrame:
    """Read the source CSV into sector | level | year | value.

    Only annual columns before FORECAST_START are kept - anything the source
    publishes for 2025+ is discarded and rebuilt by the scenarios. Blank cells
    become NaN rows and are dropped, which is what trims each series back to
    the years it actually covers.
    """
    raw = pd.read_csv(csv_path, encoding="utf-8-sig")
    missing = {"Sector", "Level"} - set(raw.columns)
    if missing:
        raise ValueError(f"{csv_path}: missing columns {sorted(missing)}.")

    year_cols = [
        c for c in raw.columns
        if _ANNUAL_COL.match(c.strip()) and int(c) < FORECAST_START
    ]
    if not year_cols:
        raise ValueError(f"{csv_path}: no annual columns before {FORECAST_START}.")

    long = raw.melt(
        id_vars=["Sector", "Level"], value_vars=year_cols,
        var_name="year", value_name="value",
    )
    long["year"] = long["year"].astype(int)
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    return (
        long.dropna(subset=["value"])
        .rename(columns={"Sector": "sector", "Level": "level"})
        .reset_index(drop=True)
    )


def _latest(actuals: pd.DataFrame, sector: str, level: str) -> tuple[int, float]:
    """(year, value) of the most recent actual for one series."""
    rows = actuals.loc[actuals["sector"].eq(sector) & actuals["level"].eq(level)]
    if rows.empty:
        raise ValueError(f"No actual {level} data for {sector}.")
    row = rows.loc[rows["year"].idxmax()]
    return int(row["year"]), float(row["value"])


# ---------------------------------------------------------------------------
# Scenario schedules
# ---------------------------------------------------------------------------

def _expand(anchors: dict[int, float], how: str) -> np.ndarray:
    """Expand a sparse {anchor year: value} schedule to every forecast year.

    how="stepped":      hold the value from the closest past (or equal) anchor.
                        Used for the compounding levers (YoY, PA), where each
                        year's rate applies for that year alone.
    how="interpolated": linear interpolation between anchors. Used for
                        penetration shares, which are levels rather than rates,
                        so the years between anchors have to ramp.

    The same rules as forecast_model._expand_scenario_rates, reimplemented here
    because that one is private to the vehicle engine and this model's
    schedules are keyed differently.
    """
    years = np.array(sorted(anchors))
    values = np.array([anchors[y] for y in years])

    if how == "interpolated":
        expanded = np.interp(FORECAST_YEARS, years, values)
    elif how == "stepped":
        expanded = values[(np.searchsorted(years, FORECAST_YEARS, side="right") - 1).clip(0)]
    else:
        raise ValueError(f"Unknown value expansion method: {how!r}")

    outside = (FORECAST_YEARS < years.min()) | (FORECAST_YEARS > years.max())
    return np.where(outside, np.nan, expanded)


def _deduction(sector_config: dict) -> np.ndarray:
    """The share of a sector's activity not served by oil, per forecast year.

    Every Penetration lever the sector has, summed. Selected on application
    type rather than by name, so the electrification lever can be "E-shipping"
    for one sector and "E-plane" for another, and adding a fourth lever is a
    schema edit rather than a code change.

    Not clamped: a schedule summing past 1 would give negative oil, which is
    left visible rather than silently floored while the sensible bounds are
    still being decided.
    """
    levers = sector_config["penetration"].values()
    return np.sum([_expand(anchors, "interpolated") for anchors in levers], axis=0)


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

def _series(sector: str, scenario: str, metric: str, years, values, last_actual: int) -> pd.DataFrame:
    """One sector-scenario-metric series as long rows, flagged actual/forecast."""
    return pd.DataFrame(
        {
            "sector": sector,
            "scenario": scenario,
            "metric": metric,
            "year": years,
            "value": values,
            "data_type": np.where(np.asarray(years) <= last_actual, "actual", "forecast"),
        }
    )


def _project_activity_sector(
    sector: str, scenario: str, config: dict, actuals: pd.DataFrame, total_liquids: float
) -> list[pd.DataFrame]:
    """Shipping or Aviation: steps 1-4. Returns [oil, activity, intensity]."""
    base_year, base_activity = _latest(actuals, sector, ACTIVITY)

    # Step 1. The one use of total liquids, and of the sector's fixed share.
    base_intensity = total_liquids * SECTOR_SHARE[sector] * ACTIVITY_SCALE / base_activity

    # Steps 2 and 3 - both compound their rate onto their own prior year.
    intensity = base_intensity * np.cumprod(1 + _expand(config["efficiency"], "stepped"))
    activity = base_activity * np.cumprod(1 + _expand(config["total_change"], "stepped"))

    # Step 4. The deduction is a level, not a rate, so it multiplies the year's
    # activity rather than compounding.
    oil = intensity * activity * (1 - _deduction(config)) / ACTIVITY_SCALE

    history = actuals.loc[actuals["sector"].eq(sector)]
    oil_history = history.loc[history["level"].eq(OIL)]
    activity_history = history.loc[history["level"].eq(ACTIVITY)]

    return [
        _series(sector, scenario, "oil",
                [*oil_history["year"], *FORECAST_YEARS],
                [*oil_history["value"], *oil], base_year),
        _series(sector, scenario, "activity",
                [*activity_history["year"], *FORECAST_YEARS],
                [*activity_history["value"], *activity], base_year),
        # Intensity has no history: it only exists from the year step 1 seeds
        # it, which is the last actual year.
        _series(sector, scenario, "intensity",
                [base_year, *FORECAST_YEARS],
                [base_intensity, *intensity], base_year),
    ]


def _project_oil_only_sector(
    sector: str, scenario: str, config: dict, actuals: pd.DataFrame
) -> list[pd.DataFrame]:
    """Petrochemicals or Buildings/Power/Other: step 5. Returns [oil]."""
    base_year, base_oil = _latest(actuals, sector, OIL)
    oil = base_oil * np.cumprod(1 + _expand(config["total_change"], "stepped"))

    history = actuals.loc[actuals["sector"].eq(sector) & actuals["level"].eq(OIL)]
    return [
        _series(sector, scenario, "oil",
                [*history["year"], *FORECAST_YEARS],
                [*history["value"], *oil], base_year)
    ]


def run_model(
    csv_path: str,
    *,
    schema_path: str | None = None,
    scenarios: dict | None = None,
    history_start: int = HISTORY_START,
) -> OtherOilResults:
    """Project all four sectors under all three scenario cases.

    `scenarios` defaults to the values parsed from the schema CSV, but can be
    overridden with a custom dict of the same shape (e.g. for a what-if
    sandbox). `schema_path` is only read when that default is actually needed.

    `history_start` trims the actuals shown; it does not affect the forecast,
    which always compounds off the last actual year whatever the trim.
    """
    if scenarios is None:
        scenarios = default_scenarios(schema_path)

    actuals = load_actuals(csv_path)
    _, total_liquids = _latest(actuals, TOTAL_SECTOR, OIL)

    frames = []
    for scenario in SCENARIOS:
        for sector in SECTOR_ORDER:
            config = scenarios[scenario][sector]
            if sector in ACTIVITY_SECTORS:
                frames += _project_activity_sector(
                    sector, scenario, config, actuals, total_liquids
                )
            else:
                frames += _project_oil_only_sector(sector, scenario, config, actuals)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.loc[combined["year"] >= history_start].reset_index(drop=True)
    combined["sector"] = pd.Categorical(combined["sector"], SECTOR_ORDER, ordered=True)
    combined = combined.sort_values(["scenario", "sector", "metric", "year"], ignore_index=True)

    def metric(name: str) -> pd.DataFrame:
        return combined.loc[combined["metric"].eq(name)].reset_index(drop=True)

    return OtherOilResults(
        consumption=metric("oil"), activity=metric("activity"), intensity=metric("intensity")
    )


def to_wide(tidy: pd.DataFrame) -> pd.DataFrame:
    """Pivot a long result to years-as-columns, for tables and export."""
    keys = [c for c in tidy.columns if c not in {"year", "value", "data_type"}]
    return (
        tidy.pivot_table(index=keys, columns="year", values="value",
                         dropna=False, observed=True)
        .reset_index()
        .rename_axis(columns=None)
    )


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    results = run_model(
        sys.argv[1] if len(sys.argv) > 1 else "input_data/weo_other_oil_consumption.csv",
        schema_path=(sys.argv[2] if len(sys.argv) > 2
                     else "input_data/other_oil_default_schema.csv"),
    )

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 250)

    show = [2022, 2024, 2025, 2030, 2035, 2040, 2045, 2050]
    for name, frame in [("Oil consumption (mb/d)", results.consumption),
                        ("Activity (bn tonne-km / bn passenger-km)", results.activity),
                        ("Intensity", results.intensity)]:
        print(f"\n== {name} ==")
        wide = to_wide(frame)
        print(wide[[c for c in wide.columns if not isinstance(c, int) or c in show]]
              .round(2).to_string(index=False))

    print("\n== Anchor years ==", ANCHOR_YEARS)
