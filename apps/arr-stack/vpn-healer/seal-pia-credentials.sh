#!/usr/bin/env bash
# Run this yourself, locally - it prompts for the PIA account
# credentials (username visible, password hidden) and seals them
# straight into pia-account-credentials-sealed-secret.yml. Neither
# value ever gets echoed, logged, or passed as a command-line argument
# (which would land in shell history) - only kubeseal's ciphertext
# output touches disk.
#
# These credentials are only used by vpn-healer's automated PIA
# WireGuard peer re-registration (get_pia_token() in reconcile_vpn.py)
# - same PIA account (p4239118) already used for the original manual
# registration back in 2026-07-23.
set -euo pipefail

export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

read -rp "PIA username: " PIA_USERNAME
read -rsp "PIA password: " PIA_PASSWORD
echo

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
OUT="$REPO_ROOT/apps/arr-stack/gluetun/pia-account-credentials-sealed-secret.yml"

USERNAME_ENC=$(printf '%s' "$PIA_USERNAME" | kubeseal --raw --scope strict \
  --namespace arr-stack --name pia-account-credentials \
  --from-file=PIA_USERNAME=/dev/stdin)
PASSWORD_ENC=$(printf '%s' "$PIA_PASSWORD" | kubeseal --raw --scope strict \
  --namespace arr-stack --name pia-account-credentials \
  --from-file=PIA_PASSWORD=/dev/stdin)

unset PIA_USERNAME PIA_PASSWORD

cat > "$OUT" <<EOF
# PIA account credentials - used only by vpn-healer's automated peer
# re-registration (get_pia_token() in reconcile_vpn.py), same PIA
# account (p4239118) already used for the original manual registration.
# Sealed via this directory's seal-pia-credentials.sh, which prompts
# for the username/password locally so they never appear in a chat
# transcript, shell history, or this file in plaintext.
#
# To rotate (e.g. after a PIA password change): re-run
# seal-pia-credentials.sh - it overwrites this file in place.
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  creationTimestamp: null
  name: pia-account-credentials
  namespace: arr-stack
spec:
  encryptedData:
    PIA_USERNAME: ${USERNAME_ENC}
    PIA_PASSWORD: ${PASSWORD_ENC}
  template:
    metadata:
      creationTimestamp: null
      name: pia-account-credentials
      namespace: arr-stack
    type: Opaque
EOF

echo "Wrote $OUT"
echo "Review it, then git add/commit/push as usual."
