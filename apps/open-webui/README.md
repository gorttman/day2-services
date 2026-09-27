# Open WebUI

**Status:** LIVE, Stage 0 spike (AI platform build plan). Namespace `open-webui`,
ArgoCD app `open-webui` (auto-sync). Image `0.11.4-slim` pinned by digest.

## What it does
Chat front end for the AI platform: the daily-driver hub in ADR-2. It talks to LiteLLM
(`apps/litellm`, ADR-3) with its own virtual key: Haiku 4.5 only, $5 per 30 days.
The model list, budget and allowed models are set in git (`apps/litellm`).

## How it runs
- Single replica (the Stage 3 session-memory sweep runs inside it and would
  duplicate across replicas). Prefers the `applications` node, free to run on either.
- Chat database: shared Postgres, database and role `openwebui`, created by the
  idempotent Job `postgres-openwebui-db-init` in `apps/postgres`.
- Data dir `/app/backend/data`: 2Gi Longhorn PVC (uploads, local vector store, spike log).
  Never NFS: the vector store is SQLite.
- Sign-up is off. The admin (`gorttman@i3sec.com.au`) is created headlessly on first
  start from `WEBUI_ADMIN_EMAIL`/`WEBUI_ADMIN_PASSWORD`. Native memory is off (ADR-11).
- Config is code: `ENABLE_PERSISTENT_CONFIG=False`, so the Deployment's environment
  is applied on every start and settings changed in the admin UI are discarded at the
  next restart. Change settings in git.

## Access
- LAN: https://open-webui.i3sec.com.au (Traefik ingress, Let's Encrypt cert; Pi-hole
  and CoreDNS resolve it in `dns-conf`).
- Off-LAN: `open-webui.i3sec.com.au` in `tunneled_hostnames` (`day1-foundation`
  cloudflare-tf). Origin is the ClusterIP Service. Behind the zone-wide mTLS rule:
  without an allow-listed device certificate Cloudflare answers 403 (verified 2026-09-27).

## Secrets (SealedSecrets)
- `openwebui-litellm`: `LITELLM_API_KEY`, the LiteLLM virtual key for this app. The
  Anthropic key now lives only in the `litellm` namespace.
- `openwebui-app`: `DATABASE_URL`, `WEBUI_SECRET_KEY`, `WEBUI_ADMIN_PASSWORD`.
- `postgres/postgres-superuser` key `OPENWEBUI_DB_PASSWORD` (used by the init Job).
Rotate a key by re-sealing it (kubeseal flags in `day0-infra-build/scripts/seal_secret.sh`).

## Stage 0 spike findings (verified live on 0.11.4, 2026-09-27)
A throwaway Event function `event_spike` logged every event during the spike and has
been deleted. The log of 34 lines is kept at `/app/backend/data/event_spike.jsonl`
on the data volume for reference.

**Event function contract (differs from the docs).** The docs show
`async def event(self, body)`. The dispatcher (`open_webui/events.py`,
`dispatch_event_functions`) calls the handler with keyword arguments matched by
name: `event` (the payload dict), `__event_name__`, `__event_id__`, `__event__`,
`__id__`, `__app__`, `__request__`. A `body` parameter fails with "missing 1 required
positional argument". Use `async def event(self, event=None, __event_name__=None, **kwargs)`.

**Payload shape.** Top-level keys: `actor`, `created_at` (seconds), `data`, `event`,
`id`, `instance_id`, `message`, `operation`, `resource`, `schema`, `source`
(`api` for API-originated calls), `subject` (`{type, id}`), `version`.

**Events that exist (source of truth is `events.py`):** `system.startup.*`,
`system.shutdown.*`, `config.*`, `auth.*`, `user.*`, `group.*`, `chat.created`,
`chat.finished`, `chat.failed`, `chat.updated`, `chat.pinned`, `chat.unpinned`,
`chat.tag_added`, `chat.tag_removed`, `chat.archived`, `chat.deleted`,
`chat.folder_updated`, `chat.cloned`, `chat.compacted`, `message.created`,
`message.updated`, `message.deleted`, `function.*`.

**The four ADR-11 questions (API tests plus real browser clicks, 2026-09-27).**
1. `chat.finished` fires for every completed reply, whether from the browser or a
   direct call to `/api/chat/completions`, as long as it carries a `chat_id`. It does
   NOT fire for a bare completion with no `chat_id`. Both report `source: api` (the
   browser uses the same API). `data`: `chat_id`, `message_id`, `model_id`, `title`,
   `url`, `user_id`, `message` (the final reply text). It also fires on every
   regeneration, with the new `message_id`.
2. `chat.updated_at` moves on: chat creation, a reply finishing, pin and unpin, and any
   write through `POST /api/v1/chats/{id}`. It does NOT move on: adding a tag, the
   title-task call, or the **UI's rename** (a rename clicked in the browser fired
   `chat.updated` with the new title but left `updated_at` unchanged). Do not use
   `updated_at` to detect renames or to detect inactivity: use
   `max(chat_message.created_at)` (as ADR-11 already says) and the events. The
   auto-generated title arrives in `chat.finished.data.title`, with no `chat.updated`.
3. Units: `chat.created_at`, `chat.updated_at`, `chat_message.created_at`,
   `chat_message.updated_at` and the event `created_at` are all bigint seconds
   (10 digits), not nanoseconds.
4. Tree: `chat.current_message_id` is a column and matches the chat JSON's
   `history.currentId`. `chat_message.id` is `<chat_id>-<message_id>`, `parent_id` links
   the tree. A real "Try Again" on the FIRST reply created a sibling assistant message
   under the same user message and switched `current_message_id` to it; the later
   exchange stayed in the table on a side branch. Walking `current_message_id` back
   through `parent_id` reproduced the visible branch exactly.

**Regeneration event sequence.** A regenerate re-emits `message.created` for the
EXISTING user message (same id as before), then `message.created` for the new
assistant message, then `chat.finished`. Consumers must de-duplicate `message.created`
by message id.

**Stage 3 distiller notes.**
- Chats driven from the browser store the full reply in `chat_message.content` with
  `done: true`. A chat driven only through the API (a completion sent with a `chat_id`
  but not saved by a client) can leave the assistant row `content: ""`, `done: false`,
  with the reply only in the `chat.finished` event. Prefer `chat.finished.data.message`
  for the latest reply if the row is empty.
- Only the current branch matters for the transcript; other branches stay in the table.

## Notes
- The model list also shows Open WebUI's built-in "arena-model" placeholder. It only
  routes among enabled models, so with Haiku as the sole model it cannot reach another.
- Upgrade: re-test on every upgrade. Plugin internals change between releases.
