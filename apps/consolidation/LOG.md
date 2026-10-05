# Consolidation LOG (newest last)

## 2026-10-06 session 1
- User approved the program, work-window rules (Mon-Wed 08:00-18:00,
  iPhone away, Jellyfin idle) and Telegram approvals.
- Created apps/consolidation (README, BRIEF, LOG) and the initial register.
- Three read-only measurements were still running (disk sizes, August vs
  live, outside-backup folders). Results not yet folded into the register.

## 2026-10-06 session 1 (later)
- User: do not assume earlier work is concluded; check everything.
- Verified Immich: 81,845 assets (was 25,950); copy ok 59,150/0 failed; ~40
  invalid source files in the error list; immich-server OOMKilled 56 restarts.
- Found: inbox quarantine 25, photos-staging 7, Public/Books 5,189 entries,
  /immicc (live Immich backups), Brett's iPhone/Recents 24,151 files.
- Built and deployed https://reports.i3sec.com.au/consolidation/ (all other
  report pages re-checked 200). Register is in reports-cm.yml.
- Measurements (disk sizes, August vs live, outside backup) still waiting on
  the media mirror (QNAP load ~7). Do not start them again; scripts are in the
  old session scratchpad and may need re-creating.

## 2026-10-06 backup disk measurement (finished 10:43)
- Disk 20.4 TB, 75% used, 5.03 TB free. Used by: monthly 5.8 TB, W34 1.16 TB,
  W33 1.06 TB, daily 0.63 TB, mirror/photos 0.71 TB, mirror/media 0.46 TB so far.
- Live media is about 10 TB (movies 6.6, bulk 1.6, tv 1.8). A full media mirror
  will NOT fit in 5 TB free unless it hardlinks against the media already in
  monthly/weekly (link-dest reuse). Decision needed before the mirror runs on.
- Other two measurements (august_compare, outside_backup) still pending.
