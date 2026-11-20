# What the Energy Demand Model is for

The Energy Demand Model is a dashboard for exploring how oil demand from vehicles and from non-road sectors could
change out to 2050, depending on how fast the energy transition happens. Slides: [purpose.html](../decks/purpose.html).

## The questions it answers

- **Light duty vehicles:** how fast do battery electric (BEV) and plug-in hybrid (PHEV) cars take over new sales in
  each region, and how many combustion-engine cars are still sold each year?
- **Heavy duty vehicles:** how fast do electric trucks and buses take over new sales in China, the USA and the rest of
  the world, and what is left for combustion engines?
- **Oil outside road transport:** how does oil use in petrochemicals, shipping, aviation and buildings/power change as
  activity grows, efficiency improves, and other fuels take a share?

Each answer comes in three **scenario cases**: Slower Transition, Base Case and Faster Transition. The gap between them
shows how much the outcome depends on the speed of change.

## Three models

| Model | Forecasts | Split by | Unit | Actuals from |
| --- | --- | --- | --- | --- |
| **LDV** | New sales of cars and light commercial vehicles (up to 6 t) | North America, Europe, APAC, RoW · BEV, PHEV, IC Only | million vehicles / year | GlobalData |
| **HDV** | New sales of trucks, buses and coaches (over 6 t) | China, USA, RoW · BEV, IC Only | million vehicles / year | GlobalData |
| **Other Oil** | Oil consumption outside road transport | Petrochemicals, Shipping, Aviation, Buildings/Power/Other · global | million barrels / day | World Energy Outlook |

Actual years run to 2024; forecast years run from 2025 to 2050. The vehicle models also offer a **Fleet** view:
cumulative sales since 2020.

## How it works

1. **Actuals:** the last measured year (2024) from the source data.
2. **Assumptions:** a few percentages per case for the anchor years 2025, 2030, 2035, 2040 and 2050: growth rates,
   efficiency gains, shares of electric or other fuels.
3. **Forecast:** every year from 2025 to 2050 is calculated from the 2024 actual and those assumptions.

For vehicles, the model grows the total market, takes the electric share of it, and what remains is combustion engines
(IC Only). For shipping and aviation, oil is activity × oil per unit of activity, minus the share served by other
fuels; petrochemicals and buildings/power simply grow at a rate. The full method is in
[`docs/methodology/`](../methodology/overview.md).

## What you can do with it

- **Explore:** edit an assumption and see the new forecast drawn as a dashed line next to the saved one, before saving.
- **Compare:** show all three scenario cases side by side, by region, powertrain or sector.
- **Save:** keep a set of assumptions as a named scenario and make it the one everyone sees.
- **Take the numbers away:** every chart has a table view that can be sorted and downloaded.

Everyone signs in with one shared login, so saved scenarios are shared by the whole team.

## What it is not

- **Projections, not predictions.** Every number follows from the assumptions; there is no statistical fitting and no
  price or economic modelling.
- **Three separate models.** Vehicle sales do not feed oil consumption, and there is no total oil demand figure.
- **One line per case.** There are no uncertainty bands; the spread between the cases is the only range shown.
- **"Sales" are production.** GlobalData records vehicles where they are built, so a region's "sales" can differ from
  what is sold there.
- **Fleet is not the vehicle stock.** It adds up sales since 2020 and never retires a vehicle.
- **No fuel use for vehicles.** The vehicle models count vehicles, not kilometres driven or fuel burned.

Next: [How to run it](running.md) · [How to use it](using.md)
