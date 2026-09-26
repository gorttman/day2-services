# Open WebUI

**Status:** LIVE, Stage 0 spike (AI platform build plan). Namespace `open-webui`,
ArgoCD app `open-webui` (auto-sync). Image `0.11.4-slim` pinned by digest.

## What it does
Chat front end for the AI platform: the daily-driver hub in ADR-2. For now it talks
straight to Anthropic (Haiku 4.5 only). In build-plan Stage 1 it moves behind LiteLLM.

## How it runs
- Single replica (the Stage 3 session-memory sweep runs inside it and would
  duplicate across replicas). Prefers the `applications` node, free to run on either.
- Chat database: shared Postgres, database and role `openwebui`, created by the
  idempotent Job `postgres-openwebui-db-init` in `apps/postgres`.
- Data dir `/app/backend/data`: 2Gi Longhorn PVC (uploads, local vector store, spike log).
  Never NFS: the vector store is SQLite.
- Sign-up is off. The admin (`gorttman@i3sec.com.au`) is created headlessly on first
  start from `WEBUI_ADMIN_EMAIL`/`WEBUI_ADMIN_PASSWORD`. Native memory is off (ADR-11).
- Model access is set by env on first start only. Open WebUI keeps the values in its
  database afterwards (`ENABLE_PERSISTENT_CONFIG`), so later changes are made in
  Admin Settings, or by resetting the database.

## Access
- LAN: https://open-webui.i3sec.com.au (Traefik ingress, Let's Encrypt cert; Pi-hole
  and CoreDNS resolve it in `dns-conf`).
- Off-LAN: `open-webui.i3sec.com.au` in `tunneled_hostnames` (`day1-foundation`
  cloudflare-tf). Origin is the ClusterIP Service. Behind the zone-wide mTLS rule:
  without an allow-listed device certificate Cloudflare answers 403 (verified 2026-09-27).

## Secrets (SealedSecrets)
- `openwebui-anthropic`: `ANTHROPIC_API_KEY`. Anthropic API is billed separately from
  a Claude subscription. Use a key dedicated to this app with a small spend limit.
- `openwebui-app`: `DATABASE_URL`, `WEBUI_SECRET_KEY`, `WEBUI_ADMIN_PASSWORD`.
- `postgres/postgres-superuser` key `OPENWEBUI_DB_PASSWORD` (used by the init Job).
Rotate a key by re-sealing it (kubeseal flags in `day0-infra-build/scripts/seal_secret.sh`).

## Stage 0 spike findings (verified live on 0.11.4, 2026-09-27)
A throwaway Event function `event_spike` logs every event to
`/app/backend/data/event_spike.jsonl`. Delete it (Admin > Functions) when the spike ends.

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

**The four ADR-11 questions.**
1. `chat.finished` fires for a completion that carries a `chat_id`, including one
   sent straight to `/api/chat/completions` (`source: api`). It does NOT fire for a
   bare completion with no `chat_id`. Its `data` has `chat_id`, `message_id`,
   `model_id`, `title`, `url`, `user_id`, `message` (the final reply text).
   An API completion with a `chat_id` returns `{status, task_ids, chat_id}` at once
   and runs as a background task.
2. `chat.updated_at` is bumped by: creating the chat, any write of the chat object
   (`POST /api/v1/chats/{id}`, so rename and regenerate), a completion against the
   chat, pin and unpin. It is NOT bumped by adding a tag, nor by the title-generation
   task call. Whether the UI's follow-up write of a generated title bumps it needs the
   browser test (that write is an ordinary chat update, so expect yes).
3. Units: `chat.created_at`, `chat.updated_at`, `chat_message.created_at`,
   `chat_message.updated_at` and the event `created_at` are all bigint seconds
   (10 digits), not nanoseconds.
4. `chat.current_message_id` exists as a column and equals the chat JSON's
   `history.currentId`. `chat_message.id` is `<chat_id>_<message_id>` and `parent_id`
   links the tree. Walking `current_message_id` back through `parent_id` gave the
   expected branch after an API-emulated regeneration. Confirming that a real UI
   regeneration behaves the same is the manual browser check.

**Caveat for the Stage 3 distiller.** After an API completion against a chat, the
assistant `chat_message` row stayed `content: ""`, `done: false`; the reply text
was only in the `chat.finished` event. The UI writes message content itself, so
UI chats should be fine (to confirm), but do not assume `chat_message.content` is
filled for API-driven chats: use `chat.finished.data.message` or the chat JSON.

## Notes
- The model list also shows Open WebUI's built-in "arena-model" placeholder. It only
  routes among enabled models, so with Haiku as the sole model it cannot reach another.
- Upgrade: re-test on every upgrade. Plugin internals change between releases.
