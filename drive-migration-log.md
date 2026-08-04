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
| Secrets of Mental Math | i3sec.com.au | Calibre | pending (not yet attempted) |
| Getting Things Done | i3sec.com.au | Calibre | pending (not yet checked against existing library - a same-titled book already exists from an unrelated bulk import, needs duplicate-check before pulling) |
| The Power of Habit | i3sec.com.au | Calibre | pending (same caveat as above) |
| The Fast Diet | i3sec.com.au | Calibre | pending (not yet attempted) |
| Making Habits Breaking Habits | i3sec.com.au | Calibre | pending (same caveat - a similarly-titled book already exists from an unrelated bulk import) |

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
- New **`Property - Hepburn (Home)`** tag created. First attempt (bare
  `hepburn` word) rejected immediately - same address-in-letterhead
  problem, would have flooded every personal document again. Second
  attempt (hepburn + generic "provider info" words) also had a real
  counterexample: doc #59 (a contractor's concrete-replacement quote -
  genuinely Hepburn-relevant) vs #60 (I CUBED's own ASIC filing, uses
  Hepburn as registered business address) and #58 (a car purchase
  contract, uses Hepburn as customer address) - both of the latter also
  have "provider info" (customer numbers, dealer licences) despite being
  nothing to do with the house. Final rule (regex, requires `hepburn`
  AND at least one home-domain term): `rates`, `casey council`/`city of
  casey` (Berwick is in the City of Casey LGA - verified, safe to hardcode),
  `electricity`, `gas supply`, `water usage`, `home insurance`,
  `contents insurance`, `mortgage`, `renovation`, `strata`,
  `real estate`, `plumber`, `electrician`, `concrete`, `landscap*`,
  `building`. Correctly tags #59, correctly excludes #58/#60. Retagged
  #59 as the first real example.
- **Still open**: actual gas/electricity/insurance provider names -
  asked user, not yet answered. Once known, add as exact-name terms to
  the Hepburn regex (far more precise than the generic category words
  currently doing that job).

(10MB Drive-download tool cap itself hasn't blocked anything yet in this
log - noted here as a standing constraint, not a specific exception:
any file over that size needs a manual browser download instead of me
pulling it directly.)
