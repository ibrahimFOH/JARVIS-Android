"""JARVIS shared Windows host bridge for Android clients.

Run from JARVIS_HOST with: python android_bridge.py
Set JARVIS_BRIDGE_TOKEN to a long random secret before exposing on the LAN.
The bridge only accepts authenticated JSON requests and binds to the local network.
"""
import json
import os
import re
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

HOST = os.environ.get("JARVIS_BRIDGE_HOST", "0.0.0.0")
PORT = int(os.environ.get("JARVIS_BRIDGE_PORT", "8765"))
TOKEN_FILE = ROOT / "config" / "bridge_token.txt"


def load_token():
    token = os.environ.get("JARVIS_BRIDGE_TOKEN", "").strip()
    if token:
        return token
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token, encoding="utf-8")
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass
    print(f"Created bridge token at: {TOKEN_FILE}")
    print("Enter this token in the Android app's HOST settings. Do not share it.")
    return token


TOKEN = load_token()


class Handler(BaseHTTPRequestHandler):
    server_version = "JARVIS-Bridge/1.0"

    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("[bridge] " + (fmt % args))

    def do_GET(self):
        if urlparse(self.path).path != "/api/health":
            return self._send(404, {"success": False, "error": "not_found"})
        if not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + TOKEN):
            return self._send(401, {"success": False, "error": "unauthorized"})
        return self._send(200, {"success": True, "service": "JARVIS", "sharedHost": True})

    def do_POST(self):
        if urlparse(self.path).path != "/api/command":
            return self._send(404, {"success": False, "error": "not_found"})
        if not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + TOKEN):
            return self._send(401, {"success": False, "error": "unauthorized"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 16384:
                return self._send(413, {"success": False, "error": "invalid_body_size"})
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            command = str(data.get("command", "")).strip()
            if not command:
                return self._send(400, {"success": False, "error": "empty_command"})
            if len(command) > 4000:
                return self._send(413, {"success": False, "error": "command_too_long"})
            profile_context = data.get("profile_context", "")
            if not isinstance(profile_context, str):
                return self._send(400, {"success": False, "error": "invalid_profile_context"})
            profile_context = profile_context.strip()
            if len(profile_context) > 1200:
                return self._send(413, {"success": False, "error": "profile_context_too_long"})
            # Treat a phone profile as factual context only and never pass obvious secrets to the model.
            profile_context = re.sub(
                r"(?i)\\b(password|parola|şifre|sifre|access[_ -]?token|api[_ -]?key|secret)\\s*[:=]\\s*[^\\s,;]+",
                r"\\1=[REDACTED]", profile_context
            )

            from core import get_jarvis
            jarvis = get_jarvis()
            if not jarvis.is_running:
                jarvis.start()

            # Use the same command processor and AI configuration as the Windows app.
            result = jarvis.command_processor.process(command, profile_context=profile_context)
            if not isinstance(result, dict):
                result = {"success": False, "response": "JARVIS geçerli bir yanıt döndürmedi."}
            response = {
                "success": bool(result.get("success", False)),
                "response": str(result.get("response", "")),
                "intent": str(result.get("intent", "")),
                "requires_confirmation": bool(result.get("requires_confirmation", False)),
                "sharedHost": True,
            }
            return self._send(200, response)
        except Exception as exc:
            print(f"[bridge] command error: {type(exc).__name__}: {exc}")
            return self._send(500, {"success": False, "error": "command_failed",
                                    "response": "Windows JARVIS komutu işlerken hata oluştu."})


_background_server = None


def start_background_server():
    """Start the authenticated LAN bridge once, inside the desktop EXE process."""
    global _background_server
    if _background_server is not None:
        return _background_server
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    worker = threading.Thread(
        target=server.serve_forever,
        name="JARVIS-Android-Bridge",
        daemon=True,
    )
    worker.start()
    _background_server = server
    print(f"JARVIS bridge listening on http://{HOST}:{PORT}")
    print("LAN access requires Windows Firewall permission for this port.")
    return server


if __name__ == "__main__":
    try:
        server = start_background_server()
        threading.Event().wait()
    except KeyboardInterrupt:
        if _background_server is not None:
            _background_server.shutdown()
        print("\nJARVIS bridge stopped.")
