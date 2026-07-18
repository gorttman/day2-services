FROM node:22-bookworm-slim

# Pinned to the version actually verified (arm64 Linux prebuilds for
# better-sqlite3, real ob --help/login/sync-* CLI surface) rather than
# floating latest on a young (0.0.x) project.
RUN npm install -g obsidian-headless@0.0.13

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
