# Portfolio Tracker

A portfolio tracker for a family office that measures private deal performance and checks each client's allocation against target, built on fictional data.

## Live app

https://jamesivis-portfolio-tracker.streamlit.app/

## What it answers

For each client family:

- How is each private deal performing?
- How much cash has come back versus what is still held?
- Does the portfolio match its target mix?

## Metrics and how they are calculated

Each private deal is measured from its dated cash flows and its current value.

| Metric | Formula |
| --- | --- |
| Paid-in | Sum of all contributions (capital called) |
| Distributions | Sum of all cash returned to the client |
| DPI | Distributions / Paid-in |
| RVPI | Current value / Paid-in |
| TVPI | DPI + RVPI, or (Distributions + Current value) / Paid-in |

**IRR** is computed the same way as Excel's XIRR, using a 365-day year. Contributions are outflows, distributions are inflows, and the current value is added as a final inflow on the valuation date. The rate is found with Newton's method, with bisection as a fallback.

**Allocation** is measured per client and asset class:

- Actual % = asset class current value / client's total current value, with public and private holdings together
- Gap = actual % minus target %, in percentage points

## How the numbers were verified

- The IRR for each deal was checked by hand against Excel's XIRR.
- Automated tests in `test_metrics.py` check every metric against the expected results: paid-in, distributions, DPI, RVPI, TVPI and IRR for each private deal, the largest allocation gap for each client, a known-answer XIRR case, and that results do not depend on the order of the cash flow rows. All 10 tests pass.

## Project structure

```
app.py             Streamlit dashboard; selects a client and displays the results
metrics.py         Calculation layer: data loading, XIRR, deal metrics, allocation gaps
test_metrics.py    Pytest suite that checks the metrics against expected results
requirements.txt   Python dependencies
data/              Fictional input data: investments, dated cash flows and target allocations
```

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
- Unfunded commitments (commitment minus paid-in)
- Downloadable PDF client report
- Handling deals with no paid-in capital yet
- Live market data

Built by James Ivis with Claude Code.
