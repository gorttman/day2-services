# arr-stack

Media automation stack behind a Mullvad VPN (Gluetun), install-only.

| App | UI | Container port |
|---|---|---|
| Sonarr 4.0.19 | https://sonarr.i3sec.com.au | 8989 |
| Radarr 6.2.1 | https://radarr.i3sec.com.au | 7878 |
| Prowlarr 2.4.0 | https://prowlarr.i3sec.com.au | 9696 |
| SABnzbd 5.0.4 | https://sabnzbd.i3sec.com.au | 8080 |
| Bazarr 1.6.0 | https://bazarr.i3sec.com.au | 6767 |
| JDownloader2 v26.03.1 | https://jdownloader.i3sec.com.au | 5800 |

## Network layout - one shared pod
Containers in a pod share a network namespace, so the whole stack runs as
**one Deployment** with Gluetun plus the six apps as containers - the
Kubernetes equivalent of docker-compose `network_mode: service:gluetun`.
All ingress and egress passes through Gluetun's namespace: its firewall
admits only the UI ports (`FIREWALL_INPUT_PORTS`) and cluster subnets
(`FIREWALL_OUTBOUND_SUBNETS`); everything else must leave via the VPN
tunnel. Per-app subdirectories hold each app's config PVC, Service and
Ingress; the Services all select the same pod on different ports.

## EXPECTED STATE: Gluetun CrashLoops until real credentials are sealed
`gluetun/gluetun-sealed-secret.yml` contains sealed **placeholder**
values, deliberately - this install pass does not touch real Mullvad
credentials. Until they exist:

- the `gluetun` container CrashLoops (invalid WireGuard key) - **this is
  not a bug**;
- the pod shows NotReady, but the app UIs stay reachable because the
  Services set `publishNotReadyAddresses: true`;
- the apps have no VPN egress (and nothing configured to use it - no
  indexers or download clients are wired up in this pass).

To go live: seal a real secret over it (same name `gluetun-vpn`,
namespace `arr-stack`, keys `VPN_SERVICE_PROVIDER`, `VPN_TYPE`,
`WIREGUARD_PRIVATE_KEY`, `WIREGUARD_ADDRESSES`) with kubeseal, commit,
and restart the deployment.

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
