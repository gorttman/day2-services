#!/usr/bin/env bash
# Run this yourself, locally - it reads a WireGuard config downloaded
# from AirVPN's Client Area Config Generator (Advanced mode OFF, single
# generic WireGuard entry - region/server-agnostic, works against any
# AirVPN relay) and seals the two genuinely-secret fields (PrivateKey,
# PresharedKey) straight into gluetun-sealed-secret.yml. Neither value
# ever gets echoed, logged, or passed as a bare command-line argument -
# only kubeseal's ciphertext output touches disk. The non-secret
# Address field gets written to the plain gluetun-config.yml ConfigMap
# instead (meaningless without the private key - same split PIA's
# config used, see that file's git history).
#
# To rotate: download a fresh config from the Config Generator, then
# re-run this script with its path. Overwrites both files in place.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <path-to-airvpn-wireguard.conf>" >&2
  exit 1
fi
CONF="$1"

export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

ADDRESS=$(grep -oP '(?<=^Address = ).*' "$CONF")
PRIVATE_KEY=$(grep -oP '(?<=^PrivateKey = ).*' "$CONF")
PRESHARED_KEY=$(grep -oP '(?<=^PresharedKey = ).*' "$CONF")

if [[ -z "$ADDRESS" || -z "$PRIVATE_KEY" || -z "$PRESHARED_KEY" ]]; then
  echo "failed to parse Address/PrivateKey/PresharedKey out of $CONF" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SECRET_OUT="$REPO_ROOT/apps/arr-stack/gluetun/gluetun-sealed-secret.yml"
CONFIG_OUT="$REPO_ROOT/apps/arr-stack/gluetun/gluetun-config.yml"

PRIVATE_KEY_ENC=$(printf '%s' "$PRIVATE_KEY" | kubeseal --raw --scope strict \
  --namespace arr-stack --name gluetun-vpn \
  --from-file=WIREGUARD_PRIVATE_KEY=/dev/stdin)
PRESHARED_KEY_ENC=$(printf '%s' "$PRESHARED_KEY" | kubeseal --raw --scope strict \
  --namespace arr-stack --name gluetun-vpn \
  --from-file=WIREGUARD_PRESHARED_KEY=/dev/stdin)

unset PRIVATE_KEY PRESHARED_KEY

cat > "$SECRET_OUT" <<EOF
# AirVPN WireGuard device credentials (switched from PIA 2026-08-27 -
# see gluetun-config.yml for why). Both fields are genuine secrets:
# PrivateKey is this device's WireGuard private key, PresharedKey adds
# post-quantum-resistant symmetric key material on top of it - both
# equivalent to a password. Sealed via this directory's
# seal-airvpn-credentials.sh, which reads them out of a Config
# Generator download so they never appear in a chat transcript, shell
# history, or this file in plaintext.
#
# To rotate: download a fresh config from AirVPN's Client Area Config
# Generator, then re-run seal-airvpn-credentials.sh with its path - it
# overwrites this file in place.
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  creationTimestamp: null
  name: gluetun-vpn
  namespace: arr-stack
spec:
  encryptedData:
    WIREGUARD_PRIVATE_KEY: ${PRIVATE_KEY_ENC}
    WIREGUARD_PRESHARED_KEY: ${PRESHARED_KEY_ENC}
  template:
    metadata:
      creationTimestamp: null
      name: gluetun-vpn
      namespace: arr-stack
    type: Opaque
EOF

python3 - "$CONFIG_OUT" "$ADDRESS" <<'PYEOF'
import sys, re
path, address = sys.argv[1], sys.argv[2]
with open(path) as f:
    content = f.read()
content = re.sub(
    r'(WIREGUARD_ADDRESSES: ").*(")',
    rf'\g<1>{address}\g<2>',
    content,
)
with open(path, "w") as f:
    f.write(content)
PYEOF

echo "Wrote $SECRET_OUT"
echo "Updated WIREGUARD_ADDRESSES in $CONFIG_OUT"
echo "Review both, then git add/commit/push as usual."
