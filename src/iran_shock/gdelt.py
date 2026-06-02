import io
import logging
import os
import time
import zipfile
from datetime import datetime, timedelta

import requests

GDELTV2 = "http://data.gdeltproject.org/gdeltv2"

log = logging.getLogger(__name__)


def build_export_urls(start: datetime, end: datetime, every_minutes: int = 60):
    """every_minutes=15 -> all files; 60 -> hourly sample."""
    urls, t = [], start
    while t <= end:
        urls.append(f"{GDELTV2}/{t:%Y%m%d%H%M%S}.export.CSV.zip")
        t += timedelta(minutes=every_minutes)
    return urls


def build_gkg_urls(start: datetime, end: datetime, every_minutes: int = 360):
    """GDELT GKG file URLs at the requested cadence.

    GKG (Global Knowledge Graph) is GDELT's richer per-article file:
    themes, locations, persons, organisations, counts, GCAM dimensions.

    every_minutes=15  -> full cadence, ~14k files for our window (~45GB raw)
    every_minutes=60  -> hourly,        ~3.6k files                (~10GB)
    every_minutes=360 -> every 6 hours, ~600 files                 (~2GB) -- demo default
    every_minutes=1440 -> daily noon,   ~150 files                 (~500MB)

    URL pattern: {YYYYMMDDHHMMSS}.gkg.csv.zip (same timestamp grid as exports).
    """
    urls, t = [], start
    while t <= end:
        urls.append(f"{GDELTV2}/{t:%Y%m%d%H%M%S}.gkg.csv.zip")
        t += timedelta(minutes=every_minutes)
    return urls


def download_gkg_to_disk(url, out_dir, *, timeout=60, max_attempts=4, theme_filter=None):
    """Download+unzip+filter one GKG file. Idempotent. Returns path or None (404).

    If `theme_filter` is provided (set of substrings), only rows whose V2THEMES
    column contains at least one of the substrings are written. Drops ~80-85%
    of rows for an energy/conflict-focused filter and keeps the on-disk size
    manageable.
    """
    stamp = url.split("/")[-1].replace(".gkg.csv.zip", "")
    day = stamp[:8]
    folder = os.path.join(out_dir, f"date={day[:4]}-{day[4:6]}-{day[6:8]}")
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, f"{stamp}.gkg.csv")
    tmp = dest + ".part"
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest

    for attempt in range(1, max_attempts + 1):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 404:
                return None
            if r.status_code >= 500:
                raise requests.HTTPError(f"{r.status_code} for {url}")
            r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                inner_name = z.namelist()[0]
                with z.open(inner_name) as f:
                    raw = f.read()
            if theme_filter is None:
                with open(tmp, "wb") as out:
                    out.write(raw)
            else:
                # GKG is tab-delimited; V2THEMES is column 8 (0-indexed). Filter
                # rowwise: keep rows whose V2THEMES contains any filter token.
                lines = raw.split(b"\n")
                keep = []
                for line in lines:
                    if not line:
                        continue
                    cols = line.split(b"\t")
                    if len(cols) < 8:
                        continue
                    themes = cols[7]
                    if any(token in themes for token in theme_filter):
                        keep.append(line)
                with open(tmp, "wb") as out:
                    out.write(b"\n".join(keep))
                    if keep:
                        out.write(b"\n")
            os.replace(tmp, dest)
            return dest
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
            if attempt == max_attempts:
                raise
            wait = 2**attempt
            log.warning("retry %d/%d for %s after %s (%ss)", attempt, max_attempts, stamp, e, wait)
            time.sleep(wait)


def download_all_gkg(urls, out_dir, *, theme_filter=None, log_every=50):
    """Download every GKG URL with filter-at-ingest. Returns (n_ok, n_404, n_failed, failures)."""
    n_ok = n_404 = n_failed = 0
    failures = []
    total = len(urls)
    for i, url in enumerate(urls, start=1):
        try:
            result = download_gkg_to_disk(url, out_dir, theme_filter=theme_filter)
            if result is None:
                n_404 += 1
            else:
                n_ok += 1
        except Exception as e:
            n_failed += 1
            failures.append((url, str(e)))
            log.error("FAILED %s: %s", url, e)
        if i % log_every == 0 or i == total:
            log.info("progress %d/%d  ok=%d  404=%d  failed=%d", i, total, n_ok, n_404, n_failed)
    return n_ok, n_404, n_failed, failures


def download_to_disk(url, out_dir, *, timeout=60, max_attempts=4):
    """Download+unzip one file to out_dir/date=YYYY-MM-DD/. Idempotent. Returns path or None (404).

    Retries transient errors (timeouts, connection errors, 5xx) with exponential backoff.
    Raises on permanent failure after max_attempts.
    """
    stamp = url.split("/")[-1].replace(".export.CSV.zip", "")
    day = stamp[:8]
    folder = os.path.join(out_dir, f"date={day[:4]}-{day[4:6]}-{day[6:8]}")
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, f"{stamp}.export.CSV")
    tmp = dest + ".part"
    # Skip only if a complete file is present. Size>0 catches truncated/empty
    # leftovers from a prior interruption; atomic rename below means dest never
    # exists in a partial state under normal flow.
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest

    for attempt in range(1, max_attempts + 1):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 404:
                return None
            if r.status_code >= 500:
                raise requests.HTTPError(f"{r.status_code} for {url}")
            r.raise_for_status()
            with (
                zipfile.ZipFile(io.BytesIO(r.content)) as z,
                z.open(z.namelist()[0]) as f,
                open(tmp, "wb") as out,
            ):
                out.write(f.read())
            os.replace(tmp, dest)  # atomic on POSIX — dest only appears when whole
            return dest
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
            if attempt == max_attempts:
                raise
            wait = 2**attempt  # 2, 4, 8 seconds
            log.warning("retry %d/%d for %s after %s (%ss)", attempt, max_attempts, stamp, e, wait)
            time.sleep(wait)


def download_all(urls, out_dir, *, log_every=50):
    """Download every URL; log progress; keep going past per-file failures.

    Returns (n_ok, n_404, n_failed). Safe to re-run — already-downloaded files are skipped.
    """
    n_ok = n_404 = n_failed = 0
    failures = []
    total = len(urls)
    for i, url in enumerate(urls, start=1):
        try:
            result = download_to_disk(url, out_dir)
            if result is None:
                n_404 += 1
            else:
                n_ok += 1
        except Exception as e:
            n_failed += 1
            failures.append((url, str(e)))
            log.error("FAILED %s: %s", url, e)
        if i % log_every == 0 or i == total:
            log.info("progress %d/%d  ok=%d  404=%d  failed=%d", i, total, n_ok, n_404, n_failed)
    return n_ok, n_404, n_failed, failures
