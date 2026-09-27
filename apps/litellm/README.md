# LiteLLM

**Status:** LIVE, build-plan Stage 1 phase 1 (Anthropic direct). Namespace `litellm`,
ArgoCD app `litellm` (auto-sync). Image `v1.102.1` pinned by digest.

## What it does
The single gateway every model caller goes through (ADR-3): Open WebUI today; n8n,
agents and the route-validation job later. It routes by `config.yaml`, enforces
per-key allowed models and budgets, tracks spend, and exports Prometheus metrics that
Telegraf writes to InfluxDB bucket `ai_metrics` (AI Platform dashboard).

## Config is code
- `config.yaml`: the model list, prices, retries and metrics settings. Models come
  from this file only (`store_model_in_db: false`); nothing is configured in the admin UI.
- The ConfigMap is generated with a content hash in its name, so editing `config.yaml`
  rolls the pod (LiteLLM reads its config only at start).
- `litellm-keys-job.yml`: a PostSync Job that creates or updates the virtual keys and
  their policy (allowed models, budget) on every sync. Key values are sealed secrets;
  policy is in git. Open WebUI's key: Haiku only, $5 per 30 days.

## Routes
| Name | Goes to | Price per M tokens (in / out) |
|---|---|---|
| `claude-haiku-4-5` | Anthropic direct, `claude-haiku-4-5-20251001` | $1 / $5 |
| `claude-sonnet-5` | Anthropic direct | $2 / $10 |
| `claude-opus-5` | Anthropic direct | $5 / $25 |

Prices are written into `config.yaml` (`input_cost_per_token`, `output_cost_per_token`)
because LiteLLM's built-in price list may lack new models, which would make spend read 0.

## Secrets (SealedSecrets, namespace `litellm`)
- `litellm-app`: `LITELLM_MASTER_KEY`, `LITELLM_SALT_KEY` (encrypts stored credentials:
  set once, never change), `DATABASE_URL`, `OPEN_WEBUI_VIRTUAL_KEY` (the value the keys
  Job registers; the same value is sealed for Open WebUI in `apps/open-webui`).
- `litellm-anthropic`: `ANTHROPIC_API_KEY`. The Anthropic API is billed separately from
  a Claude subscription. Only LiteLLM holds this key.
- Database `litellm` on the shared Postgres, created by `postgres-litellm-db-init`.

## Contracts
- Service `litellm.litellm:4000` is scraped by `apps/telegraf` (`conf/ai.conf`) with no
  key: `require_auth_for_metrics_endpoint: false`, safe because the Service is ClusterIP.
- Callers use `http://litellm.litellm.svc.cluster.local:4000/v1` with a virtual key.

## Adding OpenRouter routes (phase 2)
The plan wants three OpenRouter keys: `trusted` (generous), `showcase` (small, weekly
reset, free and experimental models) and `frontier` (dedicated, rare and expensive).
1. Seal each key into a `litellm-openrouter` secret (keys `OPENROUTER_TRUSTED_KEY`,
   `OPENROUTER_SHOWCASE_KEY`, `OPENROUTER_FRONTIER_KEY`) and add it to `kustomization.yml`.
2. Add the three env vars to the Deployment from that secret.
3. Add `model_list` entries with `model: openrouter/<provider>/<model>`, the matching
   `api_key: os.environ/...`, and prices from OpenRouter's model list.
4. Add a fallback so `claude-haiku-4-5` can fail over to the trusted OpenRouter route.
Do not add OpenRouter entries before the secret exists: LiteLLM resolves
`os.environ/...` at start and a missing variable can stop the proxy starting.

## Gotchas
- Do not use the `-stable` tags on this cluster: `v1.83.14-stable`'s arm64 image is
  mislabelled (even `/bin/sh` fails with `exec format error`). Reproduced by running the
  image locally. Verify an arm64 image runs (`docker run --rm --entrypoint /bin/sh IMAGE -c
  'uname -m'`) before pinning a new tag.
- LiteLLM reports `+Inf` remaining budget for keys and users with no budget. InfluxDB
  cannot store infinity; `apps/telegraf` drops those values.
- Counter panels need traffic across more than one scrape: the first requests after a
  series appears leave no visible increase, so a panel can look empty right after start.
- Ollama (local inference) is deferred until there is GPU or large-RAM hardware; there is
  no route for it here.
