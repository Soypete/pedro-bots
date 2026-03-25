-- Drop Twitter-era tables and recreate with Reddit-appropriate column names.
-- This discards all old Twitter classification data.

SET search_path = redditwatch;

DROP TABLE IF EXISTS tw_classifications;
DROP TABLE IF EXISTS tw_topics;

CREATE TABLE tw_topics (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  query       TEXT NOT NULL UNIQUE,
  category    TEXT NOT NULL,
  priority    INT DEFAULT 5,
  active      BOOLEAN DEFAULT true,
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE tw_classifications (
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

CREATE INDEX idx_tw_class_label ON tw_classifications(classification);
CREATE INDEX idx_tw_class_date  ON tw_classifications(classified_at DESC);
CREATE INDEX idx_tw_class_conf  ON tw_classifications(confidence DESC);
