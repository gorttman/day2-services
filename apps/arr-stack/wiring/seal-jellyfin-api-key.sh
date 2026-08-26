#!/usr/bin/env bash
# Run this yourself, locally - it prompts for a Jellyfin API key
# (hidden) and seals it into arr-stack-wiring-sealed-secret.yml as
# jellyfin_api_key, replacing only that one line. The key is never
# echoed, logged, or passed as a command-line argument (which would
# land in shell history) - only kubeseal's ciphertext touches disk.
#
# Same reasoning as vpn-healer/seal-pia-credentials.sh: a credential
# typed into a chat session lives in that transcript permanently.
#
# Get the key from: Jellyfin -> Dashboard -> API Keys -> "+", name it
# "radarr". Used by the Emby/Jellyfin Connect notification the
# reconciler configures, so Radarr tells Jellyfin to scan the moment
# it imports rather than waiting for Jellyfin's periodic scan.
set -euo pipefail

export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

read -rsp "Jellyfin API key: " JF_KEY
echo
[ -n "$JF_KEY" ] || { echo "empty key, aborting" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
OUT="$REPO_ROOT/apps/arr-stack/wiring/arr-stack-wiring-sealed-secret.yml"

ENC=$(printf '%s' "$JF_KEY" | kubeseal --raw --scope strict \
  --namespace arr-stack --name arr-stack-wiring-secret \
  --from-file=jellyfin_api_key=/dev/stdin)
unset JF_KEY

if grep -q '^    jellyfin_api_key:' "$OUT"; then
  # rotate in place
  python3 - "$OUT" "$ENC" <<'PY'
import sys,re
path,enc=sys.argv[1],sys.argv[2]
s=open(path).read()
s=re.sub(r'^    jellyfin_api_key: .*$', f'    jellyfin_api_key: {enc}', s, count=1, flags=re.M)
open(path,'w').write(s)
PY
  echo "Rotated jellyfin_api_key in $OUT"
else
  # add alongside the existing keys
  python3 - "$OUT" "$ENC" <<'PY'
import sys,re
path,enc=sys.argv[1],sys.argv[2]
s=open(path).read()
s=re.sub(r'^(    lazylibrarian_api_key: .*)$',
         r'\1\n    jellyfin_api_key: '+enc, s, count=1, flags=re.M)
open(path,'w').write(s)
PY
  echo "Added jellyfin_api_key to $OUT"
fi

echo "Review the diff, then git add/commit/push as usual."
