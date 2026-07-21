import os, sys, json, subprocess, time, uuid, socket, hashlib, base64, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests as req

DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '') or os.environ.get('RAILWAY_STATIC_URL', '') or socket.gethostname()
PORT = int(os.environ.get('PORT', 8080))

state = {
    'uid': str(uuid.uuid4()),
    'path': f"/ws/{str(uuid.uuid4())}",
    'url': ''
}
state['url'] = f"vless://{state['uid']}@{DOMAIN}:443?security=tls&encryption=none&type=ws&path={state['path']}&host={DOMAIN}&sni={DOMAIN}&fp=chrome#STARGATE"

print(f"[Stargate] {DOMAIN}:{PORT}")

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

def build_xray_config():
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "listen": "0.0.0.0", "port": PORT, "protocol": "vless",
            "settings": {"clients": [{"id": state['uid']}], "decryption": "none"},
            "streamSettings": {"network": "ws", "security": "none", "wsSettings": {"path": state['path']}},
            "sniffing": {"enabled": True, "destOverride": ["http", "tls"]}
        }],
        "outbounds": [{"protocol": "freedom", "tag": "direct", "settings": {"domainStrategy": "UseIP"}}]
    }

PANEL_HTML = f"""<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Stargate VLESS</title>
<style>:root{{--bg:#0a0a0a;--card:rgba(16,16,24,0.9);--border:rgba(88,166,255,0.2);--blue:#58a6ff;--green:#3fb950;--text:#c9d1d9;--dim:#8b949e}}
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;text-align:center;padding:20px}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:25px;max-width:650px;margin:20px auto;backdrop-filter:blur(20px)}}
h1{{font-size:2em;background:linear-gradient(135deg,#58a6ff,#bc8cff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:4px;margin-bottom:20px}}
code{{background:rgba(0,0,0,.5);padding:12px;border-radius:12px;word-break:break-all;font-family:monospace;font-size:.75em;color:var(--green);margin:15px 0;display:block;max-height:150px;overflow-y:auto}}
.btn{{padding:14px;border:none;border-radius:12px;font-weight:bold;cursor:pointer;font-size:.9em;margin:6px 0;width:100%;text-transform:uppercase;letter-spacing:1px}}
.btn-g{{background:linear-gradient(135deg,#1f6feb,#58a6ff);color:#fff}}
.btn-b{{background:linear-gradient(135deg,#238636,#3fb950);color:#fff}}
.info{{color:var(--dim);font-size:.8em;margin:8px 0}}
</style></head><body>
<div class="card">
<h1>🌌 STARGATE</h1>
<p class="info">✦ QUANTUM VLESS PROTOCOL ✦</p>
<p class="info">{DOMAIN}</p>
<code id="c">{state['url']}</code>
<p class="info">Port: 443 | TLS | WebSocket</p>
<p class="info">UUID: {state['uid'][:16]}...</p>
<button class="btn btn-g" onclick="navigator.clipboard.writeText(document.getElementById('c').textContent);alert('✅ Copied!')">📋 COPY CONFIG</button>
<button class="btn btn-b" onclick="fetch('/new').then(r=>r.json()).then(d=>{{document.getElementById('c').textContent=d.url}})">🔄 NEW CONFIG</button>
</div></body></html>"""

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers()
            self.wfile.write(PANEL_HTML.encode())
        elif self.path == '/new':
            state['uid'] = str(uuid.uuid4()); state['path'] = f"/ws/{state['uid']}"
            state['url'] = f"vless://{state['uid']}@{DOMAIN}:443?security=tls&encryption=none&type=ws&path={state['path']}&host={DOMAIN}&sni={DOMAIN}&fp=chrome#STARGATE"
            with open('xray_config.json','w') as f: json.dump(build_xray_config(),f,indent=2)
            subprocess.run(['pkill','-f','./xray']); time.sleep(1)
            subprocess.Popen(['./xray','run','-config','xray_config.json'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(json.dumps({'url':state['url']}).encode())
        elif self.path == '/health':
            self.send_response(200); self.end_headers(); self.wfile.write(b'OK')
        else: self.send_response(404); self.end_headers()
    def log_message(self,f,*a): pass

if __name__ == '__main__':
    if not download_xray(): sys.exit(1)
    with open('xray_config.json', 'w') as f: json.dump(build_xray_config(), f, indent=2)
    subprocess.Popen(['./xray', 'run', '-config', 'xray_config.json'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    print(f"[Stargate] Panel: https://{DOMAIN}")
    print(f"[Stargate] VLESS: {state['url']}")
    HTTPServer(('127.0.0.1', 10000), H)
    try:
        while True: time.sleep(3600)
    except KeyboardInterrupt: pass
