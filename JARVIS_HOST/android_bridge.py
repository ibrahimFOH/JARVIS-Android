"""JARVIS shared Windows host bridge for Android clients.

Run from JARVIS_HOST with: python android_bridge.py
Set JARVIS_BRIDGE_TOKEN to a long random secret before exposing on the LAN.
The bridge only accepts authenticated JSON requests and binds to the local network.
"""
import json
import ipaddress
import os
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

HOST = os.environ.get("JARVIS_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("JARVIS_BRIDGE_PORT", "8765"))


def _token_file_path():
    # A PyInstaller one-file app extracts code into a temporary _MEIPASS folder.
    # Never keep the pairing token there: it must survive application restarts.
    if getattr(sys, "frozen", False):
        app_data = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        return app_data / "StagepulseJARVIS" / "config" / "bridge_token.txt"
    return ROOT / "config" / "bridge_token.txt"


TOKEN_FILE = _token_file_path()


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

    def _peer_is_local(self):
        try:
            address = ipaddress.ip_address(self.client_address[0])
            if getattr(address, "ipv4_mapped", None) is not None:
                address = address.ipv4_mapped
            return address.is_loopback or address.is_private or address.is_link_local
        except (ValueError, IndexError, TypeError):
            return False

    def do_GET(self):
        if not self._peer_is_local():
            return self._send(403, {"success": False, "error": "local_network_only"})
        if urlparse(self.path).path != "/api/health":
            return self._send(404, {"success": False, "error": "not_found"})
        if not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + TOKEN):
            return self._send(401, {"success": False, "error": "unauthorized"})
        return self._send(200, {"success": True, "service": "JARVIS", "sharedHost": True})

    def do_POST(self):
        if not self._peer_is_local():
            return self._send(403, {"success": False, "error": "local_network_only"})
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

            from core import get_jarvis
            jarvis = get_jarvis()
            if not jarvis.is_running:
                jarvis.start()

            # Serialize LAN commands with desktop and microphone commands. Without
            # this lock, concurrent requests could mutate desktop state at once.
            with jarvis._command_lock:
                result = jarvis.command_processor.process(command)
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


def create_server(host="127.0.0.1", port=8765, allow_lan_http=False):
    """Create the bridge server; wildcard/LAN binding must be explicitly enabled."""
    if host in ("0.0.0.0", "::") and not allow_lan_http:
        raise RuntimeError(
            "LAN HTTP is disabled unless the user explicitly enables it on a trusted private Wi-Fi."
        )
    return ThreadingHTTPServer((host, int(port)), Handler)


if __name__ == "__main__":
    print(f"JARVIS bridge listening on http://{HOST}:{PORT}")
    allow_lan_http = os.environ.get("JARVIS_BRIDGE_ALLOW_LAN_HTTP", "") == "1"
    if HOST in ("0.0.0.0", "::"):
        print("WARNING: LAN mode uses HTTP. Use only on a trusted private Wi-Fi, never port-forward this port, and rotate the token if the device/network is untrusted.")
        if not allow_lan_http:
            raise SystemExit("LAN HTTP is disabled unless JARVIS_BRIDGE_ALLOW_LAN_HTTP=1 is explicitly set.")
        print("LAN access requires Windows Firewall permission for this port.")
    try:
        create_server(HOST, PORT, allow_lan_http=allow_lan_http).serve_forever()
    except KeyboardInterrupt:
        print("\nJARVIS bridge stopped.")
