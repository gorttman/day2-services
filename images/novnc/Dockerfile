FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-websockify ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://github.com/novnc/noVNC/archive/refs/tags/v1.5.0.tar.gz \
      | tar -xz -C /opt && mv /opt/noVNC-1.5.0 /opt/novnc

ENV VNC_HOST=localhost \
    VNC_PORT=5900 \
    NO_VNC_PORT=8080

EXPOSE 8080

CMD websockify --web /opt/novnc "$NO_VNC_PORT" "$VNC_HOST:$VNC_PORT"
