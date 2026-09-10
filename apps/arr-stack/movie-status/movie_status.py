#!/usr/bin/env python3
"""One on-demand status board for the whole media pipeline.

Same shape as backup-dashboard and for the same reason: every request
re-reads live state and renders fresh, rather than a CronJob writing a
static file whose age you then have to trust. Nothing is cached and
nothing is scheduled - the Refresh button is the whole mechanism.

Self-hosted rather than a claude.ai artifact because the data lives on
the LAN: the *arrs are only reachable in-cluster, and a hosted page
cannot fetch them. That decision was already made once for
backup-dashboard.

Five panels, in the order you actually want them:

  health    is anything stuck right now - the stall watcher's own
            verdict, plus whatever the *arrs have flagged as needing a
            person. Stuck queue items never clear themselves.
  movies    /movies is the upgrade backfill: every title already has a
            file and the job is replacing bad copies. /movies-bulk is
            the midday-movie library: titles with no copy at all,
            driven by hand, so it gets a measured rate and no fake ETA.
  tv        legacy XviD/.avi episodes - the ones with no hardware
            decoder on the TV, which force Jellyfin to transcode.
  jobs      what runs unattended, when it last ran, and whether it has
            retired itself.

Deliberately does NOT ask qBittorrent anything: its WebUI refuses
unauthenticated calls from outside its own pod (LocalHostAuth=false
covers only genuine 127.0.0.1, so the ClusterIP Service answers 403).
The *arr queues carry protocol per item, which gives the torrent-vs-
usenet split without needing those credentials, and measures what
actually matters - whether work is finishing.
"""
import datetime
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ARRS = {
    "radarr":   ("/app-config/radarr/config.xml",   "http://radarr.arr-stack.svc.cluster.local:7878"),
    "sonarr":   ("/app-config/sonarr/config.xml",   "http://sonarr.arr-stack.svc.cluster.local:8989"),
    "whisparr": ("/app-config/whisparr/config.xml", "http://whisparr.arr-stack.svc.cluster.local:6969"),
}
SAB_INI = os.environ.get("SAB_INI", "/app-config/sabnzbd/sabnzbd.ini")
SAB_URL = os.environ.get("SAB_URL", "http://sabnzbd.arr-stack.svc.cluster.local:8080")
MAIN_ROOT = os.environ.get("MAIN_ROOT", "/movies")
BULK_ROOT = os.environ.get("BULK_ROOT", "/movies-bulk")
TAG_LABEL = os.environ.get("TAG_LABEL", "upgrade-searched")
MAIN_BATCH = int(os.environ.get("MAIN_BATCH", "25"))
BULK_BATCH = int(os.environ.get("BULK_BATCH", "50"))
BULK_STATE = os.environ.get("BULK_STATE", "/state/bulk_backfill_state.json")
STALL_STATE = os.environ.get("STALL_STATE", "/vault/inbox/media-pipeline-alerts/.stall_state.json")
CRONJOBS = [c for c in os.environ.get(
    "CRONJOBS", "radarr-upgrade-search,radarr-upgrade-digest,download-stall-watch").split(",") if c]
PORT = int(os.environ.get("PORT", "8080"))
SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"
HISTORY_PAGES = int(os.environ.get("HISTORY_PAGES", "12"))
LEGACY_CODECS = {"xvid", "divx", "mpeg4", "msmpeg4", "wmv3", "vc1"}


def arr(app, path):
    config, base = ARRS[app]
    key = ET.parse(config).getroot().findtext("ApiKey")
    req = urllib.request.Request("%s/api/v3/%s" % (base, path), headers={"X-Api-Key": key})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read().decode()
    return json.loads(raw) if raw.strip() else {}


def arr_queue(app):
    records, page = [], 1
    while True:
        q = arr(app, "queue?page=%d&pageSize=200" % page)
        records += q.get("records", [])
        if len(records) >= q.get("totalRecords", 0) or not q.get("records"):
            return records
        page += 1


def cutoff_index(profile):
    pos, cut = {}, None
    for i, item in enumerate(profile["items"]):
        if item.get("quality"):
            pos[item["quality"]["id"]] = i
            if item["quality"]["id"] == profile["cutoff"]:
                cut = i
        else:
            if item.get("id") == profile["cutoff"]:
                cut = i
            for sub in item.get("items", []):
                pos[sub["quality"]["id"]] = i
    return pos, cut


def cronjob_state(name):
    try:
        with open(SA_DIR + "/token") as f:
            token = f.read().strip()
        with open(SA_DIR + "/namespace") as f:
            ns = f.read().strip()
        req = urllib.request.Request(
            "https://kubernetes.default.svc/apis/batch/v1/namespaces/%s/cronjobs/%s" % (ns, name),
            headers={"Authorization": "Bearer " + token})
        with urllib.request.urlopen(
                req, context=ssl.create_default_context(cafile=SA_DIR + "/ca.crt"), timeout=15) as r:
            cj = json.load(r)
        return {"name": name, "found": True,
                "suspended": bool(cj["spec"].get("suspend")),
                "schedule": cj["spec"].get("schedule"),
                "lastRun": cj.get("status", {}).get("lastScheduleTime")}
    except Exception as e:
        return {"name": name, "found": False, "error": str(e)[:100]}


def sab():
    try:
        key = None
        with open(SAB_INI) as f:
            for line in f:
                if line.startswith("api_key"):
                    key = line.split("=", 1)[1].strip()
                    break
        if not key:
            return {"ok": False, "error": "no api_key"}
        url = "%s/api?%s" % (SAB_URL, urllib.parse.urlencode(
            {"mode": "queue", "output": "json", "apikey": key}))
        with urllib.request.urlopen(url, timeout=30) as r:
            q = json.load(r)["queue"]
        by = {}
        for s in q.get("slots", []):
            by[s.get("status", "?")] = by.get(s.get("status", "?"), 0) + 1
        return {"ok": True, "speed": q.get("speed"), "paused": q.get("paused"),
                "jobs": len(q.get("slots", [])), "byStatus": by,
                "mbLeft": float(q.get("mbleft") or 0)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def in_flight(app, recs):
    """What is actually moving right now, newest progress first.

    "43 items queued" answers nothing on its own - the question is
    always which ones, and whether any of them are stuck at 0%. Size
    and sizeleft give real progress; estimatedCompletionTime is
    Radarr's own guess and is often absent, so it is passed through
    rather than recomputed.
    """
    out = []
    for r in recs:
        if r.get("status") != "downloading":
            continue
        size = float(r.get("size") or 0)
        left = float(r.get("sizeleft") or 0)
        out.append({
            "app": app,
            "title": (r.get("title") or "?")[:95],
            "pct": round(100 * (size - left) / size, 1) if size else 0,
            "gb": round(size / 1e9, 2),
            "protocol": r.get("protocol"),
            "eta": r.get("estimatedCompletionTime"),
        })
    out.sort(key=lambda x: -x["pct"])
    return out


def flagged_of(recs):
    out = []
    for r in recs:
        if r.get("trackedDownloadStatus") in ("warning", "error"):
            msgs = [m["messages"][0] for m in r.get("statusMessages", []) if m.get("messages")]
            out.append({"title": (r.get("title") or "?")[:90],
                        "status": r.get("status"),
                        "why": (msgs[0] if msgs else r.get("status", "")) [:130]})
    return out


def movie_side():
    profiles = {p["id"]: p for p in arr("radarr", "qualityprofile")}
    cutoffs = {pid: cutoff_index(p) for pid, p in profiles.items()}
    tag_id = next((t["id"] for t in arr("radarr", "tag") if t["label"] == TAG_LABEL), None)
    movies = arr("radarr", "movie")
    roots = {r["path"]: r for r in arr("radarr", "rootfolder")}
    queue = arr_queue("radarr")

    now = datetime.datetime.now(datetime.timezone.utc)
    day = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    week = (now - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hist, page = [], 1
    while page <= HISTORY_PAGES:
        h = arr("radarr", "history?page=%d&pageSize=250&sortKey=date&sortDirection=descending" % page)
        recs = h.get("records", [])
        hist += recs
        if not recs or len(hist) >= h.get("totalRecords", 0):
            break
        page += 1

    def below(m):
        prof = profiles.get(m["qualityProfileId"])
        if prof is None:
            return False
        pos, cut = cutoffs[m["qualityProfileId"]]
        i = pos.get(m["movieFile"]["quality"]["quality"]["id"])
        return i is not None and i < cut

    def side(root, mode):
        mine = {m["id"]: m for m in movies if m.get("rootFolderPath") == root}
        met = withfile = 0
        on_disk = 0
        tiers = {"1": 0, "2": 0, "3": 0}
        for m in mine.values():
            if not m.get("hasFile"):
                continue
            withfile += 1
            on_disk += int(m["movieFile"].get("size") or 0)
            if not below(m):
                met += 1
            else:
                r = m["movieFile"]["quality"]["quality"]["resolution"]
                tiers[str(1 if r < 720 else (2 if r == 720 else 3))] += 1
        qm = [r for r in queue if r.get("movieId") in mine]
        hm = [x for x in hist if x["movieId"] in mine]
        imported = [x for x in hm if x["eventType"] == "downloadFolderImported"]
        if mode == "upgrade":
            searched = sum(1 for m in mine.values()
                           if tag_id is not None and tag_id in m.get("tags", []))
            remaining = sum(1 for m in mine.values()
                            if m.get("hasFile") and m.get("isAvailable", True)
                            and (tag_id is None or tag_id not in m.get("tags", []))
                            and profiles.get(m["qualityProfileId"], {}).get("upgradeAllowed")
                            and below(m))
            nights = (remaining + MAIN_BATCH - 1) // MAIN_BATCH
            eta = (datetime.date.today() + datetime.timedelta(days=nights)).isoformat() if nights else None
        else:
            try:
                with open(BULK_STATE) as f:
                    searched = len(json.load(f).get("searched", []))
            except Exception:
                searched = None
            remaining = len(mine) - withfile
            nights = eta = None
        return {
            "root": root, "mode": mode, "titles": len(mine), "withFile": withfile,
            "meetCutoff": met, "belowCutoff": sum(tiers.values()), "tiers": tiers,
            "searched": searched, "remaining": remaining,
            "replaced": sum(1 for x in hm if x["eventType"] == "movieFileDeleted"
                            and x.get("data", {}).get("reason") == "Upgrade"),
            "onDisk": on_disk,
            "queue": {"total": len(qm),
                      "downloading": sum(1 for r in qm if r.get("status") == "downloading"),
                      "queued": sum(1 for r in qm if r.get("status") != "downloading"),
                      "inFlightBytes": sum(int(r.get("size") or 0) for r in qm),
                      "torrent": sum(1 for r in qm if r.get("protocol") == "torrent"),
                      "usenet": sum(1 for r in qm if r.get("protocol") == "usenet")},
            "imported24h": sum(1 for x in imported if x["date"] >= day),
            "imported7d": sum(1 for x in imported if x["date"] >= week),
            "failed7d": sum(1 for x in hm if x["eventType"] == "downloadFailed" and x["date"] >= week),
            "recent": [{"title": mine[x["movieId"]]["title"], "year": mine[x["movieId"]].get("year"),
                        "quality": x["quality"]["quality"]["name"], "date": x["date"]}
                       for x in imported[:10]],
            "batch": MAIN_BATCH if mode == "upgrade" else BULK_BATCH,
            "nights": nights, "eta": eta,
        }

    return (side(MAIN_ROOT, "upgrade"), side(BULK_ROOT, "missing"),
            round(roots.get(MAIN_ROOT, {}).get("freeSpace", 0) / 1e12, 2),
            flagged_of(queue), len(queue), in_flight("radarr", queue))


def tv_side():
    series = arr("sonarr", "series")
    profiles = {p["id"]: p for p in arr("sonarr", "qualityprofile")}
    queue = arr_queue("sonarr")
    shows = []
    legacy_total = ep_total = 0
    on_disk = [0]
    for s in series:
        try:
            files = arr("sonarr", "episodefile?seriesId=%d" % s["id"])
        except Exception:
            continue
        legacy = [f for f in files
                  if ((f.get("mediaInfo") or {}).get("videoCodec", "") or "").lower() in LEGACY_CODECS]
        ep_total += len(files)
        legacy_total += len(legacy)
        on_disk[0] += sum(int(f.get("size") or 0) for f in files)
        if legacy:
            shows.append({"title": s["title"], "legacy": len(legacy), "files": len(files),
                          "profile": profiles.get(s["qualityProfileId"], {}).get("name", "?"),
                          "upgradeAllowed": bool(profiles.get(s["qualityProfileId"], {}).get("upgradeAllowed"))})
    shows.sort(key=lambda x: -x["legacy"])
    return {
        "series": len(series), "episodeFiles": ep_total,
        "legacyFiles": legacy_total, "shows": shows[:12],
        "onDisk": on_disk[0],
        "queue": {"total": len(queue),
                  "downloading": sum(1 for r in queue if r.get("status") == "downloading"),
                  "queued": sum(1 for r in queue if r.get("status") != "downloading"),
                  "inFlightBytes": sum(int(r.get("size") or 0) for r in queue),
                  "torrent": sum(1 for r in queue if r.get("protocol") == "torrent"),
                  "usenet": sum(1 for r in queue if r.get("protocol") == "usenet")},
        "flagged": flagged_of(queue),
        "inFlight": in_flight("sonarr", queue),
    }


def health():
    stall = {}
    try:
        with open(STALL_STATE) as f:
            st = json.load(f)
        for app, v in (st.get("previous") or {}).items():
            stall[app] = {"stalled": bool((st.get("stalled") or {}).get(app)),
                          "strikes": (st.get("strikes") or {}).get(app, 0),
                          "items": v.get("items"), "bytesLeft": v.get("bytesLeft")}
        checked = st.get("checkedAt")
    except Exception:
        checked = None
    return {"stall": stall, "checkedAt": checked}


def collect():
    main, bulk, free, rflag, rq, rflight = movie_side()
    tv = tv_side()
    try:
        wq = arr_queue("whisparr")
        wflag = flagged_of(wq)
        wflight = in_flight("whisparr", wq)
    except Exception:
        wq, wflag, wflight = [], [], []
    return {
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "freeTB": free,
        "health": health(),
        "sab": sab(),
        "needsPerson": rflag + tv["flagged"] + wflag,
        "inFlight": sorted(rflight + tv["inFlight"] + wflight, key=lambda x: -x["pct"]),
        "queues": {"radarr": rq, "sonarr": tv["queue"]["total"], "whisparr": len(wq)},
        "groups": groups(main, bulk, tv),
        "main": main, "bulk": bulk, "tv": tv,
        "jobs": [cronjob_state(c) for c in CRONJOBS],
    }


def groups(main, bulk, tv):
    """The four things being worked on, in one shape.

    Every group answers the same four questions - how far through, how
    much is queued, how much is downloading, how much is finished - so
    the board can render them identically and they can be compared at a
    glance. "Finished" means the same thing in each: a file that is on
    disk and is what we want.

    Regular movies and replacements are split deliberately. They share a
    root folder but are different jobs: one is "do we have it at all",
    the other is "is the copy any good", and merging them hides whichever
    is going badly.
    """
    return [
        {"key": "movies", "name": "Regular movies",
         "what": "titles at Bluray-1080p", "root": main["root"],
         "done": main["meetCutoff"], "total": main["titles"],
         "queued": main["queue"]["queued"], "downloading": main["queue"]["downloading"],
         "finished": main["meetCutoff"],
         "onDisk": main["onDisk"], "inFlight": main["queue"]["inFlightBytes"],
         "note": "Every title already has a file; this is how many are at the quality we want."},
        {"key": "replacements", "name": "Replacements",
         "what": "poor copies replaced", "root": main["root"],
         "done": main["replaced"], "total": main["replaced"] + main["queue"]["total"] + main["remaining"],
         "queued": main["queue"]["queued"], "downloading": main["queue"]["downloading"],
         "finished": main["replaced"],
         "onDisk": None, "inFlight": main["queue"]["inFlightBytes"],
         "eta": main["eta"], "nights": main["nights"],
         "note": "Runs itself nightly. A title that went 480p to WEB 1080p counts as remaining "
                 "but will not be searched again."},
        {"key": "midday", "name": "Midday movies",
         "what": "titles found", "root": bulk["root"],
         "done": bulk["withFile"], "total": bulk["titles"],
         "queued": bulk["queue"]["queued"], "downloading": bulk["queue"]["downloading"],
         "finished": bulk["withFile"],
         "onDisk": bulk["onDisk"], "inFlight": bulk["queue"]["inFlightBytes"],
         "note": "Titles with no copy at all. Only moves when bulk_backfill.py is run."},
        {"key": "tv", "name": "TV",
         "what": "episodes on a modern codec", "root": "/tv",
         "done": tv["episodeFiles"] - tv["legacyFiles"], "total": tv["episodeFiles"],
         "queued": tv["queue"]["queued"], "downloading": tv["queue"]["downloading"],
         "finished": tv["episodeFiles"] - tv["legacyFiles"],
         "onDisk": tv["onDisk"], "inFlight": tv["queue"]["inFlightBytes"],
         "note": "The remainder is XviD/DivX, which has no hardware decoder on the TV and "
                 "forces Jellyfin to transcode."},
    ]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        raw = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith("/api/status"):
            try:
                self._send(200, json.dumps(collect()), "application/json")
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)[:300]}), "application/json")
        elif self.path == "/healthz":
            self._send(200, "ok", "text/plain")
        else:
            with open("/app/index.html") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")


if __name__ == "__main__":
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
