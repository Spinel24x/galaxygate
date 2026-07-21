import os, sys, json, subprocess, time, uuid, socket, hashlib, base64, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests as req

DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '') or os.environ.get('RAILWAY_STATIC_URL', '') or socket.gethostname()
PORT = int(os.environ.get('PORT', 8080))
XRAY_PORT = 10086

state = {
    'uid': str(uuid.uuid4()),
    'path': f"/ws/{str(uuid.uuid4())}",
    'url': ''
}
state['url'] = f"vless://{state['uid']}@{DOMAIN}:443?security=tls&encryption=none&type=ws&path={state['path']}&host={DOMAIN}&sni={DOMAIN}&fp=chrome#STARGATE"

print(f"[Stargate] Domain: {DOMAIN} | Port: {PORT} | Xray: {XRAY_PORT}")

def download_xray():
    if os.path.exists('./xray') and os.path.getsize('./xray') > 10000000: return True
    try:
        r = req.get("https://github.com/XTLS/Xray-core/releases/download/v1.8.21/Xray-linux-64.zip", timeout=120)
        with open('xray.zip', 'wb') as f: f.write(r.content)
        import zipfile
        with zipfile.ZipFile('xray.zip', 'r') as z: z.extractall('.')
        os.chmod('./xray', 0o755); os.remove('xray.zip')
        return True
    except: return False

def build_config():
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "listen": "127.0.0.1", "port": XRAY_PORT, "protocol": "vless",
            "settings": {"clients": [{"id": state['uid']}], "decryption": "none"},
            "streamSettings": {"network": "ws", "security": "none", "wsSettings": {"path": state['path']}},
            "sniffing": {"enabled": True, "destOverride": ["http", "tls"]}
        }],
        "outbounds": [{"protocol": "freedom", "tag": "direct", "settings": {"domainStrategy": "UseIP"}}]
    }

def start_xray():
    with open('xray_config.json', 'w') as f: json.dump(build_config(), f, indent=2)
    proc = subprocess.Popen(['./xray', 'run', '-config', 'xray_config.json'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    return proc.poll() is None

def load_html():
    if os.path.exists('index.html'):
        with open('index.html', 'r', encoding='utf-8') as f: return f.read()
    return None

def pipe(src, dst):
    try:
        while True:
            d = src.recv(32768)
            if not d: break
            dst.sendall(d)
    except: pass
    finally:
        try: src.close()
        except: pass
        try: dst.close()
        except: pass

def handle_ws(client):
    backend = None
    try:
        backend = socket.socket(); backend.settimeout(10)
        backend.connect(('127.0.0.1', XRAY_PORT))
        backend.sendall(f"GET {state['path']} HTTP/1.1\r\nHost: 127.0.0.1\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            c = backend.recv(4096)
            if not c: break
            resp += c
        if b"101" not in resp: return
        t1 = threading.Thread(target=pipe, args=(client, backend), daemon=True)
        t2 = threading.Thread(target=pipe, args=(backend, client), daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=300); t2.join(timeout=300)
    except: pass
    finally:
        try: client.close()
        except: pass
        if backend: try: backend.close()
        except: pass

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/ws/'):
            key = self.headers.get('Sec-WebSocket-Key', '')
            if not key: self.send_response(400); self.end_headers(); return
            acc = base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
            self.send_response(101); self.send_header('Upgrade','websocket'); self.send_header('Connection','Upgrade'); self.send_header('Sec-WebSocket-Accept',acc); self.end_headers()
            c = self.request; self.request = None
            threading.Thread(target=handle_ws, args=(c,), daemon=True).start()
        elif self.path == '/' or self.path == '/index.html':
            html = load_html()
            if html:
                html = html.replace('{{DOMAIN}}', DOMAIN)
                html = html.replace('{{URL}}', state['url'])
                html = html.replace('{{UUID}}', state['uid'])
                html = html.replace('{{UUID_SHORT}}', state['uid'][:16])
            else:
                html = f"<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Stargate</title><style>body{{font-family:system-ui;background:#0a0a0a;color:#c9d1d9;padding:20px;text-align:center}}code{{background:rgba(0,0,0,.5);padding:10px;display:block;border-radius:8px;word-break:break-all;color:#3fb950;font-size:.8em;margin:10px 0}}.btn{{background:#238636;color:white;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;font-size:1em;margin:5px}}</style></head><body><h1>🌀 Stargate VLESS</h1><p>{DOMAIN}</p><code>{state['url']}</code><button class='btn' onclick=\"navigator.clipboard.writeText('{state['url']}');alert('Copied!')\">📋 Copy</button><button class='btn' onclick=\"fetch('/api/new').then(r=>r.json()).then(d=>{{document.querySelector('code').textContent=d.url}})\">🔄 New</button></body></html>"
            self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers()
            self.wfile.write(html.encode())
        elif self.path == '/api/config':
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(json.dumps({'url':state['url'],'domain':DOMAIN,'uuid':state['uid']}).encode())
        elif self.path == '/api/new':
            state['uid'] = str(uuid.uuid4()); state['path'] = f"/ws/{state['uid']}"
            state['url'] = f"vless://{state['uid']}@{DOMAIN}:443?security=tls&encryption=none&type=ws&path={state['path']}&host={DOMAIN}&sni={DOMAIN}&fp=chrome#STARGATE"
            with open('xray_config.json','w') as f: json.dump(build_config(),f,indent=2)
            subprocess.run(['pkill','-f','./xray']); time.sleep(1)
            subprocess.Popen(['./xray','run','-config','xray_config.json'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(json.dumps({'url':state['url'],'uuid':state['uid']}).encode())
        elif self.path == '/health':
            self.send_response(200); self.end_headers(); self.wfile.write(b'OK')
        else: self.send_response(404); self.end_headers()
    def log_message(self,f,*a): pass

class T(HTTPServer):
    def process_request(self,r,a):
        threading.Thread(target=self._p,args=(r,a),daemon=True).start()
    def _p(self,r,a):
        try: self.finish_request(r,a)
        except: pass
        finally: self.shutdown_request(r)

if __name__ == '__main__':
    if not download_xray(): sys.exit(1)
    if not start_xray(): sys.exit(1)
    print(f"[Stargate] VLESS: {state['url']}")
    print(f"[Stargate] Panel: https://{DOMAIN}")
    T(('0.0.0.0', PORT), Handler).serve_forever()
