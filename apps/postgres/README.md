# Postgres (shared instance)

**Status:** ACTIVE
**Version:** 16.9 (postgres:16.9-alpine)
**Namespace:** postgres
**Sync Wave:** 0 (namespace only)
**Tags:** `database` `infra` `shared`

---

## What it does
Single shared PostgreSQL instance for cluster apps. This is the **default
route** for any app that needs Postgres: it gets its own logical database
and its own login role on this instance. Only stand up a dedicated Postgres
if an app needs extensions or tuning this shared instance can't provide
(the exception path).

## How it works
One-replica StatefulSet, 5Gi PVC on `nfs-client` (Retain). App databases
are created by `/docker-entrypoint-initdb.d` scripts from the
`postgres-initdb` ConfigMap — these run **only on first init** of an empty
data volume.

## Adding a database for a new app

Two ways, depending on how much automation you want:

**Manual (original approach, still valid)**:
1. Generate a password; seal it twice (SealedSecrets are namespace-scoped):
   once into this namespace (added as an env var on the StatefulSet for the
   init script) and once into the app's own namespace for its client config.
2. On the running instance (init scripts won't re-run):
   `kubectl exec -n postgres postgres-0 -- psql -U postgres -c "CREATE ROLE <app> LOGIN PASSWORD '...'; CREATE DATABASE <app> OWNER <app>;"`
3. Add the same statements to `postgres-init-cm.yml` so a from-scratch
   rebuild recreates them.

**Automated (introduced 2026-07-17 for `books`, see
`postgres-books-db-init-job.yml`)**: a one-time `Job` whose script does
steps 2-3's work idempotently (`IF NOT EXISTS` checks for the role/database,
`CREATE EXTENSION IF NOT EXISTS`/`CREATE TABLE IF NOT EXISTS` for anything
schema-specific), reading its password from the same sealed secret. Applies
via the normal Argo CD sync - no `kubectl exec`, no hand-typed SQL. The one
manual step left is generating and sealing the password (step 1 above is
unavoidable either way). If the Job ever needs re-running for real (e.g.
after a full from-scratch rebuild), `kubectl delete job <name> -n postgres`
and let Argo CD recreate it - Jobs are immutable once created, so Argo CD
won't re-trigger a completed one on its own. Recommended over the manual
route for any new database going forward.

## Access
`postgres.postgres.svc.cluster.local:5432` — cluster-internal only, no
ingress. Superuser password in the `postgres-superuser` sealed secret.

## Current databases
| database      | owner         | used by                                  |
|----------------|---------------|-------------------------------------------|
| paperless      | paperless     | apps/paperless (day2)                     |
| cloudflare_tf  | cloudflare_tf | day1-foundation apps/cloudflare-tf (Terraform state, `pg` backend) |
| books          | books         | apps/books-pipeline (day2) - `fingerprints` table + `pg_trgm`, provisioned via the automated Job above |
