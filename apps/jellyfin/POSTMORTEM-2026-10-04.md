# Post-mortem: Jellyfin outage, 2026-10-04

Status: Jellyfin is still down when this is written. The fix in section 6, step 1, is not applied yet.

All times are AEDT (UTC+11) unless marked UTC.

## 1. Summary

Jellyfin stopped serving at 19:55 after someone played *The Wedding Planner*.
The pod was evicted. The replacement pod then refused to start.

Two faults combined:

- A transcode cache that ran flat out and overflowed its 10 GiB limit.
  This killed the first pod.
- A config volume that was 76% full. Jellyfin refuses to start with less than
  2 GiB free. This kept the second pod from starting.

The second fault existed for weeks. The pod only checks free space at startup,
so nothing failed until the first restart.

## 2. Impact

- Jellyfin has been down since 19:55. Playback and library browsing fail.
- The reports pages, Radarr, Sonarr and downloads were not affected.
- No data was lost. The config volume, the media and the Radarr library are intact.

## 3. Timeline

- 16:50. Radarr adds *The Wedding Planner* with quality profile 1, "Any".
- 16:50. Radarr grabs a 25 GB 1080p BluRay REMUX from NZBgeek.
- 18:56. Radarr imports the file.
- 19:52. Someone plays it. Jellyfin starts an HLS stream with the video copied
  and the DTS-HD audio converted to AAC.
- 19:55:34. Kubernetes evicts the pod: "Usage of EmptyDir volume cache exceeds
  the limit 10Gi". That is 3 minutes 28 seconds after the stream started.
- 19:56 onward. The new pod crashes on every start with
  `/config/data has insufficient free space. Available: 1.9GiB, Required: 2GiB`.

## 4. Root causes

Verified from the pod logs, the Kubernetes events and the Jellyfin config files.

### 4.1 Transcode throttling is off

`encoding.xml` has `EnableThrottling` set to false.

With throttling off, ffmpeg does not wait for the player. It writes segments as
fast as it can read the source. For a copied video stream that is limited only
by the disk and the QNAP. Ten GiB in 3.5 minutes is about 48 MB/s.

A 25 GB film cannot fit in a 10 GiB cache when written this way.
The cache is an `emptyDir` on pinode-01, so the kubelet evicts the pod when it fills.

Earlier today a broken DVD transcode (*Ladyhawke*) ran at about 14 times real time.
That was the same behaviour on a smaller scale.

### 4.2 The config volume was too small for what is stored in it

The volume is 8 GiB and holds 6.0 GiB:

- 3.2 GB of posters and backdrops.
- 2.5 GB of actor photos (13,974 files).
- 0.27 GB of data, including the database (123 MB).

Jellyfin 10.11 checks for 2 GiB free at startup and exits if it is not met.
Free space was 1.9 GiB. The check only runs at startup.
The condition was present for some time, and any restart would have triggered it.
Growth is steady: about 7,600 actor photos in August and 5,800 in September.

### 4.3 The quality profile was not applied to the film

The Wedding Planner has profile 1, "Any". That profile allows remuxes.
The main profile, "Main HD" (profile 9), has Remux-1080p switched off.

67 movies use "Any". The reason profile 1 was chosen for this one is unknown.

## 5. Contributing factors

- **"Main HD" does not limit Bluray-1080p.** WEB and HDTV qualities have a
  100 MB per minute cap. Bluray-1080p and Remux have no cap.
  313 library files are Bluray-1080p. 76 library files are over 12 GB.
  The largest under "Main HD" is 36 GB.
- **Ladyhawke was grabbed under "Main HD" and is 22.7 GB.** That was my choice
  of profile. It passed because of the missing cap above.
- **No alert on volume usage or on a pod that is not Ready.** Nobody was told
  the volume was at 76%, or that Jellyfin had been down for 30 minutes.
- **One replica with a `Recreate` strategy and a ReadWriteOnce volume.**
  Any restart means downtime. This cannot be fixed without moving off RWO.
- **No software transcoding headroom.** Hardware acceleration is `none`
  on a Raspberry Pi, so any real transcode is slow.

## 6. Fix plan

Not applied yet. Each step is separate and can be done in order.

### Restore service

1. Grow `jellyfin-config` from 8 GiB to 20 GiB. Edit `jellyfin-pvcs.yml`,
   merge, let ArgoCD apply. Longhorn storage class allows expansion.
   Both nodes have more than 300 GB free.

### Stop the crash from recurring

2. Turn on transcode throttling and segment deletion in Jellyfin
   (Dashboard, Playback, Transcoding). This keeps the cache to a few minutes of
   video instead of the whole file.
3. Keep the 10 GiB cache. With throttling it holds the largest bitrates
   for several minutes.

### Stop oversized files getting in

4. Set a size cap on Bluray-1080p in Radarr, in MB per minute, matching the WEB cap.
   Decide what to do with the 76 existing files over 12 GB. Do not delete them.
5. Move the 67 "Any" movies to "Main HD", or remove "Any" as an option when adding.

### Detect problems before users do

6. Alert when a volume passes 70% and when any pod is not Ready for 5 minutes.
   The Telegraf and Grafana stack already exists.

### Related cleanup, not part of this outage

7. Refresh actor photos and bios. 4,667 photo links point at a retired TMDb host.
   28,254 of 28,258 people have no bio. This is slow and needs a Jellyfin API key.
   Do it after step 1, because it adds more photos.
8. Playback progress writes fail with `FOREIGN KEY constraint failed`
   (76 errors in two days). Investigate.
9. The *Ladyhawke* DVD folder has wrong metadata. Jellyfin lists only 5 of its
   VOB files and a runtime of about 22 minutes. The replacement download
   makes this less urgent.
10. The `jellyfin-notify` and `download-stall-watch` CronJobs are suspended.
    Decide whether to bring them back.

## 7. What went well

- Radarr, SABnzbd and the reports pages kept working.
- The read-only diagnosis pods did not touch the config volume.
- No media or config was lost.

## 8. Limits of "bullet proof"

Jellyfin runs as one pod with a single-node volume. A node loss or any restart
still means downtime. The steps above make the common failures much less likely
and make the remaining ones fast to recover from. They do not remove them.
