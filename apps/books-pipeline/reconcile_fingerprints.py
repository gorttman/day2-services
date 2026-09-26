#!/usr/bin/env python3
"""Recurring weekly job. Read-only against the database, and read-only
against the library itself - it never inserts, deletes or modifies a book
or a fingerprints row. Reports drift between books/library/ and the
fingerprints table for manual review.

ONE documented write, added 2026-09-27: a run record at
<library_dir>/.reconcile-last-run.json. It exists because
activeDeadlineSeconds kills this job by deleting its pod, which takes the
pod logs with it - three consecutive DeadlineExceeded failures left no
evidence of how far the run had got. The record is written on normal exit
AND from a SIGTERM handler, so a killed run still says where it stopped.
Dot-prefixed deliberately: walk_library_paths() skips names starting with
".", so it can never show up as an untracked file in its own report."""
import json
import os
import signal
import sys
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


# Directories between walk-progress lines. 250 keeps a ~15-25 minute run
# to a readable handful of lines rather than thousands.
PROGRESS_EVERY = int(os.environ.get("PROGRESS_EVERY", "250"))

_STARTED = time.monotonic()
_STARTED_WALL = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
_RECORD_NAME = ".reconcile-last-run.json"
_record_state = {"phase": "starting"}


def log(level, msg):
    ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    print(f"[{ts}] {level:5} {msg}", flush=True)


def write_run_record(library_dir, outcome):
    """Persist the run's timing to the share so it outlives the pod.

    Best-effort by design: this job's value is the drift report, so a
    failure to write the record must never mask it or change the exit
    code. Wrapped broadly for that reason - and because the SIGTERM path
    calls it while the NFS mount may already be going away.
    """
    elapsed = time.monotonic() - _STARTED
    record = {
        "started": _STARTED_WALL,
        "finished": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(elapsed, 1),
        "outcome": outcome,
        **_record_state,
    }
    log("INFO", f"run record: {json.dumps(record)}")
    try:
        with open(os.path.join(library_dir, _RECORD_NAME), "w") as f:
            json.dump(record, f, indent=1)
    except OSError as e:
        log("WARN", f"could not write run record: {e}")


def _on_sigterm(signum, frame):
    # activeDeadlineSeconds kills the pod via SIGTERM. Default Python
    # behaviour is to die without running finally blocks, which is
    # exactly how three failed Sundays left zero evidence. Record where
    # we got to, then exit non-zero so the Job still reads as failed.
    log("WARN", f"SIGTERM at {time.monotonic() - _STARTED:.0f}s - "
                "deadline kill, recording partial progress")
    write_run_record(_record_state.get("library_dir", "/mnt/books"), "killed-sigterm")
    sys.exit(143)


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
    # Progress every PROGRESS_EVERY directories. The walk is the whole
    # cost of this job (NFS stat latency over ~5,253 book dirs, measured
    # D-state at 1-4 millicores), and before this it emitted nothing at
    # all until it finished - so a run killed mid-walk was invisible.
    dirs_seen = 0
    for root, dirnames, files in os.walk(library_dir):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        dirs_seen += 1
        if dirs_seen % PROGRESS_EVERY == 0:
            log("INFO", f"walk progress: {dirs_seen} dirs, {len(paths)} files, "
                        f"{time.monotonic() - _STARTED:.0f}s elapsed")
        for fname in files:
            if fname.startswith(".") or fname.endswith(".quarantine-reason.txt"):
                continue
            if fname in CALIBRE_SIDECAR_NAMES:
                continue
            paths.add(os.path.join(root, fname))
    return paths


def main():
    signal.signal(signal.SIGTERM, _on_sigterm)
    config = load_config(CONFIG_PATH)
    library_dir = config["library_dir"]
    _record_state["library_dir"] = library_dir
    _record_state["phase"] = "walking"
    log("INFO", f"reconcile starting at {_STARTED_WALL}, library_dir={library_dir}")

    actual_paths = walk_library_paths(library_dir)
    walk_seconds = time.monotonic() - _STARTED
    _record_state.update(phase="querying-db", files_found=len(actual_paths),
                         walk_seconds=round(walk_seconds, 1))
    log("INFO", f"found {len(actual_paths)} actual files in library "
                f"(walk took {walk_seconds:.0f}s)")

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
    _record_state.update(phase="done", stale=len(stale), untracked=len(untracked))
    write_run_record(library_dir, "ok")
    log("INFO", f"reconcile finished in {time.monotonic() - _STARTED:.0f}s")


if __name__ == "__main__":
    main()
