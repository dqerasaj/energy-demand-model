"""Process-wide cache for the (expensive-ish) default model run, shared by
every page so it's only computed once per running app."""

import streamlit as st

from ldv_forecast_model import ForecastResults, run_model


@st.cache_data(show_spinner="Running forecast model...")
def get_forecast_results(csv_path: str) -> ForecastResults:
    return run_model(csv_path)
