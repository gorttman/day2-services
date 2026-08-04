# Immich

**Status:** ACTIVE (initial deployment 2026-08-04; Google Photos migration
and Cloudflare exposure still pending)
**Version:** v3.1.0 (ghcr.io/immich-app/immich-server,
ghcr.io/immich-app/immich-machine-learning)
**Namespace:** immich
**Sync Wave:** 2
**Tags:** `photos` `day2`

---

## What it does
Self-hosted photo/video library - upload, browse, smart search (CLIP),
face recognition. Built to replace Google Photos as part of the wider
Google Workspace cancellation effort (see the records/books migration
work in apps/paperless and apps/calibre-web for the same effort's other
two legs).

## How it works
- `immich-server` - API + web UI, single replica, `Recreate` strategy
- `immich-machine-learning` - CPU-only inference (no GPU in this
  cluster), separate Deployment/Service so it can be resourced/scaled
  independently of the server. Service name is load-bearing: it must be
  exactly `immich-machine-learning` because `immich-server` defaults
  `IMMICH_MACHINE_LEARNING_URL` to `http://immich-machine-learning:3003`
  and this repo relies on that default rather than setting it explicitly.
- Dedicated in-namespace Redis (`immich-redis`, no persistence) - same
  broker-only pattern as `paperless-redis`
- Database: `immich` logical DB on the shared Postgres instance (see
  apps/postgres/README.md's "pgvector, and what a shared instance
  actually costs" section) - the reason that extension exists at all
- Both `immich-server` and `immich-machine-learning` pinned to
  `k8smaster` (`nodeSelector`) - same tmpfs/RAM reasoning as every other
  heavy image in this cluster (paperless, books-pipeline)

## Storage
- `immich-library` PVC claims the static `qnap-immich` PV
  (day1-foundation/apps/qnap-storage, `/immich` export) - mounted at
  `/data` in `immich-server`. RWO, not RWX (single-replica, no
  multi-writer case, same reasoning as obsidian's vault).
- `immich-ml-cache` PVC (`nfs-client`, k8smaster local disk, 5Gi) holds
  the ML component's downloaded model weights at `/cache` - deliberately
  **not** on the QNAP: it's re-derivable cache, not real data, matching
  this repo's general rule (qnap-storage README) that only genuine
  media/library content belongs on the QNAP.

## Database setup
Seeded via `postgres-immich-db-init-job.yml` (day2-services/apps/postgres) -
same idempotent pattern as the books database's own init Job: creates
the `immich` role/database on the shared instance and runs
`CREATE EXTENSION IF NOT EXISTS vector` in it. No application tables are
pre-created here - `immich-server` runs its own migrations against that
role on startup and owns everything it creates itself.

`pgvector` (not VectorChord) was the deliberate choice - confirmed
against Immich's own source (`server/src/constants.ts`) that plain
pgvector `>=0.5 <1` is still a fully supported `VECTOR_EXTENSIONS`
option, not a deprecated one; VectorChord is Immich's newer *preferred*
default, not a hard requirement. See apps/postgres/README.md for why a
libc/collation-safe pgvector build was the right call for a shared
instance with 5 other databases on it, and the regression test run
immediately after that image swap.

## Machine learning - performance expectations (2026-08-04)
CPU-only inference on Pi-class ARM hardware. Expect the first
smart-search/face-recognition backfill over an existing library to be
genuinely slow - this is a real hardware constraint, not a
misconfiguration. `immich-machine-learning` resource limits (3Gi
memory / 3 CPU) are sized to fit alongside everything else already
running on `k8smaster`, not for throughput. Revisit if backfill time
turns out to be a real problem in practice (e.g. disabling face
recognition specifically, or accepting slower CLIP search) rather than
pre-tuning speculatively here.

## Deliberately unconfigured (separate pass)
- No Cloudflare Tunnel exposure yet (internal-only ingress for now,
  same posture Paperless started with)
- No admin bootstrap - Immich's first real difference from Paperless:
  the first account created via the web UI's own signup flow becomes
  the admin, no `IMMICH_ADMIN_PASSWORD`-style env var to seed
- No external-library configuration (mounting an existing photo tree
  read-only) - out of scope for this initial deployment; the actual
  Google Photos migration (downloading and importing content) is a
  separate, not-yet-started piece of work
- Storage template / library structure defaults untouched

## Access
- https://immich.i3sec.com.au - DNS entry live in `dns-conf` (pihole +
  coredns), 192.168.2.241
- No seeded admin account - sign up via the web UI on first visit

## Secrets
`immich-secret` (sealed, immich namespace): `DB_PASSWORD`. Same value
also sealed into the postgres namespace
(`postgres-superuser.IMMICH_DB_PASSWORD`) for the DB init Job, matching
every other app on the shared instance.
