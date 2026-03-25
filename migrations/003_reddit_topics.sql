-- Replace Twitter hashtag seeds with Reddit subreddits
-- Safe to re-run: ON CONFLICT DO NOTHING

SET search_path = redditwatch;

-- Remove old hashtag-style seeds
DELETE FROM tw_topics WHERE query LIKE '#%';

-- Insert subreddits
INSERT INTO tw_topics (query, category, priority, active) VALUES
    ('LocalLLaMA',        'AI/LLM',          10, true),
    ('MachineLearning',   'AI/LLM',          10, true),
    ('singularity',       'AI/LLM',           8, true),
    ('ollama',            'AI/LLM',           9, true),
    ('kubernetes',        'Infrastructure',  10, true),
    ('devops',            'Infrastructure',   8, true),
    ('selfhosted',        'Infrastructure',   7, true),
    ('golang',            'Software Eng',    10, true),
    ('Python',            'Software Eng',     9, true),
    ('programming',       'Software Eng',     7, true),
    ('artificial',        'AI/LLM',           7, true),
    ('OpenSourceAI',      'AI/LLM',           8, true),
    ('Physics',           'Physics',          8, true),
    ('startups',          'Startups/VC',      9, true),
    ('YCombinator',       'Startups/VC',      9, true)
ON CONFLICT (query) DO NOTHING;
