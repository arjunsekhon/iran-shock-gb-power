# CLAUDE.md

Project memory for Claude Code on this repo.

## What this is

A learning project: GDELT news data + Brent + TTF gas + GB MID (Elexon, APX submission) + GB FUELHH generation mix. Tests the conditional-transmission hypothesis (gas-as-marginal-fuel). Runs locally on DuckDB, ports to AWS S3 + Athena unchanged. Three-stage pipeline: ingest (`iran-shock-ingest-prices`, `iran-shock-ingest-gdelt`) → build (`iran-shock-build`) → analyse (notebook 06).

## Tone

- UK English. `behaviour`, `favourable`, `colour`.
- Reserved, concise, succinct. Less is more.
- No editorialising or marketing language ("killer detail", "ages well", "real data work runs into…"). Just facts.
- Code comments default to none. Only add when the *why* is non-obvious.
- Doc style is terse — short sentences, bullets, tables. Don't add paragraphs of "why" unless I ask.

## Stack & tooling

- `uv` for everything (`uv add`, `uv run`, `uv add --dev`). Not pip/poetry.
- Formatter + linter: `ruff format` and `ruff check`. Not black, not isort.
- Test runner: pytest with pytest-asyncio.
- Python 3.13, target-version `py313`.
- DuckDB locally; Athena in cloud; same SQL (give or take `strptime` ↔ `date_parse`).
- Hive-style partitioning (`date=YYYY-MM-DD/`), not Iceberg

## Project conventions

- Every notebook starts with the `chdir`-to-`pyproject.toml` bootstrap cell. Reason: Jupyter CWD = notebook folder.
- **Scripts do build operations; notebooks do analysis.** Notebooks 04 and 05 are read-only tutorials. `iran-shock-build` materialises the DuckDB; notebooks read from it via `read_only=True`.
- GDELT loads as all-VARCHAR; casts happen in the SQL views, not at load time.
- **Cross-series joins anchor on Brent's trading-day calendar** (no weekends/holidays). `v_event_impact` uses a CTE to find Brent's t0/t3 dates, then equality-joins TTF / power / gas-mix on those same dates. Per-series nearest-trading-day lookups silently mix calendars;
- `sql/v_*.sql` files are the canonical source of truth for views; build executes them in dependency order.
- One source of truth for parameters: `src/iran_shock/config.py`. Keep `MIDDLE_EAST` list in step with the SQL IN-list.
- Network ingestion is idempotent + resumable (atomic-rename + size-check skip) and retries transient errors with exponential backoff.
- Consumers read from `v_*` views, never raw tables.

## Behaviour

- Don't bloat docs without being asked — propose changes first if they're more than a few lines.
- Default no `/schedule` offers. Don't suggest agents/skills unless I ask.
- For UI changes (Tableau, notebooks, dashboards), say so explicitly if you can't actually run/verify the result.
- Memory directory is for cross-session preferences — feel free to update it when I correct tone, tooling, or workflow.
