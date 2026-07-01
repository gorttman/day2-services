import base64
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ALLOWED_USER = os.environ["ALLOWED_USER"]
PAM_SERVICE = os.environ.get("PAM_SERVICE", "code-server")
REALM = os.environ.get("REALM", "vscode-server")
PORT = int(os.environ.get("PORT", "8081"))


def pam_authenticate(username, password):
    try:
        result = subprocess.run(
            ["pamtester", PAM_SERVICE, username, "authenticate"],
            input=password.encode(),
            capture_output=True,
            timeout=5,
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
            if username == ALLOWED_USER and password and pam_authenticate(username, password):
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
