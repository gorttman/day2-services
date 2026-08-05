#!/usr/bin/env python3
"""Paperless post-consume script. Tags a document
"Property - Hepburn (Home)" if its content mentions the address plus a
known provider/home-domain term. Exists because the equivalent check
can't live in Paperless's own Tag.match field (256-char limit, far too
small for a real provider list) - see hepburn-providers.yaml and
apps/paperless/README.md for the design history.

Invoked by Paperless itself (PAPERLESS_POST_CONSUME_SCRIPT) after every
successful consumption, with DOCUMENT_ID set in the environment. Talks
back to Paperless over its own REST API (PAPERLESS_API_TOKEN) rather
than assuming Django internals are reachable from a subprocess - the
documented, supported extension point.
"""
import os
import urllib.request
import urllib.error
import urllib.parse
import json

import yaml

PAPERLESS_URL = os.environ.get("PAPERLESS_URL_INTERNAL", "http://localhost:8000")
API_TOKEN = os.environ["PAPERLESS_API_TOKEN"]
PROVIDERS_PATH = os.environ.get("HEPBURN_PROVIDERS_PATH", "/etc/paperless-hooks/hepburn-providers.yaml")
TAG_NAME = "Property - Hepburn (Home)"
ADDRESS_TERM = "hepburn"


def log(level, msg):
    print(f"[hepburn-tag-hook] {level:5} {msg}", flush=True)


def api_request(path, method="GET", data=None):
    url = f"{PAPERLESS_URL}{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Token {API_TOKEN}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def load_provider_terms():
    with open(PROVIDERS_PATH) as f:
        data = yaml.safe_load(f)
    terms = []
    for category in ("fixed", "electricity", "gas", "insurance", "generic"):
        terms.extend(data.get(category, []))
    return terms


def find_tag_id(name):
    result = api_request(f"/api/tags/?name__iexact={urllib.parse.quote(name)}")
    results = result.get("results", [])
    if not results:
        return None
    return results[0]["id"]


def main():
    document_id = os.environ.get("DOCUMENT_ID")
    if not document_id:
        log("WARN", "DOCUMENT_ID not set, nothing to do")
        return

    try:
        doc = api_request(f"/api/documents/{document_id}/")
    except urllib.error.URLError as e:
        log("WARN", f"could not fetch document {document_id}: {e}")
        return

    content = (doc.get("content") or "").lower()
    if ADDRESS_TERM not in content:
        return

    terms = load_provider_terms()
    matched_term = next((t for t in terms if t in content), None)
    if not matched_term:
        log("INFO", f"document {document_id} mentions '{ADDRESS_TERM}' but no known provider/home term - not tagging")
        return

    tag_id = find_tag_id(TAG_NAME)
    if tag_id is None:
        log("WARN", f"tag '{TAG_NAME}' does not exist in Paperless - create it first")
        return

    existing_tags = doc.get("tags", [])
    if tag_id in existing_tags:
        log("INFO", f"document {document_id} already tagged, nothing to do")
        return

    api_request(
        f"/api/documents/{document_id}/",
        method="PATCH",
        data={"tags": existing_tags + [tag_id]},
    )
    log("INFO", f"tagged document {document_id} ({doc.get('title')!r}) - matched on '{matched_term}'")


if __name__ == "__main__":
    main()
