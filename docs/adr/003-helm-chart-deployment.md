# ADR 003: Helm Chart for Kubernetes Deployment

## Status
Accepted

## Date
2026-03-25

## Context
The original TweetWatch deployment used raw Kubernetes YAML manifests. For better manageability, we need a Helm chart that:
- Provides configurable values for schedules, image, and secrets
- Supports both monitor and suggestion CronJobs from a single chart
- Integrates with existing ConfigMap and Secret patterns

## Decision
Create a Helm chart at `charts/reddit-watcher/` with:
- `values.yaml` for configurable schedules, image, and Discord settings
- Templates for both monitor and suggestion CronJobs
- Integration with external secrets via `secretRef`

## Consequences
- **Positive**: Single command deployment with `helm install`
- **Positive**: Environment-specific configuration via values
- **Negative**: Additional chart maintenance
- **Negative**: Requires Helm to be installed in CI/CD

## Values Structure
```yaml
image:
  repository: registry.local/reddit-watcher
  tag: latest
  pullPolicy: IfNotPresent

monitor:
  schedule: "0 8,13,18 * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 5

suggestion:
  schedule: "0 15 * * 1"  # Monday 09:00 MT
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 5

config:
  llamaCppBaseUrl: "http://llama-cpp:8080"
  llamaCppModel: "models/nemotron-3-super-120b.Q4_K_M.gguf"
  logLevel: "INFO"

discord:
  webhookUrl: ""      # Set via secrets
  notifyUserId: ""    # Set via secrets
  pingThreshold: 90   # Confidence threshold for @here
```