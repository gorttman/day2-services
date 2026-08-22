# Google Drive migration log

Tracks what's been pulled from Google Drive (both `gorttman@i3sec.com.au`
and `gorttman@gmail.com`, the latter via items shared to the former) and
where it landed, so this stays in sync across sessions instead of living
only in conversation history. Updated at the end of every import pass.

Status values: `done` (confirmed landed at destination), `pending`
(queued, not yet attempted), `exception` (blocked, see Exceptions below).

## Records/documents (i3sec.com.au, `records` Drive folder → Paperless)

27 files pulled 2026-08-03/04, all landed in Paperless except the 6 noted
in Exceptions (Office formats, blocked pending Tika/Gotenberg). See
`apps/paperless/README.md` for the full per-file table from that run.

## Books (various sources → Calibre)

| Source | Drive account | Destination | Status |
|---|---|---|---|
| Sinner Takes All - Tera Patrick | i3sec.com.au | Calibre #8041 | done (already present from unrelated earlier bulk import, confirmed duplicate) |
| CCNA Study Guide.pdf | i3sec.com.au | Calibre #10967 | done (confirmed 2026-08-04, first real use of the new PDF promotion path) |
| CCNA Review Guide.pdf | i3sec.com.au | Calibre #10966 | done (same run) |
| Secrets of Mental Math | i3sec.com.au | Calibre #10969 | done 2026-08-05 (PDF, author metadata came back "Unknown" - Calibre-side metadata gap, not a pipeline bug) |
| Getting Things Done | i3sec.com.au | n/a | correctly quarantined 2026-08-05 as a plain duplicate of existing #4659 - let books-pipeline's own dedup logic decide instead of guessing manually, it called this one right |
| The Power of Habit | i3sec.com.au | n/a | correctly quarantined 2026-08-05 as a plain duplicate of existing #10963, same as above |
| The Fast Diet | i3sec.com.au | Calibre #10970 | done 2026-08-05 |
| Making Habits Breaking Habits | i3sec.com.au | Calibre #10968 | done 2026-08-05 - confirmed genuinely different book from the existing #10962 (that one's "Making Good Habits, Breaking Bad Habits" by Joyce Meyer; this one's "Making Habits, Breaking Habits" by Jeremy Dean - similar title, different author/book, correctly NOT flagged as duplicate) |

## Photos/videos (→ Immich)

**Done 2026-08-22/23**, via Google Takeout rather than the file-by-file
Drive tool (its 10MB per-file cap would have blocked most of this
content - real raw camera files here ran 20-110MB each). Pipeline:
Takeout export -> `inbox-router` (new photo/video route added, staged
outside Immich's watched `/photos` tree at `/inbox/photos-staging` to
avoid indexing anything before it's sorted) -> `photos_importer.py`
(day0-infra-build/scripts, new) -> SHA-dedup against the existing
library + EXIF-year foldering into `/photos/<year>/`. First batch: 286
files, 270 photos/videos + 15 documents, 2 exact duplicates and 3
already-migrated documents excluded, 1 mislabeled file (HTML as .pdf)
correctly quarantined. User confirmed all Drive content migrated
2026-08-23. See memory `project_google_drive_offboarding` and
`project_immich_deployment` for the full pipeline design.

## gmail.com shared content (shared to i3sec.com.au 2026-08-04)

Note: the Drive tool's `parentId` query doesn't reliably traverse into
these shared folders (a real tool limitation, confirmed - the folders
are NOT actually empty). Workaround: paginating the full
`owner = 'gorttman@gmail.com'` listing surfaces everything, including
each item's real parentId, so the tree gets reconstructed from the
flat list instead of by querying folders directly.

Full inventory (status updated as each is pulled):

| Item | Folder | Status |
|---|---|---|
| Coq Au Vin | Recipes | done - Paperless #23 |
| Raspberry & White Chocolate Muffins | Recipes | done - Paperless #28 |
| Moroccan Meatballs | Recipes | done - Paperless #25 |
| Italian Meatballs | Recipes | done - Paperless #27 (pushed as .txt - PDF export was too small to trigger the safe file-overflow path and I won't manually transcribe base64; used read_file_content's text extraction instead, same content, safe method) |
| Business Plan.doc | Plan/Business Plan-budget | done - Paperless #26 |
| cafe-list | Plan/Business Plan-budget | done - Paperless #24 |
| cash flow | Plan/Business Plan-budget | done - Paperless #22 (pushed as .txt, same reason as Italian Meatballs) |
| Finance Plan | Plan/Business Plan-budget | done - Paperless #32 |
| Trading procedures.docx | Plan/Trading/Records | done - Paperless #33 |
| Benchmark Target | Plan/Trading/Records | done - Paperless #34 |
| Trading decisions | Plan/Trading/Records | done - Paperless #35 |
| Position Calculator | Plan/Trading/Records/Tools | done - Paperless #29 |
| Position_size5 | Plan/Trading/Records/Tools | done - Paperless #31 |
| Trading scratch.doc | Plan/Trading | done - Paperless #30 |
| 7x Bstevens_Cover_*.doc (near-duplicate cover letter drafts) | C.V./Cover Letters | done - Paperless #36-41, #43 |
| BSTEVENS-20100510a.doc (nested copy, C.V./Resume) + top-level copy | C.V./Resume + top-level | done - Paperless #42, #44, but **mis-tagged** (document_type=Contract, tags=Insurance+Property) by an over-loose "any word" auto-matching rule - see Exceptions below, needs manual fix |
| CashFlow (x2, top-level) | top-level | done - Paperless #53 (CashFlow-2), #54 (CashFlow-1) |
| Trading Calculation | top-level | done - pushed as .txt (small inline PDF, same reason as others) |
| business ideas | top-level | done - pushed as .txt |
| Cafe business Design | top-level | done - pushed as PDF |
| PC config | top-level | done - pushed as PDF |
| Exercise | top-level | done - pushed as .txt |
| BSTEVENS-20100510a.doc (top-level) | top-level | done - included in the cover-letters batch above |
| Imported from Google Notebook - Solaris Notes | top-level | done - pushed as .txt |
| Imported from Google Notebook - Ubuntu/Debian | top-level | done - pushed as .txt |
| stalls | top-level | done - pushed as .txt (condensed table, source spreadsheet may continue past what the text-extraction tool returned) |
| Untitled document | top-level | skipped - genuinely empty (confirmed via content read) |
| Untitled Presentation | top-level | skipped - genuinely empty (just slide separators, no content) |
| Margots_20112010..., Bike_trail_1_14112010... (gpx.txt) | top-level | done - Paperless #55 (Margots), #56 (Bike_trail) (both pushed as .txt - small inline PDF exports, used read_file_content text extraction) |
| neobox.zip, vespa-love-10.zip, seashore.zip, primepress.zip, Peruns_Weblog.zip, abstractblu.zip, rihanna.zip, Maggo.zip (8th found on the final full-inventory pass) | top-level | skipped - user decision 2026-08-05, old WordPress theme files not wanted |
| General, Cafe training (outer), Themes | folders | confirmed genuinely empty 2026-08-05 - full owner='gorttman@gmail.com' flat listing paginated to exhaustion, no item anywhere has a parentId matching any of these 3 folder IDs |

## Exceptions (blocked by tool limits, need manual handling)

Resolved 2026-08-05: Tika + Gotenberg deployed (`apps/paperless/paperless-tika-deployment.yml`,
`paperless-gotenberg-deployment.yml`), and the orphaned duplicate PDF
manually removed - both items below moved from "exception" to "done".

| File | Source | Status |
|---|---|---|
| 2023-04-28 Kemner Job Description.docx | i3sec.com.au records | done - Paperless #57 (Tika/Gotenberg now deployed) |
| brett stevens contract.docx | i3sec.com.au records | done - Paperless #58 |
| DC Quote 337Brett.docx | i3sec.com.au records | done - Paperless #59 |
| I CUBED CONSULTANTS...docx | i3sec.com.au records | done - Paperless #60 |
| IT_Ops_Realignment_Strategy_Document V1.5.docx | i3sec.com.au records | done - Paperless #61 |
| USA Canada Alaska Trip Planner...xlsx | i3sec.com.au records | done - Paperless #62 |
| Routine Inspection - 13 Greenlaw Cres, Berwick (1).pdf | i3sec.com.au records | done - orphaned duplicate deleted from consume folder |

Resolved 2026-08-05: tag/doc-type matching rules tightened (Contract ->
"all words" instead of "any word"; Insurance/Property -> specific
multi-word phrases instead of generic single words/address tokens).

**Correction to the note above**: at the time this was written, the
`.save()`-reverting mystery was blamed on unspecified "Paperless
save-path logic." That diagnosis was wrong. The real cause, found later
the same day: `paperless-config-seed-cm.yml` is an idempotent job that
reruns on every pod restart (TTL cleanup + ArgoCD selfHeal recreate it)
and unconditionally overwrites Tag/DocumentType rules from hardcoded
values baked into the script, then re-evaluates every document against
them. Every manual fix made via `manage.py shell` was getting silently
undone the next time that job ran - including recreating a fresh
"Property" tag with the *original* loose match string after it had
already been renamed away, which is what actually produced the
"reverting" symptom. Fixed at the real source (the seed script itself),
not worked around again - see "Property tag restructure" below for the
full account, including a second real bug found in the same fix (the
job's reclassify loop was wiping any manually-applied tag, including
the Hepburn hook's own tagging, on every rerun).

## Property tag restructure (2026-08-05)

User clarified Greenlaw and Hepburn are two separate addresses (Greenlaw
- former rental, Hepburn - current private home) that should never be
conflated under one generic "Property" tag. Investigated the 20 docs the
OLD "Property" tag had accumulated: only #15 (Routine Inspection)
actually contained rental/inspection vocabulary - the other 19 were
false positives purely from "Berwick"/"lease"/"tenancy" appearing as
bare words in letterhead addresses on totally unrelated documents (cover
letters, tax returns, a car purchase contract, an ASIC company filing).

Restructured:
- `Property` renamed to **`Property - Greenlaw (Rental)`**, match
  tightened to the single distinctive token `greenlaw` (any-word) -
  street name is specific enough on its own, unlike "Berwick" (a whole
  suburb). Kept on #5, #9, #15 only; stripped from the other 18.
- New **`Property - Hepburn (Home)`** tag created, several iterations:
  1. Bare `hepburn` word - rejected immediately, same address-in-letterhead
     problem, would have flooded every personal document again.
  2. `hepburn` + generic "provider info" words - real counterexample
     found: doc #59 (a contractor's concrete-replacement quote,
     genuinely Hepburn-relevant) vs #60 (I CUBED's own ASIC filing) and
     #58 (a car purchase contract) - both of the latter also have
     "provider info" (customer numbers, dealer licences) despite being
     nothing to do with the house.
  3. User wanted this to survive a provider *switch* automatically, not
     need re-confirming every time - expanded to a real list of major
     Australian electricity/gas/insurance providers (general knowledge,
     not user-confirmed) plus Casey Council and South East Water (both
     geography-fixed, safe to hardcode). Documented as an explicit table
     in `apps/paperless/README.md` rather than left buried in the regex,
     per user's point that the regex itself is a bad way to track "which
     providers do we match on."
  4. Hit Paperless's 256-char limit on `Tag.match` - had to trim the
     provider list hard to fit, prioritizing more common providers.
  5. **Real bug caught only by actually testing the regex**, not by
     inspection: the two-lookahead structure (`(?=.*hepburn)(?=.*(...))`)
     silently never matches when the address and the provider term are
     on different lines, since `.` doesn't cross newlines by default -
     which is the normal case for real documents. I'd manually
     force-tagged #59 earlier and claimed the rule "correctly tags #59"
     without ever actually running the regex against it - it would have
     matched nothing on the next real document. Fixed with the `(?s)`
     flag. Re-tested against every document that mentions "hepburn" at
     all (12 total) after the fix - correct on all 12.
  6. That same test run also caught bare `rates`/`insurance` as too
     generic (matched the car finance contract on "interest rates" and
     "comprehensive insurance") - replaced with specific phrases
     (`home insurance`, `contents insurance`).
- **Superseded, same day**: the whole regex approach above (items 1-6)
  was replaced entirely - see "Hepburn tag: moved off Paperless's
  Tag.match entirely" below. Kept here for the history of how the
  design got there, not because it's still live.

## n8n dead code - resolved 2026-08-05

`inbox-router` had the exact same dead n8n webhook pattern already
stripped from `books-pipeline` (`N8N_WEBHOOK_URL` pointing at a
placeholder URL, failing silently every run) - user confirmed removal
("n8n router can be deleted but noted so we can return to it later").
Stripped from source + deployed configmap, `inbox-router-secret`
deleted entirely (it was its only key), CronJob env cleaned up,
verified with a real manual run afterward. README documents where to
reintroduce it if a real n8n workflow gets built later. Separately, the
n8n Deployment itself scaled to 0 replicas (not deleted) - not ready
for use, pure idle resource cost in the meantime.

## Hepburn tag: moved off Paperless's Tag.match entirely (2026-08-05)

User's ask: an automatically-maintained provider list, sourced from the
web, not a hand-guessed one - "get the list from the web and do if in
this list then type of construct." Real blocker: Paperless's
`Tag.match` field caps at 256 characters, nowhere near enough for a
genuine provider list (confirmed empirically - even a trimmed real list
from Victoria's actual energy regulator blew past it).

Fetched real data instead of guessing: Victoria runs its own energy
retail licensing regime (Essential Services Commission), not the
national AER/Energy Made Easy framework other states use - confirmed by
checking, not assumed. Pulled the live ESC licensee register for actual
current electricity/gas retailer names. No equivalent government
registry exists for home/contents insurers, so that list stays
general-knowledge, lower confidence, flagged as such.

Built `hepburn-tag-hook.py` (Paperless post-consume script) + `hepburn-
providers.yaml` (unconstrained provider list, no size limit) +
`paperless-hepburn-hook-configmap.yml` (mounts both) - the hook checks
each newly-consumed document against the full list and tags via
Paperless's own REST API, using a token stored in `paperless-secret`.
The Hepburn Tag itself is now manual-only in Paperless
(`matching_algorithm: 0`) - it still exists so the hook can look it up,
but the hook is the real source of truth for automatic tagging now, not
Paperless's own matcher.

**Two real bugs found building this, both caught by testing, not
inspection:**
1. Sealed the API token via a bash here-string (`kubeseal <<< "$token"`)
   - here-strings always append a trailing newline, so the token had a
   stray `\n` baked in, breaking every API call with "Invalid header
   value." Resealed with `printf` instead; added `.strip()` in the
   script itself as a defense-in-depth safety net for this exact class
   of bug.
2. **The bigger one**: `paperless-config-seed-cm.yml` turned out to be
   the actual cause of the earlier ".save() reverting" mystery (see the
   correction note above `## Property tag restructure`) - it's an
   idempotent job that reruns on every pod restart and unconditionally
   overwrites Tag/DocumentType rules from hardcoded values, including
   recreating a plain "Property" tag with the *original* loose match
   string the moment the real one got renamed away. Fixed at the source:
   removed generic "Property" from the seed script's `TAGS` entirely,
   added the two address-specific tags as properly-tracked entries
   (Hepburn as manual-only), tightened Insurance, fixed Contract to
   all-words. Deleted the stale duplicate tag from the DB (the script
   fix alone doesn't retroactively remove a tag it no longer manages).
   Rerunning the corrected job then surfaced a **second** bug from the
   same script: its "re-evaluate every document" loop does
   `d.tags.set(new_tags)`, a full replace - since manual-only tags are
   never included in `match_tags()`'s output by definition, this wiped
   the Hepburn hook's own tagging off doc #59 the moment the seed job
   reran. Fixed by unioning freshly auto-matched tags with whatever
   manual-only tags were already present, instead of a full replace.
   Verified the real fix by re-running the seed job a second time after
   reapplying the Hepburn tag - it survived this time.

   The job's "re-evaluate every document" loop briefly logged a batch of
   `CRITICAL`/file-doesn't-exist errors while document_type values
   corrected away from years of incorrect over-broad "Contract"
   assignments (files mid-rename to match the new storage path).
   Checked directly rather than assumed harmless: swept all 60
   documents' `source_path` against disk after the job finished - zero
   missing files. Transient rename-handler noise, not data loss.

- **Still open**: real (not general-knowledge-guessed) gas/electricity/
  insurance provider confirmation - once known, add as exact-name terms
  to `hepburn-providers.yaml` (no size limit to fight now).

(10MB Drive-download tool cap itself hasn't blocked anything yet in this
log - noted here as a standing constraint, not a specific exception:
any file over that size needs a manual browser download instead of me
pulling it directly.)
