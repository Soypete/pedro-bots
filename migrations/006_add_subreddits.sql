-- Comprehensive subreddit list for startup co-founder search, homelab podcast, and AI/content monitoring
-- Safe to re-run: ON CONFLICT DO NOTHING

SET search_path = redditwatch;

-- AI/LLM
INSERT INTO tw_topics (query, category, priority, active) VALUES
    ('LocalLLaMA',           'AI/LLM', 10, true),
    ('MachineLearning',      'AI/LLM', 10, true),
    ('learnmachinelearning', 'AI/LLM', 10, true),
    ('artificial',           'AI/LLM', 10, true),
    ('singularity',          'AI/LLM',  8, true),
    ('ollama',               'AI/LLM',  9, true),
    ('OpenSourceAI',         'AI/LLM',  8, true),
    ('LocalLlm',             'AI/LLM', 10, true),
    ('llm',                  'AI/LLM',  8, true),
    ('人工智能',             'AI/LLM',  5, true)
ON CONFLICT (query) DO NOTHING;

-- AI Hardware
INSERT INTO tw_topics (query, category, priority, active) VALUES
    ('nvidia',        'AI Hardware', 10, true),
    ('hardwareswap',  'AI Hardware',  7, true),
    ('buildapc',      'AI Hardware',  7, true)
ON CONFLICT (query) DO NOTHING;

-- AI Security
INSERT INTO tw_topics (query, category, priority, active) VALUES
    ('cybersecurity',    'AI Security', 10, true),
    ('netsec',           'AI Security',  8, true),
    ('hacking',          'AI Security',  7, true)
ON CONFLICT (query) DO NOTHING;

-- Software Engineering
INSERT INTO tw_topics (query, category, priority, active) VALUES
    ('programming',        'Software Eng', 10, true),
    ('badcode',            'Software Eng',  9, true),
    ('compsci',            'Software Eng',  9, true),
    ('computers',          'Software Eng',  8, true),
    ('golang',             'Software Eng', 10, true),
    ('Python',             'Software Eng',  9, true),
    ('javascript',         'Software Eng',  8, true),
    ('rust',               'Software Eng',  8, true)
ON CONFLICT (query) DO NOTHING;

-- Infrastructure (Homelab)
INSERT INTO tw_topics (query, category, priority, active) VALUES
    ('homelab',            'Infrastructure', 10, true),
    ('Tailscale',          'Infrastructure', 10, true),
    ('linuxmasterrace',    'Infrastructure',  9, true),
    ('unixporn',           'Infrastructure',  8, true),
    ('selfhosted',         'Infrastructure',  9, true),
    ('kubernetes',         'Infrastructure', 10, true),
    ('devops',             'Infrastructure',  8, true),
    ('HomeServer',         'Infrastructure',  8, true),
    ('homelabber',         'Infrastructure',  7, true)
ON CONFLICT (query) DO NOTHING;

-- Startups/VC
INSERT INTO tw_topics (query, category, priority, active) VALUES
    ('startups',       'Startups/VC', 10, true),
    ('YCombinator',    'Startups/VC', 10, true),
    ('smallbiz',       'Startups/VC',  8, true),
    ('Entrepreneur',   'Startups/VC',  8, true)
ON CONFLICT (query) DO NOTHING;

-- Physics/Science
INSERT INTO tw_topics (query, category, priority, active) VALUES
    ('AskPhysics',       'Physics',  8, true),
    ('Physics',          'Physics',  8, true),
    ('quantumcomputing', 'Physics',  7, true)
ON CONFLICT (query) DO NOTHING;

-- Podcasting/Content
INSERT INTO tw_topics (query, category, priority, active) VALUES
    ('podcasts',        'Podcasting',  9, true),
    ('youtube',         'Podcasting',  7, true),
    ('substack',        'Podcasting',  8, true)
ON CONFLICT (query) DO NOTHING;

-- AI Agents & Engineering
INSERT INTO tw_topics (query, category, priority, active) VALUES
    ('agents',               'AI Agents',      10, true),
    ('AIagents',             'AI Agents',      10, true),
    ('contextengineering',   'AI Agents',       9, true),
    ('langchain',            'AI Agents',       9, true),
    ('LocalGPT',             'AI Agents',       8, true)
ON CONFLICT (query) DO NOTHING;

-- Knowledge Graphs & NLP
INSERT INTO tw_topics (query, category, priority, active) VALUES
    ('computationallinguistics', 'NLP/KG',   8, true),
    ('ontology',                 'NLP/KG',   7, true),
    ('KnowledgeGraph',           'NLP/KG',   8, true),
    ('NLP',                      'NLP/KG',   8, true)
ON CONFLICT (query) DO NOTHING;

-- Side Projects
INSERT INTO tw_topics (query, category, priority, active) VALUES
    ('sideproject',    'Startups/VC',  8, true),
    ('sideprojects',   'Startups/VC',  8, true)
ON CONFLICT (query) DO NOTHING;

-- Diversity
INSERT INTO tw_topics (query, category, priority, active) VALUES
    ('womenintech',    'Diversity',  8, true),
    ('LGBTtech',       'Diversity',  6, true)
ON CONFLICT (query) DO NOTHING;