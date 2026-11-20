# How to use the Energy Demand Model

Finding your way around the dashboard, reading the forecasts, and editing and saving scenarios. Slides:
[using.html](../decks/using.html).

## Finding your way

The sidebar has one section per model, with the same pages in each:

- **Model Dashboard Overview** opens first. Its tabs (Overview & how to use, LDV Model, HDV Model, Other Oil
  Consumption Model) explain each model's data, calculation and limits. Read **Overview & how to use** once.
- **LDV Model**, **HDV Model** and **Other Oil Consumption Model**, each with:
  - **Forecasts**: the results for the main scenario.
  - **Edit Scenario Configs**: change the assumptions and save them.
  - **Saved Scenarios**: one page per saved scenario.

## Words to know

- **Scenario case:** one of three pathways, always in this order: Slower Transition, Base Case, Faster Transition.
- **Scenario:** a named set of assumptions for all three cases. The **Default Scenario** is the permanent baseline and
  can't be overwritten.
- **Main scenario:** the scenario a model's Forecasts page shows. There is one per model, shared by everyone.
- **Anchor years:** assumptions are set for 2025, 2030, 2035, 2040 and 2050. Growth rates hold until the next anchor;
  shares ramp in a straight line between anchors.

Every assumption is a **percentage**: type `5` for 5%. The editors accept any number, so check that shares add up to no
more than 100%.

## The Forecasts page

From top to bottom:

1. **Scenario:** which saved scenario drives the page. This changes the main scenario for everyone.
2. **Scenario case:** one case, or tick **Show all scenario cases** to see the three side by side.
3. **Show: Sales / Fleet** (vehicle models): new sales each year, or cumulative sales since 2020.
4. **Scenario configuration:** open it to see the assumptions behind what you are looking at.

Then two sections of results:

- **Sales by region & powertrain:** BEV, PHEV and IC Only, with region and powertrain filters.
- **Sales by region (all LDV / HDV):** the whole market per region, including the hybrids the model does not forecast.

Each section has a **View** (Chart or Table) and a **Chart type**. Tick **Include … (not forecast by this model)** to
show full hybrids (LDV) or ICE and H2 hybrids (HDV) as GlobalData publishes them.

### Chart types

| Section | One scenario case | All scenario cases |
| --- | --- | --- |
| By region & powertrain | Powertrain trend per region · Global powertrain trend · Global powertrain split | Powertrain and scenario trend per region · Global powertrain trend per scenario · Global powertrain split per scenario |
| By region (all vehicles) | Regional trend · Regional split | Regional trend per scenario · Regional split per scenario |
| Other Oil, oil consumption | Sector trend · Sector split | Scenario trend per sector · Sector trend per scenario · Sector split per scenario |
| Other Oil, activity | Sector trend | Scenario trend per sector · Sector trend per scenario |

A **trend** is lines over time; a **split** is stacked bars showing how the total divides. A grey dashed line marks
where the actuals end (2024).

**Global** is the sum of the regions and powertrains selected in the filters, not a fixed world total.

## Editing a scenario

1. Open **Edit Scenario Configs** and choose the scenario to start from.
2. Edit the anchor-year values. There is one table per scenario case, side by side.
3. Open **View …** under a table to compare: the edited forecast is dashed ("– Updated"), the saved one solid.
4. Save with one of the buttons at the bottom:

| Button | What it does |
| --- | --- |
| **Save new scenario to dashboard** | Saves the edits under a new name and makes it the main scenario |
| **Save updates to scenario** | Overwrites the scenario you are editing (not allowed for the Default Scenario) |
| **Revert unsaved changes** | Throws the edits away |

Nothing changes elsewhere in the dashboard until you save.

## Saved Scenarios

Each saved scenario has its own page showing its assumptions for all three cases. From there:

- **Set as main … scenario** makes every page of that model use it.
- **Rename scenario** changes its name in the sidebar.

Saved scenarios are shared by everyone, and the online app keeps them in temporary storage: a restart or redeploy wipes
everything except the Default Scenario. Keep a record of any scenario that matters, such as a screenshot or a download
of its configuration tables.

## The Other Oil model

- Filters choose **sectors**: Petrochemicals, Shipping, Aviation, Buildings/Power/Other.
- Two sections: **Oil consumption (mb/d)** and **Activity** (billion tonne-km for shipping, billion passenger-km for
  aviation). Activity is never stacked, because tonne-km and passenger-km can't be added.
- Charts start in 2022, the first year every series exists.
- The levers you edit: **YoY** (growth per year, stepped and compounded), **PA** (efficiency change per year; negative
  means less oil per unit), and **Penetration** (share served by other fuels or electric, in a straight line).

## Before you share a result

- Say which scenario and which case a chart shows.
- Check the filters: a "Global" line covers only what is selected.
- Changing the main scenario changes it for everyone: tell the team.
- Use the Table view and its download for exact numbers.
- Remember the limits: projections, not predictions; "sales" are production; Fleet is not the vehicle stock.
