-- TweetWatch schema migration
-- Run once against your Supabase instance

CREATE SCHEMA IF NOT EXISTS tweetwatch;

CREATE TABLE IF NOT EXISTS tweetwatch.tw_topics (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  query       TEXT NOT NULL UNIQUE,
  category    TEXT NOT NULL,
  priority    TEXT DEFAULT 'medium',
  active      BOOLEAN DEFAULT true,
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tweetwatch.tw_classifications (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tweet_id        TEXT NOT NULL UNIQUE,
  tweet_url       TEXT NOT NULL,
  author_handle   TEXT,
  topic_query     TEXT NOT NULL,
  classification  TEXT NOT NULL CHECK (classification IN ('INTERESTING', 'NOT_INTERESTING')),
  confidence      FLOAT,
  reason          TEXT,
  summary         TEXT,
  raw_tweet       JSONB,
  classified_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tw_class_label ON tweetwatch.tw_classifications(classification);
CREATE INDEX IF NOT EXISTS idx_tw_class_date  ON tweetwatch.tw_classifications(classified_at DESC);
CREATE INDEX IF NOT EXISTS idx_tw_class_conf  ON tweetwatch.tw_classifications(confidence DESC);
