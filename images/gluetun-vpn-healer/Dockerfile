# Runs vpn-healer's reconcile_vpn.py (arr-stack/vpn-healer/) - detects
# a stale PIA WireGuard peer registration, redoes PIA's own 4-step
# registration flow, patches the live gluetun-config ConfigMap /
# gluetun-vpn Secret, restarts the arr-stack pod, and commits the
# rotation back to git. Needs: kubectl (patch/delete against the
# cluster), kubeseal (reseal the rotated private key), git+openssh
# (commit/push with a deploy key), and Python's `cryptography` package
# (X25519 keypair generation - same reasoning as the original manual
# registration, see ../../apps/arr-stack/gluetun/gluetun-sealed-secret.yml).
FROM python:3.12-slim@sha256:adbc7c33e0abc183557d1d14ce5eb5d261aaadff5451c81a8db636b3ebefcdf6

# kubectl/kubeseal versions matched to what's actually running in this
# cluster (v1.33.5+k3s1 / kubeseal 0.27.1) at the time this image was
# built - bump both here if the cluster is upgraded.
ARG KUBECTL_VERSION=v1.33.5
ARG KUBESEAL_VERSION=0.27.1

RUN apt-get update && apt-get install -y --no-install-recommends \
      git \
      openssh-client \
      ca-certificates \
      curl \
    && curl -fsSLo /usr/local/bin/kubectl \
      "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/arm64/kubectl" \
    && chmod +x /usr/local/bin/kubectl \
    && curl -fsSLo /tmp/kubeseal.tar.gz \
      "https://github.com/bitnami-labs/sealed-secrets/releases/download/v${KUBESEAL_VERSION}/kubeseal-${KUBESEAL_VERSION}-linux-arm64.tar.gz" \
    && tar -xzf /tmp/kubeseal.tar.gz -C /usr/local/bin kubeseal \
    && chmod +x /usr/local/bin/kubeseal \
    && rm -rf /tmp/kubeseal.tar.gz \
    && rm -rf /var/lib/apt/lists/*
# curl deliberately kept (not purged after use above): reconcile_vpn.py
# shells out to it for the PIA /addKey call, using --resolve to force
# the right server IP while still validating TLS against the server's
# real hostname - the same trick pia-foss/manual-connections uses, and
# not reproducible with a plain `requests` call (the URL host would
# have to be the IP itself, breaking SNI/hostname validation).

RUN pip install --no-cache-dir \
      requests==2.34.2 \
      cryptography==43.0.3

# PIA's own CA, from pia-foss/manual-connections - required to TLS-verify
# the /addKey registration call against a PIA server CN (not in any
# public CA bundle). Baked in at build time rather than fetched at
# runtime so a GitHub outage can't block a VPN self-heal.
COPY pia-ca.rsa.4096.crt /etc/ssl/pia-ca.rsa.4096.crt

# github.com's own published ed25519 host key (confirmed live via
# ssh-keyscan 2026-08-07, matches GitHub's documented SSH key
# fingerprints) - baked in and used with StrictHostKeyChecking=yes so
# the git push in reconcile_vpn.py verifies GitHub's identity properly
# instead of trust-on-first-connect.
RUN echo "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl" \
    > /etc/ssh/github_known_hosts

# UID 1000 / GID 100 ("users") - same convention as every other
# in-house image in this repo (inbox-router, books-pipeline).
RUN useradd --uid 1000 --gid 100 --no-create-home --shell /usr/sbin/nologin healer

USER 1000:100

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# No script baked in: reconcile_vpn.py is mounted from a ConfigMap at
# runtime, same pattern as arr-wiring-reconciler.
