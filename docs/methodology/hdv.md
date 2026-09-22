## Purpose

The HDV Model projects annual heavy duty vehicle volumes, meaning medium trucks, heavy trucks, and buses and coaches, from 2025 to 2050 for three regions: **China**, the **USA** and the **Rest of World (RoW)**. Its main question is: *how fast do battery electric trucks and buses take over from diesel, and how big is the overall market?*

It uses **exactly the same forecasting method as the LDV Model**. The differences are the regions, the powertrains and where the default assumptions come from.

## Input data

**Source: GlobalData medium and heavy commercial vehicle extract** (`globaldata_hdv_sales.csv`).

- Covers vehicles over 6 tonnes: heavy trucks (15 t+), medium trucks (6–15 t), and buses and coaches (6 t+).
- The extract is labelled **"Production (GlobalData)"**, so volumes are **vehicles produced**, recorded against the **country where they're built**. The dashboard labels them "sales". For an exporting or importing country, production and sales can differ significantly.
- The extract covers **2020–2037**. The model uses **2020–2024 as actuals** and discards GlobalData's own 2025–2037 forecast, except for the powertrains it doesn't forecast (see below). The fiscal-year columns are ignored.
- Three fields are used: `COUNTRY`, `POWERTRAIN TYPE` and the annual volumes. Volumes are converted to millions of vehicles.

**Default assumptions:** `hdv_default_schema.csv`, a small table of anchor-year percentages for each case, region and assumption type. Editing that file changes the Default Scenario.

### Region mapping

Regions come from the `COUNTRY` column. The extract's own `REGION` column only holds continents (for example, Asia-Pacific), with no separate China or USA.

| GlobalData `COUNTRY` | Model region |
| --- | --- |
| China | China |
| USA | USA |
| every other country, including GlobalData's "Other" group | RoW |

### Powertrain mapping

| GlobalData `POWERTRAIN TYPE` | Model powertrain | Why |
| --- | --- | --- |
| Electric | **BEV** | Battery electric and fuel cell, consistent with the LDV Model |
| ICE | **IC Only** | Conventional combustion engine |
| ICE-Hybrid | **ICE Hybrids**, not forecast | Shown from GlobalData's own figures (see below) |
| H2 ICE (hydrogen combustion) | **H2 Hybrids**, not forecast | Shown from GlobalData's own figures (see below) |

There's **no PHEV** in the HDV Model: BEV is the only powertrain driven by scenario assumptions.

## How the forecast is calculated

The calculation is the one described in detail in the **LDV Model** tab, run separately for each region and each scenario case:

1. **All-HDV total, actuals.** Every vehicle in the extract counts towards its region's total, whatever its powertrain.
2. **All-HDV total, forecast.** The 2024 total grows at the year-on-year rate in the **Total HDVs** table, stepped between anchor years and compounded:
   $$\text{Total}_{y} = \text{Total}_{y-1} \times (1 + g_{y})$$
3. **BEV.** A share of each year's forecast total. The **BEV** penetration percentages are interpolated in a straight line between anchor years:
   $$\text{BEV}_{y} = \text{Total}_{y} \times p^{\text{BEV}}_{y}$$
4. **IC Only.** The residual, after the powertrains GlobalData publishes are netted off:
   $$\text{IC Only}_{y} = \text{Total}_{y} - \text{BEV}_{y} - \text{ICE Hybrids}_{y} - \text{H2 Hybrids}_{y}$$
   This is set to zero if it would be negative.

### ICE Hybrids and H2 Hybrids

These aren't forecast by this model. Their figures come **directly from GlobalData**, including GlobalData's own forecast years, are the same in every scenario case, and **stop in 2037**, where the extract ends. They're hidden by default. Tick **"Include ICE Hybrids and H2 Hybrids (not forecast by this model)"** on the Forecasts page to show them. As with LDV full hybrids, they're always netted off before IC Only is calculated, and from 2038 IC Only takes their volume back. Both are a very small share of the market (well under 1% in 2024).

## Reading the scenario configuration

| Table | Values mean | Filled between anchors by |
| --- | --- | --- |
| **BEV** | % of the region's all-HDV volume that is BEV | straight-line interpolation |
| **Total HDVs** | year-on-year % growth in the region's all-HDV volume | stepped |

**The Default Scenario** uses the same all-HDV growth rates in all three cases (for example, China grows 7% a year from 2025, easing to 2.5% from 2035). The cases differ only in **BEV penetration**. In every case and region BEV reaches **100% by 2050**. The cases differ in how quickly it gets there, and Faster Transition reaches 100% in China by 2035.

## Assumptions

- **Same core assumptions as the LDV Model.** 2024 is the last actual year, market size and powertrain split are independent, growth rates compound and shares don't.
- **"Electric" is treated as BEV**, fuel cell trucks and buses included.
- **Trucks and buses share one set of assumptions.** A region's BEV share applies to medium trucks, heavy trucks and buses alike.
- **RoW is everything outside China and the USA**, including Europe, India and Japan, under one set of assumptions.

## Limitations

- **Production, not sales.** Volumes are attributed to the country where vehicles are built. This matters for the USA and China, where exports and imports mean domestic production can differ from domestic sales.
- **A jump at 2025 is possible.** The 2025 BEV anchor sets the 2025 share directly. If it differs from the actual 2024 share, BEV and IC Only jump between 2024 and 2025.
- **A small step in IC Only at 2038**, when the hybrid figures stop. It's small because hybrids are a small share of the market.
- **IC Only reaches zero in 2050** under every case of the Default Scenario, because BEV reaches 100% everywhere.
- **Shares aren't capped.** Values above 100% can be entered; IC Only is then set to zero and the powertrains add up to more than the total.
- **RoW is very broad.** It covers about half of heavy vehicle volume with a single set of assumptions.
- **No segment detail.** Medium trucks, heavy trucks and buses electrify at very different speeds in practice, but the model applies one share to all of them.
- **Sales, not fleet or fuel.** The model projects new vehicles per year, not the vehicle stock or its oil use.
