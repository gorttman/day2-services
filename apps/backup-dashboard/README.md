# backup-dashboard - self-hosted, always-current backup status

Replaces the claude.ai Artifact version of this dashboard (which could only
be refreshed by asking Claude to pull fresh state and republish it) with a
genuinely self-hosted, self-refreshing page: `https://backup-status.i3sec.com.au`.

## How it stays current

A CronJob (`backup-dashboard-generator`, every 15 minutes) reads real state
directly from `/mnt/backup` - Postgres dump generations/ages, QNAP snapshot
generations/ages per source, sealed-secrets key freshness - and writes a
static `index.html`. A plain nginx Deployment serves whatever that file
currently contains.

Deliberately a periodic regenerate-and-write, not a live query-on-page-load
service: nothing here needs Kubernetes API access or RBAC, and 15-minute
freshness is more than enough for something that only changes once a day
(postgres-backup at 02:00, qnap-snapshot at 03:00, sealed-secrets-backup at
04:00 - see `day2-services/apps/postgres` and `day0-infra-build`'s
`qnap_snapshot` role).

Both the generator and the server are pinned to k8smaster
(`nodeSelector: kubernetes.io/hostname: k8smaster`) and share a `hostPath`
(`/var/lib/backup-dashboard-html`) - the same pattern `postgres-backup` uses
for `/mnt/backup` itself, since hostPath requires the path to exist on
whichever node the pod actually lands on.

## Alert thresholds

The generator computes staleness itself (`STALE_WARN_DAYS = 2`,
`STALE_CRIT_DAYS = 4` in `generate_dashboard.py`) - not hardcoded "healthy"
labels. A stream that hasn't produced a new generation in the expected
window shows up as genuinely Degraded/Critical on next regeneration, no
manual editing required. First caught a real 5-day-stale sealed-secrets
backup this way during initial testing (2026-08-22).

## DNS

`backup-status.i3sec.com.au` is added in the separate `dns-conf` repo, both
`coredns/fragments/i3sec-hosts.server` (cluster-internal resolution) and
`pihole/pihole-custom-dns-cm.yml` (LAN clients) - same split-horizon pattern
every other `*.i3sec.com.au` host uses, pointing at Traefik's floating IP
(`192.168.2.241`).

## First deploy

The nginx pod can start before the generator's first scheduled run - it'll
serve an empty/404 page for up to 15 minutes until the first CronJob fires.
Trigger one manually after first deploy (`kubectl create job
--from=cronjob/backup-dashboard-generator -n backup-dashboard <name>`) to
skip the wait.
