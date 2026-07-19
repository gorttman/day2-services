FROM node:22-bookworm-slim

# oathtool computes the TOTP code for login's --mfa flag - this account's
# 2FA is 1Password's built-in TOTP, same underlying mechanism as any
# authenticator app. Deterministic from the seed + current time, no
# network call to 1Password needed.
RUN apt-get update && apt-get install -y --no-install-recommends oathtool \
    && rm -rf /var/lib/apt/lists/*

# Pinned to the version actually verified (arm64 Linux prebuilds for
# better-sqlite3, real ob --help/login/sync-* CLI surface) rather than
# floating latest on a young (0.0.x) project.
RUN npm install -g obsidian-headless@0.0.13

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
