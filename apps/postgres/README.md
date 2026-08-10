# Postgres (shared instance)

**Status:** ACTIVE
**Version:** 16.9, pgvector 0.8.6 (ghcr.io/gorttman/postgres-pgvector:1.0.0,
see images/postgres-pgvector - built 2026-08-04 for apps/immich)
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

## Backups (added 2026-08-07)

**Before this, there was none.** The instance's only durability was its
single `nfs-client` PVC, itself backed by a single hostPath export on
k8smaster's own disk (see `day0-infra-build/docs/storage-ha-proposals.md`
section 1) - a k8smaster disk failure would have taken out the only copy
of every database on this instance simultaneously, "backup" or not.

`postgres-backup-cronjob.yml` runs daily (`0 2 * * *`) via the script in
`postgres-backup-script-cm.yml`: one `pg_dump -Fc` (custom format,
self-compressing) per database, plus a separate `pg_dumpall
--globals-only` for roles/passwords (not captured by any per-db dump).
Custom format, not plain SQL, specifically so a single database can be
`pg_restore`'d on its own without hand-editing a combined dump file.

Writes to the QNAP `backup` export, under `active_backup/postgres/` -
**not** the export root. That disk still has an old, pre-this-project
backup sitting at its root (a rushed copy made after a prior disk loss)
that hasn't been verified as fully recovered yet - nothing automated
touches the root until that's cleared by hand. Mounted as a pod-level
`nfs:` volume (same pattern as `apps/inbox-router`'s CronJob), not a
static PV, since `/backup` isn't a single-consumer claim.

Retention: 7 daily, 4 weekly (promoted Sundays), 13 monthly (promoted on
the 1st - 12 completed months plus the current in-progress one), pruned
per-database each run so one large/frequently-changing db's file count
doesn't crowd out another's.

## Current databases
| database      | owner         | used by                                  |
|----------------|---------------|-------------------------------------------|
| paperless      | paperless     | apps/paperless (day2)                     |
| homeassistant  | homeassistant | apps/homeassistant (day2) - Recorder, long-lived SQLAlchemy session |
| n8n            | n8n           | apps/n8n (day2) - long-lived connection pool |
| cloudflare_tf  | cloudflare_tf | day1-foundation apps/cloudflare-tf (Terraform state, `pg` backend) - connects only during `apply`, no persistent process |
| books          | books         | apps/books-pipeline (day2) - `fingerprints` table + `pg_trgm`, provisioned via the automated Job above - fresh connection per CronJob run, no persistent pool |
| immich         | immich        | apps/immich (day2) - `pgvector`/`cube`/`earthdistance` extensions, provisioned via the automated Job above (table was missing this row until now) |
| unifi_tf       | unifi_tf      | day1-foundation apps/unifi-tf (Terraform state, `pg` backend) - connects only during `apply`, no persistent process. Provisioned via the automated Job above; app itself is still scaffolding-only as of 2026-08-04, not yet registered in Argo CD |

## pgvector, and what a shared instance actually costs (2026-08-04)

Added the `pgvector` extension (via `images/postgres-pgvector`, built on
this exact `postgres:16.9-alpine` base rather than switching to the
upstream Debian/glibc `pgvector/pgvector:pg16` image - see that
Dockerfile's own comments for why a libc/collation change on a shared
instance with 5 existing databases was the real risk, not the extension
itself) so `apps/immich` could use this instance instead of standing up
its own. This is the textbook case for **why per-app databases are
usually the better default**: a change made for one app (Immich) required
restarting Postgres for **every** app on the instance, and two of them -
`homeassistant` and `n8n` - hold long-lived connections that don't
automatically survive that. Regression-tested all five consumers
immediately after the restart:

| App | Connection pattern | Result |
|---|---|---|
| paperless | fresh connection per request (Django default) | self-healed - errors only during the actual restart window, none after |
| n8n | persistent pool | self-healed - pool evicted the dead clients on its own within ~1 min |
| homeassistant | persistent SQLAlchemy session (Recorder) | **did not self-heal** - stuck in `sqlalchemy.exc.PendingRollbackError` indefinitely; required a manual pod restart to clear |
| books-pipeline | fresh connection per CronJob run | unaffected by design |
| cloudflare_tf | Terraform `apply` only | no live process to affect |

If this were N separate Postgres instances, only Immich's own restart
would have mattered, and Home Assistant's recorder would never have
noticed. That blast radius is the real cost of "shared" - not disk, not
CPU, but every dependent app's *connection-handling code* becoming a
shared risk surface, invisible until something like an image swap
actually exercises it.

**Why we still do it as one shared instance anyway, in this environment
specifically**: this is a single-operator home lab cluster, not a team
with a platform-ops function - running N independent instances is a real
ongoing cost (patching, backup, monitoring, sealed-secret rotation,
PVC/storage overhead) for a workload where every one of these databases
is small and low-QPS, and none of them need dedicated tuning or isolation
for performance. One instance to patch and back up beats five. The tradeoff only stays acceptable
because of two things demonstrated live here: (1) regression-testing
every dependent app after any shared-instance change, not just assuming
"the DB came back up so we're fine" - the two self-healing apps *looked*
identical to the one that wasn't from the outside (pod stayed `Running`
the whole time) until logs were actually checked; and (2) knowing in
advance which consumers use long-lived connections (need active
attention after any restart) versus per-request/per-run connections
(self-heal, no action needed).
