"""Implied TTF / implied heat rate tests."""

from pathlib import Path

import duckdb
import pytest

from iran_shock.config import DUCKDB_PATH


@pytest.fixture(scope="module")
def con():
    if not Path(DUCKDB_PATH).exists():
        pytest.skip(f"{DUCKDB_PATH} not present; run `uv run iran-shock-build` first")
    return duckdb.connect(DUCKDB_PATH, read_only=True)


def test_implied_ttf_view_has_rows(con):
    n = con.execute("SELECT count(*) FROM v_implied_ttf_daily").fetchone()[0]
    assert n > 50, f"expected >50 rows, got {n}"


def test_implied_ttf_is_algebraic_inverse_of_css(con):
    """Implied TTF is the algebraic inverse of CSS:
        css = power − (ttf × heat_rate × eur_gbp) − (uka × emissions_factor)
        implied_ttf = (power − uka × emissions_factor) / (heat_rate × eur_gbp)
    So substituting ttf = implied_ttf back into the CSS formula should give
    residual = 0 (within floating-point rounding).
    """
    df = con.execute("""
        SELECT power_observed_gbp_mwh, implied_ttf_eur_mwh, uka_proxy_gbp_per_tco2
        FROM v_implied_ttf_daily
        LIMIT 50
    """).df()
    HEAT_RATE_CCGT = 1.85
    EMISSIONS_FACTOR_CCGT = 0.36
    EUR_GBP_RATE = 0.85
    # Reconstruct: theoretical_css = ttf*HR*FX + uka*EF; residual = power - theoretical
    df["theoretical_at_implied"] = (
        df["implied_ttf_eur_mwh"] * HEAT_RATE_CCGT * EUR_GBP_RATE
        + df["uka_proxy_gbp_per_tco2"] * EMISSIONS_FACTOR_CCGT
    )
    df["residual"] = df["power_observed_gbp_mwh"] - df["theoretical_at_implied"]
    # Allow ±£0.05 — view rounds to 2 dp.
    assert df["residual"].abs().max() < 0.05, (
        f"max residual {df['residual'].abs().max():.4f} exceeds rounding budget; "
        "implied_ttf is not the algebraic inverse"
    )


def test_observed_vs_implied_correlation_higher_on_high_gas(con):
    """Headline mechanism check: observed TTF tracks implied TTF only when gas is
    marginal. r(high_gas) should beat r(low_gas) by a clear margin.
    """
    hi = con.execute(
        "SELECT observed_ttf_eur_mwh, implied_ttf_eur_mwh "
        "FROM v_implied_ttf_daily WHERE regime = 'high_gas'"
    ).df()
    lo = con.execute(
        "SELECT observed_ttf_eur_mwh, implied_ttf_eur_mwh "
        "FROM v_implied_ttf_daily WHERE regime = 'low_gas'"
    ).df()
    r_hi = hi.corr().iloc[0, 1]
    r_lo = lo.corr().iloc[0, 1]
    assert r_hi - r_lo >= 0.3, (
        f"high-gas r={r_hi:.2f}, low-gas r={r_lo:.2f}; gap {r_hi - r_lo:.2f} below 0.3 — "
        "merit-order inverse-mechanism check failed"
    )
