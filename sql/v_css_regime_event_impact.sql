-- depends on: v_event_impact_regime, v_clean_spark_spread_daily
-- Athena port: ports directly; no date-arithmetic.
--
-- per-event CSS residual by gas regime.
--
-- Joins the existing regime-tagged event impacts (v_event_impact_regime) with
-- the theoretical CSS on the same anchor date, so each event row carries the
-- "did observed power track the theoretical CCGT margin on event day?" residual.
--
-- Use the residual mean by regime to test:
--   * high-gas events should have small mean |residual|
--   * low-gas  events should have large mean |residual|
-- If both are similar, gas-as-marginal-fuel isn't doing the mechanism work the
-- conditional-transmission test attributes to it.
CREATE OR REPLACE VIEW v_css_regime_event_impact AS
SELECT r.event_date,
       r.label,
       r.t0_date,
       r.regime,
       r.gas_share_pct,
       r.brent_pct_3d,
       r.ttf_pct_3d,
       r.power_pct_3d,
       c.power_observed_gbp_mwh,
       c.theoretical_css_gbp_mwh,
       c.fuel_cost_gbp_mwh,
       c.carbon_cost_gbp_mwh,
       c.residual_gbp_mwh,
       ABS(c.residual_gbp_mwh) AS abs_residual_gbp_mwh
FROM v_event_impact_regime r
LEFT JOIN v_clean_spark_spread_daily c ON c.price_date = r.t0_date
ORDER BY r.event_date;
