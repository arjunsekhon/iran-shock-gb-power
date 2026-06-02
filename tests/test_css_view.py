"""Clean Spark Spread view tests.

Sanity checks against the materialised v_clean_spark_spread_daily view.
"""

from pathlib import Path

import duckdb
import pytest

from iran_shock.config import DUCKDB_PATH


@pytest.fixture(scope="module")
def con():
    if not Path(DUCKDB_PATH).exists():
        pytest.skip(f"{DUCKDB_PATH} not present; run `uv run iran-shock-build` first")
    return duckdb.connect(DUCKDB_PATH, read_only=True)


def test_css_view_has_rows(con):
    n = con.execute("SELECT count(*) FROM v_clean_spark_spread_daily").fetchone()[0]
    assert n > 50, f"expected >50 daily rows, got {n}"


def test_css_components_non_negative(con):
    """Fuel + carbon cost are always >= 0 when inputs are well-formed."""
    df = con.execute("""
        SELECT MIN(fuel_cost_gbp_mwh)   AS min_fuel,
               MIN(carbon_cost_gbp_mwh) AS min_carbon
        FROM v_clean_spark_spread_daily
        WHERE ttf_close IS NOT NULL AND uka_proxy_gbp_per_tco2 IS NOT NULL
    """).fetchone()
    assert df[0] >= 0, f"fuel_cost has negative minimum: {df[0]}"
    assert df[1] >= 0, f"carbon_cost has negative minimum: {df[1]}"


def test_css_residual_smaller_on_high_gas_days(con):
    """Merit-order spec: observed power tracks theoretical CCGT margin more closely
    when gas is the marginal fuel. So |residual| should be smaller (and correlation
    higher) on high-gas days than on low-gas days.
    """
    rows = con.execute("""
        SELECT regime,
               AVG(ABS(residual_gbp_mwh)) AS mean_abs_residual,
               STDDEV(residual_gbp_mwh)   AS std_residual
        FROM v_clean_spark_spread_daily
        WHERE regime IN ('high_gas', 'low_gas')
          AND ttf_close IS NOT NULL
          AND uka_proxy_gbp_per_tco2 IS NOT NULL
        GROUP BY regime
    """).df()
    hi = rows[rows["regime"] == "high_gas"].iloc[0]
    lo = rows[rows["regime"] == "low_gas"].iloc[0]
    # Std should be smaller (less dispersion); means are biased by sign so we check std + r below.
    assert hi["std_residual"] < lo["std_residual"], (
        f"high-gas residual std {hi['std_residual']:.1f} >= low-gas {lo['std_residual']:.1f}; "
        "expected high-gas tighter under merit-order"
    )


def test_css_observed_vs_theoretical_correlation_higher_on_high_gas(con):
    """The headline mechanism test: Pearson r between observed power and theoretical
    CSS should be materially higher on high-gas days than on low-gas days.
    """
    hi = con.execute("""
        SELECT power_observed_gbp_mwh, theoretical_css_gbp_mwh
        FROM v_clean_spark_spread_daily
        WHERE regime = 'high_gas' AND theoretical_css_gbp_mwh IS NOT NULL
    """).df()
    lo = con.execute("""
        SELECT power_observed_gbp_mwh, theoretical_css_gbp_mwh
        FROM v_clean_spark_spread_daily
        WHERE regime = 'low_gas' AND theoretical_css_gbp_mwh IS NOT NULL
    """).df()
    r_hi = hi.corr().iloc[0, 1]
    r_lo = lo.corr().iloc[0, 1]
    assert r_hi - r_lo >= 0.3, (
        f"high-gas r={r_hi:.2f}, low-gas r={r_lo:.2f}; gap {r_hi - r_lo:.2f} < 0.3 — "
        "merit-order mechanism not visible at expected magnitude"
    )
