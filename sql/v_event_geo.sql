CREATE OR REPLACE VIEW v_event_geo AS
SELECT actiongeo_fullname AS place,
       actiongeo_countrycode AS fips_country,
       round(actiongeo_lat::DOUBLE, 1) AS lat,
       round(actiongeo_long::DOUBLE, 1) AS lon,
       count(*) AS event_count,
       avg(avgtone::DOUBLE) AS avg_tone,
       sum(nummentions::INT) AS total_mentions
FROM gdelt
WHERE quadclass IN ('3','4')
  AND actiongeo_type IN ('3','4')
  AND actiongeo_lat <> '' AND actiongeo_long <> ''
  AND strptime(day,'%Y%m%d')::DATE BETWEEN DATE '2026-01-01' AND DATE '2026-05-31'
GROUP BY 1,2,3,4;
