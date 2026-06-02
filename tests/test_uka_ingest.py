"""UKA proxy ingest tests.

Frozen-sample tests against the materialised raw CSV (skip if build hasn't run).
"""

from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture(scope="module")
def df():
    p = Path("data/raw/prices/uka_proxy.csv")
    if not p.exists():
        pytest.skip(f"{p} not present; run `uv run iran-shock-ingest-prices` first")
    return pd.read_csv(p)


def test_uka_proxy_csv_columns(df):
    """Schema is locked: ingest writes price_date, krbn_close, uka_proxy_gbp, source."""
    assert set(df.columns) == {"price_date", "krbn_close", "uka_proxy_gbp", "source"}


def test_uka_proxy_csv_rowcount_in_range(df):
    """Roughly ~100 trading days over 5 months; allow some slack."""
    assert 80 <= len(df) <= 130, f"expected ~100 trading days, got {len(df)}"


def test_uka_proxy_gbp_sensible_range(df):
    """UKA spot has traded ~£40–£90/tCO2 in 2024–2026; our proxy should be in that band."""
    uka = df["uka_proxy_gbp"].dropna()
    assert uka.min() > 30, f"UKA proxy min {uka.min()} below sensible floor £30/tCO2"
    assert uka.max() < 120, f"UKA proxy max {uka.max()} above sensible ceiling £120/tCO2"


def test_uka_proxy_source_tag(df):
    """source column tags every row with the upstream ticker."""
    assert set(df["source"].dropna().unique()) == {"KRBN"}
