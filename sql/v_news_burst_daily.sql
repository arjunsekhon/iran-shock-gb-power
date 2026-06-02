-- depends on: v_middle_east_events
-- Athena port: ROWS BETWEEN window frame ports directly.
--
-- Hawkes-inspired burst score for the Middle-East news stream.
--
--   burst_score = event_count / rolling_30d_mean(event_count)
--
-- The rolling mean uses the prior 30 event-bearing days (ROWS PRECEDING).
-- Over our window every calendar day carries Middle-East conflict events, so
-- "30 event-rows" ~= "30 calendar days". Score above ~2 = unusual burst.
--
-- Hawkes proper models self-exciting arrival processes; this is a deliberately
-- simple proxy that captures the clustering without overfitting at n=14 events.
CREATE OR REPLACE VIEW v_news_burst_daily AS
WITH base AS (
    SELECT event_date,
           event_count,
           AVG(event_count) OVER (
               ORDER BY event_date
               ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING
           ) AS rolling_30d_mean
    FROM v_middle_east_events
)
SELECT event_date,
       event_count,
       rolling_30d_mean,
       event_count / NULLIF(rolling_30d_mean, 0) AS burst_score
FROM base
ORDER BY event_date;
