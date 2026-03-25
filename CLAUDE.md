# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**RedditWatch** — a self-hosted LLM-powered agent that monitors Reddit and delivers curated digests to Discord. Built with Python 3.11+, LangChain, LangGraph, and the Deep Agents SDK. Runs on a Kubernetes homelab with a local llama.cpp inference server.

## Local Docker testing

```bash
make monitor   # builds image + runs monitor agent (op injects secrets)
make suggest   # builds image + runs suggestion agent
make push      # pushes to Zot OCI registry (IMAGE=zot.local/redditwatch:latest)
```

Docker image is built with `local-packages/middleware_py-*.whl` vendored in. Rebuild the wheel after middleware-py changes: `pixi run build-wheel`.

## Setup

```bash
pixi install       # creates .pixi/envs/default and installs all deps; also generates pixi.lock
```

Commit `pixi.lock` to version control after the first install.

## Secrets

Secrets are stored in 1Password (vault: `pedro`) and referenced via `op://` in `.env`. The `.env` file contains no real values and is safe to commit.

Local dev — `op run` is wired into every pixi task automatically:
```bash
pixi run monitor   # expands to: op run --env-file=.env -- python -m main --agent monitor
pixi run suggest
pixi run export
```

K8s — secrets are loaded from **OpenBao** at deploy time.

## Running

```bash
pixi run monitor   # post fetch + classify + Discord digest
pixi run suggest   # weekly subreddit/keyword suggestions
pixi run export    # export fine-tuning JSONL (see scripts/export_training_data.py)
```

Tasks are defined in `[tool.pixi.tasks]` in `pyproject.toml`.

## Architecture

Two LangGraph agents share one Python package and one Supabase schema:

- **MonitorAgent** — runs 3x/day via K8s CronJob: loads topics from Supabase → fetches posts (PRAW) → classifies with local LLM → stores all results → sends interesting posts to Discord
- **SuggestionAgent** — runs Monday 09:00 MT: loads last 7 days of INTERESTING classifications → LLM analyzes patterns → sends subreddit/keyword suggestions to Discord

All LLM calls go to a local llama.cpp server via `langchain-openai` (OpenAI-compatible API). Model and endpoint are env vars — no code changes needed to swap models.

### Key directories (target structure)

```
src/
  agents/     # monitor.py, suggestion.py — LangGraph graph definitions
  tools/      # reddit.py, supabase.py, discord.py — LangChain tool functions
  config.py   # get_llm() factory, env var loading
  main.py     # CLI entrypoint: --agent monitor|suggest
k8s/          # CronJob manifests, ConfigMap, Secret template
migrations/   # 001_redditwatch.sql — rw_topics and rw_classifications tables
```

### Supabase tables

- `rw_topics` — editable list of subreddit queries; active topics loaded at each run
- `rw_classifications` — every classified post with LLM reasoning, confidence, and raw JSON

### Environment variables

Secrets (via OpenBao → K8s): `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`, `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `DISCORD_NOTIFY_USER_ID`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`

Config (via K8s ConfigMap): `LLAMA_CPP_BASE_URL`, `LLAMA_CPP_MODEL`, `MAX_POSTS_PER_SUBREDDIT`, `LOG_LEVEL`

## Key constraints

- Python 3.11+ required (`deepagents` does not support <3.11).
- All LLM inference stays on-homelab; only Reddit API and Discord calls leave the network.
- Classification JSON output from the LLM must include `classification`, `confidence`, `reason`, and `summary` fields.