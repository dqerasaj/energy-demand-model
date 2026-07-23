"""
LDV sales scenario forecasting model.

Takes global vehicle model-level LDV sales data (actuals up to 2024), and projects sales to 2050 under Base, Faster and Slower scenarios.
Only BEV, PHEV and IC Only powertrains are modelled - other/blank powertrain values are dropped entirely at load time.
Scenario schedules are defined at anchor years (see scenario_config.py):
  * region level (all-LDV) scenarios are YoY growth rates, stepped from the closest past anchor
    and compounded onto the region's own prior-year sales.
  * BEV & PHEV region+powertrain scenarios are penetration shares (of the region's all-LDV sales),
    linearly interpolated between anchors and applied to the already-forecast region total -
    they are NOT compounded onto the powertrain's own prior-year sales.
  * IC Only has no scenario config: actual years use the raw measured IC Only sales, and
    forecast years are the residual needed for BEV + PHEV + IC Only to reconcile with the
    region's all-LDV total.

Results are long dataframes - the best shape for web app filtering and charting:
    region | powertrain | scenario | year | sales | data_type
sales figures are in millions of vehicles throughout.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from scenario_config import (
    FORECAST_END,
    FORECAST_START,
    BASE_POWERTRAIN_AND_REGION_SCENARIOS,
    BASE_REGION_SCENARIOS,
)


# ---------------------------------------------------------------------------
# Constraints & Mappings
# ---------------------------------------------------------------------------

@dataclass
class ForecastResults:
    region_and_powertrain_sales: pd.DataFrame  # region x powertrain, all scenarios, incl. penetration & yoy_pct
    region_sales: pd.DataFrame      # region (all LDVs), all scenarios, incl. yoy_pct
    powertrain_sales: pd.DataFrame  # global totals per powertrain, all scenarios, incl. penetration & yoy_pct
    total_sales: pd.DataFrame       # global all-LDV total, all scenarios, incl. yoy_pct


RAW_REGION_COL = "REGION"
RAW_POWERTRAIN_COL = "HYBRID & EV TYPE"
_ANNUAL_COL = re.compile(r"^\d{4}$")  # Used to identify only year col (excluding monthly and quarterly cols)
FORECAST_YEARS = np.arange(FORECAST_START, FORECAST_END + 1)

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


# ---------------------------------------------------------------------------
# Data Load & Clean
# ---------------------------------------------------------------------------

def load_actual_sales(csv_path: str) -> pd.DataFrame:
    """Read the raw CSV and return standardised actual sales:
    region | powertrain | year | sales, one row per model-level record-year.
    Sales are in millions of vehicles.

    Rows whose powertrain isn't BEV, PHEV or IC Only (including blank/unmapped values)
    are dropped entirely - they don't feature in region or total figures either.

    #TODO = keep their projected sales for comparison
    Only annual columns before FORECAST_START are kept - the source file's own 2025+ forecast is discarded and rebuilt by the scenarios.
    """
    header = pd.read_csv(csv_path, nrows=0).columns
    actual_years = [
        c for c in header
        if _ANNUAL_COL.match(c.strip()) and int(c) < FORECAST_START
    ]

    raw = pd.read_csv(
        csv_path, usecols=[RAW_REGION_COL, RAW_POWERTRAIN_COL, *actual_years]
    )

    sales = pd.DataFrame(
        {
            "region": bucket_region(raw[RAW_REGION_COL]),
            "powertrain": raw[RAW_POWERTRAIN_COL].map(POWERTRAIN_BUCKETS),
        }
    )
    sales[actual_years] = raw[actual_years].apply(pd.to_numeric, errors="coerce") / 1_000_000
    sales = sales.dropna(subset=["powertrain"])

    sales = sales.melt(
        id_vars=["region", "powertrain"], var_name="year", value_name="sales"
    )
    sales["year"] = sales["year"].astype(int)
    return sales


# ---------------------------------------------------------------------------
# Scenario rate schedules
# ---------------------------------------------------------------------------

def _expand_scenario_rates(anchors: dict[int, float], how: str) -> np.ndarray:
    """Expand a sparse {anchor_year: value} schedule to every forecast year.
    Used both for YoY growth rates and for penetration shares.

    how="interpolated": linear interpolation between anchors.
    how="stepped":      hold the value from the closest past (or equal) anchor.

    Years outside the anchor range are NaN (no extrapolation).
    """
    years = np.array(sorted(anchors))
    values = np.array([anchors[y] for y in years])

    if how == "interpolated":
        expanded = np.interp(FORECAST_YEARS, years, values)
    elif how == "stepped":
        idx = np.searchsorted(years, FORECAST_YEARS, side="right") - 1
        expanded = np.where(idx >= 0, values[idx.clip(0)], np.nan)
    else:
        raise ValueError(f"Unknown value expansion method: {how!r}")

    outside = (FORECAST_YEARS < years.min()) | (FORECAST_YEARS > years.max())
    return np.where(outside, np.nan, expanded)


def _flatten_scenario_rates(
    scenarios: dict, key_cols: list[str], how: str
) -> pd.DataFrame:
    """Flatten nested scenario config into a tidy table:
    *key_cols | scenario | year | value."""
    records = []
    for scenario, groups in scenarios.items():
        for key, anchors in groups.items():
            key = key if isinstance(key, tuple) else (key,)
            values = _expand_scenario_rates(anchors, how)
            records.append(
                pd.DataFrame(
                    {
                        **dict(zip(key_cols, key)),
                        "scenario": scenario,
                        "year": FORECAST_YEARS,
                        "value": values,
                    }
                )
            )
    if not records:
        return pd.DataFrame(
            {
                **{c: pd.Series(dtype=str) for c in key_cols},
                "scenario": pd.Series(dtype=str),
                "year": pd.Series(dtype=int),
                "value": pd.Series(dtype=float),
            }
        )
    return pd.concat(records, ignore_index=True)


# ---------------------------------------------------------------------------
# Forecasting engine
# ---------------------------------------------------------------------------

def _add_yoy_pct(df: pd.DataFrame, key_cols: list[str]) -> pd.DataFrame:
    """Add a yoy_pct column: sales % change vs. the prior year within each series.
    First year in timeseries is NaN."""
    df["yoy_pct"] = (
        df.groupby([df[c] for c in (*key_cols, "scenario")])["sales"]
        .pct_change(fill_method=None)
    )
    return df


def _project_yoy(
    actuals: pd.DataFrame,
    scenarios: dict,
    key_cols: list[str],
    how: str,
) -> pd.DataFrame:
    """Compound scenario YoY rates onto each group's last actual value.

    Returns: *key_cols | scenario | year | sales | data_type | yoy_pct
    Contains complete self-contained series - the actual history plus the 2025-2050 forecast.
    Groups with no configured scenario rates get null forecast sales.
    """
    rates = _flatten_scenario_rates(scenarios, key_cols, how).rename(columns={"value": "rate"})

    # growth factor = cumulative product of (1 + rate) within each series
    rates["factor"] = (
        (1.0 + rates["rate"])
        .groupby([rates[c] for c in (*key_cols, "scenario")])
        .cumprod()
    )

    base = (
        actuals.loc[actuals["year"].eq(actuals["year"].max())]
        .drop(columns="year")
        .rename(columns={"sales": "base_sales"})
    )

    # every group appears under every scenario; missing rates -> null sales
    forecast = (
        base.merge(pd.DataFrame({"scenario": list(scenarios)}), how="cross")
        .merge(pd.DataFrame({"year": FORECAST_YEARS}), how="cross")
        .merge(rates, on=[*key_cols, "scenario", "year"], how="left")
    )
    forecast["sales"] = forecast["base_sales"] * forecast["factor"]
    forecast["data_type"] = "forecast"

    history = actuals.merge(
        pd.DataFrame({"scenario": list(scenarios)}), how="cross"
    )
    history["data_type"] = "actual"

    out = pd.concat(
        [history, forecast[[*key_cols, "scenario", "year", "sales", "data_type"]]],
        ignore_index=True,
    ).sort_values([*key_cols, "scenario", "year"], ignore_index=True)

    return _add_yoy_pct(out, key_cols)


def _project_penetration(
    actuals: pd.DataFrame,
    region_sales: pd.DataFrame,
    scenarios: dict,
    key_cols: list[str],
) -> pd.DataFrame:
    """Apply penetration-share scenarios on top of already-forecast region totals.

    Anchor values in `scenarios` are penetration shares (fraction of the region's
    all-LDV sales), linearly interpolated between anchors and multiplied onto
    `region_sales` for the matching region/scenario/year to derive forecast sales -
    NOT compounded onto the group's own prior-year sales.

    The `penetration` column itself is then derived uniformly across the whole
    series (actual and forecast alike) as sales / region_sales, rather than
    trusting the scenario value directly - it's equivalent for forecast rows since
    that's how their sales were built, and it's the only option for actual rows.

    Returns: *key_cols | scenario | year | sales | data_type | penetration | yoy_pct
    Contains complete self-contained series - the actual history plus the 2025-2050 forecast.
    Groups with no configured penetration get null forecast sales.
    """
    region_key = "region"
    penetration_schedule = _flatten_scenario_rates(scenarios, key_cols, how="interpolated").rename(
        columns={"value": "penetration"}
    )

    groups = actuals[key_cols].drop_duplicates()

    region_forecast = (
        region_sales.loc[
            region_sales["data_type"].eq("forecast"),
            [region_key, "scenario", "year", "sales"],
        ]
        .rename(columns={"sales": "region_sales"})
    )

    # every group appears under every scenario; missing penetration -> null sales
    forecast = (
        groups.merge(pd.DataFrame({"scenario": list(scenarios)}), how="cross")
        .merge(pd.DataFrame({"year": FORECAST_YEARS}), how="cross")
        .merge(penetration_schedule, on=[*key_cols, "scenario", "year"], how="left")
        .merge(region_forecast, on=[region_key, "scenario", "year"], how="left")
    )
    forecast["sales"] = forecast["region_sales"] * forecast["penetration"]
    forecast["data_type"] = "forecast"

    history = actuals.merge(
        pd.DataFrame({"scenario": list(scenarios)}), how="cross"
    )
    history["data_type"] = "actual"

    out = pd.concat(
        [
            history[[*key_cols, "scenario", "year", "sales", "data_type"]],
            forecast[[*key_cols, "scenario", "year", "sales", "data_type"]],
        ],
        ignore_index=True,
    ).sort_values([*key_cols, "scenario", "year"], ignore_index=True)

    region_all = region_sales[[region_key, "scenario", "year", "sales"]].rename(
        columns={"sales": "region_sales"}
    )
    out = out.merge(region_all, on=[region_key, "scenario", "year"], how="left")
    out["penetration"] = out["sales"] / out["region_sales"]
    out = out.drop(columns="region_sales")

    return _add_yoy_pct(out, key_cols)


def _residual_ic_only(
    ic_only_actuals: pd.DataFrame,
    modeled_sales: pd.DataFrame,
    region_sales: pd.DataFrame,
    scenarios: dict,
) -> pd.DataFrame:
    """IC Only has no scenario config. Actual years use the raw measured IC Only
    sales from the CSV as-is. Forecast years have no raw data, so they're the
    residual needed for BEV + PHEV + IC Only to reconcile with the region's
    all-LDV total (this happens to equal the raw figure for actual years too,
    but actual years use the raw figure directly rather than relying on that).

    Returns: region | powertrain | scenario | year | sales | data_type | penetration | yoy_pct
    """
    history = ic_only_actuals.merge(
        pd.DataFrame({"scenario": list(scenarios)}), how="cross"
    )
    history["data_type"] = "actual"

    modeled_forecast_total = (
        modeled_sales.loc[modeled_sales["data_type"].eq("forecast")]
        .groupby(["region", "scenario", "year"])["sales"]
        .sum()
        .reset_index()
        .rename(columns={"sales": "modeled_sales"})
    )
    forecast = (
        region_sales.loc[
            region_sales["data_type"].eq("forecast"), ["region", "scenario", "year", "sales"]
        ]
        .rename(columns={"sales": "region_sales"})
        .merge(modeled_forecast_total, on=["region", "scenario", "year"], how="left")
    )
    forecast["powertrain"] = "IC Only"
    forecast["sales"] = forecast["region_sales"] - forecast["modeled_sales"]
    forecast["data_type"] = "forecast"

    out = pd.concat(
        [
            history[["region", "powertrain", "scenario", "year", "sales", "data_type"]],
            forecast[["region", "powertrain", "scenario", "year", "sales", "data_type"]],
        ],
        ignore_index=True,
    ).sort_values(["region", "powertrain", "scenario", "year"], ignore_index=True)

    region_all = region_sales[["region", "scenario", "year", "data_type", "sales"]].rename(
        columns={"sales": "region_sales"}
    )
    out = out.merge(region_all, on=["region", "scenario", "year", "data_type"], how="left")
    out["penetration"] = out["sales"] / out["region_sales"]
    out = out.drop(columns="region_sales")

    return _add_yoy_pct(out, ["region", "powertrain"])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def aggregate_powertrain_sales(region_and_powertrain_sales: pd.DataFrame) -> pd.DataFrame:
    """Sales per powertrain, summed across whatever regions are present in
    the input - pass the full region_and_powertrain_sales for the true global
    figure, or a region/powertrain-filtered subset to get a rollup scoped to
    just that subset (e.g. for a filtered dashboard view).

    Returns: powertrain | scenario | year | sales | data_type | penetration | yoy_pct
    penetration = that powertrain's share of the summed total for the same
    scenario/year/data_type (i.e. relative to whatever's in the input, not
    necessarily the true global total).
    """
    out = (
        region_and_powertrain_sales
        .groupby(["powertrain", "scenario", "year", "data_type"])["sales"]
        .sum()
        .reset_index()
        .sort_values(["powertrain", "scenario", "year"], ignore_index=True)
    )
    total = out.groupby(["scenario", "year", "data_type"])["sales"].transform("sum")
    out["penetration"] = out["sales"] / total

    return _add_yoy_pct(out, ["powertrain"])


def aggregate_total_sales(region_sales: pd.DataFrame) -> pd.DataFrame:
    """All-LDV sales, summed across whatever regions are present in the
    input - pass the full region_sales for the true global figure, or a
    region-filtered subset to get a rollup scoped to just that subset.
    Actual-year sales are identical across scenarios (only forecast years
    diverge), same as region_sales itself.

    Returns: scenario | year | sales | data_type | yoy_pct
    """
    out = (
        region_sales
        .groupby(["scenario", "year", "data_type"])["sales"]
        .sum()
        .reset_index()
        .sort_values(["scenario", "year"], ignore_index=True)
    )
    return _add_yoy_pct(out, [])


def run_model(
    csv_path: str,
    *,
    region_scenarios: dict | None = None,
    region_powertrain_scenarios: dict | None = None,
) -> ForecastResults:
    """`region_scenarios`/`region_powertrain_scenarios` default to the
    scenario_config.py constants, but can be overridden with a custom
    scenario dict of the same shape (e.g. for a what-if sandbox)."""
    if region_scenarios is None:
        region_scenarios = BASE_REGION_SCENARIOS
    if region_powertrain_scenarios is None:
        region_powertrain_scenarios = BASE_POWERTRAIN_AND_REGION_SCENARIOS

    sales = load_actual_sales(csv_path)

    by_region_and_powertrain = (
        sales.groupby(["region", "powertrain", "year"])["sales"].sum().reset_index()
    )
    by_region = sales.groupby(["region", "year"])["sales"].sum().reset_index()

    region_sales = _project_yoy(
        by_region, region_scenarios,
        key_cols=["region"], how="stepped",
    )
    total_sales = aggregate_total_sales(region_sales)

    modeled_actuals = by_region_and_powertrain.loc[
        by_region_and_powertrain["powertrain"].isin(["BEV", "PHEV"])
    ]
    modeled_sales = _project_penetration(
        modeled_actuals, region_sales, region_powertrain_scenarios,
        key_cols=["region", "powertrain"],
    )

    ic_only_actuals = by_region_and_powertrain.loc[
        by_region_and_powertrain["powertrain"].eq("IC Only")
    ]
    ic_only_sales = _residual_ic_only(
        ic_only_actuals, modeled_sales, region_sales, region_powertrain_scenarios,
    )

    region_and_powertrain_sales = pd.concat(
        [modeled_sales, ic_only_sales], ignore_index=True
    ).sort_values(["region", "powertrain", "scenario", "year"], ignore_index=True)

    powertrain_sales = aggregate_powertrain_sales(region_and_powertrain_sales)

    return ForecastResults(
        region_and_powertrain_sales=region_and_powertrain_sales,
        region_sales=region_sales,
        powertrain_sales=powertrain_sales,
        total_sales=total_sales,
    )


def to_wide(tidy: pd.DataFrame) -> pd.DataFrame:
    """Pivot a tidy result's sales to years-as-columns for inspection/export.
    Drops any non-sales metric columns (e.g. yoy_pct, penetration)."""
    non_key_cols = {"year", "sales", "data_type", "yoy_pct", "penetration"}
    keys = [c for c in tidy.columns if c not in non_key_cols]
    return (
        tidy.pivot_table(index=keys, columns="year", values="sales", dropna=False)
        .reset_index()
        .rename_axis(columns=None)
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