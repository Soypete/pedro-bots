-- Default RSS feeds for startup and podcast content
-- Safe to re-run: ON CONFLICT DO NOTHING

SET search_path = socialwatch;

-- Substack feeds for startup/AI content
INSERT INTO feeds (url, feed_type, name, active) VALUES
    ('https://soypetetech.substack.com/feed', 'substack', 'soypetetech', true),
    ('https://www.sequoiacap.com/feed/', 'substack', 'Sequoia', true),
    ('https://a16z.com/feed/', 'substack', 'a16z', true),
    ('https://www.lennysnewsletter.com/feed', 'substack', 'Lenny Newsletter', true),
    ('https://hunterwalk.substack.com/feed', 'substack', 'Hunter Walk', true),
    ('https://newsletter.posthog.com/feed', 'substack', 'PostHog', true),
    ('https://marginalrevolution.com/feed/', 'substack', 'Marginal Revolution', true),
    ('https://www.collaborativefund.com/blog?format=rss', 'substack', 'Collaborative Fund', true),
    ('https://sarahkcalahan.substack.com/feed', 'substack', 'Sarah K Calahan', true),
    ('https://generalistmanifesto.substack.com/feed', 'substack', 'Generalist Manifesto', true)
ON CONFLICT DO NOTHING;

-- AI/tech YouTube channels (channel_id format for rss.py)
INSERT INTO feeds (url, feed_type, name, channel_id, active) VALUES
    ('', 'youtube', 'AI Explained', 'UC9ChLEf0Lv9nqg5JwQ5qFAA', true),
    ('', 'youtube', 'Dot CSV', 'UC2\_pa8RvlEMg5lH-FId-M-Q', true),
    ('', 'youtube', 'Chris Alex', 'UCo-7Ob7lK0-2\_c6OE3kL5\_g', true)
ON CONFLICT DO NOTHING;