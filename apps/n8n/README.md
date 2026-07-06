# n8n

Self-hosted workflow automation at `https://n8n.i3sec.com.au`
(internal-only, private-ca cert, DNS in dns-conf).

## Architecture

- **Workflows/credentials/executions → shared Postgres** (`n8n` DB in
  the `postgres` namespace instance, same as paperless/homeassistant).
  `DB_TYPE=postgresdb` is set explicitly - n8n defaults to SQLite, and
  getting this wrong is the most common cause of a silent fallback.
- **`/home/node/.n8n` on a plain nfs-client PVC**: with an external
  Postgres backend this directory only holds the encryption key file,
  local settings cache, and (if ever enabled) filesystem-mode binary
  data - low write volume, no locking concerns, so it doesn't need the
  RAM+backup trick used for SQLite apps (pihole/kavita/grafana/HA).
- **`N8N_ENCRYPTION_KEY` is fixed and sealed** (`openssl rand -hex 32`,
  generated once). This key encrypts credentials at rest in Postgres -
  if it's ever regenerated, all stored credentials become undecryptable
  and every credential in the UI needs re-entering. Never rotate it
  casually.
- **Soft affinity to lane=infrastructure**: the n8n image (~360MB
  compressed, likely 700MB+ extracted - it bundles every integration
  node) doesn't reliably fit pinode-01's 4G tmpfs image store, same
  reasoning as grafana/homeassistant.
- **`N8N_PROXY_HOPS=1`**: trusts one layer of X-Forwarded-* headers
  (traefik) so n8n sees the real client IP/protocol instead of the
  proxy's.

## First-run setup (manual, once)

1. Browse to https://n8n.i3sec.com.au → owner account setup (email,
   name, password) on first visit.
2. Add credentials for any service a workflow needs to call - these are
   entered and encrypted via the UI, never stored in git.
3. Webhook-triggered workflows are reachable at
   `https://n8n.i3sec.com.au/webhook/...` since `WEBHOOK_URL` is set to
   the public hostname.

## Notes

- Image pinned at `n8nio/n8n:2.29.6` on Docker Hub (verified present
  and multi-arch, including arm64, via the registry API directly).
- Install-only: no workflows are pre-built. Bring your own automations.
