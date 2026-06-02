-- depends on: gdelt_gkg
--
-- direct Hormuz / Persian Gulf / Strait mentions per day.
--
-- v2EnhancedLocations is a semicolon-delimited list of location records.
-- Each record is `#`-delimited: type#name#country#FIPS#admin#lat#lon#feature_id#offset
-- We pattern-match the *name* field via CONTAINS on the full string — looking
-- for "Hormuz", "Strait of Hormuz", "Persian Gulf", "Kharg Island", "Ras Laffan"
-- (the specific places named in the project's transmission story).
--
-- IMPORTANT: GDELT GKG does NOT have a `MARITIME_CHOKEPOINT` theme (we
-- checked: 0 rows for `CHOKEPOINT` substring in either v1themes or
-- v2enhancedthemes across our 115k filtered articles). The roadmap doc had
-- MARITIME_CHOKEPOINT in the cherry-pick list as a wish. The actual maritime
-- themes are MARITIME_INCIDENT (~23k rows), MARITIME_PIRACY (~1.2k), and
-- MARITIME_TRANSPORT. For Hormuz-specific signal we therefore use
-- entity-name matching in V2EnhancedLocations against Hormuz / Persian Gulf /
-- Kharg (Island) / Ras Laffan (Qatar LNG terminal) / Bandar (Iranian ports).
-- Documented in `41_war_stories.md`.
CREATE OR REPLACE VIEW v_gdelt_gkg_hormuz_daily AS
WITH base AS (
    SELECT strptime(SUBSTR(gkg_datestamp, 1, 8), '%Y%m%d')::DATE AS event_date,
           v2enhancedlocations
    FROM gdelt_gkg
    WHERE v2enhancedlocations IS NOT NULL
)
SELECT event_date,
       COUNT(*) AS n_articles,
       SUM(CASE WHEN CONTAINS(v2enhancedlocations, 'Hormuz')        THEN 1 ELSE 0 END) AS n_hormuz,
       SUM(CASE WHEN CONTAINS(v2enhancedlocations, 'Persian Gulf')  THEN 1 ELSE 0 END) AS n_persian_gulf,
       SUM(CASE WHEN CONTAINS(v2enhancedlocations, 'Kharg')         THEN 1 ELSE 0 END) AS n_kharg,
       SUM(CASE WHEN CONTAINS(v2enhancedlocations, 'Ras Laffan')    THEN 1 ELSE 0 END) AS n_ras_laffan,
       SUM(CASE WHEN CONTAINS(v2enhancedlocations, 'Bandar')        THEN 1 ELSE 0 END) AS n_bandar_iranian_port,
       SUM(CASE WHEN CONTAINS(v2enhancedlocations, 'Hormuz')
                  OR CONTAINS(v2enhancedlocations, 'Persian Gulf')
                  OR CONTAINS(v2enhancedlocations, 'Kharg')
                  OR CONTAINS(v2enhancedlocations, 'Ras Laffan')    THEN 1 ELSE 0 END) AS n_chokepoint_total
FROM base
WHERE event_date BETWEEN DATE '2026-01-01' AND DATE '2026-05-31'
GROUP BY event_date
ORDER BY event_date;
