import html
import json
import os
import secrets
import subprocess
import threading
import time
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

ALLOWED_USER = os.environ["ALLOWED_USER"]
PAM_SERVICE = os.environ.get("PAM_SERVICE", "code-server")
PORT = int(os.environ.get("PORT", "8081"))
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "43200"))
COOKIE_NAME = os.environ.get("COOKIE_NAME", "vscode_gorttman_session")
COOKIE_PATH = os.environ.get("COOKIE_PATH", "/gorttman")
DEFAULT_REDIRECT = COOKIE_PATH + "/"

# Basic-Auth-over-forwardAuth doesn't survive Safari's WebSocket handshake
# (Safari won't reliably resend cached Basic-Auth creds on a WS upgrade),
# so auth is a real cookie session instead: a login form served outside the
# forwardAuth path, and a /verify endpoint forwardAuth calls that just
# checks the session cookie (no PAM call on the hot path).
_sessions = {}
_lock = threading.Lock()

LOGIN_FORM = """<!doctype html>
<html><head><title>vscode-server login</title>
<style>body{{font-family:sans-serif;max-width:320px;margin:80px auto}}
input{{display:block;width:100%;margin-bottom:10px;padding:8px;box-sizing:border-box}}
.error{{color:#c00}}</style></head>
<body>
<h3>vscode-server</h3>
{error}
<form method="POST" action="">
<input type="hidden" name="redirect" value="{redirect}">
<input type="text" name="username" placeholder="Username" autofocus required>
<input type="password" name="password" placeholder="Password" required>
<input type="submit" value="Log in">
</form>
</body></html>
"""


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


def issue_session():
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = time.monotonic() + SESSION_TTL_SECONDS
    return token


def session_valid(token):
    with _lock:
        expiry = _sessions.get(token)
        if expiry is None:
            return False
        if expiry < time.monotonic():
            del _sessions[token]
            return False
        return True


def safe_redirect(target):
    if target and target.startswith(COOKIE_PATH):
        return target
    return DEFAULT_REDIRECT


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path == "/verify":
            self.handle_verify()
        else:
            self.handle_login_get()

    def do_POST(self):
        if urlparse(self.path).path == "/verify":
            self.handle_verify()
        else:
            self.handle_login_post()

    def handle_verify(self):
        jar = cookies.SimpleCookie()
        jar.load(self.headers.get("Cookie", ""))
        token = jar[COOKIE_NAME].value if COOKIE_NAME in jar else None
        if token and session_valid(token):
            self.send_response(200)
            self.send_header("Remote-User", ALLOWED_USER)
            self.end_headers()
            return

        proto = self.headers.get("X-Forwarded-Proto", "https")
        host = self.headers.get("X-Forwarded-Host", "vscode.i3sec.com.au")
        uri = self.headers.get("X-Forwarded-Uri", DEFAULT_REDIRECT)
        login_url = f"{proto}://{host}{COOKIE_PATH}/auth?redirect={quote(uri, safe='')}"
        # 401, not 302: nginx's auth_request module only accepts 2xx/401/403
        # from the auth subrequest - anything else (including 302) is treated
        # as an internal error, since nginx expects to build the redirect
        # itself via its own auth-signin annotation on a 401. Traefik's
        # forwardAuth passes a non-2xx response through unaltered (status,
        # headers, and body), so the client-side redirect below keeps the
        # internal (Traefik) path working exactly as it did with a 302.
        body = (
            "<!doctype html><html><head>"
            f'<meta http-equiv="refresh" content="0; url={html.escape(login_url)}">'
            f"<script>window.location.replace({json.dumps(login_url)});</script>"
            "</head><body>Redirecting to login&hellip; "
            f'<a href="{html.escape(login_url)}">click here if not redirected</a>.'
            "</body></html>"
        ).encode()
        self.send_response(401)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_login_get(self):
        query = parse_qs(urlparse(self.path).query)
        redirect = safe_redirect(query.get("redirect", [""])[0])
        body = LOGIN_FORM.format(error="", redirect=html.escape(redirect)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_login_post(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        fields = parse_qs(raw.decode())
        username = fields.get("username", [""])[0]
        password = fields.get("password", [""])[0]
        redirect = safe_redirect(fields.get("redirect", [""])[0])

        if username == ALLOWED_USER and password and pam_authenticate(username, password):
            token = issue_session()
            self.send_response(302)
            self.send_header("Location", redirect)
            self.send_header(
                "Set-Cookie",
                f"{COOKIE_NAME}={token}; Path={COOKIE_PATH}; Max-Age={SESSION_TTL_SECONDS}; "
                "HttpOnly; Secure; SameSite=Lax",
            )
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        body = LOGIN_FORM.format(
            error='<p class="error">Invalid username or password.</p>',
            redirect=html.escape(redirect),
        ).encode()
        self.send_response(401)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
