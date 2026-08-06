-- Reconcile rw_topics with what the code actually queries.
--
-- The live table descends from the Twitter-era tw_topics, renamed by
-- 005_rename_tables.sql, so it carries (subreddit, keywords). The agents and
-- migrations/redditwatch.sql expect (query, category, priority), so
-- load_active_topics() fails with UndefinedColumn on every monitor run.
--
-- subreddit already holds exactly what the code wants from query, and keywords
-- is empty on every row, so renaming is lossless.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rw_topics' AND column_name = 'subreddit'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rw_topics' AND column_name = 'query'
    ) THEN
        ALTER TABLE rw_topics RENAME COLUMN subreddit TO query;
    END IF;
END $$;

ALTER TABLE rw_topics ADD COLUMN IF NOT EXISTS category TEXT;
ALTER TABLE rw_topics ADD COLUMN IF NOT EXISTS priority TEXT DEFAULT 'medium';

-- load_active_topics() orders by priority DESC; a NULL there would sort
-- unpredictably against populated rows.
UPDATE rw_topics SET priority = 'medium' WHERE priority IS NULL;
UPDATE rw_topics SET category = 'tech' WHERE category IS NULL;

-- keywords is unused by the agents and empty in practice. Left in place rather
-- than dropped, so this migration stays reversible.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'rw_topics_query_key'
    ) THEN
        ALTER TABLE rw_topics ADD CONSTRAINT rw_topics_query_key UNIQUE (query);
    END IF;
END $$;
