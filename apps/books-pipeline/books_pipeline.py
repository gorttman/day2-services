#!/usr/bin/env python3
import html.parser
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
    return {k: v for k, v in result.items() if k != "error"}


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

    final_path = os.path.join(quarantine_dir, name)
    if os.path.exists(final_path):
        log("CRIT", f"quarantine collision for {name} - leaving original in place: {reason}")
        return

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


def promote(conn, meta, src_path, config, counters):
    """DB insert happens in the same transaction as the file move, and is
    only committed after the move succeeds - but a crash between the
    filesystem rename and the commit can still leave a file in the
    library with no fingerprint row. That specific drift shape (file
    exists, no row) is exactly what prompt 5's weekly reconcile job is
    built to detect and report - true cross-system atomicity between a
    filesystem and a database isn't achievable here, so this is an
    accepted, monitored gap rather than an ignored one."""
    is_comic = meta["format"] in COMIC_FORMATS
    library_dir = config["library_comics_dir"] if is_comic else config["library_books_dir"]

    author_display = bookutils.safe_filename_component(meta["author"], "Unknown Author")
    title_display = bookutils.safe_filename_component(meta["title"], None)
    if title_display is None:
        return False, "insufficient metadata to compute canonical path (no title after backfill)"

    dest_dir = os.path.join(library_dir, author_display)
    name = f"{title_display}.{meta['format']}"
    final_path = os.path.join(dest_dir, name)

    if os.path.exists(final_path):
        return False, f"destination filename collision: {final_path} already exists"

    try:
        os.makedirs(dest_dir, exist_ok=True)
    except OSError as e:
        return False, f"could not create library directory {dest_dir}: {e}"

    incoming_path = os.path.join(dest_dir, f"{INCOMING_PREFIX}{name}")

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

        try:
            shutil.copy2(src_path, incoming_path)
            if os.path.getsize(src_path) != os.path.getsize(incoming_path):
                raise OSError("size mismatch after copy")
            os.rename(incoming_path, final_path)
        except OSError as e:
            conn.rollback()
            if os.path.exists(incoming_path):
                os.remove(incoming_path)
            return False, f"move to library failed: {e}"

        os.remove(src_path)
        conn.commit()

    counters["routes"]["promoted"] = counters["routes"].get("promoted", 0) + 1
    log("INFO", f"promoted {os.path.basename(src_path)} -> {final_path}")
    return True, None


# ---------------------------------------------------------------------------
# Per-file pipeline
# ---------------------------------------------------------------------------

def process_file(conn, path, config, counters):
    name = os.path.basename(path)

    # Stage 1
    meta = extract_metadata(path)
    log("INFO", f"stage1 metadata: {name} title={meta['title']!r} author={meta['author']!r} isbn13={meta['isbn13']!r} format={meta['format']}")

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

    is_pdf_source = meta["format"] == "pdf"

    with tempfile.TemporaryDirectory() as workdir:
        # Stage 3
        converted_path, convert_error = convert_to_epub(path, meta, workdir)

        if converted_path is None:
            reason = f"conversion failed: {convert_error}"
            if is_pdf_source:
                reason += " - original PDF may be promotable as-is after human review (library policy: EPUB-preferred, PDF-tolerated), but requires manual confirmation, not automatic promotion"
            quarantine(path, reason, config["quarantine_dir"], counters)
            return

        # Stage 4 (skipped for comics - nothing to quality-check, they
        # bypassed conversion entirely and stay in their original format)
        if meta["format"] not in COMIC_FORMATS:
            passed, quality_reason = quality_check(converted_path, config)
            if not passed:
                reason = f"quality check failed: {quality_reason}"
                if is_pdf_source:
                    reason += " - original PDF may be promotable as-is after human review, requires manual confirmation"
                quarantine(path, reason, config["quarantine_dir"], counters)
                return
            meta["format"] = "epub"
            promote_src = converted_path
        else:
            promote_src = path

        # Stage 5
        meta = backfill_metadata(meta, config)

        # Stage 6
        ok, promote_reason = promote(conn, meta, promote_src, config, counters)
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
        for entry in sorted(os.listdir(import_dir)):
            path = os.path.join(import_dir, entry)
            if os.path.isdir(path) or entry.startswith(INCOMING_PREFIX) or entry.startswith("."):
                continue
            if not is_settled(path, config["settle_seconds"]):
                continue
            try:
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
