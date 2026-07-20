# books-pipeline

**Status:** ACTIVE (deployed 2026-07-17)
**Namespace:** books-pipeline
**Schedules:** `books-pipeline` `*/15 * * * *`, `books-fingerprint-reconcile` `0 3 * * 0` (weekly)
**Tags:** `automation` `books-domain` `database`

---

## What it does

Processes arrivals in `books/import/` (populated by `inbox-router`,
recursively - real arrivals are often a whole `Author/Title.ext` tree,
not flat files) through six stages and promotes clean results into
Calibre's own library at `/books` via `calibredb add` (books and comics
share one library - see "Resolved 2026-07-18" below):

0. **PDFs skip straight to quarantine** - PDF triage is explicitly out
   of scope for this pipeline (see the "PDF triage subagent" note
   below); attempting `ebook-convert` on one anyway just burns its
   timeout for a result that was never going to auto-promote regardless.
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
6. **Promote** - `calibredb add`, passing this pipeline's own
   (possibly backfilled) title/author/ISBN explicitly. `fingerprints`
   INSERT happens after a successful add, committed only then.

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

## Resolved 2026-07-18: `promote()` now uses `calibredb add`, not a plain file copy

Was: no shared library format with calibre-web. `promote()` did a plain
`shutil.copy2` into a predictable `Author/Title.ext` path - real files,
but nothing in Calibre's `metadata.db` ever pointed at them, and
calibre-web only ever shows what's *registered*, not whatever it finds
scanning the filesystem. Found live 2026-07-18 after the recursive-scan
fix (below) actually started promoting real books and they still didn't
show up in calibre-web.

Now: `promote()` calls `calibredb add <file> --library-path
/mnt/books --duplicates --title ... --authors ... --isbn ...` instead.
Consequences worth knowing:

- **`library_dir` replaces `library_books_dir`/`library_comics_dir`** -
  one shared root (`/mnt/books`, same NFS path calibre-web's own
  `config_calibre_dir` already points at - see `calibre-web/README.md`),
  not two separate trees. Calibre happily mixes books and comics in one
  library; the old book/comics split existed only because this
  pipeline's own hand-rolled placement needed it, not because Calibre
  does.
- **Calibre owns the file layout now** - `<Author>/<Title> (<id>)/`,
  plus a `metadata.opf` and `cover.jpg` it generates itself per book.
  The `fingerprints.path` column stores whatever `calibredb list
  --for-machine` reports back as the real path (best-effort lookup - if
  it fails, the add itself still succeeded, just logged with a
  placeholder path).
- **`--duplicates` is deliberate, not a safety hole**: Calibre does its
  own (simpler, title+author-text-only) duplicate check on every add,
  which would otherwise silently veto an add that this pipeline's own
  `dedup_check()` - the actual authority here, already run before
  `promote()` is ever called - already decided should happen.
- **`--title`/`--authors`/`--isbn` are passed explicitly** from this
  pipeline's `meta` dict (possibly enriched by stage 5's metadata
  backfill), not left to whatever's embedded in the raw file - otherwise
  a successful backfill would never actually reach what calibre-web
  displays.
- `reconcile_fingerprints.py` had to change too: its file-vs-database
  drift walk now excludes `metadata.opf`/`cover.jpg`/`metadata.db` -
  every one of those is created by every single `calibredb add` and was
  about to become two permanent false-positive "untracked" entries per
  book, plus one for the whole library.
- `bookutils.safe_filename_component()` was removed - it existed only
  to compute the old hand-rolled path, which Calibre now computes
  itself.

**One-time backfill required** for anything promoted under the *old*
scheme before this fix - those files exist for real but were never
registered in Calibre's `metadata.db` either. See `HISTORY`/commit log
for the one-off backfill run, if one was needed at the time this
landed.

## Webhook

`N8N_WEBHOOK_URL` in `books-pipeline-secret` (shared with
`books-fingerprint-reconcile`) is currently a placeholder - no real n8n
workflow exists yet. Failed POSTs log a `WARN`, never fail the job.

## Real bug found 2026-07-18: NFS ownership never matched the runtime UID

User dropped ~4,480 real files into `import/` and none processed - every
`books-pipeline` run for ~2 hours had been failing with `error: timed
out waiting for the condition` (the 1800s `activeDeadlineSeconds`).

Root cause, in order: `import/`, `quarantine/`, and `library/{books,comics}/`
on the NFS export were owned `root:100` with the directory only granting
write to owner/group - but the then-live `books-pipeline:0.1.0` ran as
the invented `10001:10001` (matches neither), so every `quarantine()`
call failed with `EACCES`, and a failed quarantine leaves the original
file in `import/` untouched - so the *next* run picked up the exact same
stuck files and repeated the same expensive `ebook-convert` attempt
(most of these are old scanned PDFs; `ebook-convert` was genuinely
taking the full 600s timeout on several of them, not hanging), burning
the entire job deadline on 2-3 files before timing out. Compounding
factor, unrelated to the permission bug but hit in the same failure
window: on a `promote()` failure *after* a successful conversion,
`quarantine()` was called with the converted `tempfile.TemporaryDirectory()`
artifact - generically named `converted.epub` for every book - instead
of the original file, which both loses the original filename for human
review and guarantees a same-name collision on the second such failure.
Fixed in `books_pipeline.py`/`books-pipeline-configmap-script.yml`:
always quarantine the original file, matching the other two quarantine
call sites in `process_file()`.

**Separately**, a parallel session had already landed (`662a071`/`22be1af`)
the real structural fix for the UID mismatch class of bug - standardizing
`books-pipeline`/`inbox-router`/`calibre-web` on `UID 1000 / GID 100`
(matching every other linuxserver-based app in this cluster, and the
NFS directories' pre-existing `root:100` group ownership) rather than
the invented `10001:10001`. That fix was already synced by the time
this was investigated. **A first pass at fixing this live mistakenly
`chown`'d the NFS directories to `10001:10001`** (based on what the
*old*, already-dead job's `id` showed, without checking whether a fix
was already in flight elsewhere) - which briefly broke write access
again, just for the *new* UID instead of the old one. Caught by
checking `git log` mid-fix and re-diffing live state against
`kubectl get cronjob ... -o jsonpath='{...image}'`, which showed
`0.2.0` already deployed. Corrected: `import/`, `quarantine/`,
`library/{books,comics}/`, and (found while checking for the same
pattern) `calibre-web`'s `metadata.db` (owned `10001:10001`, no
group/other write bit - same rollout gap, calibre-web's actual process
also runs `1000:100` now) all re-`chown`'d to `1000:100`, the latter
also `chmod 664`.

**Lesson**: this NFS ownership state isn't code, so it doesn't show up
in a diff and won't regress on its own - but it also isn't self-healing
the way Argo CD's `selfHeal` is for everything else in this repo. Check
`git log` for recent parallel-session commits *before* diagnosing a
permission issue as "needs a chown to match what's currently running" -
another session may have already changed what "currently running"
means.

Verified after both the code fix and the correct `chown`: a manual
`kubectl create job --from=cronjob/books-pipeline` run actually wrote a
real quarantine entry (correct original filename, real reason sidecar,
removed from `import/` - count dropped by exactly one) with no
`EACCES`, and correctly detected+skipped a pre-existing same-name
collision without crashing the run. Real throughput on the current PDF
backlog is still slow - up to ~10 minutes per file when `ebook-convert`
times out - so draining 4,480 files (many of them PDFs) at 2-3
files/15-minute cycle will take a long time. Not addressed here: the
README's own stated design (a separate, not-yet-built "PDF triage
subagent") already anticipated PDFs shouldn't go through full
`ebook-convert` attempts in this pipeline at all - worth revisiting if
the backlog needs to drain faster than "eventually."

## Two more bugs found and fixed, arr-stack extension discovery (2026-07-21)

Found doing Phase 1 discovery for the arr-stack/LazyLibrarian books
extension - neither related to that extension itself, both pre-existing:

1. **`main()` crashed the entire job on a broken symlink.**
   `import/Books` was a symlink to `MD0_DATA/Public/Media/Books` - a
   QNAP-internal path notation, not reachable via the `/books` NFS
   export from this cluster's side. `os.walk()` picked it up fine (it's
   not a directory to descend into), but `is_settled()`'s `os.stat()`
   call follows symlinks and raised `FileNotFoundError` on the
   unreachable target - **outside** the per-file `try/except`, so it
   killed the whole run, every time the walk reached "Books"
   alphabetically. Confirmed against three consecutive `Failed` job runs
   immediately before this fix. Fixed: broken symlinks are detected
   (`os.path.islink() and not os.path.exists()`) and quarantined via a
   new `quarantine_broken_symlink()` - `os.rename()`, which doesn't
   follow the link, unlike the existing `quarantine()`'s `shutil.copy2()`
   which would have hit the exact same crash trying to "back it up"
   properly.

2. **`quarantine()`'s collision check was basename-only.** Generic
   sidecar names (`cover.jpg`, `metadata.opf`) recur across thousands
   of different book folders once the scan is recursive - the first
   occurrence quarantined fine, every one after collided on the bare
   filename and was left stuck in `import/` forever (**1,576 files**
   already piled up in `quarantine/` by the time this was found, an
   unknown share of the remaining `import/` backlog stuck the same
   way). Fixed: quarantined names are now disambiguated by parent
   directory (`"<parent dir> - <filename>"`), with a numeric-suffix
   fallback for the rare case two genuinely different files still
   collide - a source is now never left unquarantined for lack of a
   free name.

Both fixes double as the remediation for the one stray file found in
the same discovery pass (the broken symlink itself) - no separate
cleanup command needed, the fixed pipeline quarantines it properly
(with a real reason file) the next time it runs, rather than needing a
manual `rm`.
