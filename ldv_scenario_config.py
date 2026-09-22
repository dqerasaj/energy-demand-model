"""
Default scenario configuration for the LDV forecasting model.

Generated from default_scenarios.xlsx. Anchor years are defined per scenario:

BASE_POWERTRAIN_AND_REGION_SCENARIOS: penetration shares (e.g. 0.05 = 5% of the region's all-LDV
    sales), linearly interpolated between anchors and applied to the region's forecast total.
BASE_REGION_SCENARIOS: YoY sales-change fractions (e.g. 0.05 = +5%), stepped from the closest
    past anchor and compounded onto the region's own prior-year sales.
"""

FORECAST_START = 2025
FORECAST_END = 2050

# per (region, powertrain) - penetration share of the region's all-LDV sales. Linearly interpolated between anchor years.
BASE_POWERTRAIN_AND_REGION_SCENARIOS = {
    "Base Case": {
        ("North America", "PHEV"): {2025: 0.025, 2030: 0.075, 2035: 0.05, 2040: 0.0, 2050: 0.0},
        ("Europe", "PHEV"): {2025: 0.07, 2030: 0.05, 2035: 0.05, 2040: 0.0, 2050: 0.0},
        ("APAC", "PHEV"): {2025: 0.13, 2030: 0.18, 2035: 0.08, 2040: 0.0, 2050: 0.0},
        ("RoW", "PHEV"): {2025: 0.02, 2030: 0.05, 2035: 0.05, 2040: 0.0, 2050: 0.0},
        ("North America", "BEV"): {2025: 0.090616, 2030: 0.2, 2035: 0.5, 2040: 0.8, 2050: 1.0},
        ("Europe", "BEV"): {2025: 0.154105, 2030: 0.45, 2035: 0.75, 2040: 0.95, 2050: 1.0},
        ("APAC", "BEV"): {2025: 0.188723, 2030: 0.5, 2035: 0.8, 2040: 1.0, 2050: 1.0},
        ("RoW", "BEV"): {2025: 0.02, 2030: 0.25, 2035: 0.75, 2040: 0.95, 2050: 1.0},
    },
    "Faster Transition": {
        ("North America", "PHEV"): {2025: 0.025, 2030: 0.075, 2035: 0.05, 2040: 0.0, 2050: 0.0},
        ("Europe", "PHEV"): {2025: 0.07, 2030: 0.05, 2035: 0.05, 2040: 0.0, 2050: 0.0},
        ("APAC", "PHEV"): {2025: 0.13, 2030: 0.18, 2035: 0.08, 2040: 0.0, 2050: 0.0},
        ("RoW", "PHEV"): {2025: 0.02, 2030: 0.05, 2035: 0.05, 2040: 0.0, 2050: 0.0},
        ("North America", "BEV"): {2025: 0.090616, 2030: 0.3, 2035: 0.7, 2040: 1.0, 2050: 1.0},
        ("Europe", "BEV"): {2025: 0.154105, 2030: 0.6, 2035: 0.9, 2040: 1.0, 2050: 1.0},
        ("APAC", "BEV"): {2025: 0.188723, 2030: 0.65, 2035: 0.9, 2040: 1.0, 2050: 1.0},
        ("RoW", "BEV"): {2025: 0.02, 2030: 0.35, 2035: 0.9, 2040: 1.0, 2050: 1.0},
    },
    "Slower Transition": {
        ("North America", "PHEV"): {2025: 0.025, 2030: 0.075, 2035: 0.05, 2040: 0.0, 2050: 0.0},
        ("Europe", "PHEV"): {2025: 0.07, 2030: 0.05, 2035: 0.05, 2040: 0.0, 2050: 0.0},
        ("APAC", "PHEV"): {2025: 0.13, 2030: 0.18, 2035: 0.08, 2040: 0.0, 2050: 0.0},
        ("RoW", "PHEV"): {2025: 0.02, 2030: 0.05, 2035: 0.05, 2040: 0.0, 2050: 0.0},
        ("North America", "BEV"): {2025: 0.090616, 2030: 0.1, 2035: 0.4, 2040: 0.65, 2050: 0.95},
        ("Europe", "BEV"): {2025: 0.154105, 2030: 0.35, 2035: 0.6, 2040: 0.8, 2050: 0.95},
        ("APAC", "BEV"): {2025: 0.188723, 2030: 0.4, 2035: 0.7, 2040: 0.9, 2050: 0.95},
        ("RoW", "BEV"): {2025: 0.02, 2030: 0.15, 2035: 0.6, 2040: 0.85, 2050: 0.95},
    },
}

# per region, all LDVs - YoY sales-change rate. Stepwise (closest past anchor year).
BASE_REGION_SCENARIOS = {
    "Base Case": {
        "North America": {2025: 0.0, 2030: 0.0, 2035: 0.0, 2040: 0.0, 2050: 0.0},
        "Europe": {2025: 0.0, 2030: 0.0, 2035: 0.0, 2040: 0.0, 2050: 0.0},
        "APAC": {2025: 0.025, 2030: 0.015, 2035: 0.01, 2040: 0.005, 2050: 0.005},
        "RoW": {2025: 0.0, 2030: 0.0, 2035: 0.0, 2040: 0.0, 2050: 0.0},
    },
    "Faster Transition": {
        "North America": {2025: 0.0, 2030: 0.0, 2035: 0.0, 2040: 0.0, 2050: 0.0},
        "Europe": {2025: 0.0, 2030: 0.0, 2035: 0.0, 2040: 0.0, 2050: 0.0},
        "APAC": {2025: 0.025, 2030: 0.015, 2035: 0.01, 2040: 0.005, 2050: 0.005},
        "RoW": {2025: 0.0, 2030: 0.0, 2035: 0.0, 2040: 0.0, 2050: 0.0},
    },
    "Slower Transition": {
        "North America": {2025: 0.0, 2030: 0.0, 2035: 0.0, 2040: 0.0, 2050: 0.0},
        "Europe": {2025: 0.0, 2030: 0.0, 2035: 0.0, 2040: 0.0, 2050: 0.0},
        "APAC": {2025: 0.025, 2030: 0.015, 2035: 0.01, 2040: 0.005, 2050: 0.005},
        "RoW": {2025: 0.0, 2030: 0.0, 2035: 0.0, 2040: 0.0, 2050: 0.0},
    },
}