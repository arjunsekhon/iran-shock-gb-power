-- Athena port: "+ INTERVAL N DAY" -> date_add('day', N, t.event_date)
--
-- Multi-horizon event-impact at t+1, t+3, t+5, t+10 trading days.
-- All four horizons anchored on Brent's trading-day calendar (same fix as
-- v_event_impact -- see comments there). Lets the analysis separate:
--   t+1  short-shock impact
--   t+3  standard short-horizon event-study window
--   t+5  one-week persistence
--   t+10 two-week persistence (phase-2 supply-destruction effects)
CREATE OR REPLACE VIEW v_event_impact_multi AS
WITH anchored AS (
    SELECT t.event_date, t.label,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= t.event_date) AS t0,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= t.event_date + INTERVAL 1 DAY)  AS t1,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= t.event_date + INTERVAL 3 DAY)  AS t3,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= t.event_date + INTERVAL 5 DAY)  AS t5,
           (SELECT MIN(price_date) FROM v_brent_daily WHERE price_date >= t.event_date + INTERVAL 10 DAY) AS t10
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
