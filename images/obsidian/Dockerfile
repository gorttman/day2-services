FROM debian:bookworm-slim AS extract

ARG OBSIDIAN_VERSION=1.12.7
ARG TARGETARCH

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) FILE="Obsidian-${OBSIDIAN_VERSION}.AppImage" ;; \
        arm64) FILE="Obsidian-${OBSIDIAN_VERSION}-arm64.AppImage" ;; \
        *) echo "Unsupported arch: ${TARGETARCH}" && exit 1 ;; \
    esac; \
    curl -fsSL \
        "https://github.com/obsidianmd/obsidian-releases/releases/download/v${OBSIDIAN_VERSION}/${FILE}" \
        -o obsidian.AppImage \
    && chmod +x obsidian.AppImage \
    && ./obsidian.AppImage --appimage-extract \
    && mv squashfs-root /opt/obsidian \
    && rm obsidian.AppImage

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      xvfb \
      openbox \
      x11vnc \
      libnss3 \
      libatk1.0-0 \
      libatk-bridge2.0-0 \
      libcups2 \
      libdrm2 \
      libxkbcommon0 \
      libxcomposite1 \
      libxdamage1 \
      libxfixes3 \
      libxrandr2 \
      libgbm1 \
      libasound2 \
      libpango-1.0-0 \
      libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=extract /opt/obsidian /opt/obsidian
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5900

ENTRYPOINT ["/entrypoint.sh"]
