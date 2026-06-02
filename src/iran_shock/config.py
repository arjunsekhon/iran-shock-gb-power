"""Project-wide parameters. One source of truth for the window and the filter."""

from datetime import datetime

WINDOW_START = datetime(2026, 1, 1)  # extended baseline: 1 month of pre-shock data before 28 Feb war start
WINDOW_END = datetime(2026, 5, 31, 23, 0, 0)
SAMPLE_MINUTES = 15  # 15 = every file (full cadence); 60 = hourly sample
MIDDLE_EAST = [
    "IR",
    "IS",
    "US",
    "SA",
    "AE",
    "QA",
    "IZ",
    "KU",
    "BA",
    "LE",
    "SY",
    "YM",
]  # FIPS codes
RAW_DIR = "data/raw/gdelt"
EXPORT_DIR = "data/exports"
DUCKDB_PATH = "iran.duckdb"
AWS_REGION = "eu-west-2"  # used in Stage 3
S3_BUCKET = "iran-shock-XXX"  # set to your bucket in Stage 3

# ---- Clean Spark Spread (theoretical CCGT margin) ----
# Modern CCGT (~54% efficient): thermal MWh per electrical MWh
HEAT_RATE_CCGT = 1.85
# Modern CCGT carbon intensity (tCO2 / MWh electric)
EMISSIONS_FACTOR_CCGT = 0.36
# EUR -> GBP for converting TTF (€/MWh) to GBP. Flat for the project window; v2 would
# pull from FRED daily. EUR/GBP averaged ~0.85 across Jan–May 2026.
EUR_GBP_RATE = 0.85

# UKA proxy: KraneShares Global Carbon Strategy ETF (KRBN) anchored to a documented
# base UKA price at the start of the window. The basis adjustment captures *relative*
# moves; absolute level is the documented anchor. See `fetch_uka_proxy` in prices.py.
UKA_PROXY_TICKER = "KRBN"
UKA_BASE_PRICE_GBP_PER_TCO2 = 72.0  # ~early-2026 UKA ICE spot
UKA_BASE_DATE = "2026-01-02"  # first KRBN print in window

# ---- GDELT GKG ingest cadence + theme filter ----
GKG_RAW_DIR = "data/raw/gdelt_gkg"
# 360 = every 6 hours (4 files/day). 15 = full cadence (~14k files, ~45GB raw).
# Keep this at 360 for the demo; production-grade analysis would use 60 or 15.
GKG_SAMPLE_MINUTES = 360
# Filter applied row-by-row at download time. Drops ~80-85% of GKG rows;
# keeps energy + conflict + maritime themes relevant to the project hypothesis.
GKG_THEME_FILTER = [
    b"ECON_OIL",
    b"ECON_OILEXPORT",
    b"ENERGY_SECURITY",
    b"ENV_NATGAS",
    b"ENV_NUCLEARPOWER",
    b"MARITIME_TRANSPORT",
    b"MARITIME_INCIDENT",
    b"MILITARY_OPERATIONS",
    b"ARMEDCONFLICT",
    b"TERROR",
    b"WB_2042_OIL_INDUSTRY",
]
