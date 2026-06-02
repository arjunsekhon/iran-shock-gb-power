-- depends on: v_event_impact_multi, timeline
--
-- Phase-aware multi-horizon split — tests the long-form PDF's three-phase
-- prediction directly. Each timeline event is tagged with a `phase` value:
--
--   war-risk repricing  — early conflict; markets price expected supply risk
--   supply destruction  — actual physical impact (Hormuz, LNG strikes, blockade)
--   de-escalation       — talks, ceasefires, partial truce, framework
--
-- PDF claim: phase-1 events should be visible at t+3, phase-2 events need
-- t+10/t+20 to fully materialise, phase-3 events are a regime shift rather
-- than a single-day move. This view rolls per-event impacts up to phase x
-- horizon means so the prediction is testable in one table.
CREATE OR REPLACE VIEW v_event_impact_multi_phase AS
WITH joined AS (
    SELECT i.event_date, i.label,
           COALESCE(t.phase, 'unassigned') AS phase,
           i.brent_pct_1d, i.brent_pct_3d, i.brent_pct_5d, i.brent_pct_10d,
           i.ttf_pct_1d,   i.ttf_pct_3d,   i.ttf_pct_5d,   i.ttf_pct_10d,
           i.power_pct_1d, i.power_pct_3d, i.power_pct_5d, i.power_pct_10d
    FROM v_event_impact_multi i
    LEFT JOIN timeline t ON t.event_date = i.event_date
)
SELECT phase,
       count(*) AS n_events,
       round(AVG(brent_pct_1d),  1) AS brent_pct_1d_mean,
       round(AVG(brent_pct_3d),  1) AS brent_pct_3d_mean,
       round(AVG(brent_pct_5d),  1) AS brent_pct_5d_mean,
       round(AVG(brent_pct_10d), 1) AS brent_pct_10d_mean,
       round(AVG(ttf_pct_1d),    1) AS ttf_pct_1d_mean,
       round(AVG(ttf_pct_3d),    1) AS ttf_pct_3d_mean,
       round(AVG(ttf_pct_5d),    1) AS ttf_pct_5d_mean,
       round(AVG(ttf_pct_10d),   1) AS ttf_pct_10d_mean,
       round(AVG(power_pct_1d),  1) AS power_pct_1d_mean,
       round(AVG(power_pct_3d),  1) AS power_pct_3d_mean,
       round(AVG(power_pct_5d),  1) AS power_pct_5d_mean,
       round(AVG(power_pct_10d), 1) AS power_pct_10d_mean
FROM joined
GROUP BY phase
ORDER BY
    CASE phase
        WHEN 'war-risk repricing' THEN 1
        WHEN 'supply destruction' THEN 2
        WHEN 'de-escalation'      THEN 3
        ELSE 4
    END;
