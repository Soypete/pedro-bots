-- Reconcile rw_classifications with what the agents actually read and write.
--
-- Same Twitter-era drift as rw_topics (see 009): the live table came from
-- tw_classifications via 005_rename_tables.sql and carries
-- (subreddit, post_title, raw_json, created_at), while the code uses
-- (topic_query, author_handle, raw_post, classified_at).
--
-- store_classification() failed with UndefinedColumn on author_handle, and
-- get_interesting_posts() -- which drives the weekly suggestion digest --
-- filters on classified_at, which did not exist either.

-- subreddit holds the topic the post came from, which is what the code calls
-- topic_query. raw_json/raw_post and created_at/classified_at are likewise the
-- same data under different names, so these renames are lossless.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'rw_classifications' AND column_name = 'subreddit')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'rw_classifications' AND column_name = 'topic_query') THEN
        ALTER TABLE rw_classifications RENAME COLUMN subreddit TO topic_query;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'rw_classifications' AND column_name = 'raw_json')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'rw_classifications' AND column_name = 'raw_post') THEN
        ALTER TABLE rw_classifications RENAME COLUMN raw_json TO raw_post;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'rw_classifications' AND column_name = 'created_at')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'rw_classifications' AND column_name = 'classified_at') THEN
        ALTER TABLE rw_classifications RENAME COLUMN created_at TO classified_at;
    END IF;
END $$;

-- author_handle has no equivalent in the old schema; it is simply new.
ALTER TABLE rw_classifications ADD COLUMN IF NOT EXISTS author_handle TEXT;
ALTER TABLE rw_classifications ADD COLUMN IF NOT EXISTS topic_query TEXT;
ALTER TABLE rw_classifications ADD COLUMN IF NOT EXISTS raw_post JSONB;
ALTER TABLE rw_classifications ADD COLUMN IF NOT EXISTS classified_at TIMESTAMPTZ DEFAULT now();

-- store_classification() relies on ON CONFLICT (post_id).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'rw_classifications_post_id_key'
    ) THEN
        ALTER TABLE rw_classifications ADD CONSTRAINT rw_classifications_post_id_key
            UNIQUE (post_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_rw_class_classified_at
    ON rw_classifications(classified_at DESC);
