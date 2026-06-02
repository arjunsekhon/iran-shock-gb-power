-- Athena ports of sql/v_*.sql (Stage 3). Run in the iran_shock database/workgroup.
-- Statements run ONE AT A TIME, in this (dependency) order.
-- Swaps from DuckDB: strptime(...)::DATE -> CAST(date_parse(...) AS DATE);
--   col::TYPE -> CAST(col AS TYPE); + INTERVAL N DAY -> date_add('day', N, ...).
-- Numeric casts on raw gdelt use TRY_CAST: Athena's TSV SerDe reads empty fields
--   as '' (DuckDB reads them as NULL), and CAST('' AS DOUBLE) errors; TRY_CAST
--   returns NULL instead, matching DuckDB and ignored by avg/sum.
-- v_event_impact_multi uses LEFT JOINs rather than the scalar-subquery select list
--   from the DuckDB version: same result, parses cleanly in Trino/Athena.

-- 1. price/gen-mix passthroughs (no swaps needed)
CREATE OR REPLACE VIEW v_brent_daily AS SELECT * FROM brent ORDER BY price_date;

CREATE OR REPLACE VIEW v_ttf_daily AS SELECT * FROM ttf ORDER BY price_date;

CREATE OR REPLACE VIEW v_gb_power_daily AS SELECT * FROM gb_power ORDER BY price_date;

CREATE OR REPLACE VIEW v_gb_gen_mix_daily AS SELECT * FROM gb_gen_mix ORDER BY price_date;

-- 2. daily conflict signal
CREATE OR REPLACE VIEW v_middle_east_events AS
SELECT CAST(date_parse(day,'%Y%m%d') AS DATE) AS event_date,
       count(*) AS event_count,
       avg(TRY_CAST(avgtone AS DOUBLE)) AS avg_tone,
       avg(TRY_CAST(goldsteinscale AS DOUBLE)) AS avg_goldstein,
       sum(TRY_CAST(nummentions AS INTEGER)) AS total_mentions
FROM gdelt
WHERE actiongeo_countrycode IN ('IR','IS','US','SA','AE','QA','IZ','KU','BA','LE','SY','YM')
  AND quadclass IN ('3','4')
  AND CAST(date_parse(day,'%Y%m%d') AS DATE) BETWEEN DATE '2026-01-01' AND DATE '2026-05-31'
GROUP BY 1 ORDER BY 1;

-- 3. per-place rollup for the map
CREATE OR REPLACE VIEW v_event_geo AS
SELECT actiongeo_fullname AS place,
       actiongeo_countrycode AS fips_country,
       round(TRY_CAST(actiongeo_lat AS DOUBLE), 1) AS lat,
       round(TRY_CAST(actiongeo_long AS DOUBLE), 1) AS lon,
       count(*) AS event_count,
       avg(TRY_CAST(avgtone AS DOUBLE)) AS avg_tone,
       sum(TRY_CAST(nummentions AS INTEGER)) AS total_mentions
FROM gdelt
WHERE quadclass IN ('3','4')
  AND actiongeo_type IN ('3','4')
  AND actiongeo_lat <> '' AND actiongeo_long <> ''
  AND CAST(date_parse(day,'%Y%m%d') AS DATE) BETWEEN DATE '2026-01-01' AND DATE '2026-05-31'
GROUP BY 1,2,3,4;

-- 4. four series on Brent's calendar
CREATE OR REPLACE VIEW v_combined_daily AS
SELECT b.price_date AS d,
       b.brent_close,
       g.ttf_close,
       p.gb_power_avg,
       e.event_count,
       e.avg_tone
FROM v_brent_daily b
LEFT JOIN v_ttf_daily          g ON b.price_date = g.price_date
LEFT JOIN v_gb_power_daily     p ON b.price_date = p.price_date
LEFT JOIN v_middle_east_events e ON b.price_date = e.event_date
ORDER BY d;

-- 5. event study at +3 trading days (Brent-anchored)
CREATE OR REPLACE VIEW v_event_impact AS
WITH anchored AS (
    SELECT t.event_date, t.label,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= t.event_date) AS t0_date,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= date_add('day',3,t.event_date)) AS t3_date
    FROM timeline t
),
e AS (
    SELECT a.event_date, a.label,
           (SELECT brent_close FROM v_brent_daily WHERE price_date = a.t0_date) AS brent_t,
           (SELECT brent_close FROM v_brent_daily WHERE price_date = a.t3_date) AS brent_t3,
           (SELECT ttf_close FROM v_ttf_daily WHERE price_date = a.t0_date) AS ttf_t,
           (SELECT ttf_close FROM v_ttf_daily WHERE price_date = a.t3_date) AS ttf_t3,
           (SELECT gb_power_avg FROM v_gb_power_daily WHERE price_date = a.t0_date) AS power_t,
           (SELECT gb_power_avg FROM v_gb_power_daily WHERE price_date = a.t3_date) AS power_t3
    FROM anchored a
)
SELECT event_date, label,
       brent_t, brent_t3, round(100.0*(brent_t3 - brent_t)/brent_t, 1) AS brent_pct_3d,
       ttf_t,   ttf_t3,   round(100.0*(ttf_t3   - ttf_t  )/ttf_t,   1) AS ttf_pct_3d,
       power_t, power_t3, round(100.0*(power_t3 - power_t)/power_t, 1) AS power_pct_3d
FROM e
ORDER BY event_date;

-- 6. multi-horizon event impact (t+1, t+3, t+5, t+10) -- JOIN form (Trino-friendly)
CREATE OR REPLACE VIEW v_event_impact_multi AS
WITH anchored AS (
    SELECT t.event_date, t.label,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= t.event_date) AS t0,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= date_add('day',1,t.event_date))  AS t1,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= date_add('day',3,t.event_date))  AS t3,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= date_add('day',5,t.event_date))  AS t5,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= date_add('day',10,t.event_date)) AS t10
    FROM timeline t
)
SELECT a.event_date, a.label,
       round(100.0*(b1.brent_close-b0.brent_close)/b0.brent_close, 1)   AS brent_pct_1d,
       round(100.0*(b3.brent_close-b0.brent_close)/b0.brent_close, 1)   AS brent_pct_3d,
       round(100.0*(b5.brent_close-b0.brent_close)/b0.brent_close, 1)   AS brent_pct_5d,
       round(100.0*(b10.brent_close-b0.brent_close)/b0.brent_close, 1)  AS brent_pct_10d,
       round(100.0*(g1.ttf_close-g0.ttf_close)/g0.ttf_close, 1)         AS ttf_pct_1d,
       round(100.0*(g3.ttf_close-g0.ttf_close)/g0.ttf_close, 1)         AS ttf_pct_3d,
       round(100.0*(g5.ttf_close-g0.ttf_close)/g0.ttf_close, 1)         AS ttf_pct_5d,
       round(100.0*(g10.ttf_close-g0.ttf_close)/g0.ttf_close, 1)        AS ttf_pct_10d,
       round(100.0*(p1.gb_power_avg-p0.gb_power_avg)/p0.gb_power_avg, 1)   AS power_pct_1d,
       round(100.0*(p3.gb_power_avg-p0.gb_power_avg)/p0.gb_power_avg, 1)   AS power_pct_3d,
       round(100.0*(p5.gb_power_avg-p0.gb_power_avg)/p0.gb_power_avg, 1)   AS power_pct_5d,
       round(100.0*(p10.gb_power_avg-p0.gb_power_avg)/p0.gb_power_avg, 1)  AS power_pct_10d
FROM anchored a
LEFT JOIN v_brent_daily    b0  ON b0.price_date  = a.t0
LEFT JOIN v_brent_daily    b1  ON b1.price_date  = a.t1
LEFT JOIN v_brent_daily    b3  ON b3.price_date  = a.t3
LEFT JOIN v_brent_daily    b5  ON b5.price_date  = a.t5
LEFT JOIN v_brent_daily    b10 ON b10.price_date = a.t10
LEFT JOIN v_ttf_daily      g0  ON g0.price_date  = a.t0
LEFT JOIN v_ttf_daily      g1  ON g1.price_date  = a.t1
LEFT JOIN v_ttf_daily      g3  ON g3.price_date  = a.t3
LEFT JOIN v_ttf_daily      g5  ON g5.price_date  = a.t5
LEFT JOIN v_ttf_daily      g10 ON g10.price_date = a.t10
LEFT JOIN v_gb_power_daily p0  ON p0.price_date  = a.t0
LEFT JOIN v_gb_power_daily p1  ON p1.price_date  = a.t1
LEFT JOIN v_gb_power_daily p3  ON p3.price_date  = a.t3
LEFT JOIN v_gb_power_daily p5  ON p5.price_date  = a.t5
LEFT JOIN v_gb_power_daily p10 ON p10.price_date = a.t10
ORDER BY a.event_date;

-- 7. conditional-transmission test: event impact tagged by gas-share regime
CREATE OR REPLACE VIEW v_event_impact_regime AS
WITH anchored AS (
    SELECT t.event_date, t.label,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= t.event_date) AS t0_date
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
