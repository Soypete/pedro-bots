-- Seed initial monitored topics
-- Safe to re-run (ON CONFLICT DO NOTHING)

INSERT INTO redditwatch.tw_topics (query, category, priority) VALUES
  ('#LLM',                   'AI / LLM',             'high'),
  ('#AIAgents',              'AI / LLM',             'high'),
  ('#LocalAI',               'AI / LLM',             'high'),
  ('#OpenSourceAI',          'AI / LLM',             'high'),
  ('#SoftwareEngineering',   'Software Engineering', 'high'),
  ('#DevTools',              'Software Engineering', 'high'),
  ('#CloudNative',           'Software Engineering', 'high'),
  ('#AgentFrameworks',       'AI Agents',            'high'),
  ('#LangChain',             'AI Agents',            'high'),
  ('#AutoGPT',               'AI Agents',            'high'),
  ('#Kubernetes',            'Infrastructure',       'medium'),
  ('#Homelab',               'Infrastructure',       'medium'),
  ('#SelfHosted',            'Infrastructure',       'medium'),
  ('#VCFunding',             'Startups / VC',        'medium'),
  ('#StartupFunding',        'Startups / VC',        'medium'),
  ('#TechStartups',          'Startups / VC',        'medium'),
  ('#Physics',               'Physics',              'medium'),
  ('#QuantumComputing',      'Physics',              'medium'),
  ('#TheoreticalPhysics',    'Physics',              'medium'),
  ('#GolangNews',            'Go / Python',          'low'),
  ('#PythonTips',            'Go / Python',          'low')
ON CONFLICT (query) DO NOTHING;
