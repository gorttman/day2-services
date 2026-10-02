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
- **`pot-provider` sidecar** (`bgutil-ytdlp-pot-provider` 1.2.1, the only
  version MA supports) serves the Proof-of-Origin token YouTube Music
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

## Working configuration

(To fill in as things are proven in the UI.)
