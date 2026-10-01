# -*- coding: utf-8 -*-
"""Lightweight LAN bridge for the Android JARVIS client.
No extra dependency: stdlib HTTP server + existing JARVIS CommandProcessor.
"""
from __future__ import annotations
import json, os, socket, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
try:
    from utils.config_manager import get_config
    from core.command_processor import CommandProcessor
except Exception as exc:
    raise SystemExit(f"JARVIS host import failed: {exc}")

CONFIG = get_config()
BRIDGE = CONFIG.get('android_bridge', {}) or {}
HOST = os.getenv('JARVIS_BRIDGE_HOST', BRIDGE.get('host','0.0.0.0'))
PORT = int(os.getenv('JARVIS_BRIDGE_PORT', BRIDGE.get('port',8765)))
TOKEN = os.getenv('JARVIS_BRIDGE_TOKEN', BRIDGE.get('token','JARVIS-ANDROID-2026-STAGEPULSE'))

processor = CommandProcessor()
lock = threading.Lock()


def local_ips():
    ips=[]
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET):
            ip=info[4][0]
            if not ip.startswith('127.') and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips


def json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode('utf-8')


class Handler(BaseHTTPRequestHandler):
    server_version = 'JARVIS-Android-Bridge/1.0'

    def log_message(self, fmt, *args):
        print('[BRIDGE]', fmt % args)

    def _send(self, code:int, data:Any):
        body=json_bytes(data)
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        token=self.headers.get('X-JARVIS-TOKEN','')
        return token == TOKEN

    def _read_json(self):
        n=int(self.headers.get('Content-Length','0') or 0)
        if n>1024*1024:
            raise ValueError('İstek çok büyük')
        raw=self.rfile.read(n)
        return json.loads(raw.decode('utf-8') or '{}')

    def do_GET(self):
        if self.path == '/health':
            self._send(200, {'ok':True,'service':'JARVIS Android Bridge','version':'1.0','ollama_model':getattr(processor.ai_brain,'model','qwen3:0.6b'),'ips':local_ips()})
            return
        if self.path == '/':
            self._send(200, {'ok':True,'service':'JARVIS Android Bridge','endpoints':['/health','/api/chat']})
            return
        self._send(404, {'ok':False,'error':'Endpoint bulunamadı'})

    def do_POST(self):
        if self.path != '/api/chat':
            self._send(404, {'ok':False,'error':'Endpoint bulunamadı'}); return
        if not self._authorized():
            self._send(401, {'ok':False,'error':'Geçersiz JARVIS token'}); return
        try:
            data=self._read_json()
            command=str(data.get('command','')).strip()
            if not command:
                self._send(400, {'ok':False,'error':'command boş olamaz'}); return
            with lock:
                result=processor.process(command)
            result['ok']=True
            result['bridge']='android'
            self._send(200,result)
        except Exception as exc:
            self._send(500, {'ok':False,'error':str(exc)})


def run():
    print('JARVIS Android Bridge')
    print(f'Listen: http://{HOST}:{PORT}')
    print('LAN IP(s):', ', '.join(local_ips()) or 'bulunamadı')
    print('Token:', TOKEN)
    server=ThreadingHTTPServer((HOST,PORT),Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__=='__main__':
    run()
