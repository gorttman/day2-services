#!/bin/sh
set -eu

VAULT_PATH=/vault
CONFIG_DIR=.obsidian-headless-sync

# Account-level: log in if we're not already. sync-list-remote is a cheap,
# account-scoped call that fails cleanly if unauthenticated - used as the
# "am I logged in" check since `ob login` with no args wasn't verifiable
# without real credentials at proposal time.
if ! ob sync-list-remote >/tmp/remotes.log 2>&1; then
  echo "[*] Not logged in - logging in"
  ob login --email "$OBSIDIAN_EMAIL" --password "$OBSIDIAN_PASSWORD"
  ob sync-list-remote >/tmp/remotes.log
fi

# Vault-level: create the remote vault if it doesn't exist yet. The
# encryption password is set here, at creation time - not something that
# pre-exists to look up.
if ! grep -q "$OBSIDIAN_VAULT_NAME" /tmp/remotes.log; then
  echo "[*] Remote vault '$OBSIDIAN_VAULT_NAME' doesn't exist yet - creating it"
  ob sync-create-remote \
    --name "$OBSIDIAN_VAULT_NAME" \
    --encryption e2ee \
    --password "$OBSIDIAN_SYNC_PASSWORD"
fi

# Local-level: link this local path to the remote vault if not already
# linked. sync-status succeeding is the signal a link already exists -
# this is what makes re-running login/sync-create-remote/sync-setup safe
# on every pod restart rather than just on first boot.
if ! ob sync-status --path "$VAULT_PATH" >/tmp/sync-status.log 2>&1; then
  echo "[*] Local vault not yet linked - running sync-setup"
  ob sync-setup \
    --vault "$OBSIDIAN_VAULT_NAME" \
    --path "$VAULT_PATH" \
    --password "$OBSIDIAN_SYNC_PASSWORD" \
    --device-name "$OBSIDIAN_DEVICE_NAME" \
    --config-dir "$CONFIG_DIR"
  ob sync-config \
    --path "$VAULT_PATH" \
    --mode bidirectional \
    --excluded-folders .git
else
  echo "[*] Vault already linked, skipping setup"
  cat /tmp/sync-status.log
fi

exec ob sync --path "$VAULT_PATH" --continuous
