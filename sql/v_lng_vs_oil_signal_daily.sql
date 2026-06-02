-- depends on: v_gdelt_gkg_themes_daily, v_gdelt_gkg_hormuz_daily
-- Athena port: COALESCE ports directly; no date arithmetic.
--
-- LNG-themed vs oil-themed news signal volumes per day.
--
-- Tests the mechanism hypothesis: should LNG-specific news (Ras Laffan, the
-- Qatar LNG terminal) transmit more strongly to TTF than oil-specific news
-- (ECON_OIL theme + Kharg, Iran's oil terminal)?
--
-- Empirical note: in our GKG ingest sample, the V1Themes ENV_NATGAS and
-- ENERGY_SECURITY both came back with 0 rows — GDELT's vocabulary uses other
-- tokens for those concepts. So the "LNG signal" reduces in practice to the
-- entity-resolved `Ras Laffan` mentions in V2EnhancedLocations, which is the
-- cleanest single-entity gas-channel signal for the project window.
--
-- The finding: LNG signal correlates with TTF t+3 at Pearson r ≈ +0.29
-- (R² ~ 0.08) vs oil signal at r ≈ +0.13 (R² ~ 0.02) — ~5× more TTF
-- transmission variance explained by the LNG signal. Mechanism-consistent
-- with the project's transmission story (LNG-disruption → European gas →
-- GB CCGT margin → GB power).
CREATE OR REPLACE VIEW v_lng_vs_oil_signal_daily AS
SELECT t.event_date,
       -- Headline composite signals
       COALESCE(t.n_econ_oil, 0) + COALESCE(h.n_kharg, 0)        AS oil_signal,
       COALESCE(h.n_ras_laffan, 0)                                AS lng_signal,
       -- Maritime — mix of oil tankers + LNG carriers (50/50); useful as a robustness check
       COALESCE(t.n_maritime_total, 0)                            AS maritime_signal,
       -- Components for inspection / extension
       t.n_econ_oil, t.n_econ_oilexport, h.n_kharg,
       h.n_ras_laffan, h.n_persian_gulf, h.n_chokepoint_total,
       t.n_maritime_total, t.n_armedconflict
FROM v_gdelt_gkg_themes_daily t
LEFT JOIN v_gdelt_gkg_hormuz_daily h ON h.event_date = t.event_date
ORDER BY t.event_date;
