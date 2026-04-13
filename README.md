# Reddit Watcher

A self-hosted LLM-powered agent that monitors Reddit and delivers curated digests to Discord. Built with Python 3.11+, LangChain, LangGraph, and runs on Kubernetes with local llama.cpp inference.

## Features

- **Automated Monitoring**: Fetches and classifies Reddit posts 3x daily
- **LLM Classification**: Uses local llama.cpp for relevance filtering
- **Discord Notifications**: Rich message formatting with mentions and @here for high-signal alerts
- **Weekly Suggestions**: Analyzes trends to suggest new subreddits and keywords
- **Database Storage**: All classifications stored in Supabase for future fine-tuning

## Architecture

RedditWatch consists of two LangGraph agents that share a Supabase database:

**MonitorAgent** (runs 3x/day via Kubernetes CronJob)
- Loads active topics from `rw_topics` table
- Fetches posts from Reddit using PRAW
- Classifies each post with the local LLM
- Stores results in `rw_classifications`
- Sends interesting posts to Discord

**SuggestionAgent** (runs weekly)
- Loads last 7 days of classifications from Supabase
- Analyzes patterns to find new subreddit/keyword suggestions
- Sends recommendations to Discord

```
src/
  main.py           # CLI entry: --agent monitor|suggest
  core/
    config.py       # LLM factory, env var loading
    agents/
      monitor.py    # MonitorAgent LangGraph definition
      suggestion.py # SuggestionAgent LangGraph definition
    tools/
      reddit.py     # Reddit API client (PRAW)
      discord.py    # Discord webhook integration
      supabase_tools.py # Database operations
```

## Monitored Subreddits

Topics are stored in `rw_topics` in Supabase and loaded at each run. Default subreddits:

| Subreddit | Category | Priority |
|-----------|----------|----------|
| LocalLLaMA | AI/LLM | 10 |
| MachineLearning | AI/LLM | 10 |
| ollama | AI/LLM | 9 |
| OpenSourceAI | AI/LLM | 8 |
| singularity | AI/LLM | 8 |
| artificial | AI/LLM | 7 |
| kubernetes | Infrastructure | 10 |
| devops | Infrastructure | 8 |
| selfhosted | Infrastructure | 7 |
| golang | Software Eng | 10 |
| Python | Software Eng | 9 |
| programming | Software Eng | 7 |
| startups | Startups/VC | 9 |
| YCombinator | Startups/VC | 9 |
| Physics | Physics | 8 |

To add/remove topics, update the `rw_topics` table directly in Supabase. Set `active = false` to pause a subreddit without deleting it.

## Setup

```bash
pixi install
```

## Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Description |
|----------|-------------|
| `REDDIT_CLIENT_ID` | Reddit API client ID |
| `REDDIT_CLIENT_SECRET` | Reddit API client secret |
| `REDDIT_USER_AGENT` | User agent string |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `LLAMA_CPP_BASE_URL` | llama.cpp server URL |
| `LLAMA_CPP_MODEL` | Model file name |
| `DISCORD_WEBHOOK_URL` | Discord webhook URL |
| `DISCORD_NOTIFY_USER_ID` | User ID to mention |
| `PING_THRESHOLD` | Confidence threshold for @here (default: 90) |

## Running

```bash
pixi run monitor   # Fetch + classify + Discord digest
pixi run suggest   # Weekly subreddit/suggestion analysis
```

## Kubernetes Deployment

```bash
helm install reddit-watcher charts/reddit-watcher
```

## Documentation

- [Deployment Guide](docs/deployment.md)
- [PRD & Engineering Design](docs/RedditWatch-PRD-EDD.md)
- [Architecture Decision Records](docs/adr/)
- [ROADMAP.md](ROADMAP.md)