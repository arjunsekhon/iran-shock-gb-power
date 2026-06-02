-- depends on: finbert_scores (raw table)
-- Athena port: ports directly.
--
-- FinBERT-scored daily sentiment.
--
-- finbert_signed = finbert_positive - finbert_negative, in [-1, +1].
-- We aggregate to daily mean / mentions-weighted mean (NumMentions is the
-- coverage proxy carried over from the Events file).
CREATE OR REPLACE VIEW v_finbert_daily AS
SELECT day::DATE AS event_date,
       COUNT(*)                                                            AS n_articles,
       AVG(finbert_signed::DOUBLE)                                         AS mean_finbert_signed,
       AVG(finbert_positive::DOUBLE)                                       AS mean_finbert_positive,
       AVG(finbert_negative::DOUBLE)                                       AS mean_finbert_negative,
       AVG(finbert_neutral::DOUBLE)                                        AS mean_finbert_neutral,
       SUM(finbert_signed::DOUBLE * nummentions::DOUBLE) /
           NULLIF(SUM(nummentions::DOUBLE), 0)                             AS mentions_weighted_finbert_signed,
       STDDEV(finbert_signed::DOUBLE)                                      AS finbert_dispersion
FROM finbert_scores
WHERE day IS NOT NULL
GROUP BY day
ORDER BY day;
