import base64
import hashlib
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ALLOWED_USER = os.environ["ALLOWED_USER"]
PAM_SERVICE = os.environ.get("PAM_SERVICE", "code-server")
REALM = os.environ.get("REALM", "vscode-server")
PORT = int(os.environ.get("PORT", "8081"))
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "300"))

# code-server issues dozens of concurrent asset/websocket requests per
# session, each of which would otherwise spawn a pamtester subprocess.
# Cache verified credentials briefly so a burst doesn't hammer PAM.
_cache = {}
_cache_lock = threading.Lock()


def cache_key(username, password):
    return hashlib.sha256(f"{username}:{password}".encode()).hexdigest()


def cached_ok(key):
    with _cache_lock:
        expiry = _cache.get(key)
        if expiry is None:
            return False
        if expiry < time.monotonic():
            del _cache[key]
            return False
        return True


def cache_store(key):
    with _cache_lock:
        _cache[key] = time.monotonic() + CACHE_TTL_SECONDS


def pam_authenticate(username, password):
    try:
        result = subprocess.run(
            ["pamtester", PAM_SERVICE, username, "authenticate"],
            input=password.encode(),
            capture_output=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.check_auth()

    def do_POST(self):
        self.check_auth()

    def check_auth(self):
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            try:
                username, password = base64.b64decode(auth_header[6:]).decode().split(":", 1)
            except Exception:
                username, password = "", ""
            if username == ALLOWED_USER and password:
                key = cache_key(username, password)
                if cached_ok(key) or pam_authenticate(username, password):
                    cache_store(key)
                    self.send_response(200)
                    self.send_header("Remote-User", username)
                    self.end_headers()
                    return
        self.send_response(401)
        self.send_header("WWW-Authenticate", f'Basic realm="{REALM}"')
        self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
