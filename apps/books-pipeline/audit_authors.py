#!/usr/bin/env python3
import json
import subprocess
from collections import Counter

result = subprocess.run(
    ["calibredb", "list", "--library-path", "/mnt/books", "--for-machine", "--fields=title,authors"],
    capture_output=True, text=True,
)
rows = json.loads(result.stdout)
print(f"{len(rows)} total books")

author_tokens = Counter()
for r in rows:
    for a in r["authors"].split(" & "):
        author_tokens[a.strip()] += 1

print(f"{len(author_tokens)} distinct author tokens (split on &)\n")

names = sorted(author_tokens)
print("=== all distinct author tokens ===")
for n in names:
    print(f"{author_tokens[n]:3}  {n!r}")

print("\n=== potential near-duplicates (one name is a prefix of another) ===")
for i, a in enumerate(names):
    for b in names[i + 1:]:
        if b.startswith(a) or a.startswith(b):
            print(f"{a!r}  <->  {b!r}")

print("\n=== title-level exact duplicates ===")
title_counts = Counter(r["title"].strip().lower() for r in rows)
for t, c in title_counts.items():
    if c > 1:
        print(f"{c}x  {t!r}")
        for r in rows:
            if r["title"].strip().lower() == t:
                print(f"      authors={r['authors']!r}")
