"""Command-line entry points for the iran_shock pipeline.

Three-stage pipeline, each stage a CLI:

    ingest -> build -> analyse

    iran-shock-ingest-prices   Fetches Brent, GB MID, TTF, gb_gen_mix; writes data/raw/prices/*.csv
    iran-shock-ingest-gdelt    Downloads GDELT files; writes data/raw/gdelt/date=…/
    iran-shock-build           Loads raw -> DuckDB; materialises 10 SQL views

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

from iran_shock.columns import EVENT_COLUMNS
from iran_shock.config import (
    DUCKDB_PATH,
    EXPORT_DIR,
    RAW_DIR,
    SAMPLE_MINUTES,
    WINDOW_END,
    WINDOW_START,
)
from iran_shock.gdelt import build_export_urls, download_all
from iran_shock.prices import fetch_brent, fetch_gb_gen_mix, fetch_gb_power, fetch_ttf_gas

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
    DuckDB at config.DUCKDB_PATH with 6 tables and 10 views.
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
    for name in ("brent", "gb_power", "ttf", "gb_gen_mix"):
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
    ]
    for vfile in view_files:
        path = Path("sql") / vfile
        if not path.exists():
            log.error("missing %s", path)
            return 1
        log.info("applying %s", path)
        con.execute(path.read_text())

    # ---- sanity sweep ----
    log.info("sanity sweep:")
    failed = 0
    for name in [
        "timeline",
        "brent",
        "gb_power",
        "ttf",
        "gb_gen_mix",
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
    ]:
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
