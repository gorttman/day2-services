# Paperless-NGX

**Status:** ACTIVE (bare install — configuration pass pending)
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
- PVCs on `nfs-client`: data (2Gi), media (10Gi), consume (5Gi)
- Ingress: traefik + cert-manager (`private-ca`), internal-only

## Deliberately unconfigured (separate pass)
- No `PAPERLESS_CONSUMER_*` overrides; consume dir is provisioned but empty
- No tag/correspondent automation rules
- OCR language at default (`eng`)
- No Cloudflare Tunnel exposure (tunnel path blocked)

## Access
- https://paperless.i3sec.com.au — requires DNS entry in `dns-conf`
  (pihole + coredns) pointing at 192.168.2.241; add post-merge
- Admin user `admin`; password in the `paperless-secret` sealed secret

## Secrets
`paperless-secret` (sealed): `PAPERLESS_DBPASS`, `PAPERLESS_SECRET_KEY`,
`PAPERLESS_ADMIN_PASSWORD`. DB password is also sealed into the postgres
namespace (`postgres-superuser.PAPERLESS_DB_PASSWORD`) for first-init
database creation.
