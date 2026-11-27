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

ACTUAL_COLOR = "#C1A65D"  # accent gold
TARGET_COLOR = "#6F6E6C"  # muted grey
LABEL_COLOR = "#F8F5F0"   # cream, for the value labels on the bars

# Small CSS block for the "family office" look. Colours match .streamlit/config.toml.
# Muted text uses #8A8986, a slightly lighter grey than #6F6E6C, because
# #6F6E6C is too dim to read as text on the dark background.
CUSTOM_CSS = """
<style>
/* Subtle top-to-bottom gradient, near-black to dark warm bronze */
[data-testid="stApp"] {
    background: linear-gradient(180deg, #141414 0%, #1C1A16 100%);
}
[data-testid="stHeader"] { background: transparent; }

/* Centered layout, slightly wider than default so all nine table columns fit */
[data-testid="stMainBlockContainer"] { max-width: 880px; }

/* Small gold uppercase label with a short gold line before it */
.eyebrow {
    color: #C1A65D;
    font-size: 0.72rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin: 1.6rem 0 -0.4rem;
}
.eyebrow::before {
    content: "";
    display: inline-block;
    width: 28px;
    height: 1px;
    background: #C1A65D;
    vertical-align: middle;
    margin-right: 10px;
}

/* Page title: "Portfolio" in cream, "Tracker" in gold italic */
.page-title {
    font-family: "Playfair Display", serif;
    font-size: 3rem;
    font-weight: 600;
    color: #F8F5F0;
    margin: 0.2rem 0 0;
    line-height: 1.15;
}
.page-title em { color: #C1A65D; font-weight: 400; }

/* Summary figures as cards: panel background, thin gold line on top */
[data-testid="stMetric"] {
    background: #1E1E1E;
    border: none;
    border-top: 2px solid #C1A65D !important;
    border-radius: 2px;
    padding: 1rem 1.2rem;
}
[data-testid="stMetricLabel"] p { color: #8A8986; font-size: 0.8rem; }
[data-testid="stMetricValue"] {
    font-family: "Playfair Display", serif;
    font-variant-numeric: lining-nums tabular-nums;  /* digits sit on one line */
}

/* Footer */
.footer {
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid #2A2824;
    color: #8A8986;
    font-size: 0.8rem;
    text-align: center;
}
</style>
"""


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


def eyebrow(text):
    """Small gold uppercase label shown above a heading."""
    st.markdown(f'<div class="eyebrow">{text}</div>', unsafe_allow_html=True)


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

st.set_page_config(page_title="Portfolio Tracker", layout="centered")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

eyebrow("Family office dashboard")
st.markdown(
    '<h1 class="page-title">Portfolio <em>Tracker</em></h1>',
    unsafe_allow_html=True,
)
st.caption("Fictional data. All values as of 2026-09-30.")

private, gaps = get_metrics(DATA_FILE.stat().st_mtime)

clients = gaps[["client_id", "client_name"]].drop_duplicates().sort_values("client_id")
client_name = st.selectbox("Client", clients["client_name"].tolist())
client_id = clients.loc[clients["client_name"] == client_name, "client_id"].iloc[0]

client_private = private[private["client_id"] == client_id]
client_gaps = gaps[gaps["client_id"] == client_id]

# --- Summary figures -------------------------------------------------------
eyebrow("Overview")
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
eyebrow("Holdings")
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
eyebrow("Allocation")
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

# Shared position encodings for the bars and their value labels.
base = alt.Chart(chart_data).encode(
    x=alt.X("asset_class:N", title=None, axis=alt.Axis(labelAngle=0)),
    xOffset=alt.XOffset("series:N", sort=["Actual", "Target"]),
    y=alt.Y("pct:Q", title="% of portfolio"),
)
bars = base.mark_bar().encode(
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
# Value printed just above each bar, same 1-decimal format as the table.
labels = base.mark_text(dy=-8, color=LABEL_COLOR, fontSize=11).encode(
    text=alt.Text("pct:Q", format=".1f"),
)
chart = (
    alt.layer(bars, labels)
    .properties(height=320)
    .configure(background="transparent")  # let the page gradient show through
    .configure_axis(grid=False)           # no gridlines
    .configure_view(stroke=None)          # no box around the plot
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

st.markdown(
    '<div class="footer">Built by James Ivis · Fictional data</div>',
    unsafe_allow_html=True,
)
