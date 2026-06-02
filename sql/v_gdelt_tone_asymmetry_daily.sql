-- depends on: gdelt (raw table)
-- Athena port: strptime(...) -> date_parse(...);  ::TYPE -> CAST(... AS TYPE)
--
-- Asymmetric tone split — TGARCH-inspired. Separates the bad-news component
-- (negative-tone articles) from the good-news component on the same day.
--
--   negative_tone = AVG(LEAST(avgtone, 0))     -- bad-news magnitude per article
--   positive_tone = AVG(GREATEST(avgtone, 0))  -- good-news magnitude per article
--
-- Filter mirrors v_middle_east_events (keep both in step with config.MIDDLE_EAST).
-- Tests whether bad news drives transmission more than good news of comparable
-- magnitude — the TGARCH asymmetry intuition applied to news tone, not returns.
CREATE OR REPLACE VIEW v_gdelt_tone_asymmetry_daily AS
SELECT strptime(day,'%Y%m%d')::DATE AS event_date,
       AVG(LEAST(avgtone::DOUBLE, 0))    AS negative_tone,
       AVG(GREATEST(avgtone::DOUBLE, 0)) AS positive_tone,
       AVG(avgtone::DOUBLE)              AS overall_tone,
       count(*)                          AS event_count
FROM gdelt
WHERE actiongeo_countrycode IN ('IR','IS','US','SA','AE','QA','IZ','KU','BA','LE','SY','YM')
  AND quadclass IN ('3','4')
  AND strptime(day,'%Y%m%d')::DATE BETWEEN DATE '2026-01-01' AND DATE '2026-05-31'
GROUP BY 1
ORDER BY 1;
-- NOTE: the IN-list mirrors config.MIDDLE_EAST — keep the two in step.
