"""Landing page: what the dashboard is for and how each model works.

The methodology itself is plain markdown under docs/methodology/, one file per
tab, so it can be read and edited on its own - here it's only laid out. Read
fresh on every run, so an edit shows up on the next rerun without a restart.
"""

from pathlib import Path

import streamlit as st

METHODOLOGY_DIR = Path(__file__).parent / "docs" / "methodology"

# (tab label, file) in display order.
TABS = [
    ("Overview & how to use", "overview.md"),
    ("LDV Model", "ldv.md"),
    ("HDV Model", "hdv.md"),
    ("Other Oil Consumption Model", "other_oil.md"),
]


def render() -> None:
    st.title("Energy Demand Model")
    st.write(
        "This model allows users to perform scenario-based forecasts from 2025 "
        "to 2050 of light and heavy duty vehicle sales and non-road oil "
        "consumption. Start with **Overview & how to use**, "
        "then see each model's tab for its data, calculations, assumptions and "
        "limitations."
    )

    for tab, (_, filename) in zip(st.tabs([label for label, _ in TABS]), TABS):
        with tab:
            st.markdown((METHODOLOGY_DIR / filename).read_text(encoding="utf-8"))
