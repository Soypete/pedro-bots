# Reddit Watcher

A self-hosted LLM-powered agent that monitors Reddit and delivers curated digests to Discord. Built with Python 3.11+, LangChain, LangGraph, and runs on Kubernetes with local llama.cpp inference.

## Features

- **Automated Monitoring**: Fetches and classifies Reddit posts 3x daily
- **LLM Classification**: Uses local llama.cpp for relevance filtering
- **Discord Notifications**: Rich message formatting with mentions and @here for high-signal alerts
- **Weekly Suggestions**: Analyzes trends to suggest new subreddits and keywords
- **Database Storage**: All classifications stored in Supabase for future fine-tuning

## Architecture

```
src/
  main.py           # CLI entry: --agent monitor|suggest
  core/
    config.py       # LLM factory, env var loading
    agents/
      monitor.py    # Reddit fetch + classify agent
      suggestion.py # Weekly suggestions agent
    tools/
      reddit.py     # Reddit API client
      discord.py    # Discord webhook integration
      supabase_tools.py # Database operations
```

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

- [PRD & Engineering Design](docs/TweetWatch-PRD-EDD.md)
- [Architecture Decision Records](docs/adr/)
- [ROADMAP.md](ROADMAP.md)