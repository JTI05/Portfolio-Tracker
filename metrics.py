"""Calculation layer for the portfolio tracker.

Reads the investments, cash_flows and targets tabs of data/portfolio_data.xlsx
and computes:
  * per private investment: paid-in, distributions, current value,
    DPI, RVPI, TVPI and IRR (XIRR, 365-day year)
  * per client: actual allocation % by asset class and the gap to target
"""

from datetime import date
from pathlib import Path

import pandas as pd

DATA_FILE = Path(__file__).parent / "data" / "portfolio_data.xlsx"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_data(path=DATA_FILE):
    """Return (investments, cash_flows, targets) as DataFrames.

    Each comes from the tab of the same name in the Excel workbook.
    """
    sheets = pd.read_excel(path, sheet_name=["investments", "cash_flows", "targets"])
    investments = sheets["investments"]
    cash_flows = sheets["cash_flows"]
    targets = sheets["targets"]
    # Excel usually stores dates as real dates, but convert anyway in case a
    # date was typed in as text.
    investments["valuation_date"] = pd.to_datetime(investments["valuation_date"])
    cash_flows["date"] = pd.to_datetime(cash_flows["date"])
    return investments, cash_flows, targets


# ---------------------------------------------------------------------------
# XIRR
# ---------------------------------------------------------------------------

def xirr(dates, amounts, guess=0.1, tol=1e-10, max_iter=200):
    """Annual rate r that makes the net present value of dated cash flows zero.

    Same convention as Excel's XIRR:
        NPV(r) = sum( amount_i / (1 + r) ** (days_i / 365) )
    where days_i is the number of days from the first cash flow.

    We solve NPV(r) = 0 with Newton's method, and fall back to bisection
    if Newton fails to converge (bisection is slower but always works once
    we have a rate where NPV is positive and one where it is negative).
    """
    # Step 1: put the flows in date order and turn each date into a
    # "years since the first flow" number using a 365-day year.
    flows = sorted(zip(pd.to_datetime(list(dates)), amounts), key=lambda x: x[0])
    start = flows[0][0]
    years = [(d - start).days / 365.0 for d, _ in flows]
    values = [float(a) for _, a in flows]

    # Step 2: an IRR only exists if there is at least one outflow (negative)
    # and one inflow (positive). Otherwise NPV never crosses zero.
    if not (any(v < 0 for v in values) and any(v > 0 for v in values)):
        raise ValueError("XIRR needs at least one negative and one positive cash flow")

    # Step 3: define NPV(r) and its derivative dNPV/dr.
    #   d/dr [ v / (1+r)^t ] = -t * v / (1+r)^(t+1)
    def npv(r):
        return sum(v / (1.0 + r) ** t for v, t in zip(values, years))

    def d_npv(r):
        return sum(-t * v / (1.0 + r) ** (t + 1) for v, t in zip(values, years))

    # Step 4: Newton's method. Start from a guess and repeatedly move to
    #   r_new = r - NPV(r) / NPV'(r)
    # i.e. follow the tangent line of the NPV curve down to zero.
    r = guess
    for _ in range(max_iter):
        f = npv(r)
        df = d_npv(r)
        if df == 0:
            break  # flat curve: Newton can't continue, use bisection
        r_new = r - f / df
        if r_new <= -1.0:
            break  # rate below -100% is meaningless, use bisection
        if abs(r_new - r) < tol:
            return r_new  # converged
        r = r_new

    # Step 5: bisection fallback. Find a bracket [lo, hi] where NPV changes
    # sign, then keep halving it until it is tiny.
    lo, hi = -0.9999, 1.0
    while npv(hi) * npv(lo) > 0 and hi < 1e6:
        hi *= 2  # widen the upper bound until the sign changes
    if npv(hi) * npv(lo) > 0:
        raise ValueError("XIRR did not converge")
    for _ in range(1000):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid  # root is in the lower half
        else:
            lo = mid  # root is in the upper half
        if hi - lo < tol:
            break
    return (lo + hi) / 2


# ---------------------------------------------------------------------------
# Private investment metrics
# ---------------------------------------------------------------------------

def private_investment_metrics(investments, cash_flows):
    """One row per private investment with paid-in, distributions, DPI, RVPI, TVPI, IRR."""
    private = investments[investments["type"] == "private"].set_index("investment_id")

    # Sum cash flows by investment_id and flow_type (never by row position),
    # then spread flow_type into columns: contribution / distribution.
    totals = (
        cash_flows.groupby(["investment_id", "flow_type"])["amount"]
        .sum()
        .unstack("flow_type", fill_value=0)
        .reindex(private.index, fill_value=0)
    )
    for col in ("contribution", "distribution"):
        if col not in totals.columns:
            totals[col] = 0.0

    out = pd.DataFrame(index=private.index)
    out["name"] = private["name"]
    out["client_id"] = private["client_id"]
    out["asset_class"] = private["asset_class"]
    # Contributions are stored as negatives; show paid-in as a positive number.
    out["paid_in"] = -totals["contribution"]
    out["distributions"] = totals["distribution"]
    out["current_value"] = private["current_value"]
    out["dpi"] = out["distributions"] / out["paid_in"]
    out["rvpi"] = out["current_value"] / out["paid_in"]
    out["tvpi"] = out["dpi"] + out["rvpi"]

    irrs = {}
    for inv_id, row in private.iterrows():
        flows = cash_flows[cash_flows["investment_id"] == inv_id]
        dates = list(flows["date"]) + [row["valuation_date"]]
        amounts = list(flows["amount"]) + [row["current_value"]]
        try:
            irrs[inv_id] = xirr(dates, amounts)
        except ValueError:
            irrs[inv_id] = float("nan")
    out["irr"] = pd.Series(irrs)
    return out


# ---------------------------------------------------------------------------
# Client allocation vs target
# ---------------------------------------------------------------------------

def allocation_gaps(investments, targets):
    """One row per client and asset class: actual %, target % and gap (pp).

    Actual % = asset-class current value / client's total current value,
    using public and private investments together.
    """
    by_class = (
        investments.groupby(["client_id", "asset_class"])["current_value"]
        .sum()
        .reset_index()
    )
    client_total = by_class.groupby("client_id")["current_value"].transform("sum")
    by_class["actual_pct"] = by_class["current_value"] / client_total * 100

    # Outer merge so an asset class that has a target but no holdings
    # (or holdings but no target) still shows up, treated as 0%.
    merged = targets.merge(by_class, on=["client_id", "asset_class"], how="outer")
    merged["client_name"] = merged.groupby("client_id")["client_name"].transform("first")
    merged[["current_value", "actual_pct", "target_pct"]] = merged[
        ["current_value", "actual_pct", "target_pct"]
    ].fillna(0)
    merged["gap_pp"] = merged["actual_pct"] - merged["target_pct"]
    return merged[
        ["client_id", "client_name", "asset_class", "current_value",
         "actual_pct", "target_pct", "gap_pp"]
    ].sort_values(["client_id", "asset_class"]).reset_index(drop=True)


if __name__ == "__main__":
    inv, cf, tg = load_data()
    pd.set_option("display.width", 200)
    print(private_investment_metrics(inv, cf).round(4))
    print()
    print(allocation_gaps(inv, tg).round(2))
