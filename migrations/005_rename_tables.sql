-- Rename tables from Twitter-era tw_ prefix to rw_ (RedditWatch)

SET search_path = tweetwatch;

ALTER TABLE tw_topics RENAME TO rw_topics;
ALTER TABLE tw_classifications RENAME TO rw_classifications;

-- Update indexes to match new table names
ALTER INDEX idx_tw_class_label RENAME TO idx_rw_class_label;
ALTER INDEX idx_tw_class_date  RENAME TO idx_rw_class_date;
ALTER INDEX idx_tw_class_conf  RENAME TO idx_rw_class_conf;
