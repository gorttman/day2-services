# Adds the pgvector extension to the exact postgres:16.9-alpine image the
# shared instance (apps/postgres) already runs, for Immich's ML/smart-search
# features. Deliberately NOT a switch to the upstream pgvector/pgvector:pg16
# image (that's Debian/glibc-based) - all 8 existing databases on the shared
# instance were initdb'd with lc_collate=en_US.utf8 under musl (confirmed
# live, 2026-08-04: `PostgreSQL 16.9 on aarch64-unknown-linux-musl`). musl
# and glibc sort en_US.utf8 text differently, which would silently corrupt
# any btree index on a text column until a full REINDEX - a well-documented
# real-world Postgres hazard (the same bug class that hit the community
# during Ubuntu 20.04->22.04 glibc upgrades). Since these DBs use libc
# collation (not ICU), Postgres can't even detect/warn about the mismatch
# itself (datcollversion is unset). Staying on musl end-to-end avoids this
# entirely - same base, same collation behaviour, just one extra .so.
#
# Confirmed empirically (2026-08-04, live pod check against this exact tag)
# that postgres:16.9-alpine already ships pg_config and full server headers
# at /usr/local/{bin/pg_config,include/postgresql/server/} - it builds
# Postgres from source and only strips the source tree + build toolchain
# afterward, not the installed headers. So this Dockerfile deliberately does
# NOT `apk add postgresql-dev` - Alpine's own postgresql16-dev package would
# be a separate build from a different source, and compiling pgvector
# against it instead of the headers matching the actual running binary
# risks an ABI mismatch. Just add a compiler toolchain and build against
# what's already there.
FROM postgres:16.9-alpine

ARG PGVECTOR_VERSION=v0.8.6

# Build-tested live (2026-08-04) against this exact image tag: it has
# --with-llvm JIT support baked in, and pg_config reports
# LLVM_CONFIG=/usr/lib/llvm19/bin/llvm-config - PGXS's bitcode step
# invokes `clang-19` specifically (matching that LLVM build), not
# whatever version a generic `clang`/`llvm-dev` apk alias resolves to.
# First attempt used llvm15-dev/bare `clang` (apk resolved that to
# clang20) and failed with `clang-19: No such file or directory` -
# confirmed empirically, not a guess. llvm19-dev + clang19 exist as
# exact-version Alpine packages; using them fixed it. After that,
# CREATE EXTENSION vector and a real distance query
# ('[1,2,3]' <-> '[4,5,6]' = 5.196152422706632, correct) were verified
# against a live instance built from this Dockerfile before trusting it.
RUN apk add --no-cache --virtual .build-deps \
      git \
      make \
      gcc \
      musl-dev \
      llvm19-dev \
      clang19 \
    && cd /tmp \
    && git clone --branch ${PGVECTOR_VERSION} --depth 1 https://github.com/pgvector/pgvector.git \
    && cd pgvector \
    && make OPTFLAGS="" \
    && make install \
    && cd / \
    && rm -rf /tmp/pgvector \
    && apk del .build-deps
