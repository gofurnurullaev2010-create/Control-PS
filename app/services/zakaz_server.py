"""QR Zakaz: lokal HTTP server — telefon ЗАКАЗ tugmasi → dasturga signal."""
from __future__ import annotations
import json
import logging
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional
from urllib.parse import urlparse
logger = logging.getLogger(__name__)
ZakazCallback = Callable[[int], None]
_DEFAULT_PORT = 8765
def local_ip() -> str:
    """LAN IP (telefon shu tarmoqda bo\'lishi kerak)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'
def base_url(port: int=_DEFAULT_PORT) -> str:
    return f'http://{local_ip()}:{int(port)}'
def zakaz_url(n: int, port: int=_DEFAULT_PORT) -> str:
    return f'{base_url(port)}/zakaz/{int(n)}'
_PAGE_HTML = '<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n<meta charset=\"utf-8\"/>\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, maximum-scale=1\"/>\n<title>ЗАКАЗ {n}</title>\n<style>\n  * {{ box-sizing: border-box; }}\n  body {{\n    margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;\n    background: linear-gradient(160deg, #0f172a 0%, #1e293b 50%, #0f766e 100%);\n    font-family: system-ui, Segoe UI, sans-serif; color: #fff;\n  }}\n  .wrap {{ text-align: center; padding: 24px; width: 100%; max-width: 420px; }}\n  .badge {{\n    display: inline-block; background: rgba(255,255,255,0.12); border-radius: 999px;\n    padding: 8px 18px; font-weight: 800; letter-spacing: 1px; margin-bottom: 28px;\n  }}\n  button {{\n    width: 100%; border: none; border-radius: 28px; padding: 28px 20px;\n    font-size: 42px; font-weight: 900; letter-spacing: 4px; cursor: pointer;\n    background: #fbbf24; color: #111827;\n    box-shadow: 0 12px 40px rgba(0,0,0,0.35);\n    transition: transform .08s ease, filter .15s;\n  }}\n  button:active {{ transform: scale(0.97); }}\n  button:disabled {{ filter: grayscale(0.4); opacity: 0.7; }}\n  .msg {{ margin-top: 22px; min-height: 28px; font-size: 16px; font-weight: 700; color: #a7f3d0; }}\n  .num {{ font-size: 18px; opacity: 0.7; margin-top: 12px; }}\n</style>\n</head>\n<body>\n  <div class=\"wrap\">\n    <div class=\"badge\">Eagle Playstation · №{n}</div>\n    <button id=\"btn\" type=\"button\">ЗАКАЗ</button>\n    <div class=\"msg\" id=\"msg\"></div>\n    <div class=\"num\">Stol chaqiruvi #{n}</div>\n  </div>\n  <script>\n    const n = {n};\n    const btn = document.getElementById(\'btn\');\n    const msg = document.getElementById(\'msg\');\n    let busy = false;\n    btn.addEventListener(\'click\', async () => {{\n      if (busy) return;\n      busy = true;\n      btn.disabled = true;\n      msg.textContent = \'Yuborilmoqda...\';\n      try {{\n        const r = await fetch(\'/api/zakaz/\' + n, {{ method: \'POST\' }});\n        const j = await r.json();\n        if (j.ok) {{\n          msg.textContent = \'✓ Zakaz #\' + n + \' yuborildi\';\n        }} else {{\n          msg.textContent = \'Xato: \' + (j.error || \'noma\\\'lum\');\n        }}\n      }} catch (e) {{\n        msg.textContent = \'Ulanish xatosi\';\n      }}\n      setTimeout(() => {{ busy = false; btn.disabled = false; }}, 1500);\n    }});\n  </script>\n</body>\n</html>\n'
class ZakazServer:
    """Fon oqimida ishlaydigan ThreadingHTTPServer."""
    def __init__(self, port: int=_DEFAULT_PORT, on_zakaz: Optional[ZakazCallback]=None) -> None:
        self.port = int(port or _DEFAULT_PORT)
        self.on_zakaz = on_zakaz
        self._httpd = None
        self._thread = None
    @property
    def running(self) -> bool:
        return self._httpd is not None
    def start(self) -> None:
        if self._httpd is not None:
            return
        else:
            server_ref = self
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, fmt: str, *args) -> None:
                    logger.debug('zakaz-http: ' + fmt, *args)
                def _send(self, code: int, body: bytes, content_type: str) -> None:
                    self.send_response(code)
                    self.send_header('Content-Type', content_type)
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(body)
                def do_OPTIONS(self) -> None:
                    self.send_response(204)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                    self.end_headers()
                def do_GET(self) -> None:
                    path = urlparse(self.path).path.rstrip('/') or '/'
                    if path.startswith('/zakaz/'):
                        try:
                            n = int(path.split('/')[(-1)])
                        except ValueError:
                            self._send(404, b'not found', 'text/plain')
                            return None
                        if n < 1 or n > 5:
                            self._send(404, b'not found', 'text/plain')
                        else:
                            html = _PAGE_HTML.format(n=n).encode('utf-8')
                            self._send(200, html, 'text/html; charset=utf-8')
                    else:
                        if path.startswith('/qr/'):
                            try:
                                n = int(path.split('/')[(-1)].replace('.png', ''))
                            except ValueError:
                                self._send(404, b'not found', 'text/plain')
                                return None
                            png = make_qr_png(zakaz_url(n, server_ref.port))
                            self._send(200, png, 'image/png')
                        else:
                            if path in ['/', '/index']:
                                links = ''.join((f'<p><a href=\"/zakaz/{i}\" style=\"color:#fbbf24;font-size:22px;\">ЗАКАЗ {i}</a></p>' for i in range(1, 6)))
                                body = f'<html><body style=\'background:#111;color:#fff;font-family:sans-serif;padding:40px\'>{links}</body></html>'.encode()
                                self._send(200, body, 'text/html; charset=utf-8')
                            else:
                                self._send(404, b'not found', 'text/plain')
                def do_POST(self) -> None:
                    path = urlparse(self.path).path.rstrip('/')
                    if not path.startswith('/api/zakaz/'):
                        self._send(404, json.dumps({'ok': False}).encode(), 'application/json')
                        return
                    else:
                        try:
                            n = int(path.split('/')[(-1)])
                        except ValueError:
                            self._send(400, json.dumps({'ok': False, 'error': 'bad id'}).encode(), 'application/json')
                            return None
                        if n < 1 or n > 5:
                            self._send(400, json.dumps({'ok': False, 'error': 'range'}).encode(), 'application/json')
                        else:
                            try:
                                if server_ref.on_zakaz:
                                    server_ref.on_zakaz(n)
                                self._send(200, json.dumps({'ok': True, 'n': n}).encode(), 'application/json')
                            except Exception as e:
                                logger.exception('zakaz callback')
                                self._send(500, json.dumps({'ok': False, 'error': str(e)}).encode(), 'application/json')
            try:
                self._httpd = ThreadingHTTPServer(('0.0.0.0', self.port), Handler)
            except OSError as e:
                logger.error('Zakaz server start failed: %s', e)
                self._httpd = None
                raise
            self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True, name='zakaz-http')
            self._thread.start()
            logger.info('Zakaz server: %s', base_url(self.port))
    def stop(self) -> None:
        if self._httpd is None:
            return
        else:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None
            self._thread = None
def make_qr_png(data: str, box_size: int=8) -> bytes:
    """QR PNG bytes."""
    import io
    import qrcode
    qr = qrcode.QRCode(version=None, box_size=box_size, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()
_server: Optional[ZakazServer] = None
def get_server() -> Optional[ZakazServer]:
    return _server
def start_zakaz_server(port: int, on_zakaz: ZakazCallback) -> ZakazServer:
    global _server
    stop_zakaz_server()
    _server = ZakazServer(port=port, on_zakaz=on_zakaz)
    _server.start()
    return _server
def stop_zakaz_server() -> None:
    global _server
    if _server is not None:
        _server.stop()
        _server = None