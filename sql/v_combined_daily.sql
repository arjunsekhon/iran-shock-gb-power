CREATE OR REPLACE VIEW v_combined_daily AS
SELECT b.price_date AS d,
       b.brent_close,
       g.ttf_close,
       p.gb_power_avg,
       e.event_count,
       e.avg_tone
FROM v_brent_daily b
LEFT JOIN v_ttf_daily         g ON b.price_date = g.price_date
LEFT JOIN v_gb_power_daily    p ON b.price_date = p.price_date
LEFT JOIN v_middle_east_events e ON b.price_date = e.event_date
ORDER BY d;
