-- depends on: gdelt_gkg
-- Athena port: STR_TO_MAP / CONTAINS / SPLIT_PART port directly.
--
-- energy + maritime + conflict theme counts per day.
--
-- v1themes is a semicolon-delimited list of theme codes per article. We
-- count rows where the list contains each cherry-picked theme. Filter at
-- ingest already restricted the universe; here we further split by theme.
--
-- Hormuz / chokepoint detection happens in the LOCATIONS view (separate);
-- this view is theme-only.
CREATE OR REPLACE VIEW v_gdelt_gkg_themes_daily AS
WITH base AS (
    SELECT strptime(SUBSTR(gkg_datestamp, 1, 8), '%Y%m%d')::DATE AS event_date,
           v1themes
    FROM gdelt_gkg
    WHERE v1themes IS NOT NULL
)
SELECT event_date,
       COUNT(*) AS n_articles,
       -- Energy / oil themes
       SUM(CASE WHEN CONTAINS(v1themes, 'ECON_OIL')              THEN 1 ELSE 0 END) AS n_econ_oil,
       SUM(CASE WHEN CONTAINS(v1themes, 'ECON_OILEXPORT')        THEN 1 ELSE 0 END) AS n_econ_oilexport,
       SUM(CASE WHEN CONTAINS(v1themes, 'ENERGY_SECURITY')       THEN 1 ELSE 0 END) AS n_energy_security,
       SUM(CASE WHEN CONTAINS(v1themes, 'ENV_NATGAS')            THEN 1 ELSE 0 END) AS n_env_natgas,
       SUM(CASE WHEN CONTAINS(v1themes, 'ENV_NUCLEARPOWER')      THEN 1 ELSE 0 END) AS n_env_nuclearpower,
       -- Maritime + chokepoint themes (Hormuz indirect indicators)
       SUM(CASE WHEN CONTAINS(v1themes, 'MARITIME_TRANSPORT')    THEN 1 ELSE 0 END) AS n_maritime_transport,
       SUM(CASE WHEN CONTAINS(v1themes, 'MARITIME_INCIDENT')     THEN 1 ELSE 0 END) AS n_maritime_incident,
       -- Conflict themes
       SUM(CASE WHEN CONTAINS(v1themes, 'MILITARY_OPERATIONS')   THEN 1 ELSE 0 END) AS n_military_ops,
       SUM(CASE WHEN CONTAINS(v1themes, 'ARMEDCONFLICT')         THEN 1 ELSE 0 END) AS n_armedconflict,
       SUM(CASE WHEN CONTAINS(v1themes, 'TERROR')                THEN 1 ELSE 0 END) AS n_terror,
       SUM(CASE WHEN CONTAINS(v1themes, 'WB_2042_OIL_INDUSTRY')  THEN 1 ELSE 0 END) AS n_wb_oil_industry,
       -- Composite indicators
       SUM(CASE WHEN CONTAINS(v1themes, 'ECON_OIL')
                  OR CONTAINS(v1themes, 'ECON_OILEXPORT')
                  OR CONTAINS(v1themes, 'WB_2042_OIL_INDUSTRY') THEN 1 ELSE 0 END) AS n_oil_total,
       SUM(CASE WHEN CONTAINS(v1themes, 'MARITIME_TRANSPORT')
                  OR CONTAINS(v1themes, 'MARITIME_INCIDENT')   THEN 1 ELSE 0 END) AS n_maritime_total,
       SUM(CASE WHEN CONTAINS(v1themes, 'MILITARY_OPERATIONS')
                  OR CONTAINS(v1themes, 'ARMEDCONFLICT')
                  OR CONTAINS(v1themes, 'TERROR')              THEN 1 ELSE 0 END) AS n_conflict_total
FROM base
WHERE event_date BETWEEN DATE '2026-01-01' AND DATE '2026-05-31'
GROUP BY event_date
ORDER BY event_date;
