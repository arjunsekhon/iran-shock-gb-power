-- Athena ports of sql/v_*.sql (Stage 3). Run in the iran_shock database/workgroup.
-- Statements run ONE AT A TIME, in this (dependency) order.
-- Swaps from DuckDB: strptime(...)::DATE -> CAST(date_parse(...) AS DATE);
--   col::TYPE -> CAST(col AS TYPE); + INTERVAL N DAY -> date_add('day', N, ...).

-- 1. price/gen-mix passthroughs (no swaps needed)
CREATE OR REPLACE VIEW v_brent_daily AS SELECT * FROM brent ORDER BY price_date;

CREATE OR REPLACE VIEW v_ttf_daily AS SELECT * FROM ttf ORDER BY price_date;

CREATE OR REPLACE VIEW v_gb_power_daily AS SELECT * FROM gb_power ORDER BY price_date;

CREATE OR REPLACE VIEW v_gb_gen_mix_daily AS SELECT * FROM gb_gen_mix ORDER BY price_date;

-- 2. daily conflict signal
CREATE OR REPLACE VIEW v_middle_east_events AS
SELECT CAST(date_parse(day,'%Y%m%d') AS DATE) AS event_date,
       count(*) AS event_count,
       avg(CAST(avgtone AS DOUBLE)) AS avg_tone,
       avg(CAST(goldsteinscale AS DOUBLE)) AS avg_goldstein,
       sum(CAST(nummentions AS INTEGER)) AS total_mentions
FROM gdelt
WHERE actiongeo_countrycode IN ('IR','IS','US','SA','AE','QA','IZ','KU','BA','LE','SY','YM')
  AND quadclass IN ('3','4')
  AND CAST(date_parse(day,'%Y%m%d') AS DATE) BETWEEN DATE '2026-01-01' AND DATE '2026-05-31'
GROUP BY 1 ORDER BY 1;

-- 3. per-place rollup for the map
CREATE OR REPLACE VIEW v_event_geo AS
SELECT actiongeo_fullname AS place,
       actiongeo_countrycode AS fips_country,
       round(CAST(actiongeo_lat AS DOUBLE), 1) AS lat,
       round(CAST(actiongeo_long AS DOUBLE), 1) AS lon,
       count(*) AS event_count,
       avg(CAST(avgtone AS DOUBLE)) AS avg_tone,
       sum(CAST(nummentions AS INTEGER)) AS total_mentions
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

-- 6. multi-horizon event impact (t+1, t+3, t+5, t+10)
CREATE OR REPLACE VIEW v_event_impact_multi AS
WITH anchored AS (
    SELECT t.event_date, t.label,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= t.event_date) AS t0,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= date_add('day',1,t.event_date))  AS t1,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= date_add('day',3,t.event_date))  AS t3,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= date_add('day',5,t.event_date))  AS t5,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= date_add('day',10,t.event_date)) AS t10
    FROM timeline t
),
prices AS (
    SELECT a.event_date, a.label,
           (SELECT brent_close   FROM v_brent_daily    WHERE price_date = a.t0)  AS b0,
           (SELECT brent_close   FROM v_brent_daily    WHERE price_date = a.t1)  AS b1,
           (SELECT brent_close   FROM v_brent_daily    WHERE price_date = a.t3)  AS b3,
           (SELECT brent_close   FROM v_brent_daily    WHERE price_date = a.t5)  AS b5,
           (SELECT brent_close   FROM v_brent_daily    WHERE price_date = a.t10) AS b10,
           (SELECT ttf_close     FROM v_ttf_daily      WHERE price_date = a.t0)  AS g0,
           (SELECT ttf_close     FROM v_ttf_daily      WHERE price_date = a.t1)  AS g1,
           (SELECT ttf_close     FROM v_ttf_daily      WHERE price_date = a.t3)  AS g3,
           (SELECT ttf_close     FROM v_ttf_daily      WHERE price_date = a.t5)  AS g5,
           (SELECT ttf_close     FROM v_ttf_daily      WHERE price_date = a.t10) AS g10,
           (SELECT gb_power_avg  FROM v_gb_power_daily WHERE price_date = a.t0)  AS p0,
           (SELECT gb_power_avg  FROM v_gb_power_daily WHERE price_date = a.t1)  AS p1,
           (SELECT gb_power_avg  FROM v_gb_power_daily WHERE price_date = a.t3)  AS p3,
           (SELECT gb_power_avg  FROM v_gb_power_daily WHERE price_date = a.t5)  AS p5,
           (SELECT gb_power_avg  FROM v_gb_power_daily WHERE price_date = a.t10) AS p10
    FROM anchored a
)
SELECT event_date, label,
       round(100.0*(b1 -b0)/b0, 1) AS brent_pct_1d,
       round(100.0*(b3 -b0)/b0, 1) AS brent_pct_3d,
       round(100.0*(b5 -b0)/b0, 1) AS brent_pct_5d,
       round(100.0*(b10-b0)/b0, 1) AS brent_pct_10d,
       round(100.0*(g1 -g0)/g0, 1) AS ttf_pct_1d,
       round(100.0*(g3 -g0)/g0, 1) AS ttf_pct_3d,
       round(100.0*(g5 -g0)/g0, 1) AS ttf_pct_5d,
       round(100.0*(g10-g0)/g0, 1) AS ttf_pct_10d,
       round(100.0*(p1 -p0)/p0, 1) AS power_pct_1d,
       round(100.0*(p3 -p0)/p0, 1) AS power_pct_3d,
       round(100.0*(p5 -p0)/p0, 1) AS power_pct_5d,
       round(100.0*(p10-p0)/p0, 1) AS power_pct_10d
FROM prices
ORDER BY event_date;

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
