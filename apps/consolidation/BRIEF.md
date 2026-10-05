# Consolidation BRIEF (read this first in a fresh session)

## Goal
Get every scattered copy of the user's data into protected, organised storage
on the QNAP, de-duplicated, with nothing lost. Keep going across chat resets
until the register shows every source as done.

## Standing rules
- User knows nothing of the internals: give simple numbered steps.
- Hoarder: archive or hardlink duplicates, never delete by default.
- Do not stress the QNAP (1 GB RAM). One heavy job at a time.
- Plain-text questions, no pickers. Show a plan before risky changes.
- Verify live state before asserting. No deferred manual steps: put reminders
  in Telegram, not in the user's head.
- Terminal dislikes hyphens in paths: use short names like ~/seal_telegram.sh.

## Work window (heavy QNAP work such as de-dupe)
Only Mon-Wed, 08:00-18:00, and only when ALL true: the user's iPhone has been
off home Wi-Fi ~20 min (UniFi presence), Jellyfin is not streaming
(qnap_stream_watcher flag), manual override not set. Outside the window:
pause de-dupe, resume downloads/imports. Inside: pause SAB + qBittorrent.
Status: controller NOT built yet.

## Approvals
De-dupe starts READ-ONLY (report only). Findings go to Telegram for approval
(bot piClusterAlerts_bot). Fallback: user approves in chat. Actions are
hardlink/archive, never delete.

## Where things are
- Register (truth): apps/reports/consolidation-register.json
- Log: apps/consolidation/LOG.md  (append one entry per session)
- Existing workstreams: ~/gm-dev/immich-migration/STATE.md (paused
  2026-09-21), ~/gm-dev/router-tooling-brief.md (inbox-router tooling),
  reports iCloud migration page.
- Pending read-only measurements (scratchpad, may be gone after reset; rerun
  from git if needed): backup_disk_sizes.txt, august_compare.txt,
  outside_backup.txt.

## Build order and status
1. memory + BRIEF + LOG + register ........ IN PROGRESS
2. report page /consolidation/ ............ todo
3. work-window controller ................. todo
4. Telegram approval bot .................. todo
5. read-only de-dupe, then approved actions todo
6. protect irreplaceable photos/documents . todo
7. Telegram reminders / weekly digest ..... todo

## Start of session
Read this file, the last LOG entries, the register; tell the user the next
step in two sentences. End of session: append LOG, update register + status.
