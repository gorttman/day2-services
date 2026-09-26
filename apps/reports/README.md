# reports

`https://reports.i3sec.com.au` - one page that switches between the homelab
reports. Internal only.

| Tab | Source |
|---|---|
| Media | `movie-status.i3sec.com.au` (arr-stack/movie-status) |
| Backups | `backup-status.i3sec.com.au` (backup-dashboard) |
| Subscriptions | served here, `/subscriptions/` |

Deep links use the hash: `reports.i3sec.com.au/#subscriptions`.

**Add a report:** add an entry to `REPORTS` in `index.html` inside
`reports-cm.yml`. The report's own host must allow framing (the Python
servers here send no `X-Frame-Options`, so they do).

**Update subscriptions:** edit `subscriptions.json` in `reports-cm.yml`.
Statuses are `active`, `review` or `cancelled`; `cycleMonths` is 1, 12, 24 and
so on, or 0 for one-offs. The claude.ai copy of the page
(https://claude.ai/artifact/9HZSSJVTgNp4o93y4zcqfr) keeps its own list and
adds a live Gmail receipt check, which this LAN copy cannot do without its
own Gmail credentials.
