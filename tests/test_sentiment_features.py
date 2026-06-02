"""GDELT events features + GKG + FinBERT view tests."""

from pathlib import Path

import duckdb
import pytest

from iran_shock.config import DUCKDB_PATH


@pytest.fixture(scope="module")
def con():
    if not Path(DUCKDB_PATH).exists():
        pytest.skip(f"{DUCKDB_PATH} not present; run `uv run iran-shock-build` first")
    return duckdb.connect(DUCKDB_PATH, read_only=True)


def test_gdelt_events_features_has_goldstein_signal(con):
    """mentions_weighted_goldstein should be a stronger TTF-t+3 signal
    than the bare AvgTone (and stronger than mentions_weighted_tone).

    Empirically: |r(mentions_weighted_goldstein, ttf_pct_3d)| > |r(mean_tone, ttf_pct_3d)|
    over 55 trading-day pairs. This is the headline GDELT-audit finding — the
    free-zero-cost upgrade is real signal, not noise.
    """
    df = con.execute("""
        SELECT f.mean_tone, f.mentions_weighted_tone,
               f.mentions_weighted_goldstein,
               t.ttf_close
        FROM v_gdelt_events_features_daily f
        LEFT JOIN v_ttf_daily t ON t.price_date = f.event_date
        ORDER BY f.event_date
    """).df()
    df["ttf_pct_3d"] = df["ttf_close"].pct_change(3) * 100
    clean = df.dropna(subset=["mentions_weighted_goldstein", "ttf_pct_3d"])
    r_tone = clean["mean_tone"].corr(clean["ttf_pct_3d"])
    r_gold = clean["mentions_weighted_goldstein"].corr(clean["ttf_pct_3d"])
    assert abs(r_gold) > abs(r_tone), (
        f"mentions_weighted_goldstein r={r_gold:+.3f} not stronger than mean_tone r={r_tone:+.3f}; "
        "GDELT audit claim broken"
    )


def test_gkg_views_have_rows(con):
    """All four GKG views materialised with sensible row counts."""
    for view, min_rows in [
        ("v_gkg_tone_daily", 80),
        ("v_gdelt_gkg_themes_daily", 80),
        ("v_gdelt_gkg_hormuz_daily", 80),
        ("v_gdelt_gkg_gcam_daily", 80),
    ]:
        try:
            n = con.execute(f"SELECT count(*) FROM {view}").fetchone()[0]
        except duckdb.CatalogException:
            pytest.skip(f"{view} not built (GKG ingest not run?)")
        assert n >= min_rows, f"{view} has only {n} rows; expected >= {min_rows}"


def test_gkg_themes_oil_jumps_on_qatar_lng_event(con):
    """n_econ_oil on the 18 March Qatar LNG strike day should sit
    well above the median day. Tests that energy-theme picks actually track
    the project's named events.
    """
    try:
        df = con.execute(
            "SELECT event_date, n_econ_oil FROM v_gdelt_gkg_themes_daily ORDER BY event_date"
        ).df()
    except duckdb.CatalogException:
        pytest.skip("GKG view not built")
    median = df["n_econ_oil"].median()
    qatar = df[df["event_date"] == "2026-03-18"]["n_econ_oil"]
    assert len(qatar) == 1
    val = qatar.iloc[0]
    assert val > 1.5 * median, (
        f"18 Mar Qatar LNG day had {val} ECON_OIL articles vs median {median}; "
        "expected >= 1.5x"
    )


def test_finbert_daily_view_uncorrelated_with_avgtone(con):
    """FinBERT signed daily mean should be only *weakly* correlated
    with AvgTone (|r| < 0.5). If they correlated tightly, FinBERT would be
    redundant; the weak correlation is exactly the case for the upgrade.
    """
    try:
        df = con.execute("""
            SELECT f.mean_finbert_signed, m.avg_tone
            FROM v_finbert_daily f
            JOIN v_middle_east_events m ON m.event_date = f.event_date
        """).df()
    except duckdb.CatalogException:
        pytest.skip("v_finbert_daily not built (FinBERT not run?)")
    if len(df) < 30:
        pytest.skip(f"only {len(df)} day-pairs; need >= 30")
    r = df["mean_finbert_signed"].corr(df["avg_tone"])
    assert abs(r) < 0.5, (
        f"FinBERT ↔ AvgTone r={r:+.3f}; >0.5 would mean FinBERT is redundant"
    )
