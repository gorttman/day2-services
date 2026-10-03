"""Merge desired-config.json into Music Assistant's settings.json.

Runs as an init container, before MA starts, so MA never has the file open.
Dicts merge recursively; lists and scalars from the desired file REPLACE what
is there. Only keys named in desired-config.json are touched - everything
else (provider logins, library, UI-only state) is left exactly as MA wrote it.
"""
import json
import os
import sys

SETTINGS = "/data/settings.json"
DESIRED = "/desired/desired-config.json"


def merge(base, over, path, changes):
    for key, val in over.items():
        here = f"{path}.{key}" if path else key
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            merge(base[key], val, here, changes)
        elif isinstance(val, dict):
            base[key] = {}
            merge(base[key], val, here, changes)
            changes.append(f"created {here}")
        elif base.get(key) != val:
            changes.append(f"set {here}")
            base[key] = val


def main():
    if not os.path.exists(SETTINGS):
        # First ever start: MA has not written its file yet. Nothing to merge
        # into; the next pod start (or a restart) will apply it.
        print("settings.json not present yet - skipping (first run)")
        return 0
    with open(SETTINGS) as fh:
        settings = json.load(fh)
    with open(DESIRED) as fh:
        desired = json.load(fh)
    changes = []
    merge(settings, desired, "", changes)
    if not changes:
        print("settings.json already matches desired-config.json")
        return 0
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(settings, fh, indent=2)
    os.replace(tmp, SETTINGS)
    # Key paths only - never values, the file holds credentials.
    print("applied:", ", ".join(changes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
