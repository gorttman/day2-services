# Home Assistant

Home Assistant core + Mosquitto MQTT broker at
`https://homeassistant.i3sec.com.au` (internal-only, private-ca cert,
DNS in dns-conf).

## Architecture

- **Recorder → shared Postgres** (`homeassistant` DB in the `postgres`
  namespace instance). History/statistics are the hot, write-heavy
  state; putting them in Postgres keeps SQLite off NFS and lets the pod
  float. Connection URL (with credentials) is the
  `homeassistant-recorder` SealedSecret, referenced from
  `configuration.yaml` via `!env_var`.
- **/config in a RAM emptyDir** (pihole/kavita/grafana pattern): init
  container restores the newest readable tar from the
  `homeassistant-config-backup` PVC (nfs-client), sidecar re-tars
  hourly + on shutdown. Worst case after an unclean node death: ≤1h of
  config/UI edits lost; recorder history is never at risk.
- **`configuration.yaml` is git-owned**: the init container copies it
  from the `homeassistant-config` ConfigMap over the restored backup on
  every start. Edit it here, not in the UI. UI-driven state
  (automations, dashboards, integrations, users) lives in
  `automations.yaml`/`scripts.yaml`/`scenes.yaml`/`.storage/` and
  persists via the backups.
- **Soft affinity to lane=infrastructure**: the HA image (~1.5GB) does
  not fit pinode-01's 4G tmpfs image store. Soft only — see the
  deployment comment.
- **Mosquitto**: auth required; hashed password file is generated at
  pod start from the `mosquitto-users` SealedSecret (accounts:
  `homeassistant`, plus `zigbee2mqtt` reserved for future hardware).
  ClusterIP only while all clients are in-cluster — needs a MetalLB IP
  if LAN devices ever publish directly.

## First-run setup (manual, once)

1. Browse to https://homeassistant.i3sec.com.au → onboarding wizard
   (owner account, name, location, units).
2. Verify recorder: Developer tools → Statistics should populate; or
   check logs for `recorder` errors
   (`kubectl logs -n homeassistant deploy/homeassistant -c homeassistant`).
3. Add the MQTT integration when first needed: broker
   `mosquitto.homeassistant.svc.cluster.local`, port 1883, user
   `homeassistant`, password from the sealed secret.
4. Add devices by hostname/IP (no mDNS/SSDP discovery across the pod
   network — this install deliberately avoids hostNetwork).

## Notes

- HA version is pinned (`2026.6.4`). When bumping, check the release
  notes for recorder schema migrations before jumping to a fresh
  `.0`/`.1` — Postgres migrations get less soak time than SQLite.
- Zigbee2MQTT is intentionally not installed: no coordinator hardware
  yet. When one arrives it becomes its own Deployment here, pinned to
  whichever node has the USB stick (or ser2net to avoid the pin), and
  the reserved MQTT account comes into play.
