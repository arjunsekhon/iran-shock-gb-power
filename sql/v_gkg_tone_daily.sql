-- depends on: gdelt_gkg (raw table, all VARCHAR)
-- Athena port: SPLIT_PART(...) and TRY_CAST(...) port directly.
--
-- daily GKG 6-part tone vector.
--
-- V2Tone is a single comma-separated string with 7 fields:
--   tone, positive_score, negative_score, polarity, activity_density,
--   self_reference_density, word_count
-- We parse, cast, and aggregate to daily means.
CREATE OR REPLACE VIEW v_gkg_tone_daily AS
WITH parsed AS (
    SELECT strptime(SUBSTR(gkg_datestamp, 1, 8), '%Y%m%d')::DATE AS event_date,
           TRY_CAST(SPLIT_PART(v2tone, ',', 1) AS DOUBLE) AS tone,
           TRY_CAST(SPLIT_PART(v2tone, ',', 2) AS DOUBLE) AS positive_score,
           TRY_CAST(SPLIT_PART(v2tone, ',', 3) AS DOUBLE) AS negative_score,
           TRY_CAST(SPLIT_PART(v2tone, ',', 4) AS DOUBLE) AS polarity,
           TRY_CAST(SPLIT_PART(v2tone, ',', 5) AS DOUBLE) AS activity_density,
           TRY_CAST(SPLIT_PART(v2tone, ',', 6) AS DOUBLE) AS self_reference_density,
           TRY_CAST(SPLIT_PART(v2tone, ',', 7) AS INT)    AS word_count
    FROM gdelt_gkg
)
SELECT event_date,
       COUNT(*) AS n_articles,
       AVG(tone)                   AS mean_tone,
       AVG(positive_score)         AS mean_positive,
       AVG(negative_score)         AS mean_negative,
       AVG(polarity)               AS mean_polarity,
       AVG(activity_density)       AS mean_activity_density,
       AVG(self_reference_density) AS mean_self_reference,
       STDDEV(tone)                AS tone_dispersion,
       STDDEV(positive_score)      AS positive_dispersion,
       STDDEV(negative_score)      AS negative_dispersion
FROM parsed
WHERE event_date BETWEEN DATE '2026-01-01' AND DATE '2026-05-31'
GROUP BY event_date
ORDER BY event_date;
