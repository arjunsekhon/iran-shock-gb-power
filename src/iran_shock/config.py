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
