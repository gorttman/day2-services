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
| CCNA Study Guide.pdf | i3sec.com.au | Calibre | pending (re-queued in `/books/import` 2026-08-04, awaiting pipeline run with new PDF promotion path) |
| CCNA Review Guide.pdf | i3sec.com.au | Calibre | pending (same as above) |
| Secrets of Mental Math | i3sec.com.au | Calibre | pending (not yet attempted) |
| Getting Things Done | i3sec.com.au | Calibre | pending (not yet checked against existing library - a same-titled book already exists from an unrelated bulk import, needs duplicate-check before pulling) |
| The Power of Habit | i3sec.com.au | Calibre | pending (same caveat as above) |
| The Fast Diet | i3sec.com.au | Calibre | pending (not yet attempted) |
| Making Habits Breaking Habits | i3sec.com.au | Calibre | pending (same caveat - a similarly-titled book already exists from an unrelated bulk import) |

## Photos/videos (→ Immich)

Not started. Domain was untouched until Immich was deployed 2026-08-04.

## gmail.com shared content (shared to i3sec.com.au 2026-08-04)

Top-level survey only so far - folders not yet opened:

| Item | Type | Notes |
|---|---|---|
| Cover Letters | folder | not opened |
| General | folder | not opened |
| Plan | folder | not opened |
| Cafe training | folder | not opened |
| Recipes | folder | not opened |
| Resume | folder | not opened |
| Themes | folder | not opened |
| Business Plan | folder | not opened |
| C.V. | folder | not opened |
| CashFlow (x2), Trading Calculation, business ideas, Cafe business Design, PC config, Exercise, BSTEVENS-20100510a.doc (x2), 2x "Imported from Google Notebook" notes | individual docs/sheets | not yet pulled |
| neobox.zip, vespa-love-10.zip, seashore.zip, primepress.zip, Peruns_Weblog.zip, abstractblu.zip, rihanna.zip | small zips (~70-230KB) | old WordPress theme files, ~2010 - low value, not yet triaged for whether worth pulling at all |

## Exceptions (blocked by tool limits, need manual handling)

| File | Source | Reason | What to do |
|---|---|---|---|
| 2023-04-28 Kemner Job Description.docx | i3sec.com.au records | Paperless can't consume Office formats without Tika/Gotenberg (not deployed) | Deploy Tika/Gotenberg, or manually convert to PDF |
| DC Quote 337Brett.docx | i3sec.com.au records | same | same |
| I CUBED CONSULTANTS...docx | i3sec.com.au records | same | same |
| IT_Ops_Realignment_Strategy_Document V1.5.docx | i3sec.com.au records | same | same |
| brett stevens contract.docx | i3sec.com.au records | same | same |
| USA Canada Alaska Trip Planner...xlsx | i3sec.com.au records | same | same |

(10MB Drive-download tool cap itself hasn't blocked anything yet in this
log - noted here as a standing constraint, not a specific exception:
any file over that size needs a manual browser download instead of me
pulling it directly.)
