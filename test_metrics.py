from pathlib import Path

import pandas as pd
import pytest

from metrics import (
    allocation_gaps,
    capital_call_coverage,
    private_investment_metrics,
    rebalancing,
    xirr,
)

# The tests use fixed CSV copies of the data, not data/portfolio_data.xlsx,
# so editing the workbook never changes the expected results below.
FIXTURES_DIR = Path(__file__).parent / "tests" / "fixtures"

RATIO_TOL = 0.005  # DPI, RVPI, TVPI
IRR_TOL = 0.0005
# Gap targets were given to one decimal place, so allow half of that last digit.
GAP_TOL = 0.05

# investment_id: (paid_in, distributions, current_value, dpi, rvpi, tvpi, irr)
EXPECTED = {
    "I01": (400_000, 100_000, 380_000, 0.25, 0.95, 1.20, 0.043),
    "I02": (300_000, 51_000, 310_000, 0.17, 1.03, 1.20, 0.046),
    "I05": (250_000, 18_000, 265_000, 0.07, 1.06, 1.13, 0.033),
    "I06": (400_000, 244_000, 220_000, 0.61, 0.55, 1.16, 0.039),
    "I09": (200_000, 0, 165_000, 0.00, 0.825, 0.825, -0.058),
}

EXPECTED_GAPS = [
    ("Beaumont Family", "Private Equity", -2.6),
    ("Tran Family", "Real Assets", -2.2),
    ("Okafor Family", "Public Equity", 2.0),
]

EXPECTED_UNFUNDED = {
    "I01": 100_000,
    "I02": 0,
    "I05": 50_000,
    "I06": 0,
    "I09": 100_000,
}

EXPECTED_COVERAGE = [
    ("C1", 15.0),  # Beaumont Family
    ("C2", 20.0),  # Tran Family
    ("C3", 7.0),   # Okafor Family
]

EXPECTED_REBALANCE = [
    ("Beaumont Family", "Public Equity", -24_000),
    ("Beaumont Family", "Fixed Income", -52_500),
    ("Beaumont Family", "Private Equity", 58_000),
    ("Beaumont Family", "Infrastructure", 18_500),
    ("Tran Family", "Public Equity", -31_750),
    ("Tran Family", "Fixed Income", -3_000),
    ("Tran Family", "Private Credit", 2_750),
    ("Tran Family", "Real Assets", 32_000),
    ("Okafor Family", "Public Equity", -17_500),
    ("Okafor Family", "Fixed Income", 9_500),
    ("Okafor Family", "Private Equity", 8_000),
]


@pytest.fixture(scope="module")
def data():
    investments = pd.read_csv(FIXTURES_DIR / "investments.csv", parse_dates=["valuation_date"])
    cash_flows = pd.read_csv(FIXTURES_DIR / "cash_flows.csv", parse_dates=["date"])
    targets = pd.read_csv(FIXTURES_DIR / "targets.csv")
    return investments, cash_flows, targets


@pytest.fixture(scope="module")
def pm(data):
    investments, cash_flows, _ = data
    return private_investment_metrics(investments, cash_flows)


@pytest.mark.parametrize("inv_id", EXPECTED.keys())
def test_private_metrics(pm, inv_id):
    paid_in, dist, cv, dpi, rvpi, tvpi, irr = EXPECTED[inv_id]
    row = pm.loc[inv_id]
    assert row["paid_in"] == pytest.approx(paid_in)
    assert row["distributions"] == pytest.approx(dist)
    assert row["current_value"] == pytest.approx(cv)
    assert row["dpi"] == pytest.approx(dpi, abs=RATIO_TOL)
    assert row["rvpi"] == pytest.approx(rvpi, abs=RATIO_TOL)
    assert row["tvpi"] == pytest.approx(tvpi, abs=RATIO_TOL)
    assert row["irr"] == pytest.approx(irr, abs=IRR_TOL)


@pytest.mark.parametrize("client_name,asset_class,gap", EXPECTED_GAPS)
def test_allocation_gaps(data, client_name, asset_class, gap):
    investments, _, targets = data
    gaps = allocation_gaps(investments, targets)
    row = gaps[(gaps["client_name"] == client_name) & (gaps["asset_class"] == asset_class)]
    assert len(row) == 1
    assert row["gap_pp"].iloc[0] == pytest.approx(gap, abs=GAP_TOL)


def test_xirr_simple_known_answer():
    # -100 today, +110 exactly 365 days later -> exactly 10% per year.
    assert xirr(["2023-01-01", "2024-01-01"], [-100, 110]) == pytest.approx(0.10, abs=1e-9)


def test_results_do_not_depend_on_row_order(data):
    # Shuffling the cash-flow rows must not change any result.
    investments, cash_flows, _ = data
    shuffled = cash_flows.sample(frac=1, random_state=42).reset_index(drop=True)
    a = private_investment_metrics(investments, cash_flows)
    b = private_investment_metrics(investments, shuffled)
    for col in ["paid_in", "distributions", "dpi", "rvpi", "tvpi", "irr"]:
        assert a[col].tolist() == pytest.approx(b[col].tolist())


@pytest.mark.parametrize("inv_id,unfunded", EXPECTED_UNFUNDED.items())
def test_unfunded(pm, inv_id, unfunded):
    assert pm.loc[inv_id, "unfunded"] == pytest.approx(unfunded)


@pytest.mark.parametrize("client_id,expected", EXPECTED_COVERAGE)
def test_capital_call_coverage(data, client_id, expected):
    investments, cash_flows, _ = data
    cov = capital_call_coverage(investments, cash_flows)
    assert cov.loc[client_id, "coverage"] == pytest.approx(expected)


@pytest.mark.parametrize("client_name,asset_class,amount", EXPECTED_REBALANCE)
def test_rebalancing(data, client_name, asset_class, amount):
    investments, _, targets = data
    rb = rebalancing(investments, targets)
    row = rb[(rb["client_name"] == client_name) & (rb["asset_class"] == asset_class)]
    assert len(row) == 1
    assert row["rebalance"].iloc[0] == pytest.approx(amount, abs=0.01)


def test_rebalancing_sums_to_zero(data):
    investments, _, targets = data
    rb = rebalancing(investments, targets)
    for client_id, total in rb.groupby("client_id")["rebalance"].sum().items():
        assert total == pytest.approx(0, abs=0.01), client_id
