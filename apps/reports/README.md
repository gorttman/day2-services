# reports

`https://reports.i3sec.com.au` - one landing page for the homelab reports.
Internal only.

| Report | Where |
|---|---|
| Backups | `/backups/` here - formerly the separate `backup-dashboard` app, see [BACKUPS.md](BACKUPS.md) |
| Subscriptions | `/subscriptions/` here |
| Media | `movie-status.i3sec.com.au`, stays in arr-stack (needs Radarr's RWO volume) |

One Python server (`server.py` in `reports-cm.yml`) serves everything, pinned
to k8smaster for `/mnt/backup`. `backup-status.i3sec.com.au` still resolves
here and redirects to `/backups/`.

**Add a report:** add a card to `index.html` in `reports-cm.yml`, and a route
in `server.py` if it's served from this pod.

**Update subscriptions:** edit `subscriptions.json` in `reports-cm.yml`.
Statuses are `active`, `review` or `cancelled`; `cycleMonths` is 1, 12, 24 and
so on, or 0 for one-offs. The claude.ai copy of the page
(https://claude.ai/artifact/9HZSSJVTgNp4o93y4zcqfr) keeps its own list and
adds a live Gmail receipt check, which this LAN copy cannot do without its
own Gmail credentials.

## History

**2026-09-26:** created as an iframe tab switcher (nginx). Same day, turned
into a single Python server with a landing page, absorbing backup-dashboard
(which had been scaled to 0 outside Git) so there is one reports app.
