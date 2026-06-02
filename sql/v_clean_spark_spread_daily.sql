-- depends on: v_brent_daily, v_ttf_daily, v_gb_power_daily, v_uka_proxy_daily, v_gb_gen_mix_daily
-- Athena port: window function and CASE expressions port directly; no date arithmetic involved.
--
-- Clean Spark Spread (CSS) overlay.
--
-- Operationalises the merit-order theory: when CCGT is marginal in the GB stack,
-- observed power should track the theoretical CCGT margin closely. CSS captures
-- that margin — the £/MWh that a gas plant earns net of fuel and carbon costs.
--
--   theoretical_css_gbp_mwh = ttf €/MWh × HEAT_RATE × EUR_GBP_RATE       -- fuel cost in £
--                           + uka £/tCO2 × EMISSIONS_FACTOR              -- carbon cost in £
--   residual_gbp_mwh        = power_observed - theoretical_css_gbp_mwh   -- = power − (fuel + carbon)
--
-- Interpretation:
--   * On high-gas-share days, residual should be small (gas IS the marginal price-setter).
--   * On low-gas-share days, residual is large (renewables, imports, demand set the price).
--
-- Constants (must mirror src/iran_shock/config.py):
--   HEAT_RATE_CCGT       = 1.85  (thermal MWh per electric MWh, ~54% efficiency)
--   EMISSIONS_FACTOR_CCGT = 0.36 (tCO2 per electric MWh)
--   EUR_GBP_RATE         = 0.85 (flat for window; v2 would use FRED daily)
CREATE OR REPLACE VIEW v_clean_spark_spread_daily AS
WITH joined AS (
    SELECT b.price_date,
           b.brent_close,
           t.ttf_close,
           p.gb_power_avg,
           u.uka_close_gbp_per_tco2,
           g.gas_share_pct
    FROM v_brent_daily b
    JOIN v_ttf_daily t      ON t.price_date = b.price_date
    JOIN v_gb_power_daily p ON p.price_date = b.price_date
    LEFT JOIN v_uka_proxy_daily u ON u.price_date = b.price_date
    LEFT JOIN v_gb_gen_mix_daily g ON g.price_date = b.price_date
)
SELECT price_date,
       brent_close,
       ttf_close,
       gb_power_avg                                                          AS power_observed_gbp_mwh,
       uka_close_gbp_per_tco2                                                AS uka_proxy_gbp_per_tco2,
       gas_share_pct,
       -- Components
       ROUND(ttf_close * 1.85 * 0.85, 2)                                     AS fuel_cost_gbp_mwh,
       ROUND(uka_close_gbp_per_tco2 * 0.36, 2)                               AS carbon_cost_gbp_mwh,
       ROUND(ttf_close * 1.85 * 0.85 + uka_close_gbp_per_tco2 * 0.36, 2)     AS theoretical_css_gbp_mwh,
       -- Residual = observed power - theoretical CCGT margin. Small + on high-gas days
       -- = mechanism working; large residual on low-gas days = something else marginal.
       ROUND(gb_power_avg - (ttf_close * 1.85 * 0.85 + uka_close_gbp_per_tco2 * 0.36), 2)
                                                                              AS residual_gbp_mwh,
       CASE
           WHEN gas_share_pct IS NULL THEN 'unknown'
           WHEN gas_share_pct >= 30 THEN 'high_gas'
           ELSE 'low_gas'
       END                                                                    AS regime
FROM joined
ORDER BY price_date;
