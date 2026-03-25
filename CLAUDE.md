# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**TweetWatch** — a self-hosted LLM-powered agent that monitors Twitter/X and delivers curated digests to WhatsApp. Built with Python 3.9, LangChain, LangGraph, and the Deep Agents SDK. Runs on a Kubernetes homelab with a local llama.cpp inference server. Full PRD and engineering design doc at `docs/TweetWatch-PRD-EDD.md`.

## Local Docker testing

```bash
make monitor   # builds image + runs monitor agent (op injects secrets)
make suggest   # builds image + runs suggestion agent
make push      # pushes to Zot OCI registry (IMAGE=zot.local/tweetwatch:latest)
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

K8s — secrets are loaded from **OpenBao** at deploy time (not `kubectl create secret`).

## Running

```bash
pixi run monitor   # tweet fetch + classify + WhatsApp digest
pixi run suggest   # weekly hashtag/account suggestions
pixi run export    # export fine-tuning JSONL (see scripts/export_training_data.py)
```

Tasks are defined in `[tool.pixi.tasks]` in `pyproject.toml`.

## Architecture

Two LangGraph agents share one Python package and one Supabase schema:

- **MonitorAgent** — runs 3x/day via K8s CronJob: loads topics from Supabase → fetches tweets (Tweepy) → classifies with local LLM → stores all results → sends interesting tweets to WhatsApp (Twilio)
- **SuggestionAgent** — runs Monday 09:00 MT: loads last 7 days of INTERESTING classifications → LLM analyzes patterns → sends hashtag/account suggestions to WhatsApp

All LLM calls go to a local llama.cpp server via `langchain-openai` (OpenAI-compatible API). Model and endpoint are env vars — no code changes needed to swap models.

### Key directories (target structure)

```
src/
  agents/     # monitor.py, suggestion.py — LangGraph graph definitions
  tools/      # twitter.py, supabase.py, whatsapp.py — LangChain tool functions
  config.py   # get_llm() factory, env var loading
  main.py     # CLI entrypoint: --agent monitor|suggest
k8s/          # CronJob manifests, ConfigMap, Secret template
migrations/   # 001_tweetwatch.sql — tw_topics and tw_classifications tables
docs/         # TweetWatch-PRD-EDD.md
```

### Supabase tables

- `tw_topics` — editable list of hashtag queries; active topics loaded at each run
- `tw_classifications` — every classified tweet with LLM reasoning, confidence, and raw JSON (future fine-tuning dataset)

### Environment variables

Secrets (via OpenBao → K8s): `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_BEARER_TOKEN`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `TWILIO_TO_NUMBER`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`

Config (via K8s ConfigMap): `LLAMA_CPP_BASE_URL`, `LLAMA_CPP_MODEL`, `TWITTER_API_TIER`, `MAX_TWEETS_PER_QUERY`, `LOG_LEVEL`

## Key constraints

- Python 3.11+ required (`deepagents` does not support <3.11).
- Twitter/X Free tier is severely limited (1 query, 10 tweets/response). Basic tier ($100/mo) is required for full multi-topic polling.
- All LLM inference stays on-homelab; only Twitter API and Twilio calls leave the network.
- Classification JSON output from the LLM must include `classification`, `confidence`, `reason`, and `summary` fields — this is the fine-tuning dataset schema.
