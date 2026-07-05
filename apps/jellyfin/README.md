# Jellyfin

Bare-install media server at https://jellyfin.i3sec.com.au (internal-only,
private-ca TLS via Traefik). First visit runs Jellyfin's setup wizard.

## Deliberately unconfigured (install-only)
- No library scan paths, no media volume - media storage doesn't exist yet
- No user accounts (create the admin in the first-run wizard)
- No transcoding config
- No node affinity yet - see the marker comment in the deployment and
  `components/workload-affinity/`

## Storage - PLACEHOLDER
Config (2Gi, holds Jellyfin's internal SQLite DB) and cache (5Gi) PVCs sit
on k3s's default `local-path` class: **node-local and non-durable**. The
deployment temporarily hard-pins to k8smaster - the only node with real
disk: on diskless pinode-01, `/var/lib/rancher/k3s` (containerd images
and local-path volumes alike) is a 4G RAM tmpfs, so the jellyfin image
doesn't fit there and PVC data would vanish on reboot. Remove the
nodeSelector together with the storage swap. Swap to
NFS-backed storage once real storage exists - but note SQLite must never
sit directly on NFS (see the pihole gravity.db incident); the config
volume will need the same kind of treatment as pihole or block storage.

## Dependencies
None: no database (SQLite internal), no Redis, no secrets.
