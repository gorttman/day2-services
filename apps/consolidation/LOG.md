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

## 2026-10-06 August (W33/W34) vs live comparison
- Nothing missing for books, calibre-web, inbox, pihole. immich backups 14 old
  files (0.28 GB), vault 3 inbox files.
- UNRESOLVED, do not let W33/W34 prune until checked:
  1) paperless: 1,436 files / 1.34 GB in August not live by name. Live has 996
     documents in the DB and storage folders Contract/Invoice/Quote, so likely
     renamed by a storage-path change, NOT proven.
  2) media tv/The Closer: 349 files / 32.6 GB in August not live by name. Live
     has 222 files and extra "Season 1/2/4/5/6/7" folders beside "Season 01..",
     so likely Sonarr renamed/moved, NOT proven.
- Next check: compare by size+checksum or by Paperless document count per file
  type, not by name.

## 2026-10-06 outside-the-backup measurement
- USB Photo = Public/Photo (1.06 TB each); only 5,176 files (master/2016) in
  Public not on USB, 18 print files on USB not in Public. Data and public_root
  are duplicates too.
- USB Movies 5.15 TB and TV 633 GB are ONLY on the USB disk (not in Public):
  5.9 TB, mostly DVD folders and older rips. Compare with live media by title.
- Public/icloud-raw is 63 GB and outside the backup.
- Register updated and redeployed.

## 2026-10-06 icloud-raw check (read-only, renice 19, metadata only, load stayed ~1)
- 63 GB total. Photo 52 GB: 27,344 .lrprev previews + Lightroom catalog
  (229 MB lrcat, keep) + 1,762 real media (47 GB).
- Name+size vs Immich library and Public/Photo: 1,712 match, 50 (0.86 GB)
  match neither (Evelyn 30 HEIC, Dad 5, Berlin/Europe 2017 edits incl three
  111 MB TIFFs, 4 videos). List was in session scratchpad icloud_neither.txt.
- Not yet compared: Shared 3.8 GB, Downloads 3.2 GB, _pulled_images 1.9 GB,
  inbox 1.2 GB, Desktop 0.8 GB, Drawings, drafting 2, media.

## 2026-10-06 decision
- User: not going back to Lightroom. The Lightroom catalog (229 MB) and 27,344
  previews (3.9 GB) in icloud-raw need no migration. They are left in place,
  not deleted (hoarder default); they can age out with icloud-raw later.

## 2026-10-06 copied the 50 unmatched icloud photos
- Server-side cp on the QNAP (renice 19, load stayed ~1) to
  /share/CACHEDEV1_DATA/photos/icloud-raw/<original subpath>, 50 files,
  840 MB, sizes verified, perms 664/2775. Immich library scan (204) then showed
  all 50 as assets. Source in Public/icloud-raw untouched.
- Folder icloud-raw (not year folders) chosen to keep provenance; no year guessed.

## 2026-10-07 icloud-raw non-photo understanding pass (read-only, renice 19)
- Greenlaw damage photos (~350 files, 1.48 GB) match nothing in Immich or
  Paperless; same photos also as a 1.49 GB zip and 1,035 extracted copies in
  _pulled_images. Tax-21 11 files 90 MB not in Paperless. Drawings/drafting 45
  CAD files no home. Downloads: installers (Fedora ISO 1.83 GB, dmgs), notes.
  Desktop: 1Password 7 app backup. Shared SCU mostly size-matched (weak).
- Listings kept in session scratchpad (ls_ic_*.txt, ls_q_*.txt,
  ic_unmatched.tsv); regenerate if gone.
- Nothing copied or changed. Next: user decisions per group, then checksums.

## 2026-10-07 Greenlaw + Tax moved (user: "let's go")
- 354 Greenlaw damage-photo files copied server-side to
  photos/icloud-raw/Greenlaw/..., sizes verified; Immich scan: 352 assets
  (rest = 1 pdf + 1 html).
- 92 Greenlaw/Tax documents (pdf/docx/rtf/png/jpeg; no html, no zip, no damage
  photos) copied to inbox/records as icloud_<path>; router moved all 92 to
  paperless/consume. Paperless count was still 996 at the time: NEXT SESSION
  CONFIRM they landed (consume had 413 queued; duplicates are rejected by
  checksum, which is fine).
- NOT done: CAD files (no home decided), installers/1Password backup
  (archive-only, no action), Tax DNG (stays in icloud-raw).
- Watch: immich-server restarts 56 -> 64 in ~12h, OOMKilled, last 00:16 daily
  pattern. Separate investigation.
