-- CFP Watch: Store Call For Papers for conferences and meetups

CREATE TABLE IF NOT EXISTS rw_cfps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_name TEXT NOT NULL,
    event_url TEXT NOT NULL,
    cfp_url TEXT,
    location TEXT,
    event_date TEXT, -- Human-readable: "Nov 15-17, 2026" or "TBD 2026"
    cfp_deadline TEXT, -- Human-readable: "July 1, 2026" or "TBD" or "CLOSED"
    topics TEXT[], -- ['agent-governance', 'local-ai', 'opensource-ai']
    source TEXT, -- 'duckduckgo', 'sessionize', 'meetup', etc.
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(event_url)
);

-- Reconcile tables created before this migration, which lacked location/source.
ALTER TABLE rw_cfps ADD COLUMN IF NOT EXISTS location TEXT;
ALTER TABLE rw_cfps ADD COLUMN IF NOT EXISTS source TEXT;
ALTER TABLE rw_cfps ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();

-- Older tables typed `topics` as TEXT and `cfp_deadline` as DATE. The agent writes a
-- string array of topics and free-form deadlines ("TBD", "CLOSED"), so widen both.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rw_cfps' AND column_name = 'topics' AND udt_name = 'text'
    ) THEN
        ALTER TABLE rw_cfps
            ALTER COLUMN topics TYPE TEXT[] USING CASE
                WHEN topics IS NULL OR topics = '' THEN ARRAY[]::TEXT[]
                ELSE string_to_array(topics, ',')
            END;
    END IF;
END $$;

ALTER TABLE rw_cfps ALTER COLUMN cfp_deadline TYPE TEXT USING cfp_deadline::TEXT;
-- store_cfp() relies on ON CONFLICT (event_url); older tables may lack the constraint.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'rw_cfps_event_url_key'
    ) THEN
        ALTER TABLE rw_cfps ADD CONSTRAINT rw_cfps_event_url_key UNIQUE (event_url);
    END IF;
END $$;

-- Index for querying recent CFPs
CREATE INDEX IF NOT EXISTS idx_rw_cfps_created_at ON rw_cfps(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rw_cfps_topics ON rw_cfps USING GIN(topics);

-- Insert unique CFPs (upsert helper)
CREATE OR REPLACE FUNCTION upsert_cfp(
    p_event_name TEXT,
    p_event_url TEXT,
    p_cfp_url TEXT DEFAULT NULL,
    p_location TEXT DEFAULT NULL,
    p_event_date TEXT DEFAULT NULL,
    p_cfp_deadline TEXT DEFAULT NULL,
    p_topics TEXT DEFAULT NULL,
    p_source TEXT DEFAULT 'unknown'
) RETURNS UUID AS $$
DECLARE
    v_topics TEXT[];
    v_id UUID;
BEGIN
    v_topics := COALESCE(string_to_array(p_topics, ','), ARRAY[]::TEXT[]);
    INSERT INTO rw_cfps (event_name, event_url, cfp_url, location, event_date, cfp_deadline, topics, source)
    VALUES (p_event_name, p_event_url, p_cfp_url, p_location, p_event_date, p_cfp_deadline, v_topics, p_source)
    ON CONFLICT (event_url) DO UPDATE
    SET
        cfp_url = COALESCE(excluded.cfp_url, rw_cfps.cfp_url),
        location = COALESCE(excluded.location, rw_cfps.location),
        event_date = COALESCE(excluded.event_date, rw_cfps.event_date),
        cfp_deadline = COALESCE(excluded.cfp_deadline, rw_cfps.cfp_deadline),
        topics = ARRAY(SELECT DISTINCT unnest(rw_cfps.topics || excluded.topics)),
        source = CASE WHEN rw_cfps.source = 'unknown' THEN excluded.source ELSE rw_cfps.source END
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;