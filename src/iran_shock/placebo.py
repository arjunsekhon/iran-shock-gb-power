"""Placebo / permutation test for the event-study impact distribution.

If the curated event days really carry shock information, the distribution of
per-event impacts (Brent / TTF / power at t+3) should differ materially from
the distribution you get by picking the same number of *random non-event days*
from the same window.

Procedure:
    1. Cache the daily Brent / TTF / power series joined on Brent's trading-day
       calendar (same anchor as v_event_impact).
    2. For each trading day t0 compute the % move to the next trading day at
       or after t0 + 3 calendar days. Drop rows without a valid t3 lookup.
    3. Mark trading days that fall on the curated event list as ineligible.
    4. Bootstrap n_bootstrap iterations of "sample N=14 from the eligible pool,
       take the mean t+3 % impact". Returns one row per iteration.
    5. Empirical rank of the real-event mean in the placebo distribution gives
       a permutation-test p-value-style read.

Used by notebooks/06_dashboard.ipynb. Deterministic when SEED is fixed.
"""

import duckdb
import numpy as np
import pandas as pd

SEED = 42
N_BOOTSTRAP = 1000
N_SAMPLE = 14  # match the curated timeline length; updated automatically at runtime
T_PLUS_DAYS = 3


def _trading_series(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Join Brent / TTF / power on Brent's trading-day calendar."""
    df = con.execute("""
        SELECT b.price_date,
               b.brent_close,
               (SELECT ttf_close    FROM v_ttf_daily      WHERE price_date = b.price_date) AS ttf_close,
               (SELECT gb_power_avg FROM v_gb_power_daily WHERE price_date = b.price_date) AS power_avg
        FROM v_brent_daily b
        ORDER BY b.price_date
    """).df()
    df["price_date"] = pd.to_datetime(df["price_date"])
    return df.set_index("price_date").sort_index()


def _real_event_dates(con: duckdb.DuckDBPyConnection) -> pd.DatetimeIndex:
    """The curated event dates from the timeline (normalised midnight UTC-naïve)."""
    df = con.execute("SELECT event_date FROM timeline ORDER BY event_date").df()
    return pd.DatetimeIndex(pd.to_datetime(df["event_date"])).normalize()


def _attach_t3(df: pd.DataFrame, t_plus_days: int = T_PLUS_DAYS) -> pd.DataFrame:
    """Add t3_date column: first trading day at or after t0 + t_plus_days days."""
    trading_days = df.index
    t3_lookups = []
    for t0 in trading_days:
        target = t0 + pd.Timedelta(days=t_plus_days)
        mask = trading_days >= target
        t3_lookups.append(trading_days[mask].min() if mask.any() else pd.NaT)
    out = df.copy()
    out["t3_date"] = t3_lookups
    return out


def _impacts(df_with_t3: pd.DataFrame) -> pd.DataFrame:
    """Compute t+3 % changes for Brent / TTF / power on every eligible row."""
    eligible = df_with_t3.dropna(subset=["t3_date"]).copy()
    for col, suffix in (("brent_close", "brent"), ("ttf_close", "ttf"), ("power_avg", "power")):
        t3_vals = df_with_t3.loc[eligible["t3_date"], col].to_numpy()
        t0_vals = eligible[col].to_numpy()
        with np.errstate(divide="ignore", invalid="ignore"):
            eligible[f"{suffix}_pct_3d"] = 100.0 * (t3_vals - t0_vals) / t0_vals
    return eligible


def real_event_impacts(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per-event t+3 impacts for the curated event dates, on the trading calendar."""
    series = _attach_t3(_trading_series(con))
    impacts = _impacts(series)
    events = _real_event_dates(con)
    rows = []
    for ev in events:
        t0_mask = series.index >= ev
        if not t0_mask.any():
            continue
        t0 = series.index[t0_mask].min()
        if t0 not in impacts.index:
            continue
        row = impacts.loc[t0]
        rows.append(
            {
                "event_date": ev,
                "t0_date": t0,
                "brent_pct_3d": row["brent_pct_3d"],
                "ttf_pct_3d": row["ttf_pct_3d"],
                "power_pct_3d": row["power_pct_3d"],
            }
        )
    return pd.DataFrame(rows)


def placebo_distribution(
    con: duckdb.DuckDBPyConnection,
    n_sample: int = N_SAMPLE,
    n_bootstrap: int = N_BOOTSTRAP,
    seed: int = SEED,
) -> pd.DataFrame:
    """Bootstrap: for n_bootstrap iterations, sample n_sample random non-event
    trading days; compute the mean t+3 % impact for Brent / TTF / power; return
    one row per iteration.
    """
    rng = np.random.default_rng(seed)

    series = _attach_t3(_trading_series(con))
    impacts = _impacts(series)

    event_dates = set(_real_event_dates(con))
    eligible_mask = ~impacts.index.normalize().isin(event_dates)
    eligible = impacts[eligible_mask]
    if len(eligible) < n_sample:
        raise ValueError(f"need at least {n_sample} eligible non-event days; have {len(eligible)}")

    rows = []
    for i in range(n_bootstrap):
        chosen_idx = rng.choice(len(eligible), size=n_sample, replace=False)
        chosen = eligible.iloc[chosen_idx]
        rows.append(
            {
                "iter": i,
                "brent_pct_3d_mean": chosen["brent_pct_3d"].mean(),
                "ttf_pct_3d_mean": chosen["ttf_pct_3d"].mean(),
                "power_pct_3d_mean": chosen["power_pct_3d"].mean(),
            }
        )
    return pd.DataFrame(rows)


def empirical_rank(real_mean: float, placebo_means: pd.Series) -> float:
    """Empirical rank of real_mean within the placebo distribution, in [0, 1].

    Returns 0.95 if real_mean exceeds 95% of placebo values.
    NaN-safe: drops nulls from the placebo series before ranking.
    """
    p = placebo_means.dropna()
    if len(p) == 0 or pd.isna(real_mean):
        return float("nan")
    return float((p < real_mean).mean())
