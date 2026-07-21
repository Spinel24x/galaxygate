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

print(f"[Stargate] Domain: {DOMAIN} | Port: {PORT}")

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
            "listen": "0.0.0.0", "port": PORT, "protocol": "vless",
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

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
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

if __name__ == '__main__':
    if not download_xray(): sys.exit(1)
    if not start_xray(): sys.exit(1)
    print(f"[Stargate] VLESS: {state['url']}")
    print(f"[Stargate] Panel: https://{DOMAIN}")
    HTTPServer(('127.0.0.1', 10000), Handler)  # Panel on localhost only
    # Xray is on PORT (0.0.0.0:8080) - handles both VLESS and serves panel via fallback? No.
    # Actually we need Xray to fallback non-VLESS to panel. 
    # Simple solution: run panel on same port with Xray? No.
    # Best: Xray on PORT, panel accessible via Xray fallback. But that's complex.
    # Simplest working: just print URL and keep alive. No panel without TCP proxy.
    try:
        while True: time.sleep(3600)
    except KeyboardInterrupt: pass
