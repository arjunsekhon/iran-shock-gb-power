"""Command-line entry points for the iran_shock pipeline.

Three-stage pipeline, each stage a CLI:

    ingest -> build -> analyse

    iran-shock-ingest-prices   Fetches Brent, GB MID, TTF, gb_gen_mix; writes data/raw/prices/*.csv
    iran-shock-ingest-gdelt    Downloads GDELT files; writes data/raw/gdelt/date=…/
    iran-shock-build           Loads raw -> DuckDB; materialises 16 SQL views

    notebooks/06_dashboard.ipynb  Pure read-only analysis on top of the built DuckDB.

Registered in pyproject.toml under [project.scripts]. Run from the project root.

Outputs:
    logs/ingest_gdelt.log                — GDELT run log (gitignored)
    logs/ingest_prices.log               — prices run log (gitignored)
    logs/build.log                       — build run log (gitignored)
    {EXPORT_DIR}/ingest_metrics.csv      — per-day GDELT file/event counts (committed)
    {EXPORT_DIR}/prices_metrics.csv      — per-source row count + date range (committed)
    data/raw/prices/{brent,gb_power,ttf}.csv  — materialised price series (gitignored)
    iran.duckdb                          — populated database (gitignored)
"""

import logging
import os
from pathlib import Path

import duckdb
import pandas as pd

from iran_shock.columns import EVENT_COLUMNS, GKG_COLUMNS
from iran_shock.config import (
    DUCKDB_PATH,
    EXPORT_DIR,
    RAW_DIR,
    SAMPLE_MINUTES,
    WINDOW_END,
    WINDOW_START,
)
from iran_shock.gdelt import build_export_urls, build_gkg_urls, download_all, download_all_gkg
from iran_shock.prices import (
    fetch_brent,
    fetch_gb_gen_mix,
    fetch_gb_power,
    fetch_ttf_gas,
    fetch_uka_proxy,
)

log = logging.getLogger("iran_shock.ingest")


def _configure_logging(log_path: Path) -> None:
    """Console + file handler; safe to re-call (clears prior handlers)."""
    log_path.parent.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s", "%Y-%m-%d %H:%M:%S")

    file_h = logging.FileHandler(log_path)
    file_h.setFormatter(fmt)

    console_h = logging.StreamHandler()
    console_h.setFormatter(fmt)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    root.addHandler(file_h)
    root.addHandler(console_h)


def _compute_daily_metrics(raw_dir: str) -> pd.DataFrame:
    """Walk RAW_DIR/date=YYYY-MM-DD/ partitions; count files and events (rows) per day.

    Each GDELT export row is one event, so newline-count gives the event count cheaply.
    """
    rows = []
    for partition in sorted(Path(raw_dir).glob("date=*")):
        date = partition.name.replace("date=", "")
        files = sorted(partition.glob("*.export.CSV"))
        events = 0
        for f in files:
            with open(f, "rb") as fp:
                events += fp.read().count(b"\n")
        rows.append({"date": date, "file_count": len(files), "event_count": events})
    return pd.DataFrame(rows)


def ingest_gdelt() -> int:
    """Download the configured GDELT window; emit per-day metrics; log to file + console."""
    log_path = Path("logs/ingest_gdelt.log")
    _configure_logging(log_path)

    log.info(
        "ingest started; window %s -> %s, sample=%dmin", WINDOW_START, WINDOW_END, SAMPLE_MINUTES
    )
    urls = build_export_urls(WINDOW_START, WINDOW_END, SAMPLE_MINUTES)
    log.info("%d files to consider (already-present ones will be skipped)", len(urls))

    n_ok, n_404, n_failed, failures = download_all(urls, RAW_DIR)
    log.info("download done: ok=%d  404=%d  failed=%d", n_ok, n_404, n_failed)
    for url, err in failures[:10]:
        log.warning("failed: %s -> %s", url, err)

    log.info("computing per-day metrics under %s ...", RAW_DIR)
    metrics = _compute_daily_metrics(RAW_DIR)
    os.makedirs(EXPORT_DIR, exist_ok=True)
    metrics_path = Path(EXPORT_DIR) / "ingest_metrics.csv"
    metrics.to_csv(metrics_path, index=False)

    log.info("wrote %s", metrics_path)
    log.info(
        "summary: days=%d  files=%d  events=%d",
        len(metrics),
        int(metrics["file_count"].sum()),
        int(metrics["event_count"].sum()),
    )
    log.info("log file: %s", log_path)

    return 0 if n_failed == 0 else 1


def ingest_gdelt_gkg() -> int:
    """Download GDELT GKG files with filter-at-ingest.

    Pulls config.GKG_SAMPLE_MINUTES-cadence GKG files between WINDOW_START and
    WINDOW_END, keeps only rows whose V2THEMES contains at least one of
    config.GKG_THEME_FILTER tokens. Idempotent and resumable; safe to re-run.
    """
    from iran_shock.config import GKG_RAW_DIR, GKG_SAMPLE_MINUTES, GKG_THEME_FILTER

    log_path = Path("logs/ingest_gdelt_gkg.log")
    _configure_logging(log_path)

    log.info(
        "GKG ingest started; window %s -> %s, sample=%dmin, themes=%d",
        WINDOW_START,
        WINDOW_END,
        GKG_SAMPLE_MINUTES,
        len(GKG_THEME_FILTER),
    )
    urls = build_gkg_urls(WINDOW_START, WINDOW_END, GKG_SAMPLE_MINUTES)
    log.info("%d GKG files to consider (already-present skipped)", len(urls))

    n_ok, n_404, n_failed, failures = download_all_gkg(urls, GKG_RAW_DIR, theme_filter=GKG_THEME_FILTER)
    log.info("download done: ok=%d  404=%d  failed=%d", n_ok, n_404, n_failed)
    for url, err in failures[:10]:
        log.warning("failed: %s -> %s", url, err)
    log.info("log file: %s", log_path)
    return 0 if n_failed == 0 else 1


def score_finbert() -> int:
    """Score with FinBERT — the SOURCEURL slugs of event-window articles.

    Idempotent — re-running skips already-scored URLs. Loads the model on first
    run (~440MB download), then runs CPU inference at ~25-50 sentences/sec.
    """
    log_path = Path("logs/score_finbert.log")
    _configure_logging(log_path)

    from iran_shock.finbert import score_event_day_urls

    log.info("connecting to %s for URL collection", DUCKDB_PATH)
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    out = score_event_day_urls(con)
    log.info("FinBERT scoring complete; output at %s", out)
    log.info("log file: %s", log_path)
    return 0


def ingest_prices() -> int:
    """Fetch Brent, GB power MID (APX), and TTF gas; write CSVs + per-source metrics."""
    log_path = Path("logs/ingest_prices.log")
    _configure_logging(log_path)

    raw_prices_dir = Path("data/raw/prices")
    raw_prices_dir.mkdir(parents=True, exist_ok=True)

    sources = [
        ("brent", fetch_brent),
        ("gb_power", fetch_gb_power),
        ("ttf", fetch_ttf_gas),
        ("gb_gen_mix", fetch_gb_gen_mix),
        ("uka_proxy", fetch_uka_proxy),
    ]

    metrics_rows = []
    failed = 0
    for name, fetcher in sources:
        log.info("fetching %s ...", name)
        try:
            df = fetcher()
            path = raw_prices_dir / f"{name}.csv"
            df.to_csv(path, index=False)
            first = df["price_date"].min() if not df.empty else None
            last = df["price_date"].max() if not df.empty else None
            log.info("wrote %s (%d rows, %s -> %s)", path, len(df), first, last)
            metrics_rows.append(
                {"source": name, "rows": len(df), "first_date": first, "last_date": last}
            )
        except Exception as e:
            log.error("FAILED %s: %s", name, e)
            failed += 1
            metrics_rows.append({"source": name, "rows": 0, "first_date": None, "last_date": None})

    os.makedirs(EXPORT_DIR, exist_ok=True)
    metrics_path = Path(EXPORT_DIR) / "prices_metrics.csv"
    pd.DataFrame(metrics_rows).to_csv(metrics_path, index=False)
    log.info("wrote %s", metrics_path)
    log.info("log file: %s", log_path)

    return 0 if failed == 0 else 1


def build() -> int:
    """Load raw CSVs into DuckDB and materialise the canonical SQL views.

    Run after `iran-shock-ingest-prices` and `iran-shock-ingest-gdelt`. Reads from
    data/epic_fury_timeline.csv, data/raw/prices/*.csv, and data/raw/gdelt/**/*.export.CSV;
    executes each sql/v_*.sql file in dependency order; produces a populated
    DuckDB at config.DUCKDB_PATH with 7 tables and 16 views.
    """
    log_path = Path("logs/build.log")
    _configure_logging(log_path)

    log.info("connecting to %s", DUCKDB_PATH)
    con = duckdb.connect(DUCKDB_PATH)

    # ---- raw tables ----
    log.info("loading timeline from data/epic_fury_timeline.csv")
    con.execute("""
        CREATE OR REPLACE TABLE timeline AS
        SELECT * FROM read_csv('data/epic_fury_timeline.csv', header=true)
    """)

    log.info("loading price tables from data/raw/prices/")
    for name in ("brent", "gb_power", "ttf", "gb_gen_mix", "uka_proxy"):
        path = f"data/raw/prices/{name}.csv"
        if not Path(path).exists():
            log.error("missing %s — run `uv run iran-shock-ingest-prices` first", path)
            return 1
        con.execute(
            f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_csv('{path}', header=true)"
        )

    log.info("loading gdelt from %s/**/*.export.CSV (all VARCHAR)", RAW_DIR)
    if not any(Path(RAW_DIR).glob("date=*/*.export.CSV")):
        log.error("no GDELT files under %s — run `uv run iran-shock-ingest-gdelt` first", RAW_DIR)
        return 1
    names = [c.lower() for c in EVENT_COLUMNS]
    con.execute(f"""
        CREATE OR REPLACE TABLE gdelt AS
        SELECT * FROM read_csv('{RAW_DIR}/**/*.export.CSV',
            delim='\t', header=false, names={names}, all_varchar=true)
    """)

    # ---- GDELT GKG — optional; load if present ----
    from iran_shock.config import GKG_RAW_DIR

    if any(Path(GKG_RAW_DIR).glob("date=*/*.gkg.csv")):
        log.info("loading gdelt_gkg from %s/**/*.gkg.csv (all VARCHAR)", GKG_RAW_DIR)
        gkg_names = [c.lower() for c in GKG_COLUMNS]
        con.execute(f"""
            CREATE OR REPLACE TABLE gdelt_gkg AS
            SELECT * FROM read_csv('{GKG_RAW_DIR}/**/*.gkg.csv',
                delim='\t', header=false, names={gkg_names}, all_varchar=true,
                ignore_errors=true)
        """)
    else:
        log.info("no gdelt_gkg files under %s — GKG views will be skipped", GKG_RAW_DIR)

    # ---- FinBERT headline scores — optional ----
    finbert_path = Path("data/raw/finbert/headline_scores.csv")
    if finbert_path.exists():
        log.info("loading finbert_scores from %s", finbert_path)
        con.execute(
            f"CREATE OR REPLACE TABLE finbert_scores AS "
            f"SELECT * FROM read_csv('{finbert_path}', header=true, all_varchar=false)"
        )
    else:
        log.info("no finbert_scores at %s — v_finbert_daily view will be skipped", finbert_path)

    # ---- views from sql/, in dependency order ----
    view_files = [
        "v_middle_east_events.sql",  # depends on gdelt
        "v_event_geo.sql",  # depends on gdelt
        "v_brent_daily.sql",  # depends on brent
        "v_gb_power_daily.sql",  # depends on gb_power
        "v_ttf_daily.sql",  # depends on ttf
        "v_gb_gen_mix_daily.sql",  # depends on gb_gen_mix
        "v_combined_daily.sql",  # depends on the four above
        "v_event_impact.sql",  # depends on timeline + price views (Brent-anchored t/t+3)
        "v_event_impact_multi.sql",  # multi-horizon (t+1, t+3, t+5, t+10)
        "v_event_impact_regime.sql",  # gas-share regime split (conditional-transmission test)
        "v_news_burst_daily.sql",  # Hawkes-inspired burst score
        "v_gdelt_tone_asymmetry_daily.sql",  # TGARCH-inspired tone split
        "v_event_impact_multi_phase.sql",  # phase-aware multi-horizon split
        "v_uka_proxy_daily.sql",  # UKA proxy daily series (KRBN-anchored)
        "v_clean_spark_spread_daily.sql",  # theoretical CCGT margin + observed power
        "v_css_regime_event_impact.sql",  # per-event CSS residual by gas regime
        "v_gdelt_events_features_daily.sql",  # Goldstein × NumMentions, QuadClass, EventRootCode
        "v_implied_ttf_daily.sql",  # implied TTF / basis (inverse CSS)
    ]
    # GKG views — applied only if gdelt_gkg table exists.
    gkg_view_files = [
        "v_gkg_tone_daily.sql",  # 6-part tone vector + dispersion
        "v_gdelt_gkg_themes_daily.sql",  # energy/maritime/conflict theme counts
        "v_gdelt_gkg_hormuz_daily.sql",  # Hormuz / Persian Gulf / Kharg / Ras Laffan mentions
        "v_gdelt_gkg_gcam_daily.sql",  # cherry-picked GCAM emotion dimensions
    ]
    has_gkg = (
        con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = 'gdelt_gkg'"
        ).fetchone()[0]
        > 0
    )
    finbert_view_files = ["v_finbert_daily.sql"]  # FinBERT daily
    has_finbert = (
        con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = 'finbert_scores'"
        ).fetchone()[0]
        > 0
    )
    for vfile in view_files:
        path = Path("sql") / vfile
        if not path.exists():
            log.error("missing %s", path)
            return 1
        log.info("applying %s", path)
        con.execute(path.read_text())

    if has_gkg:
        for vfile in gkg_view_files:
            path = Path("sql") / vfile
            if not path.exists():
                log.error("missing %s", path)
                return 1
            log.info("applying %s (GKG)", path)
            con.execute(path.read_text())
    else:
        log.info("gdelt_gkg table absent; skipping %d GKG views", len(gkg_view_files))

    if has_finbert:
        for vfile in finbert_view_files:
            path = Path("sql") / vfile
            log.info("applying %s (FinBERT)", path)
            con.execute(path.read_text())
    else:
        log.info("finbert_scores table absent; skipping v_finbert_daily")

    # ---- sanity sweep ----
    log.info("sanity sweep:")
    failed = 0
    for name in [
        "timeline",
        "brent",
        "gb_power",
        "ttf",
        "gb_gen_mix",
        "uka_proxy",
        "gdelt",
        "v_middle_east_events",
        "v_event_geo",
        "v_brent_daily",
        "v_gb_power_daily",
        "v_ttf_daily",
        "v_gb_gen_mix_daily",
        "v_combined_daily",
        "v_event_impact",
        "v_event_impact_multi",
        "v_event_impact_regime",
        "v_news_burst_daily",
        "v_gdelt_tone_asymmetry_daily",
        "v_event_impact_multi_phase",
        "v_uka_proxy_daily",
        "v_clean_spark_spread_daily",
        "v_css_regime_event_impact",
        "v_gdelt_events_features_daily",
        "v_implied_ttf_daily",
    ] + (
        [
            "gdelt_gkg",
            "v_gkg_tone_daily",
            "v_gdelt_gkg_themes_daily",
            "v_gdelt_gkg_hormuz_daily",
            "v_gdelt_gkg_gcam_daily",
        ]
        if has_gkg
        else []
    ) + (["finbert_scores", "v_finbert_daily"] if has_finbert else []):
        try:
            n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            log.info("  %-25s %10s rows", name, f"{n:,}")
            if n == 0:
                log.warning("  %s has zero rows", name)
                failed += 1
        except Exception as e:
            log.error("  %s: %s", name, e)
            failed += 1

    log.info("build done; log file: %s", log_path)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(ingest_gdelt())
