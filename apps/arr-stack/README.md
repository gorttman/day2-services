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

LazyLibrarian joins the shared pod as an eighth container (ninth
counting its own config-seed sidecar, which reuses its image rather
than pulling a new one). Three pieces:

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
   no extra hop. **Not automated**: SABnzbd's category config lives in
   `sabnzbd.ini` under a `[[section]]`-per-category `ConfigObj` format
   that Python's `configparser` can't safely round-trip - a blind
   automated patch risked corrupting the whole config file. This one
   genuinely is a manual step:
   - SABnzbd UI → Config → Categories → add `books`, Folder/Path =
     `/books-import`
   - Prowlarr UI → add your indexers (which services you use is a real
     choice only you can make, not something to automate) → enable the
     Books category on any indexer that supports it

`downloads/complete` and `downloads/incomplete` (SABnzbd's own,
non-books completed/in-progress dirs) are a second, separate raw NFS
volume onto the previously-unused `/downloads` QNAP export - see the
same qnap-storage README entry for the chown/layout details.

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

`gluetun/gluetun-sealed-secret.yml` holds a real, working WireGuard
peer registration for PIA (`VPN_SERVICE_PROVIDER=custom`,
`VPN_TYPE=wireguard`, `WIREGUARD_ENDPOINT_IP`/`_PORT`/`_PUBLIC_KEY`/
`_PRIVATE_KEY`/`_ADDRESSES`). Confirmed live: gluetun logs a real
tunnel-up event and a PIA exit IP (`117.120.9.36`, Sydney), and every
other container in the pod (checked: sonarr, sabnzbd, lazylibrarian)
gets real internet egress through it with that same exit IP.

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

The WireGuard peer is tied to one specific PIA server IP
(`117.120.9.43`, AU Sydney) - if PIA ever retires/rotates that server,
the tunnel needs a fresh registration. See the header comment in
`gluetun-sealed-secret.yml` for the exact 4-step flow to repeat and
which fields to reseal (`kubeseal --raw`, scope strict, namespace
`arr-stack`, name `gluetun-vpn`) - same pattern as every other
multi-field sealed secret in this repo.

## Deliberately unconfigured (install-only)
- No indexers (Prowlarr), no download clients wired into Sonarr/Radarr
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
