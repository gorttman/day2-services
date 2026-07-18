FROM python:3.12-slim@sha256:55842c72c6b3584d06ec84c731fc516b30b8a53ad262ebd085e47ab568b3bfc1

RUN apt-get update && apt-get install -y --no-install-recommends \
      libmagic1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
      python-magic==0.4.27 \
      PyYAML==6.0.3 \
      requests==2.34.2

# UID 1000 / GID 100 (users) - matches the pre-existing day0/day1
# convention (every linuxserver-based app in this cluster already runs
# PUID=1000), not an invented UID. GID 100 "users" already exists in
# the base image (standard Debian default, confirmed empty) - no
# groupadd needed, just reuse it, matching gorttman's own real
# supplementary group on the QNAP host. Lets a human's direct file
# copy and this container's writes coexist via shared group
# permissions instead of exclusive single-UID ownership.
RUN useradd --uid 1000 --gid 100 --no-create-home --shell /usr/sbin/nologin router

USER 1000:100

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# No script, ENTRYPOINT, or CMD is baked in: the router script is mounted from
# a ConfigMap at runtime, and the CronJob's command/args invoke it directly.
