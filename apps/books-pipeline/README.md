# books-pipeline

**Status:** ACTIVE (deployed 2026-07-17)
**Namespace:** books-pipeline
**Schedules:** `books-pipeline` `*/15 * * * *`, `books-fingerprint-reconcile` `0 3 * * 0` (weekly)
**Tags:** `automation` `books-domain` `database`

---

## What it does

Processes arrivals in `books/import/` (populated by `inbox-router`)
through six stages and promotes clean results into
`books/library/{books,comics}/`:

1. **Extract metadata** (`ebook-meta`) - title, author, ISBN.
2. **Dedup check** against the `fingerprints` Postgres table - exact
   ISBN match first, then `pg_trgm`-narrowed candidates scored with
   `rapidfuzz`. Same format + confident match → plain duplicate;
   different format → format-upgrade candidate. Either way, quarantines
   immediately, no further stages run.
3. **Convert to EPUB** (`ebook-convert`) - EPUB and CBZ/CBR bypass
   entirely (comics are never converted).
4. **Quality checks** on the resulting EPUB - raw-HTML-in-text
   detection, paragraph-density check. Thresholds in `config.yaml`
   (`quality.*`), starting guesses, meant to be tuned against real data.
5. **Metadata backfill** (`fetch-ebook-metadata`, Open Library + Google
   Books) - only if title/author/ISBN still incomplete.
6. **Promote** - canonical `Author/Title.ext` path, comics always to
   `library/comics/` unconditionally by format (never content
   judgment). DB insert and file move happen in one transaction,
   committed only after the move succeeds.

`books-fingerprint-reconcile` (weekly, Sunday 03:00) walks the library
and the `fingerprints` table in both directions, reporting drift
(`stale` = row with no file, `untracked` = file with no row) via
webhook - never auto-corrects.

## Scope: books-only, live

`paperless/consume`-adjacent logic (the `office-to-records` MIME rule
in the upstream inbox-router) is dormant by design - this pipeline
only ever sees files inbox-router already routed to `books/import`,
so it's unaffected either way. PDF conversion is explicitly **not**
automated (Calibre's PDF handling is the known weak point) - PDFs are
handled by the separate PDF triage subagent (proposal not yet applied).

## Image

`ghcr.io/gorttman/books-pipeline:0.1.0` - Calibre 9.11.0 (official
installer, signature-verified, not Debian's frozen 8.5.0),
`python:3.12-slim` base, `pypdf`/`psycopg2-binary`/`rapidfuzz` added on
top. No `xvfb` (PDF conversion out of scope, so its one confirmed
justification doesn't apply). Built via
`.github/workflows/books-pipeline-image.yml`.

## Database

`books` database, `books` role, `fingerprints` table + `pg_trgm`,
provisioned via `apps/postgres/postgres-books-db-init-job.yml` (a
one-time idempotent Job, not hand-typed SQL).

**Real bug found and fixed on first deployment (2026-07-17)**: the
provisioning Job runs as the Postgres superuser, so `CREATE TABLE` left
`fingerprints` owned by `postgres`, not `books` - the pipeline's own
role would have gotten `permission denied for table fingerprints` on
its very first `INSERT`. Not caught in review; caught by testing the
actual consumer against the actual table. Fixed with
`ALTER TABLE fingerprints OWNER TO books;`, added to the provisioning
script (idempotent, safe to leave in place permanently).

## Verified working (2026-07-17)

Two real end-to-end tests, both against the live cluster:
- **Promotion path**: a real EPUB with embedded title/author/ISBN
  dropped in `inbox/books` → routed by inbox-router →
  `books/import/` → all six stages ran → promoted to
  `books/library/books/<Author>/<Title>.epub` → `fingerprints` row
  correctly inserted with normalized title/author, ISBN, format, path.
- **Dedup path**: an identical copy of the same file run through
  afterward → correctly detected as a plain duplicate via exact ISBN
  match → quarantined to `books/quarantine/` with a sidecar reason
  file naming the exact existing library path.

Test artifacts (the file, its library copy, its fingerprints row, the
quarantine copy and sidecar) were all cleaned up after verification -
the library and `fingerprints` table are back to empty, ready for real
use.

## Known gap: no shared library format with calibre-web

See `apps/calibre-web/README.md` and
`~/gm-dev/homelab-book/chapters/002-kavita-to-calibre-web.md` - this
pipeline's `promote()` doesn't produce a real Calibre library
(`metadata.db`), so calibre-web won't see promoted books as library
entries yet. Not fixed here.

## Webhook

`N8N_WEBHOOK_URL` in `books-pipeline-secret` (shared with
`books-fingerprint-reconcile`) is currently a placeholder - no real n8n
workflow exists yet. Failed POSTs log a `WARN`, never fail the job.
