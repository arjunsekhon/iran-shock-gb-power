-- Athena port: strptime(...) -> date_parse(...);  ::TYPE -> CAST(... AS TYPE)
CREATE OR REPLACE VIEW v_middle_east_events AS
SELECT strptime(day,'%Y%m%d')::DATE AS event_date,
       count(*) AS event_count,
       avg(avgtone::DOUBLE) AS avg_tone,
       avg(goldsteinscale::DOUBLE) AS avg_goldstein,
       sum(nummentions::INT) AS total_mentions
FROM gdelt
WHERE actiongeo_countrycode IN ('IR','IS','US','SA','AE','QA','IZ','KU','BA','LE','SY','YM')
  AND quadclass IN ('3','4')
  AND strptime(day,'%Y%m%d')::DATE BETWEEN DATE '2026-01-01' AND DATE '2026-05-31'
GROUP BY 1 ORDER BY 1;
-- NOTE: the IN-list mirrors config.MIDDLE_EAST — keep the two in step.
