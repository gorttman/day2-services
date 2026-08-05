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

Not started. Domain was untouched until Immich was deployed 2026-08-04.

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
multi-word phrases instead of generic single words/address tokens), and
document_type + tags force-cleared on #42/#44 via a queryset `.update()`
(a plain `.save()` was silently reverting the change - Paperless has
some save-path logic that reasserts fields, worth remembering if this
comes up again). Watch #42/#44 on the next reprocess/redo-OCR to confirm
the tightened Contract rule (now "all words": contract+agreement+
employment) doesn't retrigger - Brett's IT-contracting background makes
it plausible the resume text genuinely contains all three words, in
which case this specific false positive may need a document-level
exclude rather than a global rule change.

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
- **Still open**: real (not general-knowledge-guessed) gas/electricity/
  insurance provider confirmation - asked user, not yet answered. Once
  known, the confirmed provider replaces the guessed list entries for
  that category (frees up character budget too).

(10MB Drive-download tool cap itself hasn't blocked anything yet in this
log - noted here as a standing constraint, not a specific exception:
any file over that size needs a manual browser download instead of me
pulling it directly.)

## Small follow-up spotted, not yet actioned (2026-08-05)

`inbox-router` has the exact same dead n8n webhook pattern that was
stripped from `books-pipeline` on 2026-08-05 (`N8N_WEBHOOK_URL` pointing
at `n8n.i3sec.com.au/webhook/REPLACE-ME-inbox-router`, fails silently
every run). Same fix would apply - not done yet, just noted while
working on the books import so it doesn't get lost.
