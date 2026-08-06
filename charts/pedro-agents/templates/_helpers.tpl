{{/*
Expand the name of the chart.
*/}}
{{- define "reddit-watcher.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "reddit-watcher.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "reddit-watcher.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "reddit-watcher.labels" -}}
helm.sh/chart: {{ include "reddit-watcher.chart" . }}
{{ include "reddit-watcher.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "reddit-watcher.selectorLabels" -}}
app.kubernetes.io/name: {{ include "reddit-watcher.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
{{/*
Vault agent-injection annotations. Rendered only when .Values.vault.enabled is true;
otherwise secrets come from the existing Kubernetes Secret (see "reddit-watcher.envFrom").
*/}}
{{- define "reddit-watcher.vaultAnnotations" -}}
vault.hashicorp.com/agent-inject: "true"
vault.hashicorp.com/agent-pre-populate-only: "true"
vault.hashicorp.com/role: {{ .Values.vault.role | quote }}
vault.hashicorp.com/agent-inject-secret-reddit: {{ .Values.vault.redditPath | quote }}
vault.hashicorp.com/agent-inject-secret-discord: {{ .Values.vault.discordPath | quote }}
vault.hashicorp.com/agent-inject-secret-supabase: {{ .Values.vault.supabasePath | quote }}
vault.hashicorp.com/agent-inject-template-reddit: |
  {{`{{- with secret "`}}{{ .Values.vault.redditPath }}{{`" -}}`}}
  {{`export REDDIT_CLIENT_ID="{{ .Data.data.reddit_client_id }}"`}}
  {{`export REDDIT_CLIENT_SECRET="{{ .Data.data.reddit_client_secret }}"`}}
  {{`export REDDIT_USER_AGENT="{{ .Data.data.reddit_user_agent }}"`}}
  {{`{{- end }}`}}
vault.hashicorp.com/agent-inject-template-discord: |
  {{`{{- with secret "`}}{{ .Values.vault.discordPath }}{{`" -}}`}}
  {{`export DISCORD_BOT_TOKEN="{{ .Data.data.client_secret }}"`}}
  {{`export DISCORD_CHANNEL_ID="{{ .Data.data.permission }}"`}}
  {{`export DISCORD_NOTIFY_USER_ID="{{ .Data.data.public_key }}"`}}
  {{`{{- end }}`}}
vault.hashicorp.com/agent-inject-template-supabase: |
  {{`{{- with secret "`}}{{ .Values.vault.supabasePath }}{{`" -}}`}}
  {{`export SUPABASE_URL="{{ .Data.data.url }}"`}}
  {{`export SUPABASE_SERVICE_KEY="{{ .Data.data.private_key }}"`}}
  {{`export POSTGRES_URL="{{ .Data.data.postgres_url }}"`}}
  {{`{{- end }}`}}
{{- end }}

{{/*
Container envFrom: always the chart ConfigMap, plus the existing Secret when Vault is off.
*/}}
{{- define "reddit-watcher.envFrom" -}}
- configMapRef:
    name: {{ include "reddit-watcher.fullname" . }}-config
{{- if not .Values.vault.enabled }}
- secretRef:
    name: {{ .Values.existingSecret }}
{{- end }}
{{- end }}

{{/*
Container command/args for an agent. With Vault the secrets land as files that must be
sourced, so the entrypoint is wrapped in a shell; otherwise the agent runs directly.
*/}}
{{- define "reddit-watcher.agentArgs" -}}
{{- $agent := .agent -}}
{{- $root := .root -}}
{{- if $root.Values.vault.enabled }}
command: ["/bin/sh", "-c"]
args: [". /vault/secrets/reddit && . /vault/secrets/discord && . /vault/secrets/supabase && python -m main agent --agent {{ $agent }}"]
{{- else }}
args: ["agent", "--agent", "{{ $agent }}"]
{{- end }}
{{- end }}
