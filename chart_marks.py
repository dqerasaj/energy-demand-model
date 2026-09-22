"""
Marks drawn on every forecast chart, shared by the vehicle and Other Oil pages.
"""

from forecast_model import FORECAST_START

# Every model treats the years before FORECAST_START as actuals.
LAST_ACTUAL_YEAR = FORECAST_START - 1


def mark_forecast_start(fig, bars: bool = False):
    """A dashed vertical line where the actuals end and the forecast begins,
    drawn in every facet.

    On a line chart it sits on LAST_ACTUAL_YEAR - the last actual point, which
    the forecast lines carry on from. On a bar chart it sits halfway to the
    first forecast year instead, so it falls between the two bars rather than
    cutting through the last actual one."""
    x = LAST_ACTUAL_YEAR + 0.5 if bars else LAST_ACTUAL_YEAR
    fig.add_vline(x=x, line_dash="dash", line_width=1, line_color="grey")
    return fig
