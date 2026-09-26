# icloud-migration-status

**Status:** ACTIVE (deployed 2026-09-26)
**Namespace:** monitoring (shares grafana/influxdb's namespace, not its own)
**Schedule:** `*/15 * * * *`
**Tags:** `observability` `icloud-migration`

---

## What it does

Pushes current status of the iCloud Drive -> QNAP/homelab migration
(see project memory / conversation history for the full migration
project) into InfluxDB bucket `icloud_migration` (org `pilab`,
measurement `migration_status`), one point per category: photo_archive,
scu_coursework, greenlaw, downloads_misc, desktop_1password,
obsidian_vault, lightroom_catalog.

Feeds the "iCloud Migration" Grafana dashboard (day1-foundation
`apps/grafana/grafana-dashboards-cm.yml`).

## Why it lives in `monitoring`, not its own namespace

Reuses the existing `grafana-influxdb` SealedSecret (org + token)
already provisioned there for Grafana's InfluxDB datasource, rather
than sealing a second copy of the same credentials into a new
namespace. Writes into its own bucket (`icloud_migration`), not that
secret's default-bucket field (`telegraf`) - same shared-org/
per-topic-bucket pattern the Subscriptions dashboard already
established.

## What's actually live vs manual

Only `scu_coursework`'s progress is computed live, each run: it counts
files remaining in the Paperless consume queue (NFS-mounted read-only,
`qnap:/paperless` subPath `consume`) against the known reconciled total
of 1355 files - no Paperless API or exec needed, the queue count alone
tells you how many haven't been absorbed yet.

Every other category is manual state hardcoded in the script
(`icloud-migration-status-configmap-script.yml`'s `MANUAL_CATEGORIES`)
- there's no cheap live signal for "has someone actually copied the
Greenlaw docs into Paperless yet." Update those fields by hand as each
category's real-world status changes.

## Verified working

2026-09-26: bucket `icloud_migration` created via the InfluxDB API,
seeded manually with an initial snapshot, confirmed queryable from
Grafana before this CronJob existed. This CronJob keeps `scu_coursework`
current going forward; the rest still needs a manual script edit per
update until each category gets its own cheap live signal (if ever).
