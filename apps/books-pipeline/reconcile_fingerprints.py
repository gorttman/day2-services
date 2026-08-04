#!/usr/bin/env python3
"""Recurring weekly job. Read-only against both the filesystem and the
database - never inserts, deletes, or modifies anything. Reports drift
between books/library/ and the fingerprints table for manual review."""
import os
import time

import psycopg2
import yaml

CONFIG_PATH = os.environ["PIPELINE_CONFIG"]

DB_ENV = dict(
    host=os.environ.get("BOOKS_DB_HOST", "postgres.postgres.svc.cluster.local"),
    port=os.environ.get("BOOKS_DB_PORT", "5432"),
    dbname=os.environ.get("BOOKS_DB_NAME", "books"),
    user=os.environ.get("BOOKS_DB_USER", "books"),
    password=os.environ.get("BOOKS_DB_PASSWORD"),
)


def log(level, msg):
    ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    print(f"[{ts}] {level:5} {msg}", flush=True)


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


# Every calibredb add (2026-07-18) creates these alongside the actual
# book file - metadata.opf and cover.jpg per book, metadata.db once at
# the library root. None are tracked in fingerprints (which only ever
# stores the promoted ebook file itself), so without this exclusion
# every single book would report two permanent false-positive
# "untracked" entries, plus one more for the whole library.
CALIBRE_SIDECAR_NAMES = {"metadata.opf", "cover.jpg", "metadata.db"}


def walk_library_paths(library_dir):
    paths = set()
    if not os.path.isdir(library_dir):
        log("WARN", f"library dir does not exist, skipping: {library_dir}")
        return paths
    for root, dirnames, files in os.walk(library_dir):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fname in files:
            if fname.startswith(".") or fname.endswith(".quarantine-reason.txt"):
                continue
            if fname in CALIBRE_SIDECAR_NAMES:
                continue
            paths.add(os.path.join(root, fname))
    return paths


def main():
    config = load_config(CONFIG_PATH)

    actual_paths = walk_library_paths(config["library_dir"])
    log("INFO", f"found {len(actual_paths)} actual files in library")

    conn = psycopg2.connect(**DB_ENV)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT path FROM fingerprints")
            db_paths = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()
    log("INFO", f"found {len(db_paths)} rows in fingerprints")

    # stale: a row exists but the file doesn't - book was deleted or
    # moved outside the pipeline.
    stale = sorted(db_paths - actual_paths)
    # untracked: a file exists but there's no row - arrived outside the
    # pipeline (manually copied in), or is the exact crash-window gap
    # documented in books_pipeline.py's promote() (file renamed, DB
    # commit never happened).
    untracked = sorted(actual_paths - db_paths)

    for p in stale:
        log("WARN", f"stale row (no file): {p}")
    for p in untracked:
        log("WARN", f"untracked file (no row): {p}")

    log("INFO", f"reconcile summary: stale={len(stale)} untracked={len(untracked)}")


if __name__ == "__main__":
    main()
