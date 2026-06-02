-- Athena port: "+ INTERVAL 3 DAY" -> date_add('day',3,t.event_date)
--
-- Date anchors come from Brent (futures, no weekends). Power has weekend data
-- in Elexon, but if we let each series pick its own nearest date we get
-- mismatched windows -- a Sun event would look up Sun's low-demand power vs
-- Mon's Brent, generating spurious +X% moves that are actually weekday-vs-
-- weekend seasonality. Anchoring all three on Brent's calendar fixes this.
CREATE OR REPLACE VIEW v_event_impact AS
WITH anchored AS (
    SELECT t.event_date, t.label,
           (SELECT MIN(price_date) FROM v_brent_daily
              WHERE price_date >= t.event_date) AS t0_date,
           (SELECT MIN(price_date) FROM v_brent_daily
              WHERE price_date >= t.event_date + INTERVAL 3 DAY) AS t3_date
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
