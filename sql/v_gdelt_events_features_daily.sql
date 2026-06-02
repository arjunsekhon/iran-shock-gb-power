-- depends on: gdelt (raw table)
-- Athena port: strptime(...) -> date_parse(...);  ::TYPE -> CAST(... AS TYPE);
--              SUM(CASE WHEN ...) ports identically.
--
-- better-than-AvgTone signals already in our GDELT Events file.
--
-- We currently use AvgTone (single dictionary score). The Events file already
-- carries four richer signals — `GoldsteinScale`, `NumMentions`, `QuadClass`,
-- `EventRootCode` — that we don't use yet. This view rolls them up per day for
-- the same Middle-East / QuadClass-conflict scope as v_middle_east_events.
--
-- Goldstein × NumMentions: calibrated political-stability impact (−10..+10
-- per CAMEO event type, fixed lookup) weighted by coverage volume — *less
-- noisy* than dictionary tone for political events. Sum across day = total
-- coverage-weighted impact; mean = average impact per article.
--
-- QuadClass features split the news flow into verbal vs material × conflict
-- vs cooperation, so the asymmetric-tone test from 1.2 has a structural
-- complement: did material-conflict (4) news drive transmission more than
-- verbal-conflict (3)?
--
-- EventRootCode breakdown: 19 (fight) vs 17 (coerce) vs 20 (force) move
-- markets differently. Reported as the dominant root code each day plus a
-- count of distinct roots.
CREATE OR REPLACE VIEW v_gdelt_events_features_daily AS
WITH base AS (
    SELECT strptime(day, '%Y%m%d')::DATE AS event_date,
           avgtone::DOUBLE       AS avgtone,
           goldsteinscale::DOUBLE AS goldstein,
           nummentions::INT      AS nummentions,
           quadclass             AS quadclass,
           eventrootcode         AS eventrootcode
    FROM gdelt
    WHERE actiongeo_countrycode IN ('IR','IS','US','SA','AE','QA','IZ','KU','BA','LE','SY','YM')
      AND quadclass IN ('3','4')
      AND strptime(day, '%Y%m%d')::DATE BETWEEN DATE '2026-01-01' AND DATE '2026-05-31'
)
SELECT event_date,
       COUNT(*)                                                        AS event_count,
       SUM(nummentions)                                                AS total_mentions,
       -- Tone signals
       AVG(avgtone)                                                    AS mean_tone,
       SUM(avgtone * nummentions) / NULLIF(SUM(nummentions), 0)        AS mentions_weighted_tone,
       -- Goldstein-scale signals (political-stability calibrated)
       AVG(goldstein)                                                  AS mean_goldstein,
       SUM(goldstein * nummentions) / NULLIF(SUM(nummentions), 0)      AS mentions_weighted_goldstein,
       SUM(goldstein * nummentions)                                    AS total_weighted_goldstein,
       -- QuadClass features
       SUM(CASE WHEN quadclass = '3' THEN 1 ELSE 0 END)                AS n_verbal_conflict,
       SUM(CASE WHEN quadclass = '4' THEN 1 ELSE 0 END)                AS n_material_conflict,
       -- Event-type breakdown (19=fight, 17=coerce, 20=force, 14=protest etc.)
       SUM(CASE WHEN eventrootcode = '19' THEN 1 ELSE 0 END)           AS n_fight,
       SUM(CASE WHEN eventrootcode = '18' THEN 1 ELSE 0 END)           AS n_assault,
       SUM(CASE WHEN eventrootcode = '17' THEN 1 ELSE 0 END)           AS n_coerce,
       SUM(CASE WHEN eventrootcode = '20' THEN 1 ELSE 0 END)           AS n_force,
       SUM(CASE WHEN eventrootcode = '14' THEN 1 ELSE 0 END)           AS n_protest,
       SUM(CASE WHEN eventrootcode = '13' THEN 1 ELSE 0 END)           AS n_threaten
FROM base
GROUP BY event_date
ORDER BY event_date;
