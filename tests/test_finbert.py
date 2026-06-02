"""FinBERT scoring tests."""

from pathlib import Path

import pytest

from iran_shock.finbert import url_to_slug


def test_url_to_slug_reuters():
    """Reuters article URLs convert to readable space-separated tokens."""
    url = "https://www.reuters.com/world/middle-east/iran-attacks-qatar-lng-2026-03-18/"
    slug = url_to_slug(url)
    assert "iran" in slug
    assert "qatar" in slug
    assert "lng" in slug


def test_url_to_slug_strips_extensions():
    """HTML/PHP extensions are stripped from the last segment."""
    assert "html" not in url_to_slug("https://example.com/some/article-title.html").lower()
    assert "php" not in url_to_slug("https://example.com/some/article-title.php").lower()


def test_url_to_slug_handles_garbage():
    """Garbage / empty URLs return strings without raising."""
    assert url_to_slug("") == ""
    # urlparse treats "not-a-url" as a relative path; that's tolerable and
    # downstream slug-length filter (>=6 chars) drops these in the pipeline.
    assert isinstance(url_to_slug("not-a-url"), str)
    assert url_to_slug("https://example.com/") == ""


def test_finbert_csv_exists_after_run():
    """If FinBERT has been run, the CSV exists with expected columns."""
    path = Path("data/raw/finbert/headline_scores.csv")
    if not path.exists():
        pytest.skip("FinBERT not yet run; `uv run iran-shock-score-finbert` first")
    import pandas as pd

    df = pd.read_csv(path)
    expected = {
        "source_url",
        "day",
        "nummentions",
        "slug",
        "finbert_positive",
        "finbert_neutral",
        "finbert_negative",
        "finbert_signed",
    }
    assert expected.issubset(set(df.columns)), f"missing: {expected - set(df.columns)}"
    assert (df["finbert_signed"].abs() <= 1.001).all(), "finbert_signed out of [-1,1] range"
    assert len(df) > 100, f"only {len(df)} rows scored"
