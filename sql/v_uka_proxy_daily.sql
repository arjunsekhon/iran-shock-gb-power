-- depends on: uka_proxy (raw table)
-- Athena port: ::TYPE -> CAST(... AS TYPE); column types already-cast by yfinance
--
-- Standardised daily UKA proxy view. Source is KraneShares Global Carbon
-- Strategy ETF (KRBN), anchored to a documented base UKA price at the start of
-- the window — see `fetch_uka_proxy` in src/iran_shock/prices.py for the basis
-- assumption and config.UKA_BASE_PRICE_GBP_PER_TCO2 / config.UKA_BASE_DATE for
-- the constants.
CREATE OR REPLACE VIEW v_uka_proxy_daily AS
SELECT price_date::DATE AS price_date,
       uka_proxy_gbp::DOUBLE AS uka_close_gbp_per_tco2,
       krbn_close::DOUBLE AS krbn_close_usd,
       source
FROM uka_proxy
ORDER BY price_date;
