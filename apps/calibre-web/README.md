# calibre-web

Reading server (books/comics) at `https://books.i3sec.com.au` (public,
via Cloudflare Tunnel) and `https://calibre-web.i3sec.com.au`
(internal-only, private-ca TLS via Traefik) — same dual-hostname
pattern kavita used. Replaces kavita entirely (2026-07-17) - see
`~/gm-dev/homelab-book/chapters/002-kavita-to-calibre-web.md` for the
full story of why.

## Image

`lscr.io/linuxserver/calibre-web:0.6.26-ls391` - confirmed real arm64
manifest (checked via `docker manifest inspect`, not just the tag
existing). The optional `DOCKER_MODS=linuxserver/mods:universal-calibre`
conversion mod is deliberately **not** set - it's x86-64 only per
linuxserver's own docs, and unneeded regardless: `books-pipeline`
(prompt 3/4) already does all real Calibre conversion work in its own
container. calibre-web here is purely a reading/browsing UI.

## Storage

- **`/books`** - `calibre-web-books` PVC, `ReadWriteMany`, binds the
  same static `qnap-books` PV kavita used (`day1-foundation`
  `apps/qnap-storage`). **Read-write**, unlike kavita's read-only mount
  - calibre-web writes back to `metadata.db` (tags, read status,
  custom columns) as well as reading.
- **`/config`** - RAM `emptyDir` + hourly tar backup to
  `calibre-web-config-backup` (`nfs-client` PVC), same pihole/kavita/
  grafana pattern: SQLite must never sit directly on NFS. Init
  container restores the newest readable backup on start; sidecar
  backs up hourly and again on `preStop`. Worst case after an unclean
  node death: up to an hour of settings/reading-progress lost.

## PUID/PGID: 10001, not linuxserver's default 1000

Deliberately matches `books-pipeline`'s non-root UID - both containers
need to read *and* write the same library files and `metadata.db`, so
they need to agree on ownership rather than fighting over it via
mismatched UIDs.

## ⚠️ Known gap: this library isn't actually a Calibre library yet

**calibre-web requires a real Calibre library to function** - a
directory containing `metadata.db`, which Calibre itself creates and
maintains via `calibredb add` (or the desktop GUI's own add-books
flow). It can bootstrap a fresh one as books are uploaded *through its
own UI*, but it does not "adopt" a folder of pre-existing files dropped
in by an external process.

`books_pipeline.py`'s `promote()` (prompt 4) does exactly that: a plain
`shutil.copy2` + rename into `library/{books,comics}/<Author>/<Title>.ext`,
with dedup/metadata tracked in a **separate Postgres `fingerprints`
table** - not `calibredb add`, no `metadata.db` anywhere in the tree.
This was a deliberate, reasonable choice for the pipeline (Postgres is
a better fit for the fuzzy-matching dedup logic than Calibre's own
database), made independently of - and before - the decision to use
calibre-web as the reading UI. The two designs don't currently talk to
each other.

**Practical effect**: books promoted by `books_pipeline.py` will sit in
`/books` as real files, correctly organized, correctly deduped in
Postgres - but calibre-web will not see them as library entries until
something creates the `metadata.db` calibre-web actually reads from.

**Not fixed here** - flagging clearly rather than silently deploying
something that looks done but won't actually show any books. Options,
not yet decided:
1. Change `books_pipeline.py`'s `promote()` to shell out to
   `calibredb add` instead of (or alongside) the current move
   mechanic, maintaining both a Calibre-native library and the Postgres
   fingerprints table.
2. Point calibre-web at a library location it initializes itself, and
   have the pipeline promote into *that* structure rather than a bare
   folder tree.
3. Accept the split for now (Postgres for dedup, something else
   entirely for calibre-web) and treat this as two genuinely separate
   concerns rather than forcing them to share a filesystem tree.

Worth resolving before this deployment is actually useful for reading
- not before it's safe to apply (it's harmless either way, just
possibly empty).

## Migration from kavita (2026-07-17)

Kavita was genuinely install-only - no library ever configured, no
user accounts, no reading history (confirmed via its own README and a
live cluster check immediately before removal). Nothing was migrated
because there was nothing to migrate.

**Two real gotchas hit during the actual teardown, not just anticipated
ones - recorded here since they'll recur for any future app removal in
this repo:**

1. **`qnap-books`'s `Retain` reclaim policy** meant kavita's PVC
   deletion left the PV as `Released`, not `Available` - it still
   carried a `claimRef` pointing at the deleted PVC. A patch
   (`kubectl patch pv qnap-books --type merge -p '{"spec":{"claimRef": null}}'`)
   was needed before `calibre-web-books` could bind to it. Anticipated
   in planning, confirmed exactly as expected in practice.
2. **Not anticipated**: removing `kavita/kavita-app.yml` from
   `apps/kustomization.yml` deleted the `kavita` Argo CD `Application`
   object itself (via the parent app-of-apps' own sync), but kavita's
   `Application` had never been given the
   `resources-finalizer.argocd.argoproj.io` finalizer. That finalizer
   is what makes Argo CD cascade-delete an Application's own managed
   resources when the Application object is deleted - without it,
   deleting the Application just **orphans** everything it created.
   Result: kavita's namespace, pod, PVCs, and both Ingresses were all
   still live and serving traffic well after the "removal" had merged
   and synced - including its `books-ingress`, which briefly coexisted
   with calibre-web's own Ingress claiming the identical
   `books.i3sec.com.au` host. Fixed with a direct
   `kubectl delete namespace kavita`, which cascades properly on its
   own. Worth remembering for next time: `prune: true` only prunes
   resources *removed from an Application's own manifest set* while
   the Application itself survives - it does not cover the Application
   object being deleted out from under its own resources. Any future
   app-removal in this repo should add the cascade finalizer to the
   `Application` *before* relying on deleting it to clean up, not
   discover the gap afterward.
