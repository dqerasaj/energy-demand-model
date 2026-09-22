## Purpose

The Other Oil Consumption model projects oil consumption from 2025 to 2050 in four sectors outside road transport:

- **Petrochemicals**
- **Shipping**
- **Aviation**
- **Buildings/Power/Other**

Its main question is: *how does oil use in these sectors change as activity grows, efficiency improves, and low-emission fuels and electrification take a share?*

Results are global (there are no regions) and in **million barrels per day (mb/d)**.

## Input data

**Source: World Energy Outlook (WEO) extract** (`weo_other_oil_consumption.csv`). One row per series, with years as columns:

| Series | Unit | Years available | Used for |
| --- | --- | --- | --- |
| Total oil (total liquids) | mb/d | 2014–2024 | Setting the 2024 oil intensity for Shipping and Aviation only; never shown |
| Petrochemicals oil | mb/d | 2014–2024 | Actuals and the starting point for the forecast |
| Shipping oil | mb/d | 2014–2024 | Actuals |
| Shipping activity | billion tonne-km | 2022–2024 | Actuals and the starting point for the forecast |
| Aviation oil | mb/d | 2019–2024 | Actuals |
| Aviation activity | billion passenger-km | 2022–2024 | Actuals and the starting point for the forecast |
| Buildings/Power/Other oil | mb/d | 2019–2024 | Actuals and the starting point for the forecast |

- **2024 is the last actual year.** Anything the file holds for 2025 onwards would be ignored.
- **Charts and tables start in 2022**, the first year every series is available. Earlier years are dropped from the display but don't affect the forecast.
- In the source dataset, **Shipping and Aviation oil are fixed shares of total liquids: 7% and 8%** respectively in every year. That split is applied when the dataset is prepared, not by this model.

**Default assumptions:** `other_oil_default_schema.csv`, one row per sector, assumption and case, with anchor-year percentages. Editing that file changes the Default Scenario.

## The two kinds of sector

The sectors are modelled in two different ways, depending on whether there's an activity measure behind the oil:

| Sector | Method | Assumptions (levers) |
| --- | --- | --- |
| **Shipping** | Activity × intensity | Activity growth, Efficiency, Low-emission Fuel, E-shipping |
| **Aviation** | Activity × intensity | Activity growth, Efficiency, Low-emission Fuel, E-plane |
| **Petrochemicals** | Oil growth only | Oil growth |
| **Buildings/Power/Other** | Oil growth only | Oil growth |

## How the forecast is calculated

Each lever works in one of three ways. The editor shows the type in brackets after each lever's name:

- **YoY (year-on-year growth).** Stepped between anchor years and compounded each year.
- **PA (per-annum efficiency change).** Stepped and compounded in the same way. A negative value means less oil per unit of activity.
- **Penetration.** A share of activity served by something other than oil. Interpolated in a straight line between anchor years, and applied as a level, not compounded.

### Shipping and Aviation: activity × intensity

**Step 1: Starting oil intensity (2024).** Oil used per unit of activity in 2024, worked out from the sector's share of total liquids:

$$
I_{2024} = \frac{\text{Total liquids}_{2024} \times \text{share} \times 365{,}000}{A_{2024}}
$$

where the share is 7% for Shipping and 8% for Aviation, $A$ is activity, and 365,000 converts barrels per day into the intensity's per-unit-of-activity basis. This is the **only** place total liquids and the 7%/8% shares are used.

**Step 2: Intensity improves at the efficiency rate.**

$$
I_{y} = I_{y-1} \times (1 + e_{y})
$$

**Step 3: Activity grows at its own rate.**

$$
A_{y} = A_{y-1} \times (1 + g_{y})
$$

**Step 4: Oil = intensity × activity, less the share not served by oil.**

$$
\text{Oil}_{y} = \frac{I_{y} \times A_{y} \times \left(1 - \sum p_{y}\right)}{365{,}000}
$$

where $\sum p_y$ is **all the sector's penetration levers added together** (for Shipping, Low-emission Fuel + E-shipping).

Because Steps 1 and 4 undo each other, the calculation is equivalent to:

$$
\text{Oil}_{y} = \text{Oil}_{2024} \times \prod_{t=2025}^{y}(1 + e_{t}) \times \prod_{t=2025}^{y}(1 + g_{t}) \times \left(1 - \sum p_{y}\right)
$$

In words: **2024 oil, grown by cumulative activity growth, reduced by cumulative efficiency gains, then scaled down by the share of activity served by low-emission fuels and electrification in that year.**

### Petrochemicals and Buildings/Power/Other: oil growth only

With no activity measure, oil grows directly from its 2024 value at the sector's year-on-year rate:

$$
\text{Oil}_{y} = \text{Oil}_{y-1} \times (1 + g_{y})
$$

### Worked example (illustrative numbers)

Shipping, with 2024 oil of **7.0 mb/d**, activity growth of **2%**, efficiency of **−0.5%**, Low-emission Fuel of **2%** and E-shipping of **1%** in 2025:

| 2025 | Calculation | Result |
| --- | --- | --- |
| Activity | 2024 activity × 1.02 | +2% |
| Intensity | 2024 intensity × (1 − 0.005) | −0.5% |
| Share not served by oil | 2% + 1% | 3% |
| Oil | 7.0 × 1.02 × 0.995 × (1 − 0.03) | **6.89 mb/d** |

Petrochemicals, with 2024 oil of **20.0 mb/d** and oil growth of **1.5%** in 2025: 20.0 × 1.015 = **20.3 mb/d**.

## Reading the scenario configuration

Each sector has one table per scenario case, with one row per lever:

| Lever | Sectors | Values mean | Filled between anchors by |
| --- | --- | --- | --- |
| **Activity growth (YoY)** | Shipping, Aviation | yearly % growth in tonne-km or passenger-km | stepped |
| **Oil growth (YoY)** | Petrochemicals, Buildings/Power/Other | yearly % growth in oil consumption | stepped |
| **Efficiency (PA)** | Shipping, Aviation | yearly % change in oil per unit of activity (negative = improving) | stepped |
| **Low-emission Fuel (Penetration)** | Shipping, Aviation | % of activity served by low-emission fuels | straight-line interpolation |
| **E-shipping / E-plane (Penetration)** | Shipping / Aviation | % of activity served by electrification | straight-line interpolation |

The Forecasts page also has an **Activity** section showing the Shipping and Aviation activity forecasts. The other two sectors have no activity measure.

## Assumptions

- **2024 is fully served by oil.** The model starts deducting penetration from 2025. In 2024 there's no deduction, so any low-emission fuel or electric share that already existed in 2024 is assumed to be part of the reported oil figure. The 2025 penetration values therefore reduce oil straight away (a 3% combined share takes 3% off 2025 oil).
- **The 7%/8% split of total liquids** used to set Shipping and Aviation's starting intensity is taken from the source dataset. It isn't a scenario lever, and it's the same in every case.
- **Intensity is set once, in 2024,** then moves only with the efficiency lever.
- **Levers are independent.** Activity growth doesn't respond to oil prices or to penetration, and efficiency doesn't respond to activity.
- **Penetration levers add up.** Low-emission fuel and electrification shares are summed, and treated as serving separate parts of activity.

## Limitations

- **Not all oil is covered.** The four sectors are only part of total liquids. Road transport and anything else outside these sectors isn't modelled here, so the model doesn't give total oil demand.
- **Penetration isn't capped.** If a sector's penetration levers add up to more than 100%, its oil goes negative. This is left visible rather than hidden. The editor doesn't stop you entering such values.
- **Short activity history.** Activity data starts in 2022, so there are only three actual years to compare assumptions against.
- **Two sectors have no physical driver.** Petrochemicals and Buildings/Power/Other are straight growth rates on oil, with no link to activity, efficiency or fuel switching. Any such change has to be built into their growth rate.
- **Global only.** There's no regional breakdown, so regional differences in growth or fuel switching can't be represented.
- **Oil intensity isn't shown.** The model calculates it, but the dashboard doesn't display it yet.
