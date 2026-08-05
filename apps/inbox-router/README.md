# inbox-router

**Status:** ACTIVE (deployed 2026-07-17)
**Namespace:** inbox-router
**Schedule:** `*/5 * * * *`
**Tags:** `automation` `books-domain`

---

## What it does

Watches `/mnt/inbox` (QNAP `qnap.i3sec.com.au:/inbox`) and sorts arriving
files to their destination share, based on directory convention first
(highest precedence, no content inspection) then MIME-type detection
(`python-magic`) as a fallback. Never converts or processes files
itself - classification and routing only.

Precedence: `explicit_dirs` (files dropped in `inbox/books`, etc. -
directory placement is a manual declaration, bypasses MIME sniffing
entirely) evaluated first, then `mime_defaults` for files sitting in
the bare inbox root, then quarantine if nothing matches.

Config lives in `routes.yaml`, mounted via the `inbox-router-routes`
ConfigMap - edit the source file and regenerate the ConfigMap (see the
generation command at the top of `inbox-router-configmap-routes.yml`'s
history) rather than hand-editing the embedded copy.

## Scope: books + records live, vault still dormant

`inbox/books` → `books/import` (and the matching `books-ebook`/
`books-comic` MIME rules) and, as of 2026-08-01, `inbox/records` →
`paperless/consume` (plus the `office-to-records` MIME fallback) both
reach a mounted destination. `/mnt/paperless` is now mounted
(`qnap.i3sec.com.au:/paperless`) and points at the exact directory
Paperless-ngx's own deployment consumes from (its PVC-backed consume
volume was swapped for the same export) - the earlier "wrong
underlying storage" caveat is resolved.

`inbox/working` → `vault/incoming` is still **dormant** - `/mnt/vault`
is not mounted by this CronJob, so files landing there quarantine with
reason `destination unreachable`, not silently dropped. Deliberate, not
a bug - per explicit direction, each domain gets proven out before the
next expands.

`pdf-to-triage` routes undeclared bare-root PDFs to `inbox/triage` for
the PDF triage subagent (separate app, proposal not yet applied) - a
PDF placed via `inbox/records` bypasses this entirely and goes straight
to Paperless by directory convention.

## Image

`ghcr.io/gorttman/inbox-router:0.2.0` - built via
`.github/workflows/inbox-router-image.yml`, semver-tag-triggered,
linux/arm64 only.

## Storage

Direct pod-level `nfs:` volumes for `/mnt/inbox`, `/mnt/books`, and
(since 2026-08-01) `/mnt/paperless` (`qnap.i3sec.com.au`) - not PV/PVC.
`qnap-books` (the static PV pattern used elsewhere) is already bound to
calibre-web's PVC; a direct volume avoids needing a second PV for the
same export, and both `/inbox` and `/paperless` are genuinely
multi-consumer (this CronJob writes, the destination app reads), which
a single-writer PVC can't support anyway. No resource requests/limits
set - no CronJob precedent existed anywhere in this repo when this was
designed.

## Verified working

**2026-07-17**: Manually triggered end to end with a real file: dropped
into `inbox/books`, correctly routed to `books/import` via the
`explicit:inbox/books` rule.

**2026-08-01**: `inbox/records` → `paperless/consume`, real file, full
chain including Paperless's own consumption (not just the routing
hop). Hit a real blocker first: `/inbox`'s own export root had reverted
to `root:users 755` (no group-write), the same regression `/books`
independently hit the same day - see
`day1-foundation/apps/qnap-storage/README.md`. Fixed, then the route
worked on the very next scheduled cycle.

## n8n webhook - removed 2026-08-05

Used to POST a run summary to a placeholder n8n URL
(`https://n8n.i3sec.com.au/webhook/REPLACE-ME-inbox-router`) that never
had a real workflow behind it - every run logged a `WARN` and failed
silently, by design. Stripped entirely (same cleanup already done for
`books-pipeline` the same day - see `apps/books-pipeline/README.md`),
along with `inbox-router-secret` (`N8N_WEBHOOK_URL` was its only key).
If a real n8n workflow gets built later, this is the natural
reintroduction point - `main()` already computes a `summary` dict
(routes taken, quarantined files) right before the run ends, just needs
a POST added back where `log_summary()` is called.
