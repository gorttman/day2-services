# Paperless-NGX

**Status:** ACTIVE (consumer folder + tag/document-type/filing config done
2026-08-03; Cloudflare exposure + extra users still pending)
**Version:** 2.20.15 (ghcr.io/paperless-ngx/paperless-ngx)
**Namespace:** paperless
**Sync Wave:** 0 (namespace only)
**Tags:** `documents` `day2`

---

## What it does
Document management system: scan/upload, OCR, search, archive.

## How it works
- Webserver deployment (single replica, Recreate strategy — PVCs are RWO)
- Dedicated in-namespace Redis broker (`paperless-redis`, no persistence)
- Database: `paperless` logical DB on the shared Postgres instance
  (see apps/postgres/README.md — default shared-instance route)
- PVCs on `nfs-client`: data (2Gi), media (10Gi). `consume` is **not** a
  PVC — see below.
- Ingress: traefik + cert-manager (`private-ca`), internal-only

## Consumer folder (2026-08-01)

`consume` is a raw QNAP export (`qnap.i3sec.com.au:/paperless`, subPath
`consume`), not a PVC — `inbox-router` writes into the exact same
directory from its own pod (`inbox/records` explicit route, plus a
bare-inbox-root MIME fallback for office docs), so it has to be a
directly-mounted multi-consumer volume like `/books` and `/inbox`, not a
single-writer PVC. The original `paperless-consume` PVC was confirmed
empty and removed rather than migrated. See
`day1-foundation/apps/qnap-storage/README.md` ("paperless directory")
and `day2-services/apps/inbox-router/README.md` for the routing side.

`data` and `media` are still on the `nfs-client` StorageClass (backed by
k8smaster's own local-disk export, not the QNAP) — same "wrong home"
pattern flagged and fixed for Obsidian's vault. Not migrated here; out
of scope for the consumer-folder pass, flagged for a later one.

**`PAPERLESS_CONSUMER_POLLING=30` is required**, not optional, for this
setup — Paperless defaults to inotify-based watching, which only fires
for writes made through the *same* client's local mount. inbox-router
writes into `consume/` from a completely separate pod/NFS client, so
its writes were invisible to Paperless's inotify watcher (confirmed
live: a real test file sat unconsumed until this was set). Polling mode
is the documented fix for any network-share consume directory.

Verified end-to-end 2026-08-01: a file dropped into `inbox/records`
(via inbox-router) was routed to `/mnt/paperless/consume`, picked up by
Paperless's poller within ~30s, and consumed successfully (`New
document id 1 created`).

Also pinned to `k8smaster` (`nodeSelector`) — `pinode-01`'s k3s root is
RAM-backed tmpfs and can't unpack this image (OCR + scipy/numpy deps);
confirmed live via "no space left on device" during this same rollout.

## Verified working (2026-08-01)

Real end-to-end test: dropped a file into `inbox/records`, confirmed it
routed to `/mnt/paperless/consume` via inbox-router's next scheduled
run, and confirmed Paperless consumed it into a new document (id 1).
Two real bugs found and fixed along the way, not just config: `/inbox`'s
own export root had the same permission regression `/books` hit
(`root:users 755` instead of `2775` — see qnap-storage README), and
Paperless's default inotify watching doesn't see a second NFS client's
writes (see `PAPERLESS_CONSUMER_POLLING` above).

## Tags, document types, and filing (2026-08-03)

Seeded via `paperless-config-seed-job.yml` (idempotent, same pattern as
`postgres-books-db-init-job.yml` — runs `manage.py shell` against the
script in `paperless-config-seed-cm.yml`, using the same image/DB env as
the main Deployment rather than a REST API token):

- **Tags** (auto-match on document content, "Any word"): Tax, Property,
  Insurance, Contracts, Business, Vehicle. Personal and Correspondence
  are manual-only (no auto-match) by design — too generic to keyword-match
  reliably.
- **Document types** (auto-match): Invoice, Statement, Contract, Report,
  Quote.
- **Filing**: two separate template mechanisms, deliberately not unified
  because they use different syntax:
  - `PAPERLESS_FILENAME_FORMAT` (paperless-deployment.yml) - the global
    default for any document not matched to a specific `StoragePath`.
    Old-style `{var}` placeholders (Paperless auto-converts these
    internally); NOT Jinja2.
  - The seeded `StoragePath` named "Default filing" - `matching_algorithm:
    0` (manual-assignment only), Jinja2 syntax (`{{ document.field }}`).
    Exists as a selectable option in the UI rather than an active
    auto-rule; the global format above is what actually applies day to
    day.
  - Both render the same effective scheme:
    `{document_type}/{created_year}/{correspondent}-{title}`.

Category choices are based on what's actually shown up in the first real
document import pass (tax returns, ASIC statements, property inspection
reports, contracts, trade quotes) — expect to add/adjust tags as more
document types show up, not a fixed final set.

## Office format support via Tika/Gotenberg (2026-08-05)
`gotenberg` and `tika` (own Deployments/Services in this namespace,
`paperless-gotenberg-deployment.yml` / `paperless-tika-deployment.yml`)
convert Office formats (.docx/.xlsx/.pptx/.odt/etc.) to PDF and extract
their text, wired via `PAPERLESS_TIKA_ENABLED`/`PAPERLESS_TIKA_ENDPOINT`/
`PAPERLESS_TIKA_GOTENBERG_ENDPOINT` in `paperless-deployment.yml`.
Without these, Office formats land in `consume/` and are never picked
up — six files did exactly this from the first i3sec.com.au records
import pass, sitting untouched until this landed.

## Deliberately unconfigured (separate pass)
- OCR language at default (`eng`)
- No Cloudflare Tunnel exposure (tunnel path blocked)
- User management: only the single `admin` superuser exists so far

## Access
- https://paperless.i3sec.com.au — DNS entry live in `dns-conf`
  (pihole + coredns), 192.168.2.241
- Admin user `admin`; password in the `paperless-secret` sealed secret

## Secrets
`paperless-secret` (sealed): `PAPERLESS_DBPASS`, `PAPERLESS_SECRET_KEY`,
`PAPERLESS_ADMIN_PASSWORD`. DB password is also sealed into the postgres
namespace (`postgres-superuser.PAPERLESS_DB_PASSWORD`) for first-init
database creation.
