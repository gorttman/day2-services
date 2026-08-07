# arr-stack

Media automation stack behind a PIA VPN via WireGuard (Gluetun -
switched from OpenVPN 2026-07-23, see "LIVE 2026-07-23" below).
Originally install-only (see below) - extended 2026-07-21 to also
cover books via LazyLibrarian, feeding the same `books-pipeline`
import path every other book-arrival route already uses.

| App | UI | Container port |
|---|---|---|
| Sonarr 4.0.19 | https://sonarr.i3sec.com.au | 8989 |
| Radarr 6.2.1 | https://radarr.i3sec.com.au | 7878 |
| Prowlarr 2.4.0 | https://prowlarr.i3sec.com.au | 9696 |
| SABnzbd 5.0.4 | https://sabnzbd.i3sec.com.au | 8080 |
| Bazarr 1.6.0 | https://bazarr.i3sec.com.au | 6767 |
| JDownloader2 v26.03.1 | https://jdownloader.i3sec.com.au | 5800 |
| LazyLibrarian a7c70e36-ls311 | https://lazylibrarian.i3sec.com.au | 5299 |

## Books extension (2026-07-21)

LazyLibrarian joins the shared pod as an eighth app container. Three pieces:

1. **LazyLibrarian itself** - mounts `books-pipeline`'s own `import/`
   directory directly, via `subPath: import` on a raw NFS volume onto
   the same `/books` export `books-pipeline`/`calibre-web` already use
   (same pattern as those two - a static PV doesn't fit a multi-
   consumer-within-one-pod case, see `day1-foundation/apps/qnap-storage/
   README.md`'s "downloads directories" entry). This is a structural
   guarantee, not just convention: the container literally cannot see
   anything else under `/books` - no `metadata.db`, no other author's
   files, nothing - because nothing else is mounted.
2. **`lazylibrarian-config-seed`** - patches `config.ini` once
   LazyLibrarian creates it on first boot (`DESTINATION_DIR` = the
   import mount, per-book folder naming turned off), then self-restarts
   the pod so the change takes effect - same shape as calibre-web's
   `config_calibre_dir` seed. Verified 2026-07-23 against a live,
   internet-connected instance: `config.ini` ends up with
   `destination_dir=/import`, `destination_copy=0`, `ebook_dest_folder`
   empty, `ebook_dest_file=$Title - $Author` - exactly as intended, no
   key-name corrections needed.
3. **SABnzbd's `books` category** - mounted the same `import/` subPath
   directly (`/books-import` in the sabnzbd container), so the
   category's completed-directory can point straight at it - no sweep,
   no extra hop. Set live by the wiring reconciler (below) via
   SABnzbd's own config API, not a blind `sabnzbd.ini` patch - see
   "Cross-app wiring" for the mechanism and why the category name/path
   isn't hardcoded here.

`downloads/complete` and `downloads/incomplete` (SABnzbd's own,
non-books completed/in-progress dirs) are a second, separate raw NFS
volume onto the previously-unused `/downloads` QNAP export - see the
same qnap-storage README entry for the chown/layout details.

## Cross-app wiring (2026-07-23)

`wiring/arr-stack-wiring-config.yml` is the one file to edit for
SABnzbd's category, which apps get it as a download client, and which
Prowlarr indexer(s) to run - human choices, captured declaratively,
same "edit, commit, push, done" workflow as the Pi-hole DNS ConfigMap
(`dns-conf/pihole/pihole-custom-dns-cm.yml`), but without that one's
manual-restart limitation: this ConfigMap is mounted as a whole
directory (not `subPath`, which doesn't hot-reload on this cluster),
so an edit lands automatically via kubelet's normal sync.

Two sidecars apply it, split by whether the target app needs a restart
to pick up a change:

- **`arr-wiring-reconciler`** - Sonarr, Radarr, Prowlarr, SABnzbd all
  have real REST APIs, so this just loops every 5 minutes, re-reads the
  mounted config, and re-applies it (SABnzbd category via
  `mode=set_config`; Sonarr/Radarr download clients and Prowlarr
  indexers via each app's own `.../schema` endpoint - fetch the schema,
  fill in the fields matching what's declared, POST-or-PUT). No pod
  restart, ever. Every field mapping here (SABnzbd's `name`/`dir`
  params, Sonarr's `tvCategory` vs Radarr's `movieCategory` field name,
  Prowlarr's indexer `definitionName` matching) was confirmed live
  against this exact install (Sonarr 4.0.19, Radarr 6.2.1, Prowlarr
  2.4.0, SABnzbd 5.0.4), not guessed from docs - their real API
  reference pages are JS-rendered and not fetchable, so the live
  cluster's own `/schema` endpoints were the source of truth instead.
  Always re-applies rather than diffing first: every app's API masks
  `apiKey`-type fields as `"********"` on GET, which would make a
  real diff always look changed for the one field that actually
  matters, so "always re-assert desired state" is simpler and more
  correct than tracking drift.
- **`lazylibrarian-config-seed`** (extended, see above) - LazyLibrarian
  has no REST API for this, only `config.ini` read at startup, so this
  reads the same wiring-config, patches `config.ini`'s `[SABnzbd]`
  section (`SAB_HOST`/`SAB_PORT`/`SAB_API`/`SAB_CAT`) and `[USENET]`'s
  `NZB_DOWNLOADER_SABNZBD` toggle, then self-restarts the pod only if
  something actually changed. Real key names confirmed against
  LazyLibrarian's own upstream source
  (`lazylibrarian/__init__.py`'s config definitions), not guessed.

Neither app's own auto-generated API key lives in the wiring-config -
those aren't ours to set, so both sidecars read them live from each
app's own config file (`config.xml`'s `<ApiKey>` for Sonarr/Radarr/
Prowlarr, `sabnzbd.ini`'s `api_key` for SABnzbd) every pass, mounted
read-only for exactly that purpose.

Indexer API keys go in `wiring/arr-stack-wiring-sealed-secret.yml`
(referenced by name from `wiring.yml`, never in the plaintext config) -
currently just a placeholder since no indexer is configured yet; see
that file's header comment for how to add a real one.

## Network layout - one shared pod
Containers in a pod share a network namespace, so the whole stack runs as
**one Deployment** with Gluetun plus the six apps as containers - the
Kubernetes equivalent of docker-compose `network_mode: service:gluetun`.
All ingress and egress passes through Gluetun's namespace: its firewall
admits only the UI ports (`FIREWALL_INPUT_PORTS`) and cluster subnets
(`FIREWALL_OUTBOUND_SUBNETS`); everything else must leave via the VPN
tunnel. Per-app subdirectories hold each app's config PVC, Service and
Ingress; the Services all select the same pod on different ports.

## LIVE 2026-07-23: real PIA (Private Internet Access) via WireGuard

`gluetun/gluetun-config.yml` (plain) and `gluetun/gluetun-sealed-secret.yml`
(sealed) together hold a real, working WireGuard peer registration for
PIA (`VPN_SERVICE_PROVIDER=custom`, `VPN_TYPE=wireguard`,
`WIREGUARD_ENDPOINT_IP`/`_PORT`/`_PUBLIC_KEY`/`_PRIVATE_KEY`/
`_ADDRESSES` - split between the two 2026-08-07, see "LIVE 2026-08-07:
automated self-healing" below for why). Confirmed live: gluetun logs a
real tunnel-up event and a PIA exit IP (`117.120.9.36`, Sydney), and
every other container in the pod (checked: sonarr, sabnzbd,
lazylibrarian) gets real internet egress through it with that same
exit IP.

WireGuard was reached in two steps:
1. **2026-07-22, PIA via OpenVPN** - switched from Mullvad/WireGuard
   because the user already had a PIA subscription (no need for a
   second VPN service) and gluetun's native PIA support is
   OpenVPN-only. This never actually worked: UDP 1197, UDP 8080 and
   TCP 501 all failed (TLS handshake timeout / hard connect timeout)
   against multiple real PIA server IPs across two regions, while
   plain HTTPS egress from the same pod network was fine - pointing at
   something in this network path blocking OpenVPN specifically.
2. **2026-07-23, PIA via WireGuard, custom provider** - gluetun has no
   native PIA WireGuard support (confirmed upstream: "slow work in
   progress"), and PIA doesn't publish static WireGuard configs, so
   the peer above was registered directly against PIA's own API
   (`pia-foss/manual-connections`'s documented flow: auth token → pick
   a server from the region's server list → generate an X25519
   keypair → register it via `/addKey`) rather than left as a manual
   step, fully scripted end to end.

Disabled 2026-07-17 through 2026-07-22 on a placeholder VPN secret
(`gluetun` CrashLoopBackOff, `replicas: 0`) - kept here for context,
not because it's still true:
- the pod showed NotReady, but app UIs stayed reachable regardless
  (`publishNotReadyAddresses: true` on every Service) - that
  mechanism is still in place, just no longer masking a real problem;
- no indexers or download clients were wired up in the install-only
  pass - still true, see "Deliberately unconfigured" below.

The WireGuard peer is tied to one specific PIA server IP - if PIA ever
retires/rotates that server, the tunnel needs a fresh registration.
This happened twice (2026-07-23's server was gone 12 days later;
2026-08-05's replacement went stale within ~36-48h) before it was
automated away - see "LIVE 2026-08-07: automated self-healing" below.
Manual rotation is still possible if ever needed: see the header
comment in `gluetun-sealed-secret.yml` for the exact 4-step flow and
which field to reseal.

## LIVE 2026-08-07: automated self-healing (vpn-healer)

Manually noticing the tunnel was dead, then redoing PIA's 4-step
registration by hand, wasn't sustainable - PIA's server rotation isn't
predictable enough. `vpn-healer/` now does this automatically:

- **Split the secret** (`gluetun/gluetun-config.yml` +
  `gluetun/gluetun-sealed-secret.yml`): only `WIREGUARD_PRIVATE_KEY` is
  a genuine secret (equivalent to a password). Endpoint IP/port and the
  PIA server's own public key aren't - they come straight from PIA's
  own public server list, and public keys are meant to be shared by
  definition - so those live in a plain ConfigMap instead. This also
  means an automated rotation is a readable git diff, not an opaque
  re-encrypted blob.
- **`vpn-healer-cronjob.yml`** runs every 15 minutes, as its own
  CronJob - deliberately NOT inside the arr-stack pod, since every
  container there shares gluetun's network namespace and its firewall
  force-routes all non-cluster egress through the VPN tunnel. A healer
  living in there would be stuck trying to reach PIA's API through the
  very tunnel it's supposed to be fixing.
- **`reconcile_vpn.py`** (see its own module docstring for the full
  design) checks whether the current peer's server IP is still in
  PIA's live server list (proactive - catches a retirement before
  gluetun even notices) plus a gluetun-log restart-loop scan as a
  backup. On a stale peer: redoes the registration, patches the live
  ConfigMap + SealedSecret, restarts the arr-stack pod, and commits the
  rotation back to this repo (its own git deploy key, GitHub identity
  verified via a baked-in known_hosts, not trust-on-first-connect) so a
  future ArgoCD sync can't revert to the stale peer.
- **Two new sealed secrets it needs**, both narrowly scoped and used
  for nothing else: `gluetun/pia-account-credentials-sealed-secret.yml`
  (the PIA account login, for re-registration - sealed locally via
  `vpn-healer/seal-pia-credentials.sh`, never typed into a chat
  session) and `vpn-healer/vpn-healer-git-deploy-key-sealed-secret.yml`
  (a dedicated SSH deploy key, write access on this repo only).
- **RBAC** (`vpn-healer-rbac.yml`): its own ServiceAccount, resourceName-scoped
  to exactly `gluetun-config` and `gluetun-vpn` - deliberately not
  reusing `arr-stack-seed`, so this doesn't widen what the config-seed
  sidecars in the shared pod can touch.
- **Image** (`images/gluetun-vpn-healer/`): python3 + `cryptography`
  (X25519 keypair generation, same reasoning as the original manual
  registration) + `kubectl`/`kubeseal` + `git`/`curl`. Built and pushed
  to `ghcr.io/gorttman/gluetun-vpn-healer` the same way as every other
  in-house image here - push a `gluetun-vpn-healer-vX.Y.Z` tag, or run
  the workflow manually.

**Bootstrap steps still needed before this can run** (both one-time):
run `vpn-healer/seal-pia-credentials.sh` to create the PIA credentials
secret, and add the deploy key's public half (in that sealed secret's
own header comment) as a write-enabled Deploy Key on this GitHub repo.

## Deliberately unconfigured (install-only)
- No Prowlarr indexers - see "Cross-app wiring" above, this is the one
  genuinely manual choice left (which provider/indexer to use); SABnzbd
  category and Sonarr/Radarr/LazyLibrarian download-client wiring are
  handled by the reconcilers there
- No quality profiles, no root folders
- **No shared media PVC** - where the media library lives is a
  configuration-time decision, out of scope here
- SABnzbd will show "hostname verification failed" for
  sabnzbd.i3sec.com.au until its `host_whitelist` is set - config-pass item
- No workload-affinity block yet (marker comment in the deployment)

## Storage - PLACEHOLDER
Six 2Gi config PVCs on `local-path`: node-local, non-durable, SQLite
inside - same caveats and the same temporary k8smaster nodeSelector as
apps/jellyfin (pinode-01's k3s dir is a 4G RAM tmpfs). Remove the
nodeSelector together with the storage swap.
