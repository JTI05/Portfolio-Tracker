"""Streamlit dashboard for the portfolio tracker.

Every number shown here comes from metrics.py. This file only picks the
rows for the selected client, adds up totals for the summary figures,
and formats values for display.

Run with:  streamlit run app.py
"""

import altair as alt
import pandas as pd
import streamlit as st

from metrics import DATA_FILE, allocation_gaps, load_data, private_investment_metrics

ACTUAL_COLOR = "#1f4e79"  # dark blue
TARGET_COLOR = "#a6b8c9"  # light grey-blue


# ---------------------------------------------------------------------------
# Display formats
# ---------------------------------------------------------------------------

def fmt_dollars(x):
    return f"${x:,.0f}"


def fmt_multiple(x):
    return f"{x:.2f}x"


def fmt_irr(x):
    return "n/a" if pd.isna(x) else f"{x * 100:.1f}%"


def fmt_pct(x):
    return f"{x:.1f}%"


def fmt_gap(x):
    return f"{x:+.1f}"


# ---------------------------------------------------------------------------
# Data (computed once by metrics.py, then cached)
# ---------------------------------------------------------------------------

@st.cache_data
def get_metrics(data_mtime):
    # data_mtime is not used inside the function. It is the cache key: when the
    # workbook is saved, its last-modified time changes, so Streamlit treats it
    # as a new call and reloads the data instead of reusing the cached result.
    investments, cash_flows, targets = load_data()
    return (
        private_investment_metrics(investments, cash_flows),
        allocation_gaps(investments, targets),
    )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Portfolio Tracker", layout="wide")

st.title("Portfolio Tracker")
st.caption("Fictional data. All values as of 2026-09-30.")

private, gaps = get_metrics(DATA_FILE.stat().st_mtime)

clients = gaps[["client_id", "client_name"]].drop_duplicates().sort_values("client_id")
client_name = st.selectbox("Client", clients["client_name"].tolist())
client_id = clients.loc[clients["client_name"] == client_name, "client_id"].iloc[0]

client_private = private[private["client_id"] == client_id]
client_gaps = gaps[gaps["client_id"] == client_id]

# --- Summary figures -------------------------------------------------------
st.subheader("Summary")
st.caption(
    "Total portfolio value is the current value of all holdings, public and private. "
    "Paid-in and distributions cover private investments only."
)
c1, c2, c3 = st.columns(3)
c1.metric("Total portfolio value", fmt_dollars(client_gaps["current_value"].sum()))
c2.metric("Total private paid-in", fmt_dollars(client_private["paid_in"].sum()))
c3.metric("Total private distributions", fmt_dollars(client_private["distributions"].sum()))

# --- Private investments table --------------------------------------------
st.subheader("Private investments")
st.caption(
    "Cash paid in and returned for each private investment, with performance multiples "
    "and annualized IRR to the valuation date."
)
pi_table = pd.DataFrame({
    "Investment": client_private["name"],
    "Asset class": client_private["asset_class"],
    "Paid-in": client_private["paid_in"],
    "Distributions": client_private["distributions"],
    "Current value": client_private["current_value"],
    "DPI": client_private["dpi"],
    "RVPI": client_private["rvpi"],
    "TVPI": client_private["tvpi"],
    "IRR": client_private["irr"],
}).reset_index(drop=True)
st.dataframe(
    pi_table.style.format({
        "Paid-in": fmt_dollars,
        "Distributions": fmt_dollars,
        "Current value": fmt_dollars,
        "DPI": fmt_multiple,
        "RVPI": fmt_multiple,
        "TVPI": fmt_multiple,
        "IRR": fmt_irr,
    }),
    hide_index=True,
    width="stretch",
)

# --- Allocation vs target --------------------------------------------------
st.subheader("Allocation vs target")
st.caption(
    "Share of the client's total portfolio value in each asset class, compared with the "
    "target. Gap is actual minus target, in percentage points (pp)."
)

chart_data = client_gaps.melt(
    id_vars="asset_class",
    value_vars=["actual_pct", "target_pct"],
    var_name="series",
    value_name="pct",
)
chart_data["series"] = chart_data["series"].map({"actual_pct": "Actual", "target_pct": "Target"})

chart = (
    alt.Chart(chart_data)
    .mark_bar()
    .encode(
        x=alt.X("asset_class:N", title=None, axis=alt.Axis(labelAngle=0)),
        xOffset=alt.XOffset("series:N", sort=["Actual", "Target"]),
        y=alt.Y("pct:Q", title="% of portfolio"),
        color=alt.Color(
            "series:N",
            title=None,
            scale=alt.Scale(domain=["Actual", "Target"], range=[ACTUAL_COLOR, TARGET_COLOR]),
            legend=alt.Legend(orient="top"),
        ),
        tooltip=[
            alt.Tooltip("asset_class:N", title="Asset class"),
            alt.Tooltip("series:N", title="Series"),
            alt.Tooltip("pct:Q", title="%", format=".1f"),
        ],
    )
    .properties(height=320)
)
st.altair_chart(chart, width="stretch")

alloc_table = pd.DataFrame({
    "Asset class": client_gaps["asset_class"],
    "Actual %": client_gaps["actual_pct"],
    "Target %": client_gaps["target_pct"],
    "Gap (pp)": client_gaps["gap_pp"],
}).reset_index(drop=True)
st.dataframe(
    alloc_table.style.format({
        "Actual %": fmt_pct,
        "Target %": fmt_pct,
        "Gap (pp)": fmt_gap,
    }),
    hide_index=True,
    width="stretch",
)
