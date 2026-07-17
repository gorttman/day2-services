#!/usr/bin/env python3
"""Recurring weekly job. Read-only against both the filesystem and the
database - never inserts, deletes, or modifies anything. Reports drift
between books/library/ and the fingerprints table for manual review."""
import os
import time

import psycopg2
import requests
import yaml

CONFIG_PATH = os.environ["PIPELINE_CONFIG"]
WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL")

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


def walk_library_paths(*library_dirs):
    paths = set()
    for library_dir in library_dirs:
        if not os.path.isdir(library_dir):
            log("WARN", f"library dir does not exist, skipping: {library_dir}")
            continue
        for root, _dirs, files in os.walk(library_dir):
            for fname in files:
                if fname.startswith(".") or fname.endswith(".quarantine-reason.txt"):
                    continue
                paths.add(os.path.join(root, fname))
    return paths


def main():
    config = load_config(CONFIG_PATH)

    actual_paths = walk_library_paths(config["library_books_dir"], config["library_comics_dir"])
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

    summary = {"stale": stale, "untracked": untracked}
    if not WEBHOOK_URL:
        log("INFO", "N8N_WEBHOOK_URL not set, skipping notification")
        return

    try:
        resp = requests.post(WEBHOOK_URL, json=summary, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        log("WARN", f"failed to post reconcile summary to webhook: {e}")


if __name__ == "__main__":
    main()
