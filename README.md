# Portfolio Tracker

A portfolio tracker for a family office that measures private deal performance and checks each client's allocation against target, built on fictional data.

## Live app

https://jamesivis-portfolio-tracker.streamlit.app/

## What it answers

For each client family:

- How is each private deal performing?
- How much cash has come back versus what is still held?
- Does the portfolio match its target mix?
- Could the client meet future capital calls from liquid holdings?
- What would it take to bring each asset class back to target?

## Metrics and how they are calculated

Each private deal is measured from its dated cash flows and its current value.

| Metric | Formula |
| --- | --- |
| Commitment | Total capital the client agreed to invest in the deal |
| Paid-in | Sum of all contributions (capital called) |
| Unfunded | Commitment minus paid-in, never below 0 |
| Distributions | Sum of all cash returned to the client |
| DPI | Distributions / Paid-in |
| RVPI | Current value / Paid-in |
| TVPI | DPI + RVPI, or (Distributions + Current value) / Paid-in |

**IRR** is computed the same way as Excel's XIRR, using a 365-day year. Contributions are outflows, distributions are inflows, and the current value is added as a final inflow on the valuation date. The rate is found with Newton's method, with bisection as a fallback.

**Allocation** is measured per client and asset class:

- Actual % = asset class current value / client's total current value, with public and private holdings together
- Gap = actual % minus target %, in percentage points

**Capital call coverage** is measured per client:

- Unfunded commitments = sum of unfunded across the client's private deals
- Coverage = client's total current value of public holdings / unfunded commitments, shown as a multiple such as 15.0x
- If the client has no unfunded commitments, the app shows "No unfunded commitments" instead of a ratio

**Rebalancing** is measured per client and asset class:

- Rebalance = target % / 100 x client's total current value, minus the asset class's current value
- Positive means add to the asset class, negative means reduce it. Each client's amounts sum to 0
- An asset class is private for a client when the client's holdings in it are private investments, and public otherwise. This is worked out from the data, not from a fixed list
- Public gaps close by trading. Private gaps close through new commitments over time, since private holdings cannot be traded quickly

## How the numbers were verified

- The IRR for each deal was checked by hand against Excel's XIRR.
- Automated tests in `test_metrics.py` check every metric against the expected results: paid-in, distributions, DPI, RVPI, TVPI and IRR for each private deal, the largest allocation gap for each client, unfunded for each private deal, capital call coverage for each client, the rebalancing amount for every client and asset class, that each client's rebalancing amounts sum to 0, a known-answer XIRR case, and that results do not depend on the order of the cash flow rows. All 30 tests pass.

## Project structure

```
app.py             Streamlit dashboard; selects a client and displays the results
metrics.py         Calculation layer: data loading, XIRR, deal metrics, allocation gaps,
                   capital call coverage, rebalancing
test_metrics.py    Pytest suite that checks the metrics against expected results
requirements.txt   Python dependencies
data/              portfolio_data.xlsx: fictional input data in three tabs
                   (investments, cash_flows, targets)
tests/fixtures/    Fixed CSV copies of the data that the tests run against
```

## Updating the data

Edit `data/portfolio_data.xlsx` and save it. The app reloads the data the next time the page refreshes. The tests run on the fixed copies in `tests/fixtures/`, so editing the workbook does not affect them.

## Run locally

```bash
pip install -r requirements.txt
```

```bash
streamlit run app.py
```

To run the tests:

```bash
pytest test_metrics.py
```

## Next steps

These were scoped out of v1 on purpose:

- PME (Kaplan-Schoar) against a public index
- Time-weighted return and Sharpe ratio for public holdings
- Downloadable PDF client report
- Handling deals with no paid-in capital yet
- Live market data

Built by James Ivis with Claude Code.
