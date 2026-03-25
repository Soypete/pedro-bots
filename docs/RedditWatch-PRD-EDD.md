# Reddit Watcher — Reddit Intelligence Agent

**Product Requirements & Engineering Design Document**

| Field | Value |
|---|---|
| Version | 1.0 |
| Status | Draft — For Review |
| Author | Miriah Peterson (SoypeteTech) |
| Date | March 2026 |
| Stack | Python · LangChain · LangGraph · Deep Agents |
| Deployment | Kubernetes (homelab) |
| Inference | llama.cpp (configurable model) |

---

# Part 1 — Product Requirements Document

---

## 1. Overview

RedditWatch is a self-hosted, LLM-powered agent that monitors Reddit on your behalf. It runs on your existing Kubernetes homelab, uses your local llama.cpp inference server for all LLM calls, and delivers curated tech updates to **Discord** via webhooks. The agent classifies posts for relevance, stores results in your existing Supabase instance, and generates weekly suggestions for new subreddits and keywords to follow. All classifications are stored with LLM reasoning to support future fine-tuning of the classifier.

> **⚠️ Critical Constraint: Reddit API Rate Limits**
>
> Reddit's free API tier allows 60 requests/minute with strict rate limiting. For reliable multi-subreddit polling 3× per day, the **Premium tier ($5/mo) or using PRAW's built-in rate limiting** is recommended. This document is architected for free tier with proper rate limiting. Premium tier is noted for higher throughput if needed.

---

## 2. Goals & Non-Goals

### Goals

- Keep Miriah informed of tech Reddit without requiring active browsing
- Surface new tools, research, funding announcements, and best practices in AI, cloud, software, agents, and physics
- Classify post relevance using a local LLM — no data leaves the homelab (except Discord and Reddit API calls)
- Store all post classifications and LLM reasoning in Supabase for future fine-tuning of the classifier model
- Weekly suggestions for new subreddits and keywords based on what has been engaging
- Run entirely on the existing Kubernetes cluster with no new infrastructure required

### Non-Goals

- Replying to or posting on Reddit on your behalf
- Full post archival or search history beyond Supabase storage
- A web UI or dashboard (Discord is the sole interface for now)
- Real-time streaming (not required for current use case)

---

## 3. User Stories

| User Story | Acceptance Criteria |
|---|---|
| As Miriah, I want to receive a Discord digest of interesting posts 3× per day so I stay informed without doomscrolling | Agent runs at 08:00, 13:00, 18:00 MT; sends ≥1 message per run if relevant posts exist |
| As Miriah, I want the LLM to decide what's interesting so I don't get noise | LLM classifies each post; only INTERESTING posts are forwarded; classification + reasoning stored in Supabase |
| As Miriah, I want post links in my Discord so I can open them directly | Each message includes the post URL; Discord webhook sends a formatted message with link |
| As Miriah, I want weekly subreddit + keyword suggestions | Every Monday at 09:00 MT, a separate agent run generates a suggestion message via Discord |
| As Miriah, I want the model to be swappable without code changes | Model endpoint and name are environment variables; no hardcoded model strings |
| As Miriah, I want my classification history saved so it can be used to fine-tune the model later | Every classification (INTERESTING or NOT_INTERESTING) is persisted with full LLM reasoning and raw post JSON |

---

## 4. Monitored Topics (Initial Set)

Subreddit and keyword queries are stored in the `rw_topics` Supabase table and are editable without redeployment.

| Category | Subreddits / Keywords | Priority |
|---|---|---|
| AI / LLM | r/LocalLLaMA, r/Artificial, AI agents, LLMs | High |
| Software Engineering | r/programming, r/devops, r/kubernetes | High |
| AI Agents | r/Agentic, LangChain, AutoGPT | High |
| Infrastructure | r/homelab, r/selfhosted, Kubernetes | Medium |
| Startups / VC | r/startups, VC funding, tech startups | Medium |
| Physics | r/physics, r/quantumcomputing | Medium |
| Go / Python | r/golang, r/python | Low |

---

## 5. API Tier Behavior

| Feature | Free Tier (fallback) | Basic Tier (recommended) |
|---|---|---|
| API calls/minute | 60 | 60 |
| Subreddits per run | 1 query; must rotate through topics | All topics per run (batched) |
| Results per query | 10 posts max | 100 posts max |
| Rate limit handling | Built-in exponential backoff | Built-in exponential backoff |
| Polling frequency | 1 subreddit per 3× daily run | Full topic sweep 3× daily |

---

## 6. Discord Webhook Setup

To deliver messages to your **Discord channel**, you need to create a webhook. Discord webhooks allow you to send messages to a channel without a bot user.

### Creating a Discord Webhook

1. Open Discord and go to Server Settings → Integrations → Webhooks
2. Click "New Webhook" to create one
3. Name it (e.g., "RedditWatcher")
4. Select the channel where messages should be delivered
5. Copy the webhook URL — this is your `DISCORD_WEBHOOK_URL`

### Webhook Features

- **@here mentions:** Include `{{<@here>}}` or `{{<@everyone>}}` in the message to ping the channel (optional, configurable)
- **User mentions:** Mention specific users with `{{<@user_id}}`
- **Rich embeds:** Messages support Discord's embed format for better visual presentation

### Message Format

```
RedditWatcher — [08:00 Digest]

**1. [r/LocalAI] u/username**
> Post title or excerpt...
> 🔼 42 points | 💬 15 comments
> https://reddit.com/r/LocalAI/comments/...

**2. [r/AIAgents] u/username2**
> Post summary...
> 🔼 128 points | 💬 32 comments
> https://reddit.com/r/...

-- 2 of 14 fetched posts were relevant --
```

Weekly suggestion messages:

```
RedditWatcher Weekly Suggestions

**Subreddits to consider adding:**
  - r/MLOps — trending in your interest areas this week
  - r/Rust — appearing alongside r/Programming

**Keywords to consider following:**
  - "AI agents" — high engagement on agent posts
  - "local inference" — consistent LocalAI and DevTools content
```

---

## 7. Fine-Tuning Strategy (Future)

Every classification written to `rw_classifications` is a training example. The schema captures everything needed to build a supervised dataset:

- **Input:** raw post text + author + topic context
- **Label:** `INTERESTING` or `NOT_INTERESTING`
- **Reasoning:** the LLM's one-sentence explanation (useful for chain-of-thought fine-tuning)

When you're ready to fine-tune:

1. **Export training data** — query Supabase for all classifications where `confidence >= 0.8` to get the highest-quality examples first
2. **Format for instruction tuning** — each row becomes a `(system_prompt, post_text, classification + reason)` triple in the format your target model expects (ChatML, Alpaca, etc.)
3. **Review labels** — spot-check a sample of NOT_INTERESTING classifications; these are easy to mislabel early on when the prompt is still being tuned
4. **Fine-tune** — use Unsloth on your RTX 5090 against a base Qwen2.5 or Llama 3 model
5. **Swap in** — update `LLAMA_CPP_MODEL` in the ConfigMap to point to the fine-tuned GGUF; no code changes required

The goal over time is a lightweight classifier that barely needs a system prompt because the preferences are baked into the weights — significantly reducing inference cost per run.

---

## 8. Success Metrics

- Agent runs on schedule with < 2% missed windows
- Classification latency < 30s per batch of 10 posts on homelab hardware
- Discord delivery success rate > 99% (webhook is synchronous)
- Supabase write success rate > 99% per classification
- Zero PII or API credentials in code or ConfigMaps — all via Kubernetes Secrets

---

# Part 2 — Engineering Design Document

---

## 1. System Architecture

RedditWatch is composed of two independent LangGraph agents orchestrated as Kubernetes CronJobs. Both agents share the same Python package and Supabase schema, differing only in their graph topology and schedule.

```
+-------------------------------------------------------------------+
|                      Kubernetes CronJobs                          |
|                                                                   |
|   +----------------------+     +--------------------------+       |
|   |  MonitorAgent        |     |  SuggestionAgent         |       |
|   |  Schedule: 3x daily  |     |  Schedule: Mon 09:00 MT  |       |
|   +----------+-----------+     +------------+-------------+       |
|              |                               |                    |
|   +----------v-------------------------------v-----------------+  |
|   |            Deep Agents SDK  (LangGraph runtime)            |  |
|   |  LangChain tool calling + LangGraph state machine          |  |
|   +----------------------------+--------------------------------+  |
|                                |                                   |
|         +-----------+----------+----------+                       |
|         v           v                     v                       |
|   Reddit API      llama.cpp server   Discord Webhook              |
|   (PRAW search)   (homelab, :8080)   (channel messages)           |
|         |           |                     |                       |
|         +-----------+----------+----------+                       |
|                                v                                   |
|                        Supabase (existing)                        |
|                  tw_classifications + tw_topics                    |
+-------------------------------------------------------------------+
```

---

## 2. LangGraph Agent Graphs

### 2.1 MonitorAgent Graph

```
START
  |
  v
[load_topics]          Read active subreddits from Supabase rw_topics table
  |
  v
[fetch_posts]          Reddit API (PRAW) recent search — one query per topic
  |                    Deduplicates by post_id against rw_classifications
  v
[classify_batch]       LLM call: classify each post as INTERESTING / NOT_INTERESTING
  |                    Deep Agents file system used to stage large batches
  |                    without overflowing context window
  v
[store_results]        Write all classifications + reasoning to rw_classifications
  |
  v
[filter_interesting] --> (no interesting posts?) --> [log_empty_run] --> END
   |
   v
[format_discord]      Build message with summaries + post URLs
   |
   v
[send_discord]        Discord webhook call to channel
  |
  v
END
```

### 2.2 SuggestionAgent Graph

```
START
  |
  v
[load_recent_classifications]   Query Supabase: last 7 days of INTERESTING posts
   |
   v
[analyze_patterns]              LLM call: identify recurring themes, subreddits,
   |                             and keywords from the interesting post corpus
   v
[fetch_trending]                Reddit trending subreddits (no tier requirement)
   |                             Skipped gracefully if rate limited
   v
[generate_suggestions]          LLM call: produce ranked subreddit + keyword list
   |
   v
[send_discord]                  Deliver suggestion message via Discord webhook
  |
  v
END
```

---

## 3. Tool Definitions

All tools are Python functions with type annotations passed to `create_deep_agent()`. The Deep Agents SDK wraps them in LangChain's tool-calling interface.

```python
# core/tools/reddit.py

def search_reddit_posts(subreddit: str, query: str, max_results: int = 10) -> list[dict]:
    """Search recent posts in a subreddit via Reddit API. Returns list of post objects."""

def get_subreddit_trending(subreddit: str) -> list[dict]:
    """Fetch trending/hot posts from a subreddit. Returns list of popular posts."""


# core/tools/supabase_tools.py

def load_active_topics() -> list[str]:
    """Load monitored subreddit/keyword queries from Supabase rw_topics table."""

def store_classification(
    post_id: str,
    topic: str,
    classification: str,
    reasoning: str,
    summary: str,
    confidence: float,
    post_url: str,
    author: str,
    raw_post: dict,
) -> bool:
    """Persist LLM classification result to rw_classifications table."""

def get_interesting_posts(days: int = 7) -> list[dict]:
    """Retrieve INTERESTING-classified posts from the last N days."""

def get_seen_post_ids() -> set[str]:
    """Return set of post IDs already processed (for deduplication)."""


# core/tools/discord.py

def send_discord_message(body: str, mentions: str = "") -> bool:
    """Send a message via Discord webhook. Optional mentions can include user IDs or @here."""
```

---

## 4. LLM Interface

RedditWatch connects to your local llama.cpp server via LangChain's OpenAI-compatible chat interface. The server URL and model name are injected via environment variables, making the model fully swappable.

```python
# config.py
from langchain_openai import ChatOpenAI
import os

def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=os.environ["LLAMA_CPP_BASE_URL"],  # e.g. http://llamacpp-svc:8080/v1
        model=os.environ["LLAMA_CPP_MODEL"],        # e.g. qwen2.5-14b-instruct
        api_key="not-needed",
        temperature=0.2,
        max_tokens=2048,
    )
```

Classification prompt structured for consistent JSON output and future fine-tuning data collection:

```python
CLASSIFY_SYSTEM_PROMPT = """
You are a tech Reddit curator for a developer, AI researcher, and content creator.
Your job is to decide if a Reddit post is worth surfacing given these interests:
AI agents, LLMs, local inference, Kubernetes, Go, Python, cloud infrastructure,
VC funding for startups, physics, and open-source tooling.

For each post, respond with JSON only:
{
  "classification": "INTERESTING" | "NOT_INTERESTING",
  "confidence": 0.0-1.0,
  "reason": "one sentence explanation",
  "summary": "one sentence post summary (INTERESTING only, else null)"
}
"""
```

---

## 5. Supabase Schema

Two new tables added to the existing Supabase instance. Run once at setup.

```sql
-- Migration: 001_reddit-watcher.sql

CREATE TABLE IF NOT EXISTS rw_topics (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subreddit   TEXT NOT NULL,
  query       TEXT NOT NULL,
  category    TEXT NOT NULL,
  priority    TEXT DEFAULT 'medium',
  active      BOOLEAN DEFAULT true,
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rw_classifications (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id         TEXT NOT NULL UNIQUE,
  post_url        TEXT NOT NULL,
  author_name     TEXT,
  topic_query     TEXT NOT NULL,
  classification  TEXT NOT NULL CHECK (classification IN ('INTERESTING','NOT_INTERESTING')),
  confidence      FLOAT,
  reason          TEXT,      -- LLM reasoning — primary fine-tuning signal
  summary         TEXT,
  raw_post        JSONB,     -- full post object for fine-tuning input reconstruction
  classified_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_rw_class_label ON rw_classifications(classification);
CREATE INDEX idx_rw_class_date  ON rw_classifications(classified_at DESC);
CREATE INDEX idx_rw_class_conf  ON rw_classifications(confidence DESC);
```

### Fine-Tuning Export Query

```sql
-- High-confidence examples for supervised fine-tuning
SELECT
  post_id,
  author_name,
  topic_query,
  raw_post->>'title'  AS post_title,
  raw_post->>'selftext'  AS post_body,
  classification,
  confidence,
  reason,
  summary,
  classified_at
FROM rw_classifications
WHERE confidence >= 0.8
ORDER BY classified_at DESC;
```

---

## 6. Deep Agents SDK Integration

Both agents are instantiated via `create_deep_agent()` with their respective tool sets. The in-memory filesystem backend stages large post batches to prevent context overflow when fetching many posts across all topics in one run.

```python
# core/agents/monitor.py
from deepagents import create_deep_agent
from core.config import get_llm
from core.tools.reddit import search_reddit_posts, get_subreddit_trending
from core.tools.supabase_tools import load_active_topics, store_classification, get_seen_post_ids
from core.tools.discord import send_discord_message

MONITOR_SYSTEM_PROMPT = """
You are Reddit Watcher, a Reddit monitoring agent. Your job each run:
1. Call load_active_topics to get the current subreddit list
2. Call search_reddit_posts for each topic — skip any post_id in get_seen_post_ids()
3. Classify each new post (INTERESTING or NOT_INTERESTING)
4. Call store_classification for every post, regardless of classification
5. If any posts are INTERESTING, call send_discord_message with a formatted digest
6. If nothing is interesting, log the empty run and stop

Always store classifications — every result is training data for future fine-tuning.
"""

def build_monitor_agent():
    return create_deep_agent(
        llm=get_llm(),
        tools=[
            search_posts,
            load_active_topics,
            store_classification,
            get_seen_post_ids,
            send_discord_message,
        ],
        system_prompt=MONITOR_SYSTEM_PROMPT,
        filesystem_backend="memory",
    )

def run_monitor():
    agent = build_monitor_agent()
    agent.invoke({"messages": [{"role": "user", "content": "Run the Reddit monitor pipeline."}]})
```

---

## 7. Kubernetes Deployment

### 7.1 Directory Structure

```
reddit-watcher/
├── charts/
│   └── reddit-watcher/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── cronjob-monitor.yaml
│           └── cronjob-suggest.yaml
├── src/
│   ├── core/
│   │   ├── agents/
│   │   │   ├── monitor.py
│   │   └── suggestion.py
│   ├── tools/
│   │   ├── reddit.py
│   │   ├── supabase.py
│   │   └── discord.py
│   ├── config.py
│   └── main.py               # Entrypoint: --agent monitor|suggest
├── migrations/
│   └── 001_reddit-watcher.sql
├── Dockerfile
├── pyproject.toml
└── README.md
```

### 7.2 CronJob Manifests

```yaml
# cronjob-monitor.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: reddit-watcher-monitor
  namespace: reddit-watcher
spec:
  schedule: "0 14,19,0 * * *"  # 08:00, 13:00, 18:00 MT (UTC-6)
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 5
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: reddit-watcher
            image: registry.local/reddit-watcher:latest
            command: ["python", "-m", "main", "--agent", "monitor"]
            envFrom:
            - secretRef:
                name: reddit-watcher-secrets
            - configMapRef:
                name: reddit-watcher-config
```

```yaml
# cronjob-suggest.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: reddit-watcher-suggest
  namespace: reddit-watcher
spec:
  schedule: "0 15 * * 1"  # 09:00 MT Monday (UTC-6)
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: reddit-watcher
            image: registry.local/reddit-watcher:latest
            command: ["python", "-m", "main", "--agent", "suggest"]
            envFrom:
            - secretRef:
                name: reddit-watcher-secrets
            - configMapRef:
                name: reddit-watcher-config
```

### 7.3 Secrets

```bash
# Create Kubernetes secret — never commit values to git
kubectl create secret generic reddit-watcher-secrets \
  --namespace=reddit-watcher \
  --from-literal=REDDIT_CLIENT_ID='...' \
  --from-literal=REDDIT_CLIENT_SECRET='...' \
  --from-literal=REDDIT_USER_AGENT='...' \
  --from-literal=DISCORD_BOT_TOKEN='...' \
  --from-literal=DISCORD_CHANNEL_ID='...' \
  --from-literal=SUPABASE_URL='...' \
  --from-literal=SUPABASE_SERVICE_KEY='...'
```

### 7.4 ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: reddit-watcher-config
  namespace: reddit-watcher
data:
  LLAMA_CPP_BASE_URL: "http://llamacpp-svc.homelab.svc.cluster.local:8080/v1"
  LLAMA_CPP_MODEL: "qwen2.5-14b-instruct"  # swap to change model, no redeploy needed
  LLAMA_CPP_MODEL: "qwen2.5-14b-instruct"
  MAX_POSTS_PER_SUBREDDIT: "20"
  LOG_LEVEL: "INFO"
```

---

## 8. Dependencies

| Package | Version | Purpose |
|---|---|---|
| `deepagents` | latest | Agent harness + LangGraph runtime |
| `langchain` | >=0.3 | Tool calling, LLM interface, chains |
| `langgraph` | >=0.2 | Stateful agent graph execution |
| `langchain-openai` | >=0.2 | OpenAI-compat client for llama.cpp |
| `praw` | >=7.0 | Reddit API client |
| `discord.py` | >=2.0 | Discord webhook delivery |
| `supabase` | >=2.0 | Supabase Python client |
| `pydantic` | >=2.0 | Tool input/output validation |

---

## 9. Observability

- Kubernetes job logs are the primary observability surface — `kubectl logs -n reddit-watcher <pod>`
- Each agent run logs: topics fetched, posts retrieved, classifications made, messages sent
- `rw_classifications` in Supabase is the full audit trail — query it to debug classification quality over time
- Failed runs trigger Kubernetes job retry (`restartPolicy: OnFailure`); alert on `failedJobsHistoryLimit` breach via existing Prometheus/Grafana
- LangSmith tracing is optional: set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` to trace individual agent runs

---

## 10. Implementation Phases

| Phase | Scope | Exit Criteria |
|---|---|---|
| 1 | Supabase migration + Reddit fetch tool + classification prompt | Can fetch Reddit posts and write to Supabase locally |
| 2 | Discord delivery tool + end-to-end MonitorAgent | Full pipeline runs locally via `python -m main --agent monitor` |
| 3 | Kubernetes Dockerfile + Helm chart + Secrets | Agent runs on schedule in homelab k8s cluster |
| 4 | SuggestionAgent + weekly CronJob | Weekly suggestion message delivered to Discord |
| 5 | Topic management via Supabase (no redeploy to change subreddits) | Subreddits editable via Supabase dashboard |
| 6 | Fine-tuning data export + Unsloth training pipeline | First fine-tuned GGUF classifier loaded via ConfigMap swap |

---

## 11. Open Questions

- **Free tier fallback:** If staying on Free tier, how many subreddits should rotate per run to stay within API rate limits? A round-robin scheduler in `load_active_topics` can distribute across days.
- **Fine-tuning threshold:** What confidence cutoff to use when exporting training data — `>= 0.8` is proposed; review after the first few weeks of data.
- **Discord webhook:** Use a webhook per channel or a single webhook with different mentions? Single webhook with dynamic mentions provides more flexibility.
- **DST handling:** The CronJob schedules are set for UTC-6 (Mountain Standard Time). Remember to update the schedule in spring/fall when MT shifts to UTC-7 (MDT), or use a timezone-aware scheduler add-on.
