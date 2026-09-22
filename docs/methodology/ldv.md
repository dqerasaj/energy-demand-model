## Purpose

The LDV Model projects annual light duty vehicle volumes from 2025 to 2050 for four regions, broken down by powertrain. Its main question is: *how fast do battery electric and plug-in hybrid vehicles take over from combustion engines, and how big is the overall market?*

It answers that with two separate kinds of assumption:

- **how big the market is.** Total vehicles per region, driven by a year-on-year growth rate.
- **how the market is split.** The share of those vehicles that are BEV and PHEV, driven by penetration percentages. Conventional vehicles (IC Only) make up the remainder.

## Input data

**Source: GlobalData light vehicle extract** (`globaldata_ldv_sales.csv`).

- Each row is one vehicle model at one vehicle plant, with an annual volume per year. Covers vehicles up to 6 tonnes gross vehicle weight, personal and commercial.
- The extract covers **2020–2032**. The model uses **2020–2024 as actuals** and discards GlobalData's own 2025–2032 forecast, except for full hybrids (see below). Monthly columns are ignored.
- Three fields are used: `REGION`, `HYBRID & EV TYPE` and the annual volumes. Volumes are converted to millions of vehicles.

**Volumes are recorded by vehicle plant.** Because every row is tied to the plant that builds the vehicle, regions reflect **where vehicles are built**, and the volumes are effectively production. The dashboard labels them "sales". For a region that exports or imports many vehicles, production and sales can differ significantly.

### Region mapping

| GlobalData `REGION` | Model region |
| --- | --- |
| North America | North America |
| Western Europe, Eastern Europe (any region containing "Europe") | Europe |
| Asia-Pacific | APAC |
| South America, Africa, Middle East, and anything else | RoW |

### Powertrain mapping

| GlobalData `HYBRID & EV TYPE` | Model powertrain | Why |
| --- | --- | --- |
| BEV | **BEV** | Battery electric |
| EREV (range-extended electric) | **BEV** | Driven by an electric motor on grid electricity |
| FCEV, PFCEV (fuel cell) | **BEV** | Electric drive with no combustion engine; volumes are negligible |
| PHEV | **PHEV** | Has its own scenario assumptions |
| IC Only | **IC Only** | Conventional combustion engine |
| MHEV, MHEV (48V) (mild hybrids) | **IC Only** | Engine-driven; the electric assist can't drive the vehicle on its own |
| FHEV (full hybrid) | **FHEV**, not forecast | Neither scenario-driven nor really IC Only; shown from GlobalData's own figures (see below). Roughly 7% of 2024 volume |
| blank or unrecognised | none | Counted in the all-LDV totals only |

## How the forecast is calculated

The same calculation runs separately for each **region** and each **scenario case**. There are four steps.

### Step 1: All-LDV total per region (actuals)

Every vehicle in the extract counts towards its region's all-LDV total, **whatever its powertrain**, including FHEV and any unmapped rows. So in actual years, BEV + PHEV + IC Only add up to *less* than the all-LDV total, and FHEV and unmapped vehicles make up the difference.

### Step 2: Forecast the all-LDV total (the "Total LDVs" table)

The all-LDV total grows from its 2024 value at the **year-on-year growth rate** in the *Total LDVs* table. Rates are **stepped** between anchor years and **compounded**:

$$
\text{Total}_{y} = \text{Total}_{y-1} \times (1 + g_{y})
$$

where $g_y$ is the growth rate from the most recent anchor year at or before $y$ (the 2025 rate applies to 2025–2029, the 2030 rate to 2030–2034, and so on). The first forecast year, 2025, grows from the 2024 actual.

### Step 3: Forecast BEV and PHEV (the "BEV" and "PHEV" tables)

BEV and PHEV are a **share of that year's all-LDV total**. The penetration percentages in the *BEV* and *PHEV* tables are **interpolated in a straight line** between anchor years and applied to the forecast total from Step 2:

$$
\text{BEV}_{y} = \text{Total}_{y} \times p^{\text{BEV}}_{y}
\qquad
\text{PHEV}_{y} = \text{Total}_{y} \times p^{\text{PHEV}}_{y}
$$

These shares are *not* compounded on the previous year's BEV or PHEV volume. Each year's volume depends only on that year's total and that year's share.

### Step 4: IC Only is whatever remains

IC Only has no assumptions of its own. In forecast years it's the **residual**: the all-LDV total minus every powertrain already accounted for:

$$
\text{IC Only}_{y} = \text{Total}_{y} - \text{BEV}_{y} - \text{PHEV}_{y} - \text{FHEV}_{y}
$$

where $\text{FHEV}_y$ is GlobalData's published full hybrid figure for that year (up to 2032, then zero). So all powertrains always add up to the all-LDV total in forecast years. If the result would be negative, it's set to zero (see Limitations).

In actual years, IC Only is the measured volume from the extract.

### Full hybrids (FHEV)

FHEV isn't forecast by this model. Its figures come **directly from GlobalData**, including GlobalData's own forecast years, are identical in all three scenario cases, and **stop in 2032**, where the extract ends. It's hidden by default. Tick **"Include FHEV (not forecast by this model)"** on the Forecasts page to show it.

Whether it's shown or not, FHEV volume is always **netted off before IC Only is calculated**, so IC Only never absorbs volume that belongs to FHEV. From 2033, with no FHEV figures left, IC Only takes that volume back.

### Global figures

Global figures (and every "Global" row or line) are **sums of the regions**. Global penetration shares are recalculated from those sums, so they're a volume-weighted average of the regional shares, not a simple average.

### Worked example (illustrative numbers)

Take one region with a 2024 all-LDV total of **10.0 million**, a Total LDVs growth rate of **2%** at 2025 and **1%** at 2030, BEV penetration of **15%** at 2025 and **45%** at 2030, PHEV penetration of **5%** throughout, and a published FHEV figure of **0.8 million** in 2027.

| 2027 | Calculation | Result (million) |
| --- | --- | --- |
| All-LDV total | 10.0 × 1.02 × 1.02 × 1.02 (the 2025 rate applies through 2029) | 10.612 |
| BEV share | 15% + (45% − 15%) × 2⁄5 (two-fifths of the way from 2025 to 2030) | 27% |
| BEV | 10.612 × 27% | 2.865 |
| PHEV | 10.612 × 5% | 0.531 |
| FHEV | from GlobalData | 0.800 |
| IC Only | 10.612 − 2.865 − 0.531 − 0.800 | 6.416 |

## Reading the scenario configuration

| Table | Values mean | Filled between anchors by | Drives |
| --- | --- | --- | --- |
| **BEV** | % of the region's all-LDV volume that is BEV | straight-line interpolation | Step 3 |
| **PHEV** | % of the region's all-LDV volume that is PHEV | straight-line interpolation | Step 3 |
| **Total LDVs** | year-on-year % growth in the region's all-LDV volume | stepped | Step 2 |

The 2025 anchor is the **first forecast year**, not 2024. A 2025 BEV value of 15% means BEV is 15% of the 2025 total.

**The Default Scenario** holds the same PHEV shares and all-LDV growth rates in all three cases. The cases differ only in **BEV penetration**: in every region it reaches 95% by 2050 in Slower Transition, 100% by 2050 in Base Case, and 100% by 2040 in Faster Transition. So in the Default Scenario the three cases forecast the same all-LDV total and differ only in its powertrain split.

## Assumptions

- **2024 is the last actual year.** Everything from 2025 is rebuilt from the scenario configuration. GlobalData's own forecast is used only for FHEV.
- **Market size and powertrain split are independent.** Total growth doesn't respond to how fast BEVs take share, and vice versa.
- **BEV includes range-extenders and fuel cell vehicles.** Mild hybrids count as IC Only. Full hybrids are shown separately and not forecast.
- **PHEV and BEV shares are set directly for every year**, not derived from past trends. Nothing in the model checks that the 2025 share is close to the 2024 actual share.
- **Growth rates compound.** Shares don't.
- **Regions are volume-weighted aggregates** of the countries mapped to them, and each has a single set of assumptions.

## Limitations

- **Production, not sales.** Volumes are attributed to the region where vehicles are built (see Input data), which can differ from where they're sold.
- **A jump at 2025 is possible.** The 2025 penetration anchor sets the 2025 share directly. If it differs from the actual 2024 share, BEV, PHEV and IC Only jump between 2024 and 2025. The all-LDV total doesn't jump, because it grows from the 2024 actual.
- **A step in IC Only at 2033.** FHEV figures stop after 2032, so in 2033 IC Only suddenly takes back all the volume GlobalData had assigned to full hybrids in 2032. In the Default Scenario's Base Case, global IC Only rises by about a fifth between 2032 and 2033 for this reason alone. This is a feature of the data, not a forecast of hybrids disappearing.
- **Shares aren't capped.** If BEV + PHEV + FHEV adds up to more than the whole market, IC Only is set to zero rather than going negative. The powertrains then add up to slightly *more* than the all-LDV total for that region and year. The editor doesn't stop you entering shares above 100%.
- **Coarse regions.** RoW combines South America, Africa and the Middle East, and APAC combines very different markets (China, Japan, India, Southeast Asia) under one set of assumptions.
- **Sales, not fleet or fuel.** The model projects new vehicles per year. It says nothing on its own about the vehicle stock, how far vehicles travel or how much oil they use.
- **No vehicle segments.** Cars and light commercial vehicles, and small and large vehicles, are treated alike.
