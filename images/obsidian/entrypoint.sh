#!/bin/bash
set -euo pipefail

# Clean up any stale X lock files from previous runs
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1

# Start virtual display
Xvfb :1 -screen 0 1280x800x24 -nolisten tcp &

export DISPLAY=:1

# Wait for the display socket to appear
until [ -S /tmp/.X11-unix/X1 ]; do sleep 0.1; done

# Start minimal window manager
openbox &

# Start VNC server — no password, internal cluster access only
x11vnc \
    -display :1 \
    -rfbport 5900 \
    -nopw \
    -listen 0.0.0.0 \
    -xkb \
    -forever \
    -shared \
    -quiet \
    -bg

# Start noVNC websockify proxy (HTTP on 8080 → VNC on 5900)
websockify --web /opt/novnc 8080 localhost:5900 &

# Start Obsidian
exec /opt/obsidian/obsidian --no-sandbox --disable-gpu
