FROM python:3.12-slim@sha256:55842c72c6b3584d06ec84c731fc516b30b8a53ad262ebd085e47ab568b3bfc1

RUN apt-get update && apt-get install -y --no-install-recommends \
      libmagic1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
      python-magic==0.4.27 \
      PyYAML==6.0.3 \
      requests==2.34.2

RUN groupadd --gid 10001 router \
    && useradd --uid 10001 --gid router --no-create-home --shell /usr/sbin/nologin router

USER 10001:10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# No script, ENTRYPOINT, or CMD is baked in: the router script is mounted from
# a ConfigMap at runtime, and the CronJob's command/args invoke it directly.
