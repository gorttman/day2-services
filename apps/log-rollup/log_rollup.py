#!/usr/bin/env python3
"""Hourly rollup of Loki logs into InfluxDB (bucket log_rollup).

For each full hour it asks Loki a fixed set of count questions and writes the
answers as Influx points stamped at the START of that hour. Re-running an hour
overwrites the same points, so it is safe to repeat or backfill.

Usage:  log_rollup.py [--hours N] [--end-hour ISO]   (default: the last full hour)
        --hours N       roll up N hours ending at --end-hour (backfill)
Measurements (all fields are integers):
  log_events        count of matching lines per hour.
                    tags: source, class, node, namespace, app, ruleset, action,
                          action_raw, in_zone, out_zone, proto
  log_volume        lines + bytes per source/namespace/node (shows tier sizes)
  fw_top_src        top 10 firewall source IPs per hour (ruleset, action, src)
  fw_top_dport      top 10 destination ports per hour (ruleset, action, dport)
  fw_discovery      top 20 broadcast/multicast senders per hour (in_zone, src, dport);
                    excluded from log_events/fw_top_* so they do not swamp real events
  log_rollup_run    one heartbeat point per run (queries ok/failed, points written)
"""
import argparse, json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

LOKI = os.environ.get("LOKI_URL", "http://loki.loki.svc.cluster.local:3100")
INFLUX = os.environ["INFLUX_URL"]
ORG = os.environ["INFLUX_ORG"]
TOKEN = os.environ["INFLUX_TOKEN"]
BUCKET = "log_rollup"

# UniFi bridge -> zone name (br<vlan>; br0 is the untagged Default network).
ZONES = {"br0": "Main", "br10": "ClusterBackend", "br20": "Trusted",
         "br30": "Guest", "br40": "IoT", "eth4": "WAN", "": "none"}
ACTIONS = {"D": "drop", "A": "allow", "RET": "default", "B": "block", "R": "reject"}

FW_BASE = (r'{app="udm", udm_class="chatter"} |~ `Gateway \[[A-Z_0-9]+-[A-Z]+-` '
           r'| regexp `Gateway \[(?P<ruleset>[A-Z_0-9]+)-(?P<action>[A-Z]+)-\d+\].* '
           r'IN=(?P<in_if>\S*) OUT=(?P<out_if>\S*) .*SRC=(?P<src>\S+) DST=(?P<dst>\S+) .*'
           r'PROTO=(?P<proto>\S+)(?:.* DPT=(?P<dport>\d+))?`')
# Discovery chatter: anything sent to a broadcast or multicast address (Tuya 6667,
# Roborock, UniFi 10001/48000 ...). Kept out of the firewall counts and summarised
# on its own as fw_discovery so a change is still visible.
DISC = r'255[.]255[.]255[.]255|[0-9]+[.][0-9]+[.][0-9]+[.]255|2(2[4-9]|3[0-9])[.][0-9.]+'
FW = f"{FW_BASE} | dst !~ `{DISC}`"
FWD = f"{FW_BASE} | dst =~ `{DISC}`"

# (measurement, class, source, LogQL selector+filters, group-by labels, fixed tags)
COUNTS = [
    ("error_like", "k8s", '{signal_type="container"} |~ `(?i)(level=error|"level":"error"|\\berror\\b|\\bfatal\\b|panic)`',
     ["namespace", "app"]),
    ("auth_fail", "host", '{signal_type="host"} |~ `(Failed password|Invalid user|authentication failure|Connection closed by authenticating user)`',
     ["node"]),
    ("oom", "host", '{signal_type="host"} |~ `(Out of memory|oom-kill|Killed process|earlyoom.*(sending|killing))`',
     ["node"]),
    ("udm_event", "udm", '{app="udm", udm_class="event"}', []),
    ("wifi_leave", "udm", '{app="udm"} |~ `(EVENT_STA_LEAVE|disassociated)`', []),
]
FW_GROUP = ["ruleset", "action", "in_if", "out_if", "proto"]

def fw(keep, base=None):
    # `keep` trims the extracted labels to the ones being grouped on; without it
    # every per-line src/dst/port combination is its own series and Loki hits
    # its 500-series-per-query limit.
    return f"{base or FW} | keep {', '.join(keep)}"

def http(url, data=None, headers=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        return urllib.request.urlopen(req, timeout=timeout).read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:160]}") from None

def loki_vector(query, at):
    q = urllib.parse.urlencode({"query": query, "time": str(int(at.timestamp())), "limit": "5000"})
    d = json.loads(http(f"{LOKI}/loki/api/v1/query?{q}"))
    return d["data"]["result"]

def esc(v):
    return str(v).replace("\\", "\\\\").replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")

def line(meas, tags, fields, ts):
    t = ",".join(f"{k}={esc(v)}" for k, v in sorted(tags.items()) if v not in ("", None))
    f = ",".join(f"{k}={int(v)}i" for k, v in fields.items())
    return f"{meas},{t} {f} {ts}" if t else f"{meas} {f} {ts}"

def roll_hour(start):
    end = start + timedelta(hours=1)
    ts = int(start.timestamp())
    out, ok, bad = [], 0, 0
    def run(q):
        nonlocal ok, bad
        try:
            r = loki_vector(q, end); ok += 1; return r
        except Exception as e:
            bad += 1; print(f"query failed: {e}: {q[:90]}", file=sys.stderr); return []

    for cls, source, sel, by in COUNTS:
        g = f" by ({', '.join(by)})" if by else ""
        for s in run(f"sum{g} (count_over_time({sel} [1h]))"):
            m = s["metric"]; n = float(s["value"][1])
            if n > 0:
                out.append(line("log_events", {"source": source, "class": cls, **{k: m.get(k, "") for k in by}}, {"count": n}, ts))

    # Firewall: by rule set / action / zones / protocol.
    for s in run(f"sum by ({', '.join(FW_GROUP)}) (count_over_time({fw(FW_GROUP)} [1h]))"):
        m = s["metric"]; n = float(s["value"][1])
        if n <= 0: continue
        out.append(line("log_events", {
            "source": "udm", "class": "firewall", "ruleset": m.get("ruleset"),
            "action": ACTIONS.get(m.get("action"), m.get("action")), "action_raw": m.get("action"),
            "in_zone": ZONES.get(m.get("in_if"), m.get("in_if")), "out_zone": ZONES.get(m.get("out_if"), m.get("out_if")),
            "proto": m.get("proto")}, {"count": n}, ts))
    for meas, key in (("fw_top_src", "src"), ("fw_top_dport", "dport")):
        q = f"topk(10, sum by (ruleset, action, {key}) (count_over_time({fw(['ruleset', 'action', key])} [1h])))"
        for s in run(q):
            m = s["metric"]; n = float(s["value"][1])
            if n > 0 and m.get(key):
                out.append(line(meas, {"ruleset": m.get("ruleset"), "action": ACTIONS.get(m.get("action"), m.get("action")), key: m[key]}, {"count": n}, ts))

    # Discovery chatter (broadcast/multicast), top 20 per hour by zone/source/port.
    dq = f"topk(20, sum by (in_if, src, dport) (count_over_time({fw(['in_if', 'src', 'dport'], FWD)} [1h])))"
    for s in run(dq):
        m = s["metric"]; n = float(s["value"][1])
        if n > 0 and m.get("src"):
            out.append(line("fw_discovery", {"in_zone": ZONES.get(m.get("in_if"), m.get("in_if")), "src": m["src"], "dport": m.get("dport")}, {"count": n}, ts))

    # Volume per source: shows how big each retention tier really is.
    for sel, by in (('{signal_type="container"}', "namespace"), ('{signal_type="host"}', "node"), ('{signal_type="network"}', "udm_class")):
        lines_ = {tuple(sorted(s["metric"].items())): float(s["value"][1]) for s in run(f"sum by ({by}) (count_over_time({sel} [1h]))")}
        bytes_ = {tuple(sorted(s["metric"].items())): float(s["value"][1]) for s in run(f"sum by ({by}) (bytes_over_time({sel} [1h]))")}
        sig = sel.split('"')[1]
        for k, n in lines_.items():
            out.append(line("log_volume", {"signal_type": sig, **dict(k)}, {"lines": n, "bytes": bytes_.get(k, 0)}, ts))
    return out, ok, bad

def write(lines):
    if not lines: return
    url = f"{INFLUX}/api/v2/write?org={urllib.parse.quote(ORG)}&bucket={BUCKET}&precision=s"
    http(url, data="\n".join(lines).encode(), headers={"Authorization": f"Token {TOKEN}", "Content-Type": "text/plain; charset=utf-8"})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=1)
    ap.add_argument("--end-hour", help="ISO time (UTC) the last rolled hour ends at; default: top of this hour")
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    end = datetime.fromisoformat(a.end_hour).astimezone(timezone.utc) if a.end_hour else now.replace(minute=0, second=0, microsecond=0)
    t0 = time.time(); total = ok = bad = 0
    for i in range(a.hours, 0, -1):
        start = end - timedelta(hours=i)
        pts, o, b = roll_hour(start)
        write(pts); total += len(pts); ok += o; bad += b
        print(f"{start.isoformat()} points={len(pts)} queries_ok={o} failed={b}")
    write([line("log_rollup_run", {}, {"points": total, "queries_ok": ok, "queries_failed": bad, "seconds": time.time() - t0}, int(time.time()))])
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
