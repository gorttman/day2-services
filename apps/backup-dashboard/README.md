# backup-dashboard - self-hosted, on-demand backup status

Replaces the claude.ai Artifact version of this dashboard (which could only
be refreshed by asking Claude to pull fresh state and republish it) with a
genuinely self-hosted, on-demand page: `https://backup-status.i3sec.com.au`.

## How it stays current

A single Python `http.server` (`generate_dashboard.py`, no framework, no
extra dependencies) re-scans `/mnt/backup` - Postgres dump generations/ages,
QNAP snapshot generations/ages per source, sealed-secrets key freshness -
and renders the page fresh **on every single request**. Not a CronJob
writing a static file on an interval: genuinely on-demand, exactly as fresh
as the moment it's loaded, no staleness window at all.

This is deliberately simpler than the original design (CronJob + shared
hostPath + nginx serving whatever was last written) - one self-contained
process, no coordination between a writer and a reader, still no
Kubernetes API access or RBAC needed anywhere (it only ever reads local
mounted files). `Cache-Control: no-cache, must-revalidate` is set
explicitly so a viewer's own browser never serves a stale cached copy
either - see the 2026-08-22 cache-header incident below.

Pinned to k8smaster (`nodeSelector: kubernetes.io/hostname: k8smaster`),
same as `postgres-backup` - `/mnt/backup` only exists as a real mount on
that node (day0-infra-build's `qnap_client` role).

## Countdown timer

The header shows a live countdown to the next of the three real daily
backup schedules (`postgres-backup` 02:00, `qnap-snapshot` 03:00,
`sealed-secrets-backup` 04:00, all AEST - see `DAILY_SCHEDULE` in
`generate_dashboard.py`). Computed server-side as a fixed UTC instant,
ticked client-side against the viewer's own clock (plain `setInterval`
subtraction, not a server round-trip per tick) - reloads the page itself
once the countdown hits zero, so a viewer who leaves the tab open sees
the just-completed run's fresh state automatically.

Confirmed live 2026-08-22 that k8s CronJobs with no `.spec.timeZone` set
resolve their schedule against the **host's own system clock** here (AEST),
not UTC - `sealed-secrets-backup`'s `"0 4 * * *"` actually fires at 18:00
UTC the previous day, which is exactly 04:00 AEST. Worth re-checking if
this cluster's controller-manager timezone handling ever changes.

## Alert thresholds

The generator computes staleness itself (`STALE_WARN_DAYS = 2`,
`STALE_CRIT_DAYS = 4` in `generate_dashboard.py`) - not hardcoded "healthy"
labels. A stream that hasn't produced a new generation in the expected
window shows up as genuinely Degraded/Critical, no manual editing required.
First caught a real 5-day-stale sealed-secrets backup this way during
initial testing (2026-08-22) - root cause was a QNAP export outage that a
mountpoint guard correctly refused to sync through; see day0-infra-build
and day2-services `apps/postgres`'s own history for that incident.

## DNS

`backup-status.i3sec.com.au` is added in the separate `dns-conf` repo, both
`coredns/fragments/i3sec-hosts.server` (cluster-internal resolution) and
`pihole/pihole-custom-dns-cm.yml` (LAN clients) - same split-horizon pattern
every other `*.i3sec.com.au` host uses, pointing at Traefik's floating IP
(`192.168.2.241`).

## History

**2026-08-22, on-demand rewrite:** originally a CronJob regenerating a
static file every 15 minutes plus a separate nginx Deployment serving it.
Replaced with the single on-demand server described above per explicit
request - "generate on demand rather than on a schedule" - which also
happened to simplify the whole app down from 3 workload objects
(CronJob + Deployment + ConfigMap-for-nginx) to 1.

**2026-08-22, cache-control incident:** the original nginx-based version
shipped no `Cache-Control` header at all (just `ETag`/`Last-Modified`), so
a viewer's browser cached a stale copy heuristically and kept showing it
after the underlying content had genuinely updated - looked like a
reverted fix from the outside. Explicit `no-cache, must-revalidate` is
still set even after removing nginx, since the same class of bug is just
as possible with any static-looking response.
