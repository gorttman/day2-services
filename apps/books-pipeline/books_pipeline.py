#!/usr/bin/env python3
import html.parser
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

import psycopg2
import requests
import yaml

import bookutils

CONFIG_PATH = os.environ["PIPELINE_CONFIG"]
WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL")

COMIC_FORMATS = {"cbz", "cbr"}
INCOMING_PREFIX = ".incoming-"

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


def is_settled(path, settle_seconds):
    st = os.stat(path)
    return (time.time() - st.st_mtime) >= settle_seconds


# ---------------------------------------------------------------------------
# Stage 1: metadata extraction (no conversion)
# ---------------------------------------------------------------------------

def extract_metadata(path):
    result = bookutils.extract_ebook_metadata(path)
    if result["error"]:
        log("WARN", f"ebook-meta failed for {os.path.basename(path)}: {result['error']}")
    meta = {k: v for k, v in result.items() if k != "error"}

    if meta["author"]:
        deduped = bookutils.dedupe_author_credits(meta["author"])
        if deduped != meta["author"]:
            log("INFO", f"collapsed redundant author credit for {os.path.basename(path)}: {meta['author']!r} -> {deduped!r}")
        meta["author"] = deduped

    return meta


# ---------------------------------------------------------------------------
# Stage 2: dedup check
# ---------------------------------------------------------------------------

def dedup_check(conn, meta, config):
    title_norm = bookutils.normalize_title(meta["title"] or "")

    with conn.cursor() as cur:
        if meta["isbn13"]:
            cur.execute(
                "SELECT path, format FROM fingerprints WHERE isbn13 = %s LIMIT 1",
                (meta["isbn13"],),
            )
            row = cur.fetchone()
            if row:
                matched_path, matched_format = row
                kind = "duplicate" if matched_format == meta["format"] else "format_upgrade"
                return kind, matched_path

        if not title_norm:
            return None, None

        # pg_trgm's similarity operator is a literal `%`, which collides
        # with psycopg2's %s parameter placeholders - escaped as %% here.
        # title_norm is selected here too (not just used for the WHERE
        # filter) so the confidence score below compares against the
        # candidate's actual title, not the incoming title reused on
        # both sides - that would only be scoring author similarity,
        # since the WHERE clause already guarantees title similarity.
        cur.execute(
            """
            SELECT path, format, title_norm, author_norm,
                   similarity(title_norm, %s) AS sim
            FROM fingerprints
            WHERE title_norm %% %s
            ORDER BY sim DESC
            LIMIT 10
            """,
            (title_norm, title_norm),
        )
        candidates = cur.fetchall()

    threshold = config.get("fuzzy", {}).get("confident_score", 90)
    for matched_path, matched_format, matched_title_norm, matched_author_norm, _sim in candidates:
        # matched_title_norm/matched_author_norm are already normalized
        # (that's what's stored) - confident_match re-normalizes them,
        # which is a harmless no-op on already-normalized text.
        if bookutils.confident_match(meta["title"], meta["author"], matched_title_norm, matched_author_norm, threshold):
            kind = "duplicate" if matched_format == meta["format"] else "format_upgrade"
            return kind, matched_path

    return None, None


# ---------------------------------------------------------------------------
# Stage 3: convert to EPUB (comics and already-EPUB bypass entirely)
# ---------------------------------------------------------------------------

def convert_to_epub(path, meta, workdir):
    if meta["format"] == "epub" or meta["format"] in COMIC_FORMATS:
        return path, None

    dest = os.path.join(workdir, "converted.epub")
    try:
        result = subprocess.run(
            ["ebook-convert", path, dest],
            capture_output=True, text=True, timeout=600,
        )
    except (subprocess.SubprocessError, OSError) as e:
        return None, str(e)

    if result.returncode != 0 or not os.path.exists(dest):
        return None, result.stderr.strip()[:2000] or "ebook-convert failed, no output produced"

    return dest, None


# ---------------------------------------------------------------------------
# Stage 4: quality checks on the resulting EPUB
# ---------------------------------------------------------------------------

class _TextCollector(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.paragraph_count = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "div"):
            self.paragraph_count += 1

    def handle_data(self, data):
        self.text_parts.append(data)


_RAW_TAG_RE = re.compile(r"<[a-zA-Z!/][^<>]{0,50}>")


def quality_check(epub_path, config):
    quality_cfg = config.get("quality", {})
    max_raw_tag_matches = quality_cfg.get("max_raw_tag_matches", 3)
    max_avg_paragraph_len = quality_cfg.get("max_avg_paragraph_len", 4000)

    try:
        with zipfile.ZipFile(epub_path) as zf:
            content_files = [
                n for n in zf.namelist()
                if n.lower().endswith((".xhtml", ".html", ".htm"))
            ]
            if not content_files:
                return False, "no readable content files found in EPUB"

            total_text_len = 0
            total_paragraphs = 0
            raw_tag_matches = 0

            for name in content_files:
                raw = zf.read(name).decode("utf-8", errors="replace")
                collector = _TextCollector()
                collector.feed(raw)
                text = "".join(collector.text_parts)
                total_text_len += len(text)
                total_paragraphs += collector.paragraph_count
                raw_tag_matches += len(_RAW_TAG_RE.findall(text))
    except (zipfile.BadZipFile, OSError) as e:
        return False, f"could not open EPUB for quality check: {e}"

    if raw_tag_matches > max_raw_tag_matches:
        return False, f"raw HTML detected in extracted text ({raw_tag_matches} matches)"

    if total_paragraphs == 0:
        return False, "no paragraph structure found - likely a broken conversion"

    avg_paragraph_len = total_text_len / total_paragraphs
    if avg_paragraph_len > max_avg_paragraph_len:
        return False, f"low paragraph density (avg {int(avg_paragraph_len)} chars/paragraph) - likely a broken conversion"

    return True, None


# ---------------------------------------------------------------------------
# Stage 5: metadata backfill
# ---------------------------------------------------------------------------

def backfill_metadata(meta, config):
    if meta["title"] and meta["author"] and meta["isbn13"]:
        return meta

    plugins = config.get("metadata_plugins", ["Open Library", "Google Books"])
    candidate = bookutils.fetch_metadata_candidate(
        title=meta["title"], author=meta["author"], isbn13=meta["isbn13"], plugins=plugins,
    )
    if candidate is None:
        return meta

    if not meta["title"] and candidate["title"]:
        meta["title"] = candidate["title"]
    if not meta["author"] and candidate["author"]:
        meta["author"] = candidate["author"]
    if not meta["isbn13"] and candidate["isbn13"]:
        meta["isbn13"] = candidate["isbn13"]

    return meta


# ---------------------------------------------------------------------------
# Quarantine + safe move (duplicated from inbox-router's pattern - no
# shared runtime between the two separate CronJob containers/images)
# ---------------------------------------------------------------------------

def quarantine(path, reason, quarantine_dir, counters):
    name = os.path.basename(path)
    if not os.path.isdir(quarantine_dir):
        log("CRIT", f"quarantine dir unreachable ({quarantine_dir}) - leaving {name} in place: {reason}")
        return

    # Disambiguate by parent directory, not just basename - generic
    # sidecar names (cover.jpg, metadata.opf) recur across thousands of
    # different book folders under a recursive import/ scan. Basename-
    # only collisions were leaving every file after the first stuck in
    # import/ forever (found live: books-pipeline-29743020's logs,
    # 2026-07-20). Falls back to a numeric suffix in the rare case two
    # genuinely different files share both parent dir and filename, so
    # a source is never silently left unquarantined for lack of a slot.
    parent = os.path.basename(os.path.dirname(path)) or "root"
    disambiguated = f"{parent} - {name}"
    final_path = os.path.join(quarantine_dir, disambiguated)
    suffix = 2
    while os.path.exists(final_path):
        disambiguated = f"{parent} - {name} ({suffix})"
        final_path = os.path.join(quarantine_dir, disambiguated)
        suffix += 1
    name = disambiguated

    incoming_path = os.path.join(quarantine_dir, f"{INCOMING_PREFIX}{name}")
    try:
        shutil.copy2(path, incoming_path)
        if os.path.getsize(path) != os.path.getsize(incoming_path):
            raise OSError("size mismatch after copy")
        os.rename(incoming_path, final_path)
        os.remove(path)
    except OSError as e:
        if os.path.exists(incoming_path):
            os.remove(incoming_path)
        log("CRIT", f"failed to quarantine {name}: {e}")
        return

    try:
        with open(os.path.join(quarantine_dir, f"{name}.quarantine-reason.txt"), "w") as f:
            f.write(reason + "\n")
    except OSError as e:
        log("CRIT", f"quarantined {name} but failed to write reason sidecar: {e}")

    counters["quarantined"].append({"file": name, "reason": reason})


def quarantine_broken_symlink(path, reason, quarantine_dir, counters):
    """Moves a broken symlink itself (not its unreachable target) into
    quarantine. os.rename() doesn't follow symlinks, unlike quarantine()
    above's shutil.copy2() - which would try to read the target and
    crash the same way this exists to prevent. Found live 2026-07-21:
    import/Books -> a QNAP-internal path (MD0_DATA/Public/Media/Books)
    not reachable via this NFS export, crashing main()'s settle check
    (which follows symlinks) on every run once the walk reached it."""
    name = os.path.basename(path)
    if not os.path.isdir(quarantine_dir):
        log("CRIT", f"quarantine dir unreachable ({quarantine_dir}) - leaving broken symlink {name} in place: {reason}")
        return

    parent = os.path.basename(os.path.dirname(path)) or "root"
    disambiguated = f"{parent} - {name}"
    final_path = os.path.join(quarantine_dir, disambiguated)
    suffix = 2
    while os.path.lexists(final_path):
        disambiguated = f"{parent} - {name} ({suffix})"
        final_path = os.path.join(quarantine_dir, disambiguated)
        suffix += 1
    name = disambiguated

    try:
        os.rename(path, final_path)
    except OSError as e:
        log("CRIT", f"failed to quarantine broken symlink {name}: {e}")
        return

    try:
        with open(os.path.join(quarantine_dir, f"{name}.quarantine-reason.txt"), "w") as f:
            f.write(reason + "\n")
    except OSError as e:
        log("CRIT", f"quarantined broken symlink {name} but failed to write reason sidecar: {e}")

    counters["quarantined"].append({"file": name, "reason": reason})


def promote(conn, meta, src_path, original_name, config, counters):
    """calibredb add owns file placement (its own Author/Title (id)/
    folder scheme) and writes metadata.db directly - that's what makes a
    promoted book actually show up in calibre-web (see README's former
    "no shared library format with calibre-web" gap, resolved
    2026-07-18). A plain file copy, which is all this used to do, left
    real files sitting in the tree with nothing in metadata.db pointing
    at them - calibre-web only ever shows what's registered in that
    database, never what it finds by scanning the filesystem.

    --duplicates bypasses Calibre's own (cruder, title+author-text-only)
    duplicate check: dedup_check() is this pipeline's single source of
    truth for duplicate/format-upgrade decisions and already ran before
    promote() is ever called - Calibre's own redundant check must never
    silently veto an add this pipeline already decided to make.

    --title/--authors/--isbn pass this pipeline's own meta dict (which
    may have been enriched by stage 5's backfill_metadata) explicitly,
    rather than letting calibredb fall back to whatever's embedded in
    the raw file - otherwise a successful backfill would never actually
    reach calibre-web's displayed metadata.

    DB insert happens after a successful add, committed only then - a
    crash between the add and the commit can still leave a file in the
    library with no fingerprint row. That specific drift shape (file
    exists, no row) is exactly what prompt 5's weekly reconcile job is
    built to detect and report - true cross-system atomicity between a
    filesystem and a database isn't achievable here, so this is an
    accepted, monitored gap rather than an ignored one."""
    if not meta["title"]:
        return False, "insufficient metadata to add to Calibre (no title after backfill)"

    library_dir = config["library_dir"]
    add_cmd = ["calibredb", "add", src_path, "--library-path", library_dir, "--duplicates"]
    add_cmd += ["--title", meta["title"]]
    if meta["author"]:
        add_cmd += ["--authors", meta["author"]]
    if meta["isbn13"]:
        add_cmd += ["--isbn", meta["isbn13"]]

    try:
        result = subprocess.run(add_cmd, capture_output=True, text=True, timeout=120)
    except (subprocess.SubprocessError, OSError) as e:
        return False, f"calibredb add failed to run: {e}"

    if result.returncode != 0:
        return False, f"calibredb add exited {result.returncode}: {result.stderr.strip()[:2000]}"

    id_match = re.search(r"Added book ids: (\d+)", result.stdout)
    if not id_match:
        return False, f"calibredb add did not report a new book id (may have been silently rejected): {result.stdout.strip()[:1000]}"
    book_id = id_match.group(1)

    final_path = f"<calibre id {book_id}>"
    try:
        list_result = subprocess.run(
            ["calibredb", "list", "--library-path", library_dir, "--for-machine",
             "--fields=formats", "--search", f"id:{book_id}"],
            capture_output=True, text=True, timeout=30,
        )
        final_path = json.loads(list_result.stdout)[0]["formats"][0]
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError, IndexError, KeyError) as e:
        log("WARN", f"added calibre id {book_id} but path lookup failed (add itself succeeded): {e}")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO fingerprints (title_norm, author_norm, isbn13, format, path)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (path) DO NOTHING
            """,
            (
                bookutils.normalize_title(meta["title"]),
                bookutils.normalize_author(meta["author"] or ""),
                meta["isbn13"],
                meta["format"],
                final_path,
            ),
        )
    conn.commit()

    os.remove(src_path)

    counters["routes"]["promoted"] = counters["routes"].get("promoted", 0) + 1
    log("INFO", f"promoted {original_name} -> {final_path} (calibre id {book_id})")
    return True, None


# ---------------------------------------------------------------------------
# Per-file pipeline
# ---------------------------------------------------------------------------

def process_file(conn, path, config, counters):
    name = os.path.basename(path)

    # Stage 1
    meta = extract_metadata(path)
    log("INFO", f"stage1 metadata: {name} title={meta['title']!r} author={meta['author']!r} isbn13={meta['isbn13']!r} format={meta['format']}")

    if meta["author"] and not bookutils.looks_like_valid_author(meta["author"]):
        quarantine(
            path,
            "implausible author metadata (likely a title/author swap in the source "
            f"file's own embedded metadata, not a pipeline bug) - author value looks "
            f"like a title/filename fragment, not a name: {meta['author']!r}",
            config["quarantine_dir"], counters,
        )
        return

    # Stage 2
    dedup_kind, matched_path = dedup_check(conn, meta, config)
    if dedup_kind == "duplicate":
        quarantine(path, f"plain duplicate of existing {matched_path}", config["quarantine_dir"], counters)
        counters["duplicates"] = counters.get("duplicates", 0) + 1
        return
    if dedup_kind == "format_upgrade":
        quarantine(path, f"format-upgrade candidate for existing {matched_path} (different format, high-confidence content match)", config["quarantine_dir"], counters)
        counters["format_upgrade_candidates"] = counters.get("format_upgrade_candidates", 0) + 1
        return

    if meta["format"] == "pdf":
        # PDF conversion is explicitly out of scope here (see README's
        # "PDF triage subagent" note) - Calibre's PDF handling is the
        # known weak point, and a PDF-sourced conversion was never going
        # to get auto-promoted regardless (the convert-failure and
        # quality-failure branches below both already refused to
        # auto-promote one). Attempting ebook-convert anyway just burns
        # up to a 600s timeout per file for no benefit. Quarantine
        # immediately instead - same reviewability, none of the wait.
        # Found live 2026-07-18: this was the actual reason the
        # ~4,480-file import backlog (mostly PDFs) was barely draining.
        quarantine(
            path,
            "PDF - triage not automated (Calibre's PDF handling is the known weak "
            "point; see README's 'PDF triage subagent' note). Original may be "
            "promotable as-is after human review (library policy: EPUB-preferred, "
            "PDF-tolerated), but requires manual confirmation, not automatic promotion.",
            config["quarantine_dir"], counters,
        )
        return

    with tempfile.TemporaryDirectory() as workdir:
        # Stage 3
        converted_path, convert_error = convert_to_epub(path, meta, workdir)

        if converted_path is None:
            quarantine(path, f"conversion failed: {convert_error}", config["quarantine_dir"], counters)
            return

        # Stage 4 (skipped for comics - nothing to quality-check, they
        # bypassed conversion entirely and stay in their original format)
        if meta["format"] not in COMIC_FORMATS:
            passed, quality_reason = quality_check(converted_path, config)
            if not passed:
                quarantine(path, f"quality check failed: {quality_reason}", config["quarantine_dir"], counters)
                return
            meta["format"] = "epub"
            promote_src = converted_path
        else:
            promote_src = path

        # Stage 5
        meta = backfill_metadata(meta, config)

        # Stage 6
        ok, promote_reason = promote(conn, meta, promote_src, name, config, counters)
        if not ok:
            # Quarantine the original file, not promote_src - if conversion
            # happened, promote_src is a tempfile.TemporaryDirectory() path
            # named generically "converted.epub" for every book, which both
            # loses the original filename for human review and guarantees a
            # quarantine collision on the second such failure. The original
            # is guaranteed to still exist here: promote() only os.remove()s
            # it on success.
            quarantine(path, promote_reason, config["quarantine_dir"], counters)


# ---------------------------------------------------------------------------
# Webhook summary
# ---------------------------------------------------------------------------

def post_summary(counters):
    summary = {
        "promoted": counters["routes"].get("promoted", 0),
        "duplicates": counters.get("duplicates", 0),
        "format_upgrade_candidates": counters.get("format_upgrade_candidates", 0),
        "quarantined": counters["quarantined"],
    }
    log("INFO", f"run summary: {summary}")

    if not WEBHOOK_URL:
        log("INFO", "N8N_WEBHOOK_URL not set, skipping notification")
        return

    try:
        resp = requests.post(WEBHOOK_URL, json=summary, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        log("WARN", f"failed to post run summary to webhook: {e}")


def main():
    config = load_config(CONFIG_PATH)

    conn = psycopg2.connect(**DB_ENV)
    counters = {"routes": {}, "quarantined": [], "duplicates": 0, "format_upgrade_candidates": 0}

    try:
        import_dir = config["import_dir"]
        # Import arrivals can be nested (e.g. a whole Author/Title.ext
        # tree copied in wholesale, not flat individual files dropped
        # one at a time by inbox-router) - found live 2026-07-18: 4,449
        # author-named subdirectories sitting completely untouched,
        # invisible to a top-level-only os.listdir() scan since
        # directories were silently skipped. promote() always recomputes
        # its own canonical Author/Title path from extracted metadata
        # regardless of where a file came from, so the source tree's own
        # structure is never relied on - safe to flatten here.
        paths = []
        for dirpath, dirnames, filenames in os.walk(import_dir):
            dirnames[:] = [d for d in dirnames if not d.startswith(INCOMING_PREFIX) and not d.startswith(".")]
            for entry in filenames:
                if entry.startswith(INCOMING_PREFIX) or entry.startswith("."):
                    continue
                paths.append(os.path.join(dirpath, entry))

        for path in sorted(paths):
            entry = os.path.basename(path)
            # A dangling symlink passes the walk's own filter (it's not
            # a directory os.walk would descend into) but every
            # stat-following call below - is_settled(), ebook-meta,
            # everything - raises on its unreachable target. Handled
            # before any of that runs, not inside the general except
            # below: found live 2026-07-21 that this was crashing the
            # *entire* job (is_settled() sat outside that try/except),
            # not just failing this one entry, and recurring on every
            # run since nothing ever moved the symlink out of the way.
            if os.path.islink(path) and not os.path.exists(path):
                log("CRIT", f"broken symlink, quarantining without following it: {entry}")
                quarantine_broken_symlink(path, "broken symlink - target not reachable via this NFS export", config["quarantine_dir"], counters)
                continue
            try:
                if not is_settled(path, config["settle_seconds"]):
                    continue
                process_file(conn, path, config, counters)
            except Exception as e:
                log("CRIT", f"unhandled error processing {entry}: {e}")
                conn.rollback()
                quarantine(path, f"unhandled pipeline error: {e}", config["quarantine_dir"], counters)
    finally:
        conn.close()

    post_summary(counters)


if __name__ == "__main__":
    main()
