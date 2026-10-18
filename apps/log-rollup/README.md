# log-rollup

Hourly CronJob that turns Loki logs into long-term numbers in InfluxDB
(bucket `log_rollup`, infinite retention). Added 2026-10-18.

Why: Loki keeps logs for 30 days to 13 months (apps/loki/loki-values.yml).
The summaries are tiny, so they outlive the logs.

Runs at minute 7 of every hour and rolls up the previous full hour. Points are
stamped at the start of the hour and re-running overwrites them, so repeats and
backfills are safe.

Measurements (integer fields):
- `log_events` field `count`. Tags: `source` (udm/k8s/host), `class`
  (firewall, error_like, auth_fail, oom, udm_event, wifi_leave), `node`,
  `namespace`, `app`, and for firewall `ruleset`, `action` (drop/allow/default),
  `action_raw`, `in_zone`, `out_zone`, `proto`.
- `log_volume` fields `lines`, `bytes` per signal_type and namespace/node/udm_class.
- `fw_top_src`, `fw_top_dport` top 10 per hour (ruleset, action, src or dport).
- `log_rollup_run` heartbeat each run (points, queries_ok, queries_failed, seconds).

Zones come from the UniFi bridge names: br0 Main, br10 ClusterBackend,
br20 Trusted, br30 Guest, br40 IoT, eth4 WAN. Update `ZONES` in the script if
networks change.

Backfill (needs LOKI_URL, INFLUX_URL, INFLUX_ORG, INFLUX_TOKEN set):
`python3 log_rollup.py --hours 48` rolls the last 48 hours.
Loki must still hold the hours being rolled.
