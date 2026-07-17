# --- Why this base/install method (Phase 1 recommendation, prompt 3) ---
# Calibre has had official first-party ARM64 Linux support since v6.0
# (2022); current upstream is 9.11.0. Installed here via Calibre's own
# official Linux installer (download.calibre-ebook.com/linux-installer.sh),
# which SHA512-verifies the download against a published signature before
# extracting - not a bare curl-pipe-bash trust exercise. Chosen over
# Debian trixie's own calibre-bin package (which is real, arm64-native,
# and simpler) because that apt package freezes at whatever version
# Debian trixie shipped (8.5.0) for the entire life of the release, with
# no controlled way to move it forward - conversion quality is
# version-sensitive, and this project has consistently pinned exact
# versions and bumped them deliberately (pip packages, base digest)
# rather than tracking an OS snapshot. Revisit if low-maintenance patch
# cadence turns out to matter more than version currency.
#
# xvfb is deliberately NOT included. Its only confirmed justification
# (converting *to* PDF requires a real display surface - a standing
# Calibre/Qt bug) no longer applies: PDFs are excluded from automatic
# conversion by design (2026-07-16 decision - PDF handling will be a
# manual process, added later, not part of this pipeline). Including
# xvfb now with no confirmed need behind it would be exactly the
# speculative addition the original task spec said not to make.
# QT_QPA_PLATFORM=offscreen is set instead - Qt6's own headless
# platform plugin, zero extra packages/processes, sufficient for any
# remaining Qt-based operation (e.g. cover image handling) that isn't
# PDF output. Revisit (reintroduce xvfb + the ebook-convert wrapper
# below, see prior version in git history once this lands) if/when PDF
# conversion is automated in a later prompt.
#
# UNVERIFIED, flagged in README: the exact Qt/X11 client library list
# below is a best-effort based on Calibre's known Qt dependencies - this
# could not be runtime-tested in this session (Phase 2 is proposal-only,
# no builds). Same caveat for non-root HOME/XDG writability. Both need
# checking on first real build.

FROM python:3.12-slim@sha256:55842c72c6b3584d06ec84c731fc516b30b8a53ad262ebd085e47ab568b3bfc1

ARG CALIBRE_VERSION=9.11.0

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
      ca-certificates \
      xz-utils \
      libxcb-cursor0 \
      libxkbcommon0 \
      libgl1 \
      libegl1 \
      libopengl0 \
      fontconfig \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://download.calibre-ebook.com/linux-installer.sh -o /tmp/calibre-linux-installer.sh \
    && sh /tmp/calibre-linux-installer.sh version=${CALIBRE_VERSION} \
    && rm -f /tmp/calibre-linux-installer.sh

# Added for prompt 4 (books_pipeline.py): psycopg2-binary bundles its own
# libpq, no separate libpq-dev/apt package needed. rapidfuzz for dedup
# scoring, PyYAML/requests matching the inbox-router image's pattern
# (config file + webhook POST).
#
# Added for prompt 6 (pdf_triage.py): pypdf, for per-page text
# extraction and document metadata. Calibre's own CLI tools
# (ebook-meta) only expose document-level metadata, not per-page text -
# there's no way to scan specific pages for an ISBN pattern with
# Calibre alone. pypdf is pure-Python (no native deps, trivial ARM64
# fit), confirmed the better tool for this specific job rather than
# stretching Calibre to do something it wasn't built for.
RUN pip install --no-cache-dir \
      PyYAML==6.0.3 \
      requests==2.34.2 \
      psycopg2-binary==2.9.12 \
      rapidfuzz==3.14.5 \
      pypdf==6.14.2

RUN groupadd --gid 10001 books-pipeline \
    && useradd --uid 10001 --gid books-pipeline --create-home \
       --home-dir /home/books-pipeline --shell /usr/sbin/nologin books-pipeline \
    && mkdir -p /home/books-pipeline/.cache /home/books-pipeline/.config \
    && chown -R books-pipeline:books-pipeline /home/books-pipeline

ENV HOME=/home/books-pipeline \
    XDG_CACHE_HOME=/home/books-pipeline/.cache \
    XDG_CONFIG_HOME=/home/books-pipeline/.config \
    QT_QPA_PLATFORM=offscreen \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER 10001:10001

# No pipeline script, ENTRYPOINT, or CMD is baked in: matching the
# inbox-router image's pattern, the script is mounted from a ConfigMap
# at runtime, and the CronJob's command/args invoke it directly.
