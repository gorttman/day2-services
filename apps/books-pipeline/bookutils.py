import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from rapidfuzz import fuzz

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_META_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z()\s]*?)\s*:\s*(.*)$")
_ISBN_IDENTIFIER_RE = re.compile(r"isbn:([0-9Xx]{10,13})")


def extract_ebook_metadata(path, timeout=60):
    """Runs ebook-meta and parses title/author/isbn13 from its output.
    Shared by books_pipeline.py's stage 1 and seed_fingerprints.py's
    library scan - the one place this invocation and its output
    parsing should exist.

    Returns a dict {title, author, isbn13, format, error}. `error` is
    None on a clean subprocess run - even if title/author end up empty,
    that's a legitimate "ebook-meta ran but found no metadata" case,
    distinct from the subprocess itself failing to run at all (missing
    binary, timeout, non-zero exit), which is what `error` reports."""
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    result = {"title": None, "author": None, "isbn13": None, "format": ext, "error": None}

    try:
        proc = subprocess.run(["ebook-meta", path], capture_output=True, text=True, timeout=timeout)
    except (subprocess.SubprocessError, OSError) as e:
        result["error"] = f"ebook-meta failed to run: {e}"
        return result

    if proc.returncode != 0:
        result["error"] = f"ebook-meta exited {proc.returncode}: {proc.stderr.strip()[:500]}"
        return result

    for line in proc.stdout.splitlines():
        m = _META_LINE_RE.match(line)
        if not m:
            continue
        label, value = m.group(1).strip().lower(), m.group(2).strip()
        if label == "title" and value:
            result["title"] = value
        elif label.startswith("author") and value:
            # "Jane Doe [Doe, Jane]" - the bracketed part is the sort name
            result["author"] = value.split(" [")[0].strip()
        elif label == "identifiers" and value:
            isbn_match = _ISBN_IDENTIFIER_RE.search(value)
            if isbn_match:
                result["isbn13"] = normalize_isbn(isbn_match.group(1))

    return result


def normalize_title(title):
    return _normalize_text(title)


def normalize_author(author):
    return _normalize_text(author)


def _normalize_text(value):
    value = value.lower()
    value = _PUNCT_RE.sub(" ", value)
    value = _WS_RE.sub(" ", value).strip()
    return value


def normalize_isbn(raw):
    """Strip formatting, validate checksum, return a bare ISBN-13 digit
    string (converting ISBN-10 if needed) or None if invalid/unparseable.
    Never guesses - an invalid or ambiguous input returns None."""
    if not raw:
        return None
    digits = re.sub(r"[^0-9Xx]", "", raw)

    if len(digits) == 13:
        return digits if _isbn13_checksum_ok(digits) else None

    if len(digits) == 10:
        if not _isbn10_checksum_ok(digits):
            return None
        return _isbn10_to_isbn13(digits)

    return None


def _isbn13_checksum_ok(digits):
    if not digits.isdigit():
        return False
    total = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(digits[:12]))
    check = (10 - (total % 10)) % 10
    return check == int(digits[12])


def _isbn10_checksum_ok(digits):
    total = 0
    for i, ch in enumerate(digits[:9]):
        if not ch.isdigit():
            return False
        total += (10 - i) * int(ch)
    last = digits[9]
    check_value = 10 if last in ("X", "x") else (int(last) if last.isdigit() else None)
    if check_value is None:
        return False
    total += check_value
    return total % 11 == 0


def _isbn10_to_isbn13(digits):
    core = "978" + digits[:9]
    total = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(core))
    check = (10 - (total % 10)) % 10
    return core + str(check)


_OPF_NS = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}


def fetch_metadata_candidate(title=None, author=None, isbn13=None, plugins=None, timeout=30):
    """Query fetch-ebook-metadata and parse its OPF output. Returns a
    dict with title/author/isbn13 keys (any may be None if not found),
    or None if there was nothing to search on or the lookup produced no
    usable result. Shared by books_pipeline.py's backfill stage and
    pdf_triage.py's stage 2 lookup - the one place this invocation and
    its OPF parsing should exist.

    UNVERIFIED: assumes -o/--opf takes a destination path, based on
    Calibre docs' description ("Output metadata in OPF format") without
    a real image to test --help/behavior against. Confirm on first real
    run; if it instead prints OPF to stdout, redirect that instead of
    using -o here.
    """
    if not title and not author and not isbn13:
        return None

    plugins = plugins or ["Open Library", "Google Books"]
    args = ["fetch-ebook-metadata"]
    for p in plugins:
        args += ["--allowed-plugin", p]
    if title:
        args += ["-t", title]
    if author:
        args += ["-a", author]
    if isbn13:
        args += ["-i", isbn13]

    with tempfile.NamedTemporaryFile(suffix=".opf", delete=False) as tmp:
        opf_path = tmp.name
    args += ["-o", opf_path]

    result = {"title": None, "author": None, "isbn13": None}
    try:
        subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        tree = ET.parse(opf_path)
        root = tree.getroot()

        title_el = root.find(".//dc:title", _OPF_NS)
        if title_el is not None and title_el.text:
            result["title"] = title_el.text.strip()

        creator_el = root.find(".//dc:creator", _OPF_NS)
        if creator_el is not None and creator_el.text:
            result["author"] = creator_el.text.strip()

        for id_el in root.findall(".//dc:identifier", _OPF_NS):
            scheme = id_el.attrib.get(f"{{{_OPF_NS['opf']}}}scheme", "").lower()
            if scheme == "isbn" and id_el.text:
                result["isbn13"] = normalize_isbn(id_el.text)
                break
    except (subprocess.SubprocessError, ET.ParseError, OSError):
        return None
    finally:
        if os.path.exists(opf_path):
            os.remove(opf_path)

    if not result["title"] and not result["author"] and not result["isbn13"]:
        return None
    return result


def match_score(query_title, query_author, candidate_title, candidate_author):
    """Raw rapidfuzz WRatio score (0-100) over normalized title+author.
    Split out from confident_match so callers that need the borderline
    band (pdf_triage.py's stage 2/3 tiebreak), not just a yes/no, don't
    have to reimplement the scoring itself - only the threshold
    comparison differs."""
    query_combined = f"{normalize_title(query_title or '')} {normalize_author(query_author or '')}"
    candidate_combined = f"{normalize_title(candidate_title or '')} {normalize_author(candidate_author or '')}"
    return fuzz.WRatio(query_combined, candidate_combined)


def confident_match(query_title, query_author, candidate_title, candidate_author, threshold=90):
    """rapidfuzz WRatio comparison over normalized title+author, same
    scoring pattern as books_pipeline.dedup_check() - shared so a
    'confident match' means the same thing everywhere it's used
    (dedup against the fingerprint table, or a metadata-lookup result
    in pdf_triage.py)."""
    score = match_score(query_title, query_author, candidate_title, candidate_author)
    return score >= threshold
