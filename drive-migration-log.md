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
| Finance Plan | Plan/Business Plan-budget | pushed to inbox/records 2026-08-04, awaiting Paperless consume |
| Trading procedures.docx | Plan/Trading/Records | pushed to inbox/records 2026-08-04, awaiting Paperless consume |
| Benchmark Target | Plan/Trading/Records | pushed to inbox/records 2026-08-04, awaiting Paperless consume |
| Trading decisions | Plan/Trading/Records | pushed to inbox/records 2026-08-04, awaiting Paperless consume |
| Position Calculator | Plan/Trading/Records/Tools | pushed to inbox/records 2026-08-04, awaiting Paperless consume |
| Position_size5 | Plan/Trading/Records/Tools | pushed to inbox/records 2026-08-04, awaiting Paperless consume |
| Trading scratch.doc | Plan/Trading | pushed to inbox/records 2026-08-04, awaiting Paperless consume |
| ~10x Bstevens_Cover_*.doc (near-duplicate cover letter drafts) | C.V./Cover Letters | pending |
| BSTEVENS-20100510a.doc (nested copy, C.V./Resume) | C.V./Resume | pending - likely duplicate of top-level BSTEVENS-20100510a.doc, dedupe before pulling both |
| CashFlow (x2, top-level), Trading Calculation, business ideas, Cafe business Design, PC config, Exercise, BSTEVENS-20100510a.doc (top-level), 2x "Imported from Google Notebook" notes, stalls, Untitled document, Untitled Presentation | top-level individual docs/sheets | pending |
| Margots_20112010..., Bike_trail_1_14112010... (gpx.txt) | top-level | pending - GPS tracks, low priority |
| neobox.zip, vespa-love-10.zip, seashore.zip, primepress.zip, Peruns_Weblog.zip, abstractblu.zip, rihanna.zip | top-level | pending - old WordPress theme files, ~2010, low value but included per "migrate all data" |
| General, Cafe training (outer), Themes | folders | not yet found any content with matching parentId - genuinely may be empty, or not yet reached in pagination |

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
