CREATE SCHEMA IF NOT EXISTS redditwatch;

CREATE TABLE IF NOT EXISTS redditwatch.rw_topics (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  query       TEXT NOT NULL UNIQUE,
  category    TEXT NOT NULL,
  priority    TEXT DEFAULT 'medium',
  active      BOOLEAN DEFAULT true,
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS redditwatch.rw_classifications (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id         TEXT NOT NULL UNIQUE,
  post_url        TEXT NOT NULL,
  author_handle   TEXT,
  topic_query     TEXT NOT NULL,
  classification  TEXT NOT NULL CHECK (classification IN ('INTERESTING', 'NOT_INTERESTING')),
  confidence      FLOAT,
  reason          TEXT,
  summary         TEXT,
  raw_post        JSONB,
  classified_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rw_class_label ON redditwatch.rw_classifications(classification);
CREATE INDEX IF NOT EXISTS idx_rw_class_date  ON redditwatch.rw_classifications(classified_at DESC);
CREATE INDEX IF NOT EXISTS idx_rw_class_conf  ON redditwatch.rw_classifications(confidence DESC);

INSERT INTO redditwatch.rw_topics (query, category, priority) VALUES
  ('r/HomeNetworking', 'networking', 'high'),
  ('r/selfhosted', 'selfhosted', 'high'),
  ('r/kubernetes', 'kubernetes', 'high'),
  ('r/ homelab', 'homelab', 'medium');