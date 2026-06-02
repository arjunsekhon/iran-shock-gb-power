-- depends on: gdelt_gkg
-- Athena port: REGEXP_EXTRACT, TRY_CAST port directly.
--
-- cherry-picked GCAM dimensions for energy + conflict + emotion.
--
-- GCAM (Global Content Analysis Measures) is a comma-separated list of
-- key:score pairs per article. Codes like:
--   c2.1 = LIWC: anger;  c2.21 = LIWC: anxiety;  c2.6 = LIWC: certainty
--   c3.2 = General Inquirer: hostile;  c3.3 = General Inquirer: power
--   v10.1.1 = WordNetAffect: fear;  v10.1.5 = WordNetAffect: surprise
--
-- We use REGEXP_EXTRACT to pull each dimension's score per row, then aggregate
-- to daily mean + dispersion. Dimension lookups are in
-- `data/reference/gcam_dimensions.csv` (committed).
--
-- Energy-relevant picks: LIWC anxiety/anger (proxies for negative coverage),
-- LIWC certainty (level of confidence in claims), GI hostile (conflict
-- framing), WordNetAffect fear / surprise (emotional response).
CREATE OR REPLACE VIEW v_gdelt_gkg_gcam_daily AS
WITH parsed AS (
    SELECT strptime(SUBSTR(gkg_datestamp, 1, 8), '%Y%m%d')::DATE AS event_date,
           TRY_CAST(REGEXP_EXTRACT(v21gcam, 'c2\.1:(-?[\d.]+)', 1)   AS DOUBLE) AS liwc_anger,
           TRY_CAST(REGEXP_EXTRACT(v21gcam, 'c2\.21:(-?[\d.]+)', 1)  AS DOUBLE) AS liwc_anxiety,
           TRY_CAST(REGEXP_EXTRACT(v21gcam, 'c2\.6:(-?[\d.]+)', 1)   AS DOUBLE) AS liwc_certainty,
           TRY_CAST(REGEXP_EXTRACT(v21gcam, 'c2\.34:(-?[\d.]+)', 1)  AS DOUBLE) AS liwc_negate,
           TRY_CAST(REGEXP_EXTRACT(v21gcam, 'c3\.2:(-?[\d.]+)', 1)   AS DOUBLE) AS gi_hostile,
           TRY_CAST(REGEXP_EXTRACT(v21gcam, 'c3\.3:(-?[\d.]+)', 1)   AS DOUBLE) AS gi_power,
           TRY_CAST(REGEXP_EXTRACT(v21gcam, 'v10\.1\.1:(-?[\d.]+)', 1) AS DOUBLE) AS wna_fear,
           TRY_CAST(REGEXP_EXTRACT(v21gcam, 'v10\.1\.5:(-?[\d.]+)', 1) AS DOUBLE) AS wna_surprise
    FROM gdelt_gkg
    WHERE v21gcam IS NOT NULL AND v21gcam <> ''
)
SELECT event_date,
       COUNT(*) AS n_articles,
       AVG(liwc_anger)      AS mean_liwc_anger,
       AVG(liwc_anxiety)    AS mean_liwc_anxiety,
       AVG(liwc_certainty)  AS mean_liwc_certainty,
       AVG(liwc_negate)     AS mean_liwc_negate,
       AVG(gi_hostile)      AS mean_gi_hostile,
       AVG(gi_power)        AS mean_gi_power,
       AVG(wna_fear)        AS mean_wna_fear,
       AVG(wna_surprise)    AS mean_wna_surprise,
       STDDEV(liwc_anxiety) AS dispersion_liwc_anxiety,
       STDDEV(wna_fear)     AS dispersion_wna_fear
FROM parsed
WHERE event_date BETWEEN DATE '2026-01-01' AND DATE '2026-05-31'
GROUP BY event_date
ORDER BY event_date;
