# Data consolidation program

One place that tracks moving every scattered source of the user's data into
protected, organised storage, and keeps that work going across sessions.

- `BRIEF.md`   drop-in orientation for a fresh session. Read this first.
- `LOG.md`     append-only record of what each session did.
- the register `apps/reports/consolidation-register.json` is the single source
  of truth for every source and its status. The report page
  https://reports.i3sec.com.au/consolidation/ renders it.
- skill `data-consolidation` (agent-skills) holds the start-of-session and
  end-of-session routine and the helper `register.py`.

Later this folder also holds the cluster pieces: the work-window controller
(presence gate) and the Telegram approval bot.
