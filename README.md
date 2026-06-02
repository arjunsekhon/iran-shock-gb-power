# Iran Shock Transmission to GB Power

An event-study testing whether the 2026 Iran conflict (Operation Epic Fury) transmitted from crude oil markets into GB wholesale power — and identifying the mechanism through which it did.

**Headline finding.** TTF→GB power Spearman ρ tightens from **+0.60** on low-gas-share days to **+0.90** on high-gas-share days. When gas is the marginal fuel in the GB merit order, European gas flows into GB power with near-perfect rank correlation; when wind and nuclear push gas out of the stack, transmission loosens. **The gas-as-marginal-fuel theory is confirmed in the data.**

**Live dashboard.** *(Tableau Public link to follow — also available as a notebook-rendered HTML page via GitHub Pages.)*

![dashboard](assets/dashboard.png)

---

## Getting started

### Prerequisites

- **macOS or Linux** (Windows via WSL2 should also work).
- **Python 3.13+** — `uv` will install the right version automatically if missing.
- **~10 GB of free disk** for the full GDELT ingestion at 15-minute cadence (config-tunable; hourly sample uses ~2 GB).
- **Network access** to Yahoo Finance, Elexon BMRS, and `data.gdeltproject.org`.

### One-time install

```bash
# Install uv (the Python package manager used throughout — replaces pip/poetry/venv)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repo and theb cd into it
cd iran-shock-gb-power

# Restore the environment — uv reads pyproject.toml + uv.lock and creates .venv automatically
uv sync
```

### What gets ingested

| Source | Endpoint | What | Volume |
|---|---|---|---|
| **Brent** | Yahoo Finance `BZ=F` (via `yfinance`) | front-month crude futures, daily close (USD) | ~100 trading days |
| **TTF gas** | Yahoo Finance `TTF=F` (via `yfinance`) | European gas benchmark, daily close (€/MWh) | ~100 trading days |
| **GB MID power** | Elexon BMRS `/balancing/pricing/market-index?dataProviders=APXMIDP` | half-hourly Market Index Price → daily mean (£/MWh) | ~150 days (7-day calendar) |
| **GB FUELHH** | Elexon BMRS `/datasets/FUELHH` | half-hourly generation by fuel → daily fuel shares | ~150 days |
| **GDELT events** | `data.gdeltproject.org/gdeltv2/*.export.CSV.zip` | global news events with tone, geo, actors | ~12–16M rows (full cadence) |
| **Timeline** | hand-curated CSV in `data/epic_fury_timeline.csv` | 15 PDF-sourced events Feb–May 2026 | 15 rows |

Yahoo for Brent + TTF + Elexon for GB power + GDELT for news — all four are **free and require no API key**.

### Run the pipeline

```bash
uv run iran-shock-ingest-prices          # 1. Brent + GB MID + TTF + gen mix (~30s)
uv run iran-shock-ingest-gdelt           # 2. GDELT 15-min files            (1-3 hours)
uv run iran-shock-build                  # 3. load -> DuckDB; materialise views (~1m)
```

The three scripts are **idempotent and resumable** — safe to interrupt with Ctrl+C and re-run; already-downloaded files skip in milliseconds. `iran-shock-ingest-gdelt` can run unattended overnight.

When `iran-shock-build` finishes its sanity sweep, you have a populated `iran.duckdb` with **6 raw tables** (`timeline`, `brent`, `gb_power`, `ttf`, `gb_gen_mix`, `gdelt`) and **10 views** ready for analysis.

### Open the analysis

```bash
uv run jupyter lab notebooks/06_dashboard.ipynb
```

Jupyter Lab starts at <http://localhost:8888/lab/tree/> with the dashboard notebook open. Run all cells (Kernel → Restart and Run All) to render six panels: hero chart, news signal, event-impact table, conflict map, robustness stats, and conditional-transmission test.

Sanity-check what landed in DuckDB from the command line:

```bash
uv run python -c "import duckdb; print(duckdb.connect('iran.duckdb', read_only=True).execute('SELECT count(*) FROM gdelt').df())"
```

Or browse the DuckDB GUI:

```bash
uv run duckdb iran.duckdb -readonly -ui    # opens at http://localhost:4213/
```

## The question

When the Iran conflict escalated (28 February 2026), did the shock move from Brent crude into GB wholesale power — and is the mechanism *gas-as-marginal-fuel* rather than direct oil pricing?

Three series on one daily timeline (1 January – 31 May 2026): a GDELT conflict-news signal, Brent crude, TTF European gas, and GB Market Index Price for power. A 15-event curated conflict timeline anchors the event study. GB FUELHH generation-mix data tests the mechanism conditionally.

## Architecture

```text
GDELT 2.0 events ─┐                                            ┌─► Tableau Public (publish)
Brent (yfinance)  │                                            │
TTF (yfinance)    ├─► CLI ingest ─► data/raw/  ─► CLI build ─► iran.duckdb (10 views) ─┤
GB MID (Elexon)   │                                            │
GB FUELHH (Elexon)┘                                            └─► notebook 06 ─► plotly dashboard
                                                                                  (optional: HTML -> GitHub Pages)

                                                                                    │
                                                                                    └─► S3 + Athena (cloud port — same SQL)
```

Same SQL runs in DuckDB locally and Athena in the cloud.

## Repo structure

```text
src/iran_shock/    columns.py · config.py · gdelt.py · prices.py · cli.py
sql/               v_*.sql — canonical views (10; same shape in DuckDB and Athena)
notebooks/         01–03 (EDA tutorials) · 04–05 (read-only walkthroughs) · 06 (dashboard)
data/              epic_fury_timeline.csv · raw/ (gitignored) · exports/ (committed)
pipeline/          S3 + Athena DDL for the cloud port (Stage 3)
logs/              ingest_*.log · build.log (gitignored)
```

## Tech stack

- **Python** with `uv` for everything; **pandas**, **plotly**, **scipy**, **duckdb**, **yfinance**, **requests**
- **DuckDB** locally; **Athena** in the cloud (Stage 3); same SQL with three dialect swaps
- **Tableau Public** for the published dashboard; **plotly + GitHub Actions + GitHub Pages** for the auto-refreshing variant
- **AWS** (S3, Glue Data Catalog, Athena) for the cloud port