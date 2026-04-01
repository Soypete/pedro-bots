# Deployment Guide

RedditWatch runs as two Kubernetes CronJobs on the homelab cluster. This guide covers building, pushing, and deploying.

## Prerequisites

- Podman installed and running (`podman machine start` if on Mac)
- `kubectl` configured against the homelab cluster
- `helm` installed
- Access to the Zot registry at `100.81.89.62:5000` (Tailscale required)
- OpenBao/Vault with secrets at `secret/data/apps/{redditwatch,discord,supabase}`

## Vault Secrets

The following keys must exist in Vault before deploying:

| Path | Keys |
|------|------|
| `secret/data/apps/redditwatch` | `reddit_client_id`, `reddit_client_secret`, `reddit_user_agent` |
| `secret/data/apps/discord` | `client_secret` (bot token), `permission` (channel ID), `public_key` (notify user ID) |
| `secret/data/apps/supabase` | `url`, `private_key`, `postgres_url` |

## Build and Push

The image must be built for `linux/amd64` — the cluster nodes are all x86_64, even when building from an Apple Silicon Mac.

```bash
# Start Podman if not running (Mac only)
podman machine start

# Make sure podman-machine-default is the active connection (not soypete)
podman system connection default podman-machine-default

# Build for amd64 and push to Zot
podman build --platform linux/amd64 -t 100.81.89.62:5000/redditwatch:latest .
podman push 100.81.89.62:5000/redditwatch:latest
```

Or use the Makefile (which includes the platform flag):

```bash
make push   # runs build + push
```

> The `middleware-py` wheel in `local-packages/` is vendored in. Rebuild it only if
> `pedro-agentware/middleware_py` changes: `pixi run build-wheel` (requires Python 3.13).

## Deploy to Kubernetes

```bash
helm upgrade --install redditwatch charts/reddit-watcher -n agents
```

The chart creates:
- `ConfigMap` — LLM endpoint, model name, log level
- `CronJob` (monitor) — runs at 08:00, 13:00, 18:00 MT
- `CronJob` (suggest) — runs Monday 09:00 MT

## Trigger a Manual Run

```bash
kubectl create job --from=cronjob/redditwatch-reddit-watcher-monitor redditwatch-manual -n agents
kubectl logs -n agents -l job-name=redditwatch-manual -f
```

Clean up after testing:

```bash
kubectl delete job redditwatch-manual -n agents
```

## Troubleshooting

### ImagePullBackOff

Check the pod events:
```bash
kubectl describe pod <pod-name> -n agents | grep -A5 Events
```

Common causes:
- **`registry.local` DNS failure** — old image reference; ensure `values.yaml` uses `100.81.89.62:5000/redditwatch`
- **`exec format error`** — image built for wrong arch; rebuild with `--platform linux/amd64`
- **Podman not running** — run `podman machine start` and `podman system connection default podman-machine-default`

### Missing env vars / KeyError

Secrets are injected by the Vault agent sidecar into `/vault/secrets/`. The container entrypoint sources these files before starting Python. If a secret key is missing from Vault, the process will crash with a `KeyError`.

Verify Vault secrets are populated:
```bash
vault kv get secret/apps/supabase
vault kv get secret/apps/redditwatch
vault kv get secret/apps/discord
```

### Check recent job logs

```bash
kubectl logs -n agents -l app=monitor --tail=100
```
