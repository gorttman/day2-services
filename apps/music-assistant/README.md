# Music Assistant

Music Assistant (MA) at `https://music.i3sec.com.au` (internal only). Plays
radio and YouTube Music to the Google Cast speakers and groups them.

## Architecture

- **Pinned to k8smaster with `hostNetwork: true`.** MA finds players by mDNS
  and the players pull audio from MA's stream port (8097), so MA must sit
  directly on a LAN. k8smaster's `end0` is on Trusted (192.168.20.10).
- **The Cast speakers are on the main LAN (192.168.2.x), MA is on Trusted.**
  mDNS does not cross VLANs and upstream says cross-VLAN is unsupported. The
  UDM mDNS reflector bridges them: unifi `mdns` site setting must list BOTH
  Default and Trusted in `enabled_for_network_ids`. If MA shows zero Cast
  players, check that first.
- **`/data` is a Longhorn PVC** (settings.json + SQLite library). Not NFS.
- **`pot-provider` sidecar** (`bgutil-ytdlp-pot-provider`, version pinned to
  match the plugin bundled in the MA image - 2.0.1 for MA 2.10.5; the MA
  docs' "only 1.2.1" is stale) serves the Proof-of-Origin token YouTube Music
  needs. MA's YT Music provider finds it at `http://127.0.0.1:4416` by
  default, so there is nothing to configure.
- Web UI goes through Traefik. Speakers never use that hostname - they
  stream straight from `http://192.168.20.10:8097`.

## What is code and what is UI state

Code (this directory): the deployment, storage, ingress, version pin.

UI-managed, lives only in `/data` on the PVC (not declarative, and it holds
credentials, so it is NOT committed):

- Music provider logins (YouTube Music cookie, etc.) and enabled providers.
- Player settings and groups.
- Radio favourites and library.

Workflow: try things in the UI first, then record what worked in the
"Working configuration" section below so it can be rebuilt.

- **YouTube Music cookie expires.** On `401: Unauthorized` or "Unable to
  fetch PO Token" in the MA log, repeat the cookie copy (browser dev tools,
  `/browse` request, `Cookie` header, must contain `__Secure-3PAPISID`).
  Free accounts are not supported - Premium only.

## Declarative config (`desired-config.json`)

MA has no config file to hand-write, so desired state is merged into its own
`/data/settings.json` by an init container (`apply-desired-config.py`) before
MA starts. Only keys named in `desired-config.json` are enforced; dicts merge,
lists replace. Provider logins and everything else are left alone.

- Change a value in `desired-config.json`, push: the ConfigMap name carries a
  content hash, so the pod rolls and the new value is applied. MA restarts, so
  anything playing stops for ~30s.
- **Git wins for declared keys.** A UI edit to a declared key is overwritten
  at the next restart. Workflow: try it in the UI, then move the result here.
- Never put secrets in `desired-config.json` (YouTube cookie etc.) - MA keeps
  those encrypted in its own file.

Currently declared: the Chromecast **manual discovery IPs**. Cast speakers sit
on the main LAN, MA on Trusted, and mDNS does not cross - so each speaker is
listed by address (all reserved in unifi-tf `clients.tf`):

- 192.168.2.69 lounge, .197 bar, .40 shed, .188 clock, .196 pergola Chromecast
- 192.168.2.167 Bose Smart Soundbar 900 - NOT reserved in UniFi yet and its
  Cast/AirPlay ports did not answer when tested (probably standby). Harmless
  if it never connects; remove it from the list if it never works.

## Working configuration (UI state, not declarative)

- Radio Browser provider enabled (free, no login).
- Player groups: use MA's own sync groups, not Google's "Home group" (which stopped working 2026-10-09: Cast group host unreachable). A local sync group "Home (local)" is declared in desired-config.json (2026-10-09: Bar, Shed, Outside TV, Outside speaker = JBL Link 10 at 192.168.2.109, added to manual discovery because mDNS found it on a stale port) and needs Sendspin over Cast (experimental) enabled on each member; those `spb_*` players are enabled in the same file. Add Outside speaker and Bedroom clock after the trial works.
- Lounge speaker stays standalone (different listener taste) - groups are
  separate.

## OPEN ITEM - do before removing Google Home / the Google "Home group"

The Bose Smart Soundbar 900 (192.168.2.167, main-LAN Wi-Fi) **drops every
packet from outside its own subnet** (all ports and ICMP time out from the
cluster, while the Google speakers answer). So MA cannot reach it directly.
Today it only plays because it is a member of Google's "Home group", which
lives in Google Home. Remove Google Home / that group and the Bose is
unreachable from MA.

Fix to apply BEFORE that day (untested - the Bose may or may not answer on
the same subnet): create a small Wi-Fi network bound to Trusted (VLAN 20) in
unifi-tf `wlan.tf`, re-join the Bose to it with Bose's app, then add its new
192.168.20.x address to `desired-config.json` and reserve it in `clients.tf`.
Rejected alternatives: bringing k8smaster's `wlan0` up on the main LAN (risk
to the node that runs everything), or moving MA off the cluster.

The same dependency applies to any grouping done in Google Home. MA-native
sync groups for Cast need the experimental "Sendspin over Cast" opt-in per
speaker (not enabled; not tested).
