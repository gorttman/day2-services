# Kavita

Bare-install reading server (books/comics/manga) at
https://kavita.i3sec.com.au (internal-only, private-ca TLS via Traefik).
First visit runs Kavita's setup (create the admin account there).

## Library storage
The QNAP books share is mounted **read-only at `/books`** (static
`qnap-books` PV - see day1-foundation apps/qnap-storage). Point Kavita's
library at `/books` in the UI. Config/SQLite stays on local-path.

## Deliberately unconfigured (install-only)
- No library configured inside Kavita yet (UI -> add library -> /books)
- No user accounts
- No EPUB import
- No node affinity yet - see the marker comment in the deployment and
  `components/workload-affinity/`

## Storage - RAM config + NFS backups (pihole pattern)
Kavita's config (internal SQLite DB, ~a few MB plus covers) runs in a
**RAM emptyDir** (1Gi limit). A sidecar tars it to the
`kavita-config-backup` nfs-client PVC hourly (with one-generation
rotation) and again at pod shutdown via preStop; an init container
restores the newest readable backup on start. This keeps SQLite off NFS
without needing local disk, so **the pod is free to float between
nodes** - no nodeSelector. Worst case after an unclean node death: up
to an hour of reading progress lost, falling back to the previous
backup if the newest is torn. (The kavita image still has to fit
pinode-01's 4G tmpfs image store to actually run there.)

## Dependencies
None: no database (SQLite internal), no Redis, no secrets.
