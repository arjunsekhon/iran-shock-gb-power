-- depends on: v_clean_spark_spread_daily
-- Athena port: arithmetic + CASE port directly.
--
-- implied TTF / implied heat rate (mechanism polish).
--
-- Reverse-engineer the TTF that observed GB power *implies* given the CCGT
-- constants:
--
--   implied_ttf_eur_mwh = (power_price - UKA × emissions_factor)
--                         / (heat_rate × EUR_GBP_RATE)
--
-- That is the inverse of the v_clean_spark_spread_daily CSS calculation:
-- solving for TTF given the observed power and the carbon cost. Basis =
-- observed TTF − implied TTF.
--
--   basis > 0  → power is "cheaper" than the implied gas marginal cost
--               (something else — renewables / nuclear / imports — is at
--                the margin, *pulling power below* the CCGT curve)
--   basis ≈ 0  → gas is plausibly marginal (TTF prices match what power
--                says the marginal gas should cost)
--   basis < 0  → power is "more expensive" than implied gas
--               (tightness / scarcity rents on top of marginal CCGT cost)
--
-- Constants must mirror src/iran_shock/config.py:
--   HEAT_RATE_CCGT       = 1.85
--   EMISSIONS_FACTOR_CCGT = 0.36
--   EUR_GBP_RATE         = 0.85
CREATE OR REPLACE VIEW v_implied_ttf_daily AS
SELECT price_date,
       ttf_close                                        AS observed_ttf_eur_mwh,
       power_observed_gbp_mwh,
       uka_proxy_gbp_per_tco2,
       gas_share_pct,
       regime,
       -- Implied TTF that observed power implies (€/MWh thermal gas)
       ROUND(
           (power_observed_gbp_mwh - uka_proxy_gbp_per_tco2 * 0.36) / (1.85 * 0.85),
           2
       )                                                 AS implied_ttf_eur_mwh,
       -- Basis: observed − implied. Positive = power below implied CCGT margin.
       ROUND(
           ttf_close - (power_observed_gbp_mwh - uka_proxy_gbp_per_tco2 * 0.36) / (1.85 * 0.85),
           2
       )                                                 AS basis_eur_mwh,
       -- Threshold flag: |basis| > €15 = day where merit-order didn't hold
       CASE
           WHEN ABS(
               ttf_close - (power_observed_gbp_mwh - uka_proxy_gbp_per_tco2 * 0.36) / (1.85 * 0.85)
           ) > 15 THEN 'decoupled'
           ELSE 'plausibly_marginal'
       END                                               AS basis_regime
FROM v_clean_spark_spread_daily
WHERE ttf_close IS NOT NULL AND uka_proxy_gbp_per_tco2 IS NOT NULL
ORDER BY price_date;
