"""Local LAN control panel for the Discord music bot (stdlib only)."""
import hashlib
import hmac
import html
import json
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional

SERVICE = 'discord-music.service'
TIMER = 'discord-music-update.timer'
CONFIG_PATH = os.environ.get('BOT_CONFIG', '/opt/discord-music-bot/.env')
UPDATE_LOG_PATH = os.environ.get('UPDATE_LOG', '/opt/discord-music-bot/last_update.log')
PASSWORD = os.environ.get('PANEL_PASSWORD', '')
COOKIE = 'music_session'
LABEL = b'music-panel-v1'
STORE = None
UPDATE_RUNNER: Optional[Callable[[], tuple[bool, str]]] = None

_attempts: dict[str, list] = {}
_lock = threading.Lock()
# Single-process LAN panel: short-lived nonce for form POST when browser omits Origin.
_form_tokens: dict[str, float] = {}
_last_update_output: str = ''


class ConfigStore:
    """Reads/writes the bot dotenv. Never logs or echoes secret values."""

    def __init__(self, path: str):
        self.path = path

    def read(self) -> dict:
        data = {'token': '', 'guild': ''}
        try:
            with open(self.path, 'r', encoding='utf-8') as handle:
                for line in handle:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, _, value = line.partition('=')
                    key = key.strip()
                    if key == 'DISCORD_TOKEN':
                        data['token'] = value.strip()
                    elif key == 'DISCORD_GUILD_ID':
                        data['guild'] = value.strip()
        except FileNotFoundError:
            pass
        return data

    def write(self, values: dict) -> None:
        for value in values.values():
            if '\n' in value or '\r' in value:
                raise ValueError('Nilai tidak boleh mengandung baris baru.')
        body = (
            '# Dikelola panel musik. Jangan commit berkas ini.\n'
            f"DISCORD_TOKEN={values.get('token', '')}\n"
            f"DISCORD_GUILD_ID={values.get('guild', '')}\n"
        )
        directory = os.path.dirname(self.path) or '.'
        os.makedirs(directory, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(body)
        os.chmod(self.path, 0o600)


def session_value() -> str:
    return hmac.new(PASSWORD.encode(), LABEL, hashlib.sha256).hexdigest()


def store() -> ConfigStore:
    return STORE if STORE is not None else ConfigStore(CONFIG_PATH)


def bot_state() -> str:
    try:
        result = subprocess.run(['systemctl', 'is-active', SERVICE],
                                capture_output=True, text=True, timeout=3)
        state = result.stdout.strip()
        return state if state in {'active', 'inactive', 'failed'} else 'unknown'
    except Exception:
        return 'unknown'


def timer_state() -> str:
    try:
        result = subprocess.run(['systemctl', 'is-active', TIMER],
                                capture_output=True, text=True, timeout=2)
        state = result.stdout.strip()
        return 'Aktif (Mingguan)' if state == 'active' else 'Nonaktif'
    except Exception:
        return 'Tidak terpasang'


def ytdlp_version() -> str:
    try:
        import yt_dlp.version
        return getattr(yt_dlp.version, '__version__', 'terpasang')
    except Exception:
        return 'tidak diketahui'


def read_last_update_log() -> str:
    global _last_update_output
    if _last_update_output:
        return _last_update_output
    try:
        if os.path.exists(UPDATE_LOG_PATH):
            with open(UPDATE_LOG_PATH, 'r', encoding='utf-8') as handle:
                return handle.read().strip()
    except Exception:
        pass
    return ''


def read_bot_logs(lines: int = 35) -> str:
    try:
        res = subprocess.run(
            ['journalctl', '-u', SERVICE, '-n', str(lines), '--no-pager'],
            capture_output=True, text=True, timeout=4
        )
        out = res.stdout.strip()
        return out if out else '(Belum ada log tercatat)'
    except Exception as exc:
        return f'(Gagal membaca log: {exc})'


def run_update() -> tuple[bool, str]:
    global _last_update_output
    if UPDATE_RUNNER is not None:
        ok, out = UPDATE_RUNNER()
        _last_update_output = out
        return ok, out

    update_script = '/opt/discord-music-bot/update.sh'
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    if os.path.exists(update_script) and os.access(update_script, os.X_OK):
        cmd = [update_script]
    else:
        pip_bin = '/opt/discord-music-bot/venv/bin/pip'
        if not os.path.exists(pip_bin):
            pip_bin = sys.executable.replace('python', 'pip')
        cmd = [pip_bin, 'install', '-U', 'yt-dlp']

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        out = (proc.stdout + '\n' + proc.stderr).strip()
        ok = (proc.returncode == 0)
        if ok and cmd != [update_script] and bot_state() == 'active':
            subprocess.run(['systemctl', 'restart', SERVICE], timeout=15)
            out += '\nService discord-music.service berhasil dimulai ulang.'
        if os.path.exists(UPDATE_LOG_PATH):
            try:
                with open(UPDATE_LOG_PATH, 'r', encoding='utf-8') as handle:
                    file_content = handle.read().strip()
                if file_content:
                    _last_update_output = file_content
                    return ok, file_content
            except Exception:
                pass
        log_content = f'[{timestamp}] Exit code: {proc.returncode}\n{out}'
        _last_update_output = log_content
        return ok, log_content
    except Exception as exc:
        err = f'[{timestamp}] Update gagal dijalankan: {exc}'
        _last_update_output = err
        return False, err


def masked(token: str) -> str:
    if not token:
        return ''
    return f'{token[:4]}…{token[-4:]}' if len(token) > 12 else 'tersimpan'


def rate_limited(peer: str) -> bool:
    now = time.time()
    with _lock:
        hits = [t for t in _attempts.get(peer, []) if now - t < 300]
        _attempts[peer] = hits
        return len(hits) >= 8


def record_failure(peer: str) -> None:
    with _lock:
        _attempts.setdefault(peer, []).append(time.time())
        if len(_attempts) > 512:
            for key in list(_attempts)[:128]:
                _attempts.pop(key, None)


PAGE = """<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Panel Bot Musik</title>
<style>
:root{--bg:#fbfbfa;--card:#fff;--line:#eaeaea;--ink:#111;--muted:#787774}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.6 'Helvetica Neue',Arial,sans-serif}
main{max-width:640px;margin:0 auto;padding:28px 18px 96px}
h1{font-size:22px;letter-spacing:-.02em;margin:0 0 4px}
p.sub{color:var(--muted);margin:0 0 22px;font-size:13px}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:20px;margin-bottom:16px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;
color:var(--muted);margin:0 0 14px;font-weight:600}
label{display:block;font-size:13px;margin:0 0 6px;font-weight:600}
input{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;
font:inherit;background:#fdfdfc}
input:focus{outline:2px solid #111;outline-offset:1px}
button{margin-top:14px;background:#111;color:#fff;border:0;border-radius:6px;
padding:11px 18px;font:inherit;font-weight:600;cursor:pointer}
button:active{transform:scale(.98)}
button.ghost{background:#fff;color:#111;border:1px solid var(--line)}
.row{display:flex;gap:10px;flex-wrap:wrap}
.kv{display:flex;justify-content:space-between;gap:12px;padding:8px 0;
border-bottom:1px solid var(--line);font-size:14px}
.kv:last-child{border-bottom:0}
.kv span:first-child{color:var(--muted)}
code{font:13px ui-monospace,SFMono-Regular,Menlo,monospace;
background:#f7f6f3;padding:2px 6px;border-radius:4px}
.badge{display:inline-block;font-size:11px;text-transform:uppercase;
letter-spacing:.05em;padding:3px 9px;border-radius:999px}
.on{background:#edf3ec;color:#346538}
.off{background:#fdebec;color:#9f2f2d}
.note{font-size:12px;color:var(--muted);margin-top:12px}
.msg{border:1px solid var(--line);background:#f7f6f3;border-radius:8px;
padding:10px 12px;font-size:13px;margin-bottom:16px}
.log-box{background:#18181b;color:#e4e4e7;padding:12px;border-radius:8px;
font:12px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;max-height:250px;
overflow-y:auto;white-space:pre-wrap;word-break:break-all;margin:10px 0 0}
@media(max-width:540px){.kv{flex-direction:column;gap:2px}}
</style></head><body><main>
<h1>Panel Bot Musik</h1>
<p class="sub">Kontrol lokal untuk bot Discord di STB. Hanya jaringan rumah.</p>
{message}
<section>
<h2>Status</h2>
<div class="kv"><span>Service bot</span><span class="badge {state_class}">{state}</span></div>
<div class="kv"><span>Token Discord</span><span>{token_state}</span></div>
<div class="kv"><span>Guild ID</span><span>{guild}</span></div>
</section>
<form method="post" action="/save">
<input type="hidden" name="form_token" value="{form_token}">
<section>
<h2>Konfigurasi</h2>
<label for="token">Token bot Discord</label>
<input id="token" name="token" type="password" autocomplete="off"
placeholder="{token_placeholder}">
<label for="guild" style="margin-top:14px">Guild ID (server uji, opsional)</label>
<input id="guild" name="guild" value="{guild}" inputmode="numeric"
placeholder="contoh 123456789012345678">
<button type="submit">Simpan konfigurasi</button>
<p class="note">Token disimpan lokal di <code>{config}</code> (mode 0600) dan tidak
pernah ditampilkan kembali. Menyimpan tidak menyalakan bot.</p>
</section>
</form>
<section>
<h2>Jalankan</h2>
<div class="row">
<form method="post" action="/start"><input type="hidden" name="form_token" value="{form_token}"><button type="submit">Nyalakan bot</button></form>
<form method="post" action="/restart"><input type="hidden" name="form_token" value="{form_token}"><button class="ghost" type="submit">Mulai ulang</button></form>
<form method="post" action="/stop"><input type="hidden" name="form_token" value="{form_token}"><button class="ghost" type="submit">Matikan</button></form>
</div>
<p class="note">Setelah bot aktif, buka Discord, masuk voice channel, lalu ketik
<code>/musik</code> dan pakai tombol panel.</p>
</section>
<section>
<h2>Pembaruan yt-dlp & Komponen</h2>
<div class="kv"><span>Versi yt-dlp saat ini</span><span><code>{ytdlp_version}</code></span></div>
<div class="kv"><span>Auto-update berkala</span><span>{timer_state}</span></div>
<form method="post" action="/update">
<input type="hidden" name="form_token" value="{form_token}">
<button type="submit" class="ghost">Perbarui yt-dlp sekarang</button>
</form>
{update_log_section}
</section>
<section>
<div style="display:flex;justify-content:space-between;align-items:center">
<h2 style="margin:0">Log Aktivitas Bot (Journalctl)</h2>
<form method="get" action="/"><button type="submit" class="ghost" style="margin:0;padding:4px 10px;font-size:12px">Segarkan</button></form>
</div>
<pre class="log-box">{bot_logs}</pre>
</section>
<section>
<h2>Cara mengundang bot</h2>
<ol style="margin:0;padding-left:20px;font-size:14px">
<li>Buat aplikasi di Discord Developer Portal, ambil tokennya.</li>
<li>Undang dengan scope <code>bot</code> + <code>applications.commands</code>.</li>
<li>Beri izin: Send Messages, Embed Links, Connect, Speak.</li>
</ol>
</section>
</main></body></html>"""


LOGIN_PAGE = """<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Masuk panel</title>
<style>
body{margin:0;background:#fbfbfa;color:#111;font:15px/1.6 'Helvetica Neue',Arial,sans-serif}
main{max-width:360px;margin:12vh auto;padding:0 18px}
section{background:#fff;border:1px solid #eaeaea;border-radius:12px;padding:24px}
h1{font-size:19px;margin:0 0 16px;letter-spacing:-.02em}
input{width:100%;padding:11px 12px;border:1px solid #eaeaea;border-radius:8px;font:inherit}
button{margin-top:14px;width:100%;background:#111;color:#fff;border:0;
border-radius:6px;padding:11px;font:inherit;font-weight:600;cursor:pointer}
p.err{color:#9f2f2d;font-size:13px;margin:0 0 12px}
</style></head><body><main><section>
<h1>Panel Bot Musik</h1>
{error}
<form method="post" action="/login">
<input name="password" type="password" autocomplete="current-password"
placeholder="Password panel" autofocus>
<button type="submit">Masuk</button>
</form>
</section></main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = 'MusicPanel/1.0'

    def log_message(self, format: str, *args):
        sys.stderr.write('%s - %s\n' % (self.address_string(), format % args))

    # ---- helpers -------------------------------------------------
    def _send(self, status, body: str, ctype='text/html; charset=utf-8', extra=None):
        raw = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Content-Security-Policy',
                         "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(raw)

    def _redirect(self, location, extra=None):
        self._send(HTTPStatus.SEE_OTHER, '', extra={'Location': location, **(extra or {})})

    def _json(self, status, payload: dict):
        self._send(status, json.dumps(payload), 'application/json; charset=utf-8')

    def _authenticated(self) -> bool:
        # Tanpa sandi panel bersifat terbuka (LAN), tetapi CSRF tetap ditegakkan.
        if not PASSWORD:
            return True
        raw = self.headers.get('Cookie', '')
        for part in raw.split(';'):
            name, _, value = part.strip().partition('=')
            if name == COOKIE and hmac.compare_digest(value, session_value()):
                return True
        return False

    def _origin_ok(self, fields: dict) -> bool:
        origin = (self.headers.get('Origin') or '').strip()
        host = (self.headers.get('Host') or '').strip()
        sec_fetch_site = (self.headers.get('Sec-Fetch-Site') or '').strip()

        candidate = fields.get('form_token', '')
        now = time.monotonic()
        with _lock:
            expiry = _form_tokens.get(candidate, 0) if candidate else 0
            has_valid_nonce = bool(expiry > now)

        # 1. Explicit foreign Origin (e.g. http://evil.example): always reject
        if origin and origin.lower() != 'null':
            netloc = urllib.parse.urlsplit(origin).netloc
            if netloc and netloc != host:
                self.log_message('origin ditolak (foreign netloc %r != host %r)', netloc, host)
                return False
            if netloc and netloc == host:
                return True

        # 2. Sec-Fetch-Site: if cross-site without valid nonce, reject
        if sec_fetch_site == 'cross-site' and not has_valid_nonce:
            self.log_message('origin ditolak (cross-site tanpa nonce)')
            return False

        # 3. Valid page nonce accepted (covers Origin: null, missing Origin, in-app WebViews)
        if has_valid_nonce:
            return True

        # 4. Fallback: Referer matching host
        referer = (self.headers.get('Referer') or '').strip()
        if referer:
            ref_netloc = urllib.parse.urlsplit(referer).netloc
            if ref_netloc and ref_netloc == host:
                return True

        self.log_message('origin ditolak (Origin=%r Host=%r Sec-Fetch-Site=%r nonce=%s)',
                         origin, host, sec_fetch_site, has_valid_nonce)
        return False

    def _body(self) -> dict:
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return {}
        if length <= 0:
            return {}
        raw = self.rfile.read(min(length, 8192)).decode('utf-8', 'replace')
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

    # ---- routing -------------------------------------------------
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == '/login':
            if not PASSWORD:
                return self._redirect('/')
            return self._login_page()
        if path in ('/api/status', '/api/*'):
            if not self._authenticated():
                return self._json(HTTPStatus.UNAUTHORIZED, {'error': 'unauthorized'})
            data = store().read()
            return self._json(HTTPStatus.OK, {
                'bot': bot_state(),
                'token_set': bool(data['token']),
                'token_hint': masked(data['token']),
                'guild': data['guild'],
                'ytdlp_version': ytdlp_version(),
                'timer': timer_state(),
            })
        if path == '/api/logs':
            if not self._authenticated():
                return self._json(HTTPStatus.UNAUTHORIZED, {'error': 'unauthorized'})
            return self._json(HTTPStatus.OK, {
                'bot_logs': read_bot_logs(50),
                'update_log': read_last_update_log(),
                'ytdlp_version': ytdlp_version(),
            })
        if path in ('/', '/index.html'):
            if not self._authenticated():
                return self._redirect('/login')
            return self._page()
        return self._send(HTTPStatus.NOT_FOUND, 'Tidak ditemukan')

    def do_HEAD(self):
        return self.do_GET()

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == '/login':
            return self._login()
        if path not in ('/save', '/start', '/restart', '/stop', '/update'):
            return self._send(HTTPStatus.NOT_FOUND, 'Tidak ditemukan')
        if not self._authenticated():
            return self._json(HTTPStatus.UNAUTHORIZED, {'error': 'unauthorized'})
        fields = self._body()
        if not self._origin_ok(fields):
            return self._json(HTTPStatus.FORBIDDEN, {'error': 'origin'})
        if path == '/save':
            return self._save(fields)
        if path == '/update':
            return self._update()
        return self._service(path.lstrip('/'))

    def do_PUT(self):
        return self._send(HTTPStatus.METHOD_NOT_ALLOWED, 'Metode tidak diizinkan',
                          extra={'Allow': 'GET, HEAD, POST'})

    do_PATCH = do_DELETE = do_OPTIONS = do_PUT

    # ---- pages ---------------------------------------------------
    def _login_page(self, error='', status=HTTPStatus.OK):
        notice = f'<p class="err">{html.escape(error)}</p>' if error else ''
        self._send(status, LOGIN_PAGE.replace('{error}', notice))

    def _page(self, message='', status=HTTPStatus.OK):
        data = store().read()
        state = bot_state()
        banner = f'<div class="msg">{html.escape(message)}</div>' if message else ''
        now = time.monotonic()
        with _lock:
            for key, expiry in list(_form_tokens.items()):
                if expiry <= now:
                    _form_tokens.pop(key, None)
            form_token = secrets.token_urlsafe(24)
            _form_tokens[form_token] = now + 900

        last_log = read_last_update_log()
        if last_log:
            update_log_section = (
                '<div style="margin-top:14px">'
                '<label style="font-size:12px;color:var(--muted)">Log Pembaruan Terakhir:</label>'
                f'<pre class="log-box" style="max-height:160px">{html.escape(last_log)}</pre>'
                '</div>'
            )
        else:
            update_log_section = ''

        page = (PAGE
                .replace('{form_token}', form_token)
                .replace('{message}', banner)
                .replace('{state_class}', 'on' if state == 'active' else 'off')
                .replace('{state}', html.escape(state))
                .replace('{token_state}', 'tersimpan' if data['token'] else 'belum diatur')
                .replace('{token_placeholder}', 'kosong = pakai token lama'
                         if data['token'] else 'tempel token bot di sini')
                .replace('{guild}', html.escape(data['guild']))
                .replace('{config}', html.escape(CONFIG_PATH))
                .replace('{ytdlp_version}', html.escape(ytdlp_version()))
                .replace('{timer_state}', html.escape(timer_state()))
                .replace('{update_log_section}', update_log_section)
                .replace('{bot_logs}', html.escape(read_bot_logs(35))))
        self._send(status, page)

    # ---- actions -------------------------------------------------
    def _login(self):
        peer = self.client_address[0]
        if rate_limited(peer):
            return self._login_page('Terlalu banyak percobaan. Tunggu beberapa menit.',
                                    HTTPStatus.TOO_MANY_REQUESTS)
        fields = self._body()
        password = fields.get('password', '')
        if PASSWORD and hmac.compare_digest(password, PASSWORD):
            with _lock:
                _attempts.pop(peer, None)
            cookie = (f'{COOKIE}={session_value()}; Path=/; HttpOnly; SameSite=Lax; Max-Age=43200')
            return self._redirect('/', {'Set-Cookie': cookie})
        record_failure(peer)
        time.sleep(0.4)
        return self._login_page('Password salah.', HTTPStatus.FORBIDDEN)

    def _save(self, fields):
        current = store().read()
        token = fields.get('token', '').strip() or current['token']
        guild = fields.get('guild', '').strip()
        if guild and not guild.isdigit():
            return self._page('Guild ID harus berupa angka.', HTTPStatus.BAD_REQUEST)
        if token and len(token) > 200:
            return self._page('Token terlalu panjang.', HTTPStatus.BAD_REQUEST)
        try:
            store().write({'token': token, 'guild': guild})
        except (ValueError, OSError) as exc:
            self.log_message('save gagal: %s', exc)
            return self._page('Gagal menyimpan konfigurasi.', HTTPStatus.BAD_REQUEST)
        self.log_message('konfigurasi disimpan (token_set=%s guild_set=%s)',
                         bool(token), bool(guild))
        return self._redirect('/')

    def _update(self):
        ok, _ = run_update()
        if ok:
            return self._page('Pembaruan yt-dlp berhasil dijalankan.')
        return self._page('Pembaruan yt-dlp gagal: periksa log pembaruan di bawah.',
                          HTTPStatus.INTERNAL_SERVER_ERROR)

    def _service(self, action):
        data = store().read()
        if not data['token']:
            return self._page('Token Discord belum diisi. Simpan konfigurasi dulu.',
                              HTTPStatus.BAD_REQUEST)
        try:
            result = subprocess.run(['systemctl', action, SERVICE],
                                    capture_output=True, text=True, timeout=15)
        except Exception as exc:
            self.log_message('systemctl %s gagal: %s', action, exc)
            return self._page(f'Perintah systemctl {action} gagal dijalankan.',
                              HTTPStatus.INTERNAL_SERVER_ERROR)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or '').strip()[:200]
            self.log_message('systemctl %s rc=%s', action, result.returncode)
            return self._page(f'systemctl {action} gagal: {html.escape(detail)}',
                              HTTPStatus.INTERNAL_SERVER_ERROR)
        labels = {'start': 'Bot dinyalakan.', 'restart': 'Bot dimulai ulang.',
                  'stop': 'Bot dimatikan.'}
        self.log_message('systemctl %s ok', action)
        return self._page(labels.get(action, 'Selesai.'))


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        self.socket.setsockopt(1, 2, 1)  # SO_REUSEPORT
        super().server_bind()


def build_server(host: str, port: int) -> Server:
    return Server((host, port), Handler)


def main():
    host = os.environ.get('PANEL_HOST', '0.0.0.0')
    port = int(os.environ.get('PANEL_PORT', '9130'))
    if not PASSWORD:
        print('PERINGATAN: PANEL_PASSWORD kosong — panel terbuka untuk siapa pun '
              'di jaringan ini. Hanya pakai di LAN tepercaya.', flush=True)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    server = build_server(host, port)
    print(f'Panel musik di http://{host}:{port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
