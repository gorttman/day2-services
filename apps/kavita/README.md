# Kavita

Bare-install reading server (books/comics/manga) at
https://kavita.i3sec.com.au (internal-only, private-ca TLS via Traefik).
First visit runs Kavita's setup (create the admin account there).

## Deliberately unconfigured (install-only)
- No library paths, no media volume - media storage doesn't exist yet
- No user accounts
- No EPUB import
- No node affinity yet - see the marker comment in the deployment and
  `components/workload-affinity/`

## Storage - PLACEHOLDER
Single config PVC (2Gi, holds Kavita's internal SQLite DB) on k3s's
default `local-path` class: **node-local and non-durable**. Same caveats
and the same temporary k8smaster nodeSelector as apps/jellyfin - see that
README for the full explanation (pinode-01's k3s dir is a 4G RAM tmpfs).
Remove the nodeSelector together with the storage swap, and never put the
SQLite config volume directly on NFS.

## Dependencies
None: no database (SQLite internal), no Redis, no secrets.
