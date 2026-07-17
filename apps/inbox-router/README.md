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

## Scope: books-only, live

Only the `inbox/books` → `books/import` route (and the matching
`books-ebook`/`books-comic` MIME rules) actually reaches a mounted
destination right now. `inbox/records` → `paperless/consume` and
`inbox/working` → `vault/incoming` are present in `routes.yaml` but
**dormant** - neither `/mnt/paperless` nor `/mnt/vault` is mounted by
this CronJob, so files landing there quarantine with reason
`destination unreachable`, not silently dropped. Deliberate, not a
bug - per explicit direction, books gets proven out before the domain
expands. `paperless/consume` additionally still points at the wrong
underlying storage even once mounted (see routes.yaml comments) -
carried forward, not yet resolved.

`pdf-to-triage` routes undeclared bare-root PDFs to `inbox/triage` for
the PDF triage subagent (separate app, proposal not yet applied) - a
PDF placed via `inbox/records` bypasses this entirely and goes straight
to Paperless by directory convention.

## Image

`ghcr.io/gorttman/inbox-router:0.1.0` - built via
`.github/workflows/inbox-router-image.yml`, semver-tag-triggered,
linux/arm64 only.

## Storage

Direct pod-level `nfs:` volumes for `/mnt/inbox` and `/mnt/books`
(`qnap.i3sec.com.au`) - not PV/PVC. `qnap-books` (the static PV
pattern used elsewhere) is already bound to calibre-web's PVC; a
direct volume avoids needing a second PV for the same export. No
resource requests/limits set - no CronJob precedent existed anywhere
in this repo when this was designed.

## Verified working (2026-07-17)

Manually triggered end to end with a real file: dropped into
`inbox/books`, correctly routed to `books/import` via the
`explicit:inbox/books` rule, webhook POST attempted and failed
gracefully (no real n8n workflow exists yet - logged as a `WARN`, did
not fail the job, exactly as designed).

## Webhook

`N8N_WEBHOOK_URL` in `inbox-router-secret` is currently a placeholder
(`https://n8n.i3sec.com.au/webhook/REPLACE-ME-inbox-router`) - no real
n8n workflow exists yet. Failed webhook POSTs log a `WARN` and never
fail the job.
