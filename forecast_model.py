"""
Vehicle sales scenario forecasting engine, shared by the LDV and HDV models.

Takes model-level sales data (actuals up to FORECAST_START) and projects sales
to 2050 under Base, Faster and Slower scenarios. Everything that differs
between vehicle classes - which raw columns carry region and powertrain, how
those values bucket, and which powertrains are scenario-driven - is passed in
as a DataSpec; the maths below is identical for both.

Scenario schedules are defined at anchor years (see scenario_config.py for LDV,
hdv_scenario_config.py for HDV):
  * region level (all-vehicle) scenarios are YoY growth rates, stepped from the closest
    past anchor and compounded onto the region's own prior-year sales.
  * the modelled region+powertrain scenarios (BEV & PHEV for LDV, BEV alone for HDV)
    are penetration shares (of the region's all-vehicle sales), linearly interpolated
    between anchors and applied to the already-forecast region total - they are NOT
    compounded onto the powertrain's own prior-year sales.
  * the residual powertrain (IC Only) has no scenario config: actual years use the raw
    measured IC Only sales, and forecast years are the residual needed for the modelled
    powertrains plus IC Only to reconcile with the region's all-vehicle total.

Results are long dataframes - the best shape for web app filtering and charting:
    region | powertrain | scenario | year | sales | data_type
sales figures are in millions of vehicles throughout.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

# Both vehicle classes are forecast over the same horizon, and both scenario
# schedules anchor inside it, so these are shared rather than per-model.
FORECAST_START = 2025
FORECAST_END = 2050
FORECAST_YEARS = np.arange(FORECAST_START, FORECAST_END + 1)

# The three scenario cases, and the years a scenario schedule sets values at.
# Shared for the same reason.
SCENARIOS = ["Base Case", "Faster Transition", "Slower Transition"]
ANCHOR_YEARS = [2025, 2030, 2035, 2040, 2050]

# Used to identify only year cols (excluding monthly and quarterly cols)
_ANNUAL_COL = re.compile(r"^\d{4}$")


@dataclass
class ForecastResults:
    region_and_powertrain_sales: pd.DataFrame  # region x powertrain, all scenarios, incl. penetration & yoy_pct
    region_sales: pd.DataFrame      # region (all vehicles), all scenarios, incl. yoy_pct
    powertrain_sales: pd.DataFrame  # global totals per powertrain, all scenarios, incl. penetration & yoy_pct
    total_sales: pd.DataFrame       # global all-vehicle total, all scenarios, incl. yoy_pct


@dataclass(frozen=True)
class DataSpec:
    """How to read one vehicle class's raw sales extract.

    `region_col` is whichever raw column `bucket_region` needs: the LDV file
    carries usable regions in REGION, while the HDV scenarios split China and
    the USA out of their regions, so that one buckets from COUNTRY instead.

    `powertrain_buckets` maps raw powertrain values onto the model's own
    powertrain names. Anything unmapped (including blanks) is dropped outright,
    so it doesn't feature in region or total figures either.

    `modelled_powertrains` are the penetration-driven ones.
    `residual_powertrain` is derived by reconciliation instead - see
    _residual_powertrain_sales.

    `totals_include_unmapped` decides what the all-vehicle region totals mean
    for rows whose powertrain isn't in `powertrain_buckets`:

      True  - totals are every row in the file, so they really are "all
              vehicles of this class" even though the powertrain breakdown
              only covers the mapped ones. The breakdown then sums to less
              than the total in actual years, and the residual powertrain
              absorbs the difference in forecast years.
      False - totals count only the mapped rows, so the breakdown reconciles
              with them exactly in every year, but the totals exclude whatever
              the buckets leave out.
    """

    region_col: str
    powertrain_col: str
    bucket_region: Callable[[pd.Series], pd.Series]
    powertrain_buckets: dict[str, str]
    modelled_powertrains: tuple[str, ...]
    residual_powertrain: str
    encoding: str | None = None
    totals_include_unmapped: bool = False
    # {raw value in the source file: label to show it under} for powertrains
    # carried straight from the source rather than modelled - see
    # _source_other_sales. Empty means every powertrain is modelled.
    other_powertrains: tuple[tuple[str, str], ...] = ()


# ---------------------------------------------------------------------------
# Data Load & Clean
# ---------------------------------------------------------------------------

def load_actual_sales(csv_path: str, spec: DataSpec) -> pd.DataFrame:
    """Read the raw CSV and return standardised actual sales:
    region | powertrain | year | sales, one row per model-level record-year.
    Sales are in millions of vehicles.

    Rows whose powertrain isn't in spec.powertrain_buckets (including
    blank/unmapped values) are KEPT here, with powertrain set to NaN. Deciding
    what to do with them belongs to run_model, which drops them from the
    powertrain breakdown either way and counts them towards the all-vehicle
    region totals only when spec.totals_include_unmapped is set.

    #TODO = keep their projected sales for comparison
    Only annual columns before FORECAST_START are kept - the source file's own
    2025+ forecast is discarded and rebuilt by the scenarios.
    """
    header = pd.read_csv(csv_path, nrows=0, encoding=spec.encoding).columns
    actual_years = [
        c for c in header
        if _ANNUAL_COL.match(c.strip()) and int(c) < FORECAST_START
    ]

    raw = pd.read_csv(
        csv_path,
        usecols=[spec.region_col, spec.powertrain_col, *actual_years],
        encoding=spec.encoding,
        low_memory=False,
    )

    sales = pd.DataFrame(
        {
            "region": spec.bucket_region(raw[spec.region_col]),
            "powertrain": raw[spec.powertrain_col].map(spec.powertrain_buckets),
        }
    )
    sales[actual_years] = raw[actual_years].apply(pd.to_numeric, errors="coerce") / 1_000_000

    sales = sales.melt(
        id_vars=["region", "powertrain"], var_name="year", value_name="sales"
    )
    sales["year"] = sales["year"].astype(int)
    return sales


def load_source_powertrain_sales(
    csv_path: str, spec: DataSpec, raw_powertrains: tuple[str, ...]
) -> pd.DataFrame:
    """The source file's own published series for powertrains we don't model,
    exactly as it ships - every annual column it has, no scenario applied, no
    reconciliation, nothing rebuilt.

    This is the opposite of load_actual_sales, which throws the source's own
    2025+ figures away so the scenarios can rebuild them. Here they're the
    whole point: these powertrains have no scenario of ours to rebuild them
    with, so the only honest thing to show is what the publisher said.

    Note the series stops wherever the source file stops (2032 for LDV, 2037
    for HDV), well short of our own 2050 horizon - so a chart drawn from it
    ends early, on purpose.

    Returns: region | powertrain | year | sales | data_type
    powertrain keeps its raw source value; data_type is "actual" before
    FORECAST_START and "source forecast" from it on.
    """
    header = pd.read_csv(csv_path, nrows=0, encoding=spec.encoding).columns
    years = [c for c in header if _ANNUAL_COL.match(c.strip())]

    raw = pd.read_csv(
        csv_path,
        usecols=[spec.region_col, spec.powertrain_col, *years],
        encoding=spec.encoding,
        low_memory=False,
    )
    raw = raw.loc[raw[spec.powertrain_col].isin(raw_powertrains)]

    sales = pd.DataFrame(
        {
            "region": spec.bucket_region(raw[spec.region_col]),
            "powertrain": raw[spec.powertrain_col],
        },
        index=raw.index,
    )
    sales[years] = raw[years].apply(pd.to_numeric, errors="coerce") / 1_000_000

    sales = sales.melt(
        id_vars=["region", "powertrain"], var_name="year", value_name="sales"
    )
    sales["year"] = sales["year"].astype(int)
    sales = (
        sales.groupby(["region", "powertrain", "year"])["sales"].sum().reset_index()
    )
    sales["data_type"] = np.where(
        sales["year"] < FORECAST_START, "actual", "source forecast"
    )
    return sales


def _source_other_sales(
    csv_path: str,
    spec: DataSpec,
    region_sales: pd.DataFrame,
    scenarios: dict,
) -> pd.DataFrame:
    """The non-modelled powertrains, shaped like every other result frame so
    they can sit alongside the modelled ones.

    Their sales are the source file's published figures throughout - actuals
    and the publisher's own forward years alike. Nothing here is forecast by
    us: there is no scenario to apply, so the same values appear under all
    three cases, and the series simply stops where the source stops.

    Returns: region | powertrain | scenario | year | sales | data_type | penetration | yoy_pct
    """
    if not spec.other_powertrains:
        return pd.DataFrame(
            columns=["region", "powertrain", "scenario", "year", "sales",
                     "data_type", "penetration", "yoy_pct"]
        )

    labels = dict(spec.other_powertrains)
    out = load_source_powertrain_sales(csv_path, spec, tuple(labels)).drop(
        columns="data_type"
    )
    out["powertrain"] = out["powertrain"].map(labels)

    # Identical under every case - these figures aren't scenario-driven.
    out = out.merge(pd.DataFrame({"scenario": list(scenarios)}), how="cross")
    out["data_type"] = np.where(out["year"] < FORECAST_START, "actual", "forecast")

    region_all = region_sales[["region", "scenario", "year", "sales"]].rename(
        columns={"sales": "region_sales"}
    )
    out = out.merge(region_all, on=["region", "scenario", "year"], how="left")
    out["penetration"] = out["sales"] / out["region_sales"]
    out = out.drop(columns="region_sales")

    out = out.sort_values(
        ["region", "powertrain", "scenario", "year"], ignore_index=True
    )
    return _add_yoy_pct(out, ["region", "powertrain"])


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
    Contains complete self-contained series - the actual history plus the
    2025-2050 forecast. Groups with no configured scenario rates get null
    forecast sales.
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
    all-vehicle sales), linearly interpolated between anchors and multiplied onto
    `region_sales` for the matching region/scenario/year to derive forecast sales -
    NOT compounded onto the group's own prior-year sales.

    The `penetration` column itself is then derived uniformly across the whole
    series (actual and forecast alike) as sales / region_sales, rather than
    trusting the scenario value directly - it's equivalent for forecast rows since
    that's how their sales were built, and it's the only option for actual rows.

    Returns: *key_cols | scenario | year | sales | data_type | penetration | yoy_pct
    Contains complete self-contained series - the actual history plus the
    2025-2050 forecast. Groups with no configured penetration get null forecast
    sales.
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


def _residual_powertrain_sales(
    residual_actuals: pd.DataFrame,
    accounted_sales: pd.DataFrame,
    region_sales: pd.DataFrame,
    scenarios: dict,
    residual_powertrain: str,
) -> pd.DataFrame:
    """IC Only has no scenario config. Actual years use the raw measured IC Only
    sales from the CSV as-is. Forecast years have no raw data, so they're the
    residual needed for every other powertrain plus IC Only to reconcile with
    the region's all-vehicle total (this happens to equal the raw figure for
    actual years too, but actual years use the raw figure directly rather than
    relying on that).

    `accounted_sales` is every powertrain already established for those years -
    the modelled ones, plus any carried from the source (see
    _source_other_sales). Netting those off too is what stops IC Only quietly
    swallowing a powertrain that is shown separately: in a year where the
    source publishes FHEV, that volume belongs to FHEV, not to IC Only. Where
    the source stops publishing one, it has no rows, so the residual takes it
    back - which is the only thing it can do without inventing a forecast.

    Returns: region | powertrain | scenario | year | sales | data_type | penetration | yoy_pct
    """
    history = residual_actuals.merge(
        pd.DataFrame({"scenario": list(scenarios)}), how="cross"
    )
    history["data_type"] = "actual"

    accounted_forecast_total = (
        accounted_sales.loc[accounted_sales["data_type"].eq("forecast")]
        .groupby(["region", "scenario", "year"])["sales"]
        .sum()
        .reset_index()
        .rename(columns={"sales": "accounted_sales"})
    )
    forecast = (
        region_sales.loc[
            region_sales["data_type"].eq("forecast"), ["region", "scenario", "year", "sales"]
        ]
        .rename(columns={"sales": "region_sales"})
        .merge(accounted_forecast_total, on=["region", "scenario", "year"], how="left")
    )
    forecast["powertrain"] = residual_powertrain
    # A year the source no longer covers contributes nothing to net off.
    forecast["sales"] = forecast["region_sales"] - forecast["accounted_sales"].fillna(0.0)
    # Where a scenario drives the modelled powertrains to the whole market
    # while the source still publishes volume for one it doesn't model, the
    # inputs contradict each other and this would go slightly negative. Sales
    # can't be negative, so it floors at zero - at the cost of that cell's
    # powertrains summing a little above the all-vehicle total.
    forecast["sales"] = forecast["sales"].clip(lower=0.0)
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
    """All-vehicle sales, summed across whatever regions are present in the
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
    spec: DataSpec,
    region_scenarios: dict,
    region_powertrain_scenarios: dict,
) -> ForecastResults:
    """Run one vehicle class's forecast. The two scenario dicts are the anchor
    schedules to project under - either that model's own defaults or a saved
    scenario's edited values."""
    sales = load_actual_sales(csv_path, spec)

    # The powertrain breakdown only ever covers the mapped powertrains. The
    # all-vehicle region totals are a separate question - see
    # DataSpec.totals_include_unmapped.
    mapped = sales.dropna(subset=["powertrain"])
    totals_source = sales if spec.totals_include_unmapped else mapped

    by_region_and_powertrain = (
        mapped.groupby(["region", "powertrain", "year"])["sales"].sum().reset_index()
    )
    by_region = totals_source.groupby(["region", "year"])["sales"].sum().reset_index()

    region_sales = _project_yoy(
        by_region, region_scenarios,
        key_cols=["region"], how="stepped",
    )
    total_sales = aggregate_total_sales(region_sales)

    modelled_actuals = by_region_and_powertrain.loc[
        by_region_and_powertrain["powertrain"].isin(spec.modelled_powertrains)
    ]
    modelled_sales = _project_penetration(
        modelled_actuals, region_sales, region_powertrain_scenarios,
        key_cols=["region", "powertrain"],
    )

    # Carried from the source, not modelled - but established before the
    # residual, so the residual can net them off instead of absorbing them.
    other_sales = _source_other_sales(
        csv_path, spec, region_sales, region_powertrain_scenarios
    )
    accounted = (
        pd.concat([modelled_sales, other_sales], ignore_index=True)
        if not other_sales.empty
        else modelled_sales
    )

    residual_actuals = by_region_and_powertrain.loc[
        by_region_and_powertrain["powertrain"].eq(spec.residual_powertrain)
    ]
    residual_sales = _residual_powertrain_sales(
        residual_actuals, accounted, region_sales,
        region_powertrain_scenarios, spec.residual_powertrain,
    )

    region_and_powertrain_sales = pd.concat(
        [modelled_sales, other_sales, residual_sales], ignore_index=True
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
