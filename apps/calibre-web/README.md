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

## User accounts: seeded automatically, not the setup wizard (2026-07-18)

`admin` (role 479, all bits except `ROLE_ANONYMOUS`) was created by hand
through calibre-web's own first-run wizard when this was first deployed -
that account and its password are untouched by anything below.

Two more accounts - `gorttman` and `brett` - are created automatically by
a `user-seed` container in the same pod, sourced from
`day1-foundation/apps/cloudflare-tf`'s `warp_authorized_emails` (the only
place in this homelab's code that enumerates actual people; there's no
shared variable between the Terraform and Kubernetes repos, so if that
list ever changes, `calibre-web-user-seed-script.yml`'s `USERS` list has
to be updated by hand to match). No manual account creation, no wizard
click-through.

**How it works**: `calibre-web-user-seed-script.yml`'s `seed_users.py`
runs as a plain long-running container (not an `initContainer` -
`/config/app.db` doesn't exist until calibre-web itself creates it on
first boot, so an init container would just race it). It polls until the
`user` table exists, then `INSERT`s a row per configured user with a
`werkzeug.security.generate_password_hash(pw, method="scrypt")` hash -
confirmed byte-format-identical to what calibre-web's own login checks
against, since it's the same image and the same library calibre-web
itself uses. Idempotent: skips any name that already has a row, so it
never overwrites a password someone's changed since via the UI, and
restarting the pod is harmless.

**Passwords**: randomly generated once (2026-07-18), sealed into
`calibre-web-user-passwords-sealedsecret.yml`. This is intentionally
**password-based login, not passwordless SSO** - `books.i3sec.com.au` is
gated by Cloudflare's mTLS WAF rule (any valid device cert under this
account's CA), not Cloudflare Access, so there's no per-person identity
assertion available to hand calibre-web today. (calibre-web does support
trusting a reverse-proxy identity header for passwordless login -
`config_allow_reverse_proxy_header_login` in `settings` - but wiring that
up would mean adding a Cloudflare Access policy plus a JWT-verifying
proxy in front, similar in shape to `vscode-server`'s PAM-based
`vscode-auth` but Access-based instead. Not built here - out of scope,
deliberately deferred, not an oversight.) To rotate a password: reseal
just that key (`kubeseal --raw --scope strict --namespace calibre-web
--name calibre-web-user-passwords`), and either delete the user's row
from `app.db` first (the seed script won't touch an existing row) or
just change it via the calibre-web UI directly - the sealed value only
matters for the account's *first* creation.

**Roles**: both get `ROLE_READER` (350 = `DOWNLOAD+UPLOAD+EDIT+PASSWD
+EDIT_SHELFS+VIEWER`) - full reader/curator access including changing
their own password, but not `ROLE_ADMIN` (server settings, user
management) or `ROLE_DELETE_BOOKS`. Promote either account via the
calibre-web UI (Admin > Edit User) if that's ever not enough - the seed
script only creates missing rows, so it won't fight a manual role change
on next pod restart.

## Library location: also automated, not the setup wizard (2026-07-18)

Discovered live: logging in with a real seeded account still landed on
calibre-web's "Location of Calibre database" setup screen. Root cause
confirmed directly against `app.db`: `settings.config_calibre_dir` was
blank - nothing in this deployment had ever told calibre-web where the
library actually is. Fixed the same way as user accounts - no manual
UI step.

**Two pieces**:
1. **`library-init` init container** (in `calibre-web-deployment.yml`) -
   creates a real Calibre library (`metadata.db`) at `/books` if one
   doesn't exist yet. Borrows the `books-pipeline` image for this,
   since calibre-web's own image is pure Python with no Calibre CLI at
   all. `calibredb` has no dedicated "create empty library" command;
   `calibredb restore_database --really-do-it --with-library /books` is
   the documented non-interactive workaround. Idempotent - skips if
   `metadata.db` is already there.
2. **`seed_users.py` (extended)** - after seeding accounts, checks
   `settings.config_calibre_dir`; if still blank, sets it to `/books`.

**Why this needs a pod restart, and how that's automated too**:
calibre-web reads `config_calibre_dir` into memory once at process
startup - a direct SQL write from a sidecar doesn't make the
already-running calibre-web process notice, confirmed against
upstream reports of the same behavior. The only way to make it notice,
short of a human clicking Save in Admin > Basic Configuration, is a
fresh boot. So the seed script self-deletes its own pod via the
Kubernetes API (`calibre-web-rbac.yml` grants a dedicated
`calibre-web-seed` ServiceAccount exactly one permission: `delete` on
`pods`, scoped to this namespace only) when it makes that change - the
Deployment controller recreates the pod immediately, and the fresh
calibre-web process reads the now-set path correctly on its own normal
startup. No custom reload logic, just a real restart, triggered
automatically instead of by a human.

**Still true after this fix** (see the known-gap section above): the
library this creates is real and valid, but **empty**. Books already
promoted by `books_pipeline.py` won't appear until the deeper
Postgres/`calibredb` integration gap is resolved - this fix makes
calibre-web *usable* (no setup screen, can upload/browse manually),
not *populated*.

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
