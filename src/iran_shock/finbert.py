"""FinBERT scoring on GDELT SOURCEURL slugs.

Why slugs and not full headlines: GDELT's Events file gives us SOURCEURL (the
article URL) but not the article body or headline text. Fetching every URL to
extract a headline is a separate pipeline (rate limits, anti-bot defences,
~50k requests). The pragmatic baseline is to score the *URL slug* — the last
path segment of the URL, which for news sites almost always contains the
headline as a slug (e.g. `/iran-attacks-qatar-lng-facility-2026-03-18.html`).

FinBERT (ProsusAI/finbert, Apache 2.0) is a BERT model fine-tuned on financial
news. It returns three logits (positive / neutral / negative). We use:

    finbert_signed = pos_prob - neg_prob   (-1 .. +1)

so a single-axis comparison with AvgTone (-100..+100) works.

Output: data/raw/finbert/headline_scores.parquet
Schema: source_url, day, slug, finbert_positive, finbert_neutral, finbert_negative, finbert_signed

Idempotent: re-running skips URLs already scored. Deterministic on a fixed
batch order (no nondeterminism in the inference path).

Caveats for interview:
    - Slug ≠ full headline; some slugs are short/uninformative ("/article-123").
    - FinBERT was trained on financial news, not geopolitical conflict — but
      transferable for "is this market-relevant negative news?" detection.
    - For production: fetch headlines via newspaper3k or use the GDELT GKG
      file which carries article-level metadata including title
      where available.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import duckdb
import pandas as pd

log = logging.getLogger(__name__)

FINBERT_MODEL_ID = "ProsusAI/finbert"
# CSV not parquet to avoid pulling pyarrow into the dep tree for ~9k rows.
SCORES_PATH = Path("data/raw/finbert/headline_scores.csv")
BATCH_SIZE = 32


def url_to_slug(url: str) -> str:
    """Extract the last meaningful path segment from a URL, normalised to text.

    Examples:
        https://www.reuters.com/world/middle-east/iran-attacks-qatar-lng-2026-03-18/
          -> "iran attacks qatar lng 2026 03 18"
        https://www.bbc.co.uk/news/articles/abc123def
          -> "abc123def"
    """
    try:
        path = urlparse(url).path
    except Exception:
        return ""
    if not path:
        return ""
    # Take the last non-empty segment
    segments = [s for s in path.split("/") if s]
    if not segments:
        return ""
    last = segments[-1]
    # Strip trailing extensions (.html, .htm, .php, .aspx)
    last = re.sub(r"\.(html?|php|aspx)$", "", last, flags=re.I)
    last = unquote(last)
    # Replace separators with spaces
    last = re.sub(r"[-_]+", " ", last)
    # Drop pure numeric date components for cleaner sentiment scoring
    last = re.sub(r"\b(20\d{2}|0?[1-9]|1[0-2]|0?[1-9]|[12]\d|3[01])\b", " ", last)
    last = re.sub(r"\s+", " ", last).strip()
    return last


def collect_event_day_urls(
    con: duckdb.DuckDBPyConnection,
    *,
    window_days: int = 1,
    top_per_day_by_mentions: int = 200,
) -> pd.DataFrame:
    """Pull SOURCEURL + day for the top-N-by-NumMentions GDELT events near each
    curated timeline date.

    `window_days` = ± window around each timeline date.
    `top_per_day_by_mentions` = keep only the top N URLs per day by NumMentions
        (coverage volume proxy). This caps scope and biases toward "viral" /
        consequential articles.

    With defaults: 15 timeline dates × 3 days × 200 URLs ≈ 9k URLs max
    (deduplicated). FinBERT on CPU at ~25 sentences/sec → ~6 minutes.

    Output columns: source_url, day, slug, nummentions
    """
    df = con.execute(
        f"""
        WITH window_dates AS (
            SELECT DISTINCT t.event_date - INTERVAL '{window_days}' DAY AS w_start,
                            t.event_date + INTERVAL '{window_days}' DAY AS w_end
            FROM timeline t
        ),
        events AS (
            SELECT g.sourceurl,
                   strptime(g.day,'%Y%m%d')::DATE AS day,
                   MAX(TRY_CAST(g.nummentions AS INT)) AS nummentions
            FROM gdelt g
            WHERE g.actiongeo_countrycode IN ('IR','IS','US','SA','AE','QA','IZ','KU','BA','LE','SY','YM')
              AND g.quadclass IN ('3','4')
              AND g.sourceurl IS NOT NULL AND g.sourceurl <> ''
            GROUP BY g.sourceurl, day
        ),
        windowed AS (
            SELECT e.sourceurl, e.day, e.nummentions
            FROM events e
            JOIN window_dates w ON e.day BETWEEN w.w_start AND w.w_end
        ),
        ranked AS (
            SELECT sourceurl, day, nummentions,
                   ROW_NUMBER() OVER (PARTITION BY day ORDER BY nummentions DESC NULLS LAST) AS rk
            FROM windowed
        )
        SELECT sourceurl AS source_url, day, nummentions
        FROM ranked
        WHERE rk <= {top_per_day_by_mentions}
        """
    ).df()
    df["slug"] = df["source_url"].apply(url_to_slug)
    df = df[df["slug"].str.len() >= 6].reset_index(drop=True)
    return df


def score_slugs(slugs: list[str], *, batch_size: int = BATCH_SIZE) -> pd.DataFrame:
    """Run FinBERT on a list of slug strings; return per-row probabilities."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    log.info("loading FinBERT (%s) ...", FINBERT_MODEL_ID)
    tok = AutoTokenizer.from_pretrained(FINBERT_MODEL_ID)
    model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL_ID)
    model.eval()

    # FinBERT label order: positive=0, negative=1, neutral=2 (verify against id2label)
    id2label = {int(k): v.lower() for k, v in model.config.id2label.items()}
    log.info("FinBERT id2label = %s", id2label)
    # Map column positions for any label order
    pos_idx = next(k for k, v in id2label.items() if v == "positive")
    neg_idx = next(k for k, v in id2label.items() if v == "negative")
    neu_idx = next(k for k, v in id2label.items() if v == "neutral")

    rows = []
    with torch.no_grad():
        for start in range(0, len(slugs), batch_size):
            batch = slugs[start : start + batch_size]
            enc = tok(batch, padding=True, truncation=True, max_length=64, return_tensors="pt")
            logits = model(**enc).logits
            probs = torch.softmax(logits, dim=-1).cpu().numpy()
            for p in probs:
                rows.append(
                    {
                        "finbert_positive": float(p[pos_idx]),
                        "finbert_neutral": float(p[neu_idx]),
                        "finbert_negative": float(p[neg_idx]),
                    }
                )
            if (start // batch_size) % 50 == 0:
                log.info("FinBERT progress %d / %d", start + len(batch), len(slugs))
    df = pd.DataFrame(rows)
    df["finbert_signed"] = df["finbert_positive"] - df["finbert_negative"]
    return df


def score_event_day_urls(
    con: duckdb.DuckDBPyConnection,
    *,
    window_days: int = 7,
    out_path: Path = SCORES_PATH,
) -> Path:
    """End-to-end: pull URLs around timeline events, slug them, FinBERT-score,
    persist. Idempotent — re-running re-uses already-scored slugs.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    urls = collect_event_day_urls(con, window_days=window_days)
    log.info("collected %d event-window URLs to consider", len(urls))

    # Idempotency: if we already scored these slugs, skip.
    if out_path.exists():
        existing = pd.read_csv(out_path)
        already = set(existing["source_url"])
        urls = urls[~urls["source_url"].isin(already)].reset_index(drop=True)
        log.info("after dedupe vs %d existing rows, %d new URLs to score", len(already), len(urls))
    else:
        existing = pd.DataFrame()

    if not urls.empty:
        scored = score_slugs(urls["slug"].tolist())
        scored = pd.concat([urls.reset_index(drop=True), scored], axis=1)
        combined = pd.concat([existing, scored], ignore_index=True) if not existing.empty else scored
    else:
        combined = existing

    combined.to_csv(out_path, index=False)
    log.info("wrote %d FinBERT-scored rows to %s", len(combined), out_path)
    return out_path
