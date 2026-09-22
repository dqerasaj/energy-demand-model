## What this dashboard is for

The Energy Demand Model dashboard produces scenario-based forecasts, out to 2050, for three parts of oil demand:

| Model | What it forecasts | Unit |
| --- | --- | --- |
| **LDV Model** | New light duty vehicle (cars and light commercial) **sales**, by region and powertrain | million vehicles per year |
| **HDV Model** | New heavy duty vehicle (trucks and buses) **sales**, by region and powertrain | million vehicles per year |
| **Other Oil Consumption Model** | Oil **consumption** in four non-road sectors: Petrochemicals, Shipping, Aviation and Buildings/Power/Other | million barrels per day (mb/d) |

Each model starts from historical actuals and projects them forward using a small set of editable assumptions, called the **scenario configuration**. The dashboard is built for exploring those assumptions: change a number, see how the forecast moves, and save the result as a named scenario.

The forecasts are **assumption-driven projections, not predictions**. Every forecast value follows mechanically from the actuals and the scenario configuration. There is no statistical fitting, no economic or price modelling, and no feedback between the three models.

## How the dashboard is organised

Each model has its own section in the sidebar, with the same three kinds of page:

- **Forecasts.** The main view. It shows the forecast for the selected scenario as charts or tables, with filters, plus a read-only view of the scenario configuration behind it.
- **Edit Scenario Configs.** Where you change the assumptions. Every edit re-runs the model immediately and draws the edited forecast as a dashed "– Updated" line next to the saved one, so you can see the effect before saving.
- **Saved Scenarios.** One page per saved scenario, showing its configuration. From here you can make it the main scenario or rename it.

## Key concepts

### Scenario cases and scenarios

These two terms mean different things:

- A **scenario case** is one of the three transition pathways: **Slower Transition**, **Base Case** and **Faster Transition**. They always appear in that order, from slowest to fastest.
- A **scenario** is a complete, named set of assumptions covering **all three cases**. "Default Scenario" is the baseline that ships with the model. You can save your own alongside it.

So picking a *scenario* chooses a whole set of assumptions, and picking a *scenario case* chooses which of its three pathways you're looking at.

### The main scenario

Each model has one **main scenario**, and that's the one its Forecasts page shows. You can change it from the "Scenario" picker at the top of the Forecasts page or from a saved scenario's own page. Saving a new scenario also makes it the main scenario.

### Anchor years

Assumptions are entered for five **anchor years**: **2025, 2030, 2035, 2040 and 2050**. The model fills in the years between them in one of two ways, depending on the type of assumption:

- **Rates** (year-on-year growth, efficiency improvement) are **stepped**. Each anchor's rate applies to every year from that anchor until the next one, and each year's rate compounds on the previous year.
- **Shares** (penetration percentages) are **interpolated in a straight line** between anchors, so a share ramps smoothly from one anchor value to the next.

| Forecast years | Stepped rate used | Interpolated share |
| --- | --- | --- |
| 2025–2029 | the 2025 value | ramps from the 2025 value to the 2030 value |
| 2030–2034 | the 2030 value | ramps from 2030 to 2035 |
| 2035–2039 | the 2035 value | ramps from 2035 to 2040 |
| 2040–2049 | the 2040 value | ramps from 2040 to 2050 |
| 2050 | the 2050 value | the 2050 value |

For example, a share of 20% in 2030 and 40% in 2035 gives 24% in 2031, 28% in 2032 and so on. A growth rate of 2% in 2025 and 1% in 2030 means sales grow 2% a year from 2025 to 2029, then 1% a year from 2030 to 2034.

Every value in the scenario configuration tables is a **percentage** (enter `5` for 5%).

### Actuals and forecasts

- **Actuals** run up to and including **2024**. **Forecasts** run from **2025 to 2050**.
- A grey dashed vertical line on every chart marks where the actuals end.
- The source datasets publish their own forecasts for some years after 2024. The models **discard these** and rebuild every forecast year from the scenario configuration. The one exception is the vehicle powertrains the models don't forecast (see the LDV and HDV tabs), which are shown as the source publishes them.

## Using the Forecasts page

1. **Scenario.** Choose which saved scenario drives the page. This changes the main scenario for the whole model.
2. **Scenario case.** Choose one case, or tick **Show all scenario cases** to compare all three side by side.
3. **Scenario configuration.** Expand this to see the assumptions behind the forecast you're looking at.
4. **Filters.** Each chart section has its own region and powertrain filters (sector filters for Other Oil).
5. **View.** Switch between **Chart** and **Table**. Tables list every year as a column and can be sorted or downloaded.
6. **Chart type.** Choose how the data is broken down. The options change when "Show all scenario cases" is ticked.

**What "Global" means.** In the vehicle charts and tables, **Global** is the sum of the regions and powertrains *currently selected in the filters*, not a fixed worldwide figure. With every region and powertrain selected, it's the full total.

## Editing and saving scenarios

1. Open **Edit Scenario Configs** for the model and choose the scenario to start from.
2. Edit the anchor-year values in the tables. There's one table per scenario case, side by side.
3. Expand a section's charts to compare the edited forecast (dashed lines) with the saved one (solid lines).
4. Save:
   - **Save new scenario to dashboard.** Saves the edits under a new name and makes it the main scenario.
   - **Save updates to scenario.** Overwrites the scenario you're editing. The Default Scenario can't be overwritten.
   - **Revert unsaved changes.** Discards your edits.

Nothing you edit affects the rest of the dashboard until you save.

## Limitations that apply to every model

- **Saved scenarios are shared.** Everyone who uses the dashboard shares one login, so saved scenarios, and the choice of main scenario, are the same for everyone. If you change the main scenario, you change it for everyone.
- **Saved scenarios can be lost.** On the hosted dashboard, saved scenarios are held in the app's temporary storage, which is cleared whenever the app is redeployed or restarted. Only the Default Scenario is permanent. **Record any scenario you need to keep elsewhere** (for example, a screenshot or an export of its configuration tables).
- **No input validation.** The editors accept any number. Penetration shares that add up to more than 100%, or extreme growth rates, will run and give implausible results rather than an error. See each model's limitations for what happens in those cases.
- **Deterministic, single-path forecasts.** Each case produces one line, with no uncertainty range. The spread between Slower and Faster Transition is the only measure of uncertainty shown.
- **The three models are independent.** No model's output feeds another: for example, vehicle sales don't feed into oil consumption, and there's no overall oil demand total.
- **Vehicle models forecast sales, not fleets or fuel use.** The LDV and HDV models project new vehicles sold each year. They don't model the vehicle stock, how far vehicles travel, or how much fuel they use.

## Updating the input data

The source datasets are licensed and aren't stored in the dashboard's public code repository. The hosted dashboard downloads them at startup from a separate private data repository. To refresh the data, replace the relevant file in that repository with a newer extract **with the same file name and column layout**, then restart the app so it downloads the new files. The files are:

| File | Contents |
| --- | --- |
| `globaldata_ldv_sales.csv` | GlobalData light duty vehicle extract (LDV actuals) |
| `globaldata_hdv_sales.csv` | GlobalData heavy duty vehicle extract (HDV actuals) |
| `hdv_default_schema.csv` | HDV Default Scenario assumptions |
| `weo_other_oil_consumption.csv` | World Energy Outlook extract (Other Oil actuals) |
| `other_oil_default_schema.csv` | Other Oil Default Scenario assumptions |

The LDV Default Scenario assumptions are held in the dashboard's code rather than in a file.

An extract that covers later years moves the start of the forecast only if the model's forecast start year (currently 2025) is also updated. Until then, any extra years in the file are treated as source forecasts and ignored.
