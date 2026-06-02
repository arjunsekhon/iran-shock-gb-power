import pandas as pd
import requests
import yfinance as yf


def fetch_brent(start="2026-01-01", end="2026-06-01"):
    # If yfinance starts returning 401/empty, Yahoo has tightened bot detection.
    # Fix: pass a curl_cffi session impersonating Chrome (see yfinance issue #2422):
    #     from curl_cffi import requests as cffi
    #     px = yf.download("BZ=F", start=start, end=end, progress=False,
    #                      session=cffi.Session(impersonate="chrome"))
    # Second fallback: EIA daily Brent (eia.gov/dnav/pet/hist/RBRTEd.htm).
    px = yf.download("BZ=F", start=start, end=end, progress=False)
    out = px[["Close"]].reset_index()
    out.columns = ["price_date", "brent_close"]
    return out


def fetch_ttf_gas(start="2026-01-01", end="2026-06-01"):
    """TTF (Dutch Title Transfer Facility) front-month gas futures, €/MWh, daily close.

    TTF is the European wholesale gas benchmark — NBP (UK) tracks it tightly. European gas is also the first-order transmission channel into GB power
    (gas-as-marginal-fuel via CCGTs). yfinance symbol: TTF=F (ICE Endex).
    Same curl_cffi fallback applies as fetch_brent if Yahoo blocks.
    """
    px = yf.download("TTF=F", start=start, end=end, progress=False)
    out = px[["Close"]].reset_index()
    out.columns = ["price_date", "ttf_close"]
    return out


def fetch_gb_gen_mix(start="2026-01-01", end="2026-05-31", *, chunk_days=7):
    """Half-hourly GB generation by fuel type, aggregated to daily fuel shares.

    Source: Elexon BMRS `/datasets/FUELHH` endpoint. Returns one row per day with
    `total_mwh` and daily share (%) of: gas (CCGT + OCGT), renewables (WIND +
    NPSHYD), nuclear, biomass, coal+oil, pumped storage. Interconnector flows are
    excluded from the share calculation (they net to imports vs exports across
    the day rather than capacity in the marginal stack).

    Feeds the conditional-transmission test: the gas-as-marginal-fuel hypothesis
    predicts Brent/TTF -> GB power transmission is stronger on high-gas-share
    days (when gas is more likely to be the marginal generator).

    Note: FUELHH covers transmission-connected generation only; embedded solar/
    small wind aren't included. That's fine for the gas-share test — the relevant
    comparison is "of what's in the transmission stack, how much was gas".
    """
    url = "https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH"
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)

    frames = []
    cur = start_dt
    while cur <= end_dt:
        nxt = min(cur + pd.Timedelta(days=chunk_days) - pd.Timedelta(seconds=1), end_dt)
        params = {
            "settlementDateFrom": cur.strftime("%Y-%m-%d"),
            "settlementDateTo": nxt.strftime("%Y-%m-%d"),
            "format": "json",
        }
        r = requests.get(url, params=params, timeout=120)
        r.raise_for_status()
        chunk = pd.DataFrame(r.json().get("data", []))
        if not chunk.empty:
            frames.append(chunk)
        cur = nxt + pd.Timedelta(seconds=1)

    if not frames:
        return pd.DataFrame(
            columns=[
                "price_date",
                "total_mwh",
                "gas_share_pct",
                "renewables_share_pct",
                "nuclear_share_pct",
                "biomass_share_pct",
            ]
        )

    rows = pd.concat(frames, ignore_index=True)
    rows["price_date"] = pd.to_datetime(rows["settlementDate"]).dt.date
    rows["generation"] = pd.to_numeric(rows["generation"], errors="coerce").fillna(0)

    # FUELHH fuel codes per Elexon
    categories = {
        "CCGT": "gas",
        "OCGT": "gas",
        "NUCLEAR": "nuclear",
        "WIND": "renewables",
        "NPSHYD": "renewables",
        "BIOMASS": "biomass",
        "COAL": "coal_oil",
        "OIL": "coal_oil",
        "PS": "pumped_storage",
        # All INT* + OTHER fall into "other" -- excluded from the share calc base
    }
    rows["category"] = rows["fuelType"].map(categories).fillna("other")

    by_cat = rows.groupby(["price_date", "category"])["generation"].sum().reset_index()
    pivot = by_cat.pivot(index="price_date", columns="category", values="generation").fillna(0)

    # Total generation = domestic transmission-connected (excludes interconnectors)
    base_cols = ["gas", "renewables", "nuclear", "biomass", "coal_oil", "pumped_storage"]
    for c in base_cols:
        if c not in pivot.columns:
            pivot[c] = 0
    pivot["total_mwh"] = pivot[base_cols].sum(axis=1).round(0)

    for c in base_cols:
        pivot[f"{c}_share_pct"] = (pivot[c] / pivot["total_mwh"] * 100).round(1)

    return pivot.reset_index()[
        [
            "price_date",
            "total_mwh",
            "gas_share_pct",
            "renewables_share_pct",
            "nuclear_share_pct",
            "biomass_share_pct",
            "coal_oil_share_pct",
            "pumped_storage_share_pct",
        ]
    ]


def fetch_gb_power(start="2026-01-01", end="2026-05-31", *, chunk_days=7, provider="APXMIDP"):
    """GB day-ahead market-index half-hourly prices, resampled to daily mean (£/MWh).

    Elexon's market-index endpoint (a) requires RFC 3339 datetimes (date-only -> 400)
    and (b) caps each request to ~a week, so we chunk and concatenate.

    Provider defaults to APXMIDP — N2EXMIDP submissions are sparse on the project
    dates (one non-zero period per day on average); APX populates all 48.
    """
    url = "https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index"
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)

    frames = []
    cur = start_dt
    while cur <= end_dt:
        nxt = min(cur + pd.Timedelta(days=chunk_days) - pd.Timedelta(seconds=1), end_dt)
        params = {
            "from": cur.strftime("%Y-%m-%dT%H:%MZ"),
            "to": nxt.strftime("%Y-%m-%dT%H:%MZ"),
            "dataProviders": provider,
            "format": "json",
        }
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        chunk = pd.DataFrame(r.json().get("data", []))
        if not chunk.empty:
            frames.append(chunk)
        cur = nxt + pd.Timedelta(seconds=1)

    if not frames:
        return pd.DataFrame(columns=["price_date", "gb_power_avg"])

    rows = pd.concat(frames, ignore_index=True)
    rows["price_date"] = pd.to_datetime(rows["startTime"]).dt.date
    rows = rows[rows["price"] > 0]  # drop empty/zero settlement periods
    return (
        rows.groupby("price_date")["price"]
        .mean()
        .reset_index()
        .rename(columns={"price": "gb_power_avg"})
    )
