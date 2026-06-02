-- Conditional-transmission test: per-event impact alongside the GB generation
-- mix on event day. Used to test the gas-as-marginal-fuel hypothesis -- i.e.
-- whether Brent/TTF -> GB power transmission is stronger on days when gas was
-- a higher share of generation.
--
-- Anchor dates (t0, t3) come from v_event_impact, which uses Brent's trading
-- calendar. Generation-mix lookup is on the t0 day -- GB has FUELHH data on
-- weekends, but with Brent-anchored t0 the lookup naturally aligns to trading
-- days for the Brent/TTF/power moves and to actual weekday gas shares.
CREATE OR REPLACE VIEW v_event_impact_regime AS
WITH anchored AS (
    SELECT t.event_date, t.label,
           (SELECT MIN(price_date) FROM v_brent_daily
              WHERE price_date >= t.event_date) AS t0_date
    FROM timeline t
),
imp AS (
    SELECT i.event_date, i.label,
           i.brent_pct_3d, i.ttf_pct_3d, i.power_pct_3d,
           a.t0_date
    FROM v_event_impact i
    JOIN anchored a ON a.event_date = i.event_date
)
SELECT imp.event_date, imp.label, imp.t0_date,
       imp.brent_pct_3d, imp.ttf_pct_3d, imp.power_pct_3d,
       g.gas_share_pct,
       g.renewables_share_pct,
       g.nuclear_share_pct,
       g.total_mwh,
       CASE
           WHEN g.gas_share_pct IS NULL THEN 'unknown'
           WHEN g.gas_share_pct >= 30 THEN 'high_gas'
           ELSE 'low_gas'
       END AS regime
FROM imp
LEFT JOIN v_gb_gen_mix_daily g ON g.price_date = imp.t0_date
ORDER BY imp.event_date;
