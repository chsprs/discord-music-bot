"""Local LAN control panel for the Discord music bot (stdlib only)."""
import hmac
import html
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional

MAX_BODY = 65536  # 64 KB limit untuk mencegah DoS large POST body
GUILD_ID_RE = re.compile(r'^\d{17,20}$')
MAX_GUILD_INT = (1 << 64) - 1
DISCORD_TOKEN_RE = re.compile(r'^[A-Za-z0-9_\-]{24,38}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{27,45}$')

SERVICE = 'discord-music.service'
TIMER = 'discord-music-update.timer'
CONFIG_PATH = os.environ.get('BOT_CONFIG', '/opt/discord-music-bot/.env')
UPDATE_LOG_PATH = os.environ.get('UPDATE_LOG', '/opt/discord-music-bot/last_update.log')
PASSWORD = os.environ.get('PANEL_PASSWORD', '')
COOKIE = 'music_session'
STORE = None
UPDATE_RUNNER: Optional[Callable[[], tuple[bool, str]]] = None
# Hook untuk menguji /start, /restart, /stop tanpa menyentuh systemd sungguhan.
# WAJIB dipasang oleh unit test: menjalankan suite di server produksi tidak
# boleh mematikan bot yang sedang berjalan.
SERVICE_RUNNER: Optional[Callable[[str], tuple[bool, str]]] = None

# Nama host/IP yang diizinkan muncul di header Host. Tanpa allowlist, pemeriksaan
# Origin bisa dilewati dengan DNS rebinding (Host dari klien selalu dipercaya).
ALLOWED_HOSTS: set[str] = set()
for _raw in os.environ.get('PANEL_ALLOWED_HOSTS', '').split(','):
    _raw = _raw.strip().lower()
    if _raw:
        ALLOWED_HOSTS.add(_raw)

_attempts: dict[str, list] = {}
_lock = threading.Lock()
# Single-process LAN panel: short-lived nonce for form POST when browser omits Origin.
_form_tokens: dict[str, float] = {}
# Sesi server-side: token acak per login, bisa dicabut (beda dari cookie deterministic).
_sessions: dict[str, float] = {}
SESSION_TTL = 43200
MAX_SESSIONS = 512
_last_update_output: str = ''
_update_lock = threading.Lock()
_update_running = False
# PRG flash: POST handler set pesan lalu redirect 303 ke GET, refresh aman.
_flash_msg: str = ''
_state_cache: dict[str, tuple[float, str]] = {}
_state_cache_lock = threading.Lock()
STATE_CACHE_TTL = 2.0


class ConfigStore:
    """Reads/writes the bot dotenv. Never logs or echoes secret values."""

    MANAGED = ('DISCORD_TOKEN', 'DISCORD_GUILD_ID')
    HEADER = '# Dikelola panel musik. Jangan commit berkas ini.'

    def __init__(self, path: str):
        self.path = path

    @staticmethod
    def _key_of(body: str) -> str:
        """Ambil nama key dari satu baris dotenv, sadar bentuk 'export KEY=v'."""
        line = body.strip()
        if line.startswith('export '):
            line = line[len('export '):].lstrip()
        return line.partition('=')[0].strip()

    def read(self) -> dict:
        data = {'token': '', 'guild': ''}
        try:
            with open(self.path, 'r', encoding='utf-8') as handle:
                for line in handle:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key = self._key_of(line)
                    value = line.partition('=')[2].strip()
                    # Buang SATU lapis kutip yang cocok, seperti parsing
                    # EnvironmentFile systemd: DISCORD_TOKEN="abc" dari hasil
                    # edit manual tidak boleh menyimpan karakter kutip (M6).
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                        value = value[1:-1]
                    # Assignment terakhir menang, sama seperti EnvironmentFile=.
                    if key == 'DISCORD_TOKEN':
                        data['token'] = value
                    elif key == 'DISCORD_GUILD_ID':
                        data['guild'] = value
        except FileNotFoundError:
            pass
        return data

    def _preserved_lines(self) -> list[str]:
        """Baris .env yang BUKAN key ter-manage, agar tidak terhapus saat write.

        Sebelumnya write() menulis ulang berkas dari nol sehingga key tambahan
        seperti BOT_STATE_FILE / XDG_CACHE_HOME hilang tanpa peringatan.
        """
        kept: list[str] = []
        try:
            with open(self.path, 'r', encoding='utf-8') as handle:
                for line in handle:
                    stripped = line.rstrip('\r\n')
                    body = stripped.strip()
                    if not body:
                        continue
                    if body.startswith('#'):
                        # Hanya buang header yang kita kelola sendiri.
                        if body == self.HEADER:
                            continue
                        kept.append(stripped)
                        continue
                    # Buang baris apa pun yang menetapkan key ter-manage,
                    # termasuk bentuk 'export KEY=v' dan spasi di sekitar '='.
                    # Kalau tidak, baris lama bisa menimpa key baru karena
                    # sistem membaca assignment terakhir.
                    if self._key_of(body) in self.MANAGED and '=' in body:
                        continue
                    kept.append(stripped)
        except FileNotFoundError:
            pass
        return kept

    def write(self, values: dict) -> None:
        for value in values.values():
            if '\n' in value or '\r' in value:
                raise ValueError('Nilai tidak boleh mengandung baris baru.')

        preserved = self._preserved_lines()
        lines = [
            '# Dikelola panel musik. Jangan commit berkas ini.',
            f"DISCORD_TOKEN={values.get('token', '')}",
            f"DISCORD_GUILD_ID={values.get('guild', '')}",
        ]
        lines.extend(preserved)
        body = '\n'.join(lines) + '\n'

        directory = os.path.dirname(self.path) or '.'
        os.makedirs(directory, exist_ok=True)

        # Nama unik per panggilan: dua /save bersamaan tidak boleh berbagi
        # berkas sementara (yang bisa membuat salah satunya gagal atau data
        # saling menimpa). Tulis penuh + fsync lalu rename atomik agar .env
        # tidak pernah terlihat kosong/terpotong.
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix='.env.', suffix='.tmp')
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self.path)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        try:
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass



def _mint_session() -> str:
    token = secrets.token_urlsafe(32)
    now = time.monotonic()
    with _lock:
        for key, expiry in list(_sessions.items()):
            if expiry <= now:
                _sessions.pop(key, None)
        if len(_sessions) >= MAX_SESSIONS:
            oldest = min(_sessions, key=_sessions.get)
            _sessions.pop(oldest, None)
        _sessions[token] = now + SESSION_TTL
    return token


def _session_valid(token: str) -> bool:
    if not token:
        return False
    now = time.monotonic()
    with _lock:
        expiry = _sessions.get(token)
        if expiry is None:
            return False
        if expiry <= now:
            _sessions.pop(token, None)
            return False
        return True



def store() -> ConfigStore:
    return STORE if STORE is not None else ConfigStore(CONFIG_PATH)


def _cached_systemctl(kind: str, unit: str, timeout: int, fallback: str) -> str:
    """Cache hasil systemctl singkat agar satu page render tidak fork 4x (S9)."""
    started = time.monotonic()
    with _state_cache_lock:
        hit = _state_cache.get(kind)
        if hit is not None and started - hit[0] < STATE_CACHE_TTL:
            return hit[1]
    # Jangan tahan mutex selama systemctl; timeout 2-3 detik tidak boleh
    # memblokir semua render panel lain.
    try:
        result = subprocess.run(['systemctl', 'is-active', unit],
                                capture_output=True, text=True, timeout=timeout)
        value = result.stdout.strip()
    except Exception:
        value = fallback
    # Timestamp diambil SETELAH subprocess: kalau memakai `started`, entri akan
    # langsung dianggap kedaluwarsa setelah systemctl 2-3 detik.
    finished = time.monotonic()
    with _state_cache_lock:
        current = _state_cache.get(kind)
        if current is None or current[0] <= finished:
            _state_cache[kind] = (finished, value)
            return value
        # Pemanggil lain sudah mengisi data yang lebih baru saat subprocess ini jalan.
        return current[1]


def bot_state() -> str:
    state = _cached_systemctl('bot', SERVICE, 3, 'unknown')
    return state if state in {'active', 'inactive', 'failed'} else 'unknown'


def timer_state() -> str:
    state = _cached_systemctl('timer', TIMER, 2, 'inactive')
    return 'Aktif (Mingguan)' if state == 'active' else 'Nonaktif'



def ytdlp_version() -> str:
    try:
        import yt_dlp.version
        return getattr(yt_dlp.version, '__version__', 'terpasang')
    except Exception:
        return 'tidak diketahui'


def read_last_update_log() -> str:
    global _last_update_output
    with _lock:
        if _last_update_output:
            return _last_update_output
    try:
        if os.path.exists(UPDATE_LOG_PATH):
            size = os.path.getsize(UPDATE_LOG_PATH)
            with open(UPDATE_LOG_PATH, 'r', encoding='utf-8') as handle:
                if size > 65536:
                    handle.seek(max(0, size - 65536))
                    handle.readline()
                return handle.read()[-65536:].strip()
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


# Cache tail log: setiap GET / memanggil read_bot_logs yang mem-fork journalctl
# (timeout 4 dtk). Di STB lambat itu membuat panel lag dan burst refresh bisa
# menumpuk subprocess (M3). read_bot_logs() mentah tetap ada untuk pemanggilan
# langsung/test; page render memakai versi ber-cache ini.
LOG_CACHE_TTL = 15.0
_log_cache: dict[str, tuple[float, str]] = {}
_log_cache_lock = threading.Lock()


def read_bot_logs_cached(lines: int = 35, fresh: bool = False) -> str:
    """read_bot_logs dengan cache TTL (M3). `fresh=True` melewati cache."""
    key = str(lines)
    started = time.monotonic()
    if not fresh:
        with _log_cache_lock:
            hit = _log_cache.get(key)
            if hit is not None and started - hit[0] < LOG_CACHE_TTL:
                return hit[1]
    value = read_bot_logs(lines)
    finished = time.monotonic()
    with _log_cache_lock:
        _log_cache[key] = (finished, value)
    return value


def listeners_active() -> bool:
    """Apakah ada pendengar manusia aktif? Cerminan listeners_active() di update.sh.

    Dipakai jalur fallback pembaruan pip agar bot TIDAK di-restart di tengah lagu
    (M1). State basi (>60 dtk) dianggap tidak ada pendengar. Tidak pernah raise.
    """
    try:
        info = read_bot_runtime_info()
        return int(info.get('total_listeners') or 0) > 0
    except Exception:
        return False


def run_update() -> tuple[bool, str]:
    global _last_update_output, _update_running
    with _update_lock:
        if _update_running:
            return False, 'Pembaruan sedang berjalan. Tunggu selesai dulu.'
        _update_running = True
    try:
        return _run_update_inner()
    finally:
        with _update_lock:
            _update_running = False


def _run_update_inner() -> tuple[bool, str]:
    if UPDATE_RUNNER is not None:
        ok, out = UPDATE_RUNNER()
        with _lock:
            _last_update_output = out
        return ok, out

    update_script = '/opt/discord-music-bot/update.sh'
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    if os.path.exists(update_script) and os.access(update_script, os.X_OK):
        cmd = [update_script]
    else:
        pip_bin = os.path.join(os.path.dirname(sys.executable), 'pip3')
        if not os.path.exists(pip_bin):
            pip_bin = shutil.which('pip3') or '/opt/discord-music-bot/venv/bin/pip'
        req_file = '/opt/discord-music-bot/requirements.txt'
        cmd = ['sudo', '-u', 'discord-music-updater', pip_bin, 'install', '--require-hashes', '-r', req_file]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        out = (proc.stdout + '\n' + proc.stderr).strip()
        ok = (proc.returncode == 0)
        if ok and cmd != [update_script] and bot_state() == 'active':
            # M1: jangan potong musik orang — jalur fallback ini dulu me-restart
            # tanpa cek pendengar, berbeda dari update.sh.
            if listeners_active():
                out += '\nAda pendengar aktif -> restart ditunda agar musik tidak terputus.'
            else:
                restart_proc = subprocess.run(['systemctl', 'restart', SERVICE], timeout=15)
                if restart_proc.returncode == 0:
                    out += '\nService discord-music.service berhasil dimulai ulang.'
                else:
                    out += f'\nGagal merestart service, return code: {restart_proc.returncode}'
                    ok = False
        if os.path.exists(UPDATE_LOG_PATH):
            try:
                with open(UPDATE_LOG_PATH, 'r', encoding='utf-8') as handle:
                    handle.seek(0, 2)
                    size = handle.tell()
                    handle.seek(max(0, size - 65536))
                    if size > 65536:
                        handle.readline()
                    file_content = handle.read()[-65536:].strip()
                if file_content:
                    with _lock:
                        _last_update_output = file_content
                    return ok, file_content
            except Exception:
                pass
        log_content = f'[{timestamp}] Exit code: {proc.returncode}\n{out}'
        with _lock:
            _last_update_output = log_content
        return ok, log_content
    except Exception as exc:
        err = f'[{timestamp}] Update gagal dijalankan: {exc}'
        with _lock:
            _last_update_output = err
        return False, err


def read_bot_runtime_info() -> dict:
    active = bot_state() == 'active'
    default_info = {
        'status': 'online' if active else 'offline',
        'total_guilds': 0,
        'active_voice_count': 0,
        'total_listeners': 0,
        'guilds': [],
    }
    if not active:
        return default_info

    path = os.environ.get('BOT_STATE_FILE')
    if not path:
        if os.path.isdir('/run/discord-music'):
            path = '/run/discord-music/state.json'
        else:
            path = '/tmp/discord-music-state.json'

    try:
        if os.path.exists(path):
            if os.path.getsize(path) > 1048576:
                return default_info
            with open(path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            if time.time() - data.get('updated_at', 0) < 60:
                data['status'] = 'online'
                return data
    except Exception:
        pass
    return default_info


def format_guilds_html(info: dict) -> str:
    guilds = info.get('guilds', [])
    if not guilds:
        if info.get('status') == 'offline':
            return '<p class="note" style="margin-top:10px">Bot sedang offline. Nyalakan bot untuk melihat daftar server.</p>'
        return '<p class="note" style="margin-top:10px">Bot sedang online tetapi belum dimasukkan ke server Discord mana pun.</p>'

    cards = []
    for g in guilds:
        name = html.escape(str(g.get('name', 'Server Discord')))
        try:
            members = int(g.get('member_count', 0) or 0)
        except (TypeError, ValueError):
            members = 0
        connected = bool(g.get('connected', False))
        ch_name = html.escape(str(g.get('channel_name') or ''))
        raw_listeners = g.get('listeners', [])
        if not isinstance(raw_listeners, list):
            raw_listeners = []
        listeners = [html.escape(str(u)) for u in raw_listeners[:50]]
        try:
            listener_count = int(g.get('listener_count', len(listeners)) or 0)
        except (TypeError, ValueError):
            listener_count = len(listeners)
        is_playing = bool(g.get('is_playing', False))
        is_paused = bool(g.get('is_paused', False))
        track = html.escape(str(g.get('current_track') or ''))
        try:
            queue_len = int(g.get('queue_len', 0) or 0)
        except (TypeError, ValueError):
            queue_len = 0

        if connected:
            badge_class = 'on'
            badge_text = f'🔊 {ch_name}' if ch_name else '🔊 Voice Aktif'
            play_status = '⏸️ Jeda' if is_paused else ('▶️ Memutar' if is_playing else '⏹️ Standby di voice')
            if track:
                track_html = f'<div class="track-row">{play_status}: <span>{track}</span> <small style="color:var(--muted)">({queue_len} di antrean)</small></div>'
            else:
                track_html = f'<div class="track-row">{play_status} <small style="color:var(--muted)">(antrean kosong)</small></div>'

            if listener_count > 0:
                users_list = f' ({", ".join(listeners)})' if listeners else ''
                listeners_html = f'<div class="listeners-row">👥 <strong>{listener_count} user</strong> mendengarkan{users_list}</div>'
            else:
                listeners_html = '<div class="server-meta" style="color:var(--muted);margin-top:4px">Tidak ada user lain di voice channel ini</div>'
        else:
            badge_class = 'off'
            badge_text = 'Standby'
            track_html = '<div class="server-meta" style="color:var(--muted);margin-top:6px">Bot tidak sedang berada di voice channel.</div>'
            listeners_html = ''

        cards.append(
            '<div class="server-card">'
            '<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<strong style="font-size:14px">{name}</strong>'
            f'<span class="badge {badge_class}">{badge_text}</span>'
            '</div>'
            f'<div class="server-meta">Total member: {members} orang</div>'
            f'{track_html}'
            f'{listeners_html}'
            '</div>'
        )
    return '\n'.join(cards)


def reserve_login_attempt(peer: str) -> tuple[bool, int]:
    """Atomically reserve one login attempt for peer."""
    now = time.monotonic()
    with _lock:
        hits = [t for t in _attempts.get(peer, []) if now - t < 300]
        if len(hits) >= 8:
            _attempts[peer] = hits
            return False, 300
        hits.append(now)
        _attempts[peer] = hits
        if len(_attempts) > 512:
            # Buang entri yang kegagalan terakhirnya paling lama, bukan yang
            # paling awal di-insert, agar serangan rotasi IP tidak mengusir
            # entri milik penyerang sendiri.
            oldest = sorted(_attempts, key=lambda k: _attempts[k][-1] if _attempts[k] else 0)
            for key in oldest[:128]:
                _attempts.pop(key, None)
        return True, 300 if len(hits) >= 8 else 5



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
.server-card{border:1px solid var(--line);background:#fafafa;border-radius:8px;padding:12px 14px;margin-top:10px}
.server-meta{font-size:12px;color:var(--muted);margin-top:4px}
.track-row{font-size:13px;margin-top:6px;color:#111;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.listeners-row{font-size:12px;color:#2e7d32;margin-top:6px;font-weight:500}
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
{invite_html}
</section>
<section>
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
<h2 style="margin:0">Server & Pengguna Aktif</h2>
<span class="badge {runtime_badge_class}">{runtime_badge_text}</span>
</div>
<div class="kv"><span>Total server terhubung</span><span><strong>{total_guilds}</strong> server</span></div>
<div class="kv"><span>Server aktif memutar</span><span><strong>{active_voice_count}</strong> server</span></div>
<div class="kv"><span>Pengguna mendengarkan</span><span><strong>{total_listeners}</strong> user</span></div>
<div style="margin-top:14px">
{guilds_detail_html}
</div>
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
<input type="hidden" name="form_token" value="{form_token}">
<input name="password" type="password" autocomplete="current-password"
placeholder="Password panel" autofocus>
<button type="submit">Masuk</button>
</form>
</section></main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = 'MusicPanel/1.0'
    # Timeout per-koneksi. Tanpa ini, koneksi yang tidak pernah selesai
    # mengirim header/body akan menahan satu thread selamanya (S8).
    timeout = 15
    protocol_version = 'HTTP/1.0'

    def log_message(self, format: str, *args):
        sys.stderr.write('%s - %s\n' % (self.address_string(), format % args))

    # ---- helpers -------------------------------------------------
    def _send(self, status, body: str, ctype='text/html; charset=utf-8', extra=None):
        try:
            raw = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'same-origin')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy',
                             "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

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
            if name != COOKIE or not value:
                continue
            # Nilai cookie berasal dari server (token_urlsafe) dan sudah ASCII,
            # tetapi header bisa berisi byte aneh dari klien; tolak dengan aman
            # alih-alih melempar TypeError tanpa respons HTTP.
            if not value.isascii():
                continue
            if _session_valid(value):
                return True
        return False

    MAX_BODY = 65536

    def _host_ok(self, host: str) -> bool:
        """Allowlist Host untuk mencegah DNS-rebinding (S7)."""
        if not host:
            return False

        candidate = host.strip().lower()
        if candidate.startswith('['):
            if ']' not in candidate:
                return False
            hostname, sep, rest = candidate.partition(']')
            hostname += ']'
            bare = hostname[1:-1]
            if rest:
                if not rest.startswith(':'):
                    return False
                port_str = rest[1:]
                if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
                    return False
        else:
            if ':' in candidate:
                parts = candidate.split(':')
                if len(parts) != 2:
                    return False
                hostname, port_str = parts
                if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
                    return False
                bare = hostname
            else:
                hostname = candidate
                bare = hostname

        if not bare:
            return False

        if candidate in ALLOWED_HOSTS or hostname in ALLOWED_HOSTS:
            return True

        try:
            import ipaddress
            ip = ipaddress.ip_address(bare)
        except ValueError:
            return bare in _local_addresses() or bare in {'localhost'}
        except Exception:
            return False
        if ip.is_loopback:
            return True
        return str(ip) in _local_addresses()

    def _origin_ok(self, fields: dict) -> bool:
        origin = (self.headers.get('Origin') or '').strip()
        host = (self.headers.get('Host') or '').strip()
        sec_fetch_site = (self.headers.get('Sec-Fetch-Site') or '').strip()

        # 0. Host allowlist — cek paling awal, sebelum semua perbandingan origin.
        if not self._host_ok(host):
            self.log_message('ditolak (host %r tidak di allowlist)', host)
            return False

        candidate = fields.get('form_token', '')
        now = time.monotonic()
        # F5: konsumsi nonce secara ATOMIK (pop = check + remove dalam satu lock).
        # Versi lama membaca `has_valid_nonce` lalu pop di akuisisi terpisah; dua
        # POST konkuren dengan nonce sama bisa sama-sama lolos sebelum sempat
        # di-pop. Sekarang hanya pemanggil pertama yang mendapat nonce valid.
        has_valid_nonce = False
        if candidate:
            with _lock:
                expiry = _form_tokens.pop(candidate, 0)
            has_valid_nonce = bool(expiry > now)

        # 1. Sec-Fetch-Site: cross-site ditolak tanpa syarat (S5). Nonce bukan
        #    pengganti sinyal eksplisit dari browser.
        if sec_fetch_site == 'cross-site':
            self.log_message('origin ditolak (cross-site)')
            return False

        # 2. Explicit foreign Origin (e.g. http://evil.example): always reject
        if origin and origin.lower() != 'null':
            netloc = urllib.parse.urlsplit(origin).netloc
            if netloc and netloc != host:
                self.log_message('origin ditolak (foreign netloc %r != host %r)', netloc, host)
                return False
            if netloc and netloc == host:
                return True

        # 3. Valid page nonce accepted (covers Origin: null, missing Origin, in-app WebViews).
        #    Nonce sudah dikonsumsi atomik di atas (L4/F5), jadi cukup pakai hasilnya.
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

    def _drain_body(self, length: int) -> None:
        """Kuras sisa body yang belum dibaca dengan timeout singkat agar thread tidak tertahan."""
        try:
            self.connection.settimeout(0.5)
            remaining = min(length, self.MAX_BODY)
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 4096))
                if not chunk:
                    break
                remaining -= len(chunk)
        except Exception:
            pass
        finally:
            try:
                self.connection.settimeout(self.timeout)
            except Exception:
                pass

    def _body(self) -> Optional[dict]:
        """Baca body form. Return None bila request sudah ditolak (413)."""
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return {}
        if length <= 0:
            return {}
        if length > self.MAX_BODY:
            self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, 'Body terlalu besar',
                       extra={'Connection': 'close'})
            self.close_connection = True
            self._drain_body(length)
            return None
        raw = self.rfile.read(length).decode('utf-8', 'replace')
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

    # ---- routing -------------------------------------------------
    def do_GET(self):
        try:
            return self._do_get()
        except Exception:
            self.log_exception('GET %s', self.path)
            return self._server_error()

    def _do_get(self):
        path = urllib.parse.urlsplit(self.path).path
        # Host allowlist berlaku untuk GET juga: tanpa ini, DNS-rebinding bisa
        # membaca halaman/status/log meski POST sudah terlindungi (S7).
        if not self._host_ok((self.headers.get('Host') or '').strip()):
            self.log_message('ditolak (host tidak di allowlist: %r)',
                             self.headers.get('Host'))
            return self._send(HTTPStatus.FORBIDDEN, 'Host tidak diizinkan')
        if path == '/login':
            if not PASSWORD:
                return self._redirect('/')
            return self._login_page()
        if path == '/api/status':
            if not self._authenticated():
                return self._json(HTTPStatus.UNAUTHORIZED, {'error': 'unauthorized'})
            data = store().read()
            runtime = read_bot_runtime_info()
            # token_hint dihapus: potongan token Discord tidak diperlukan UI dan
            # bisa dipanen saat panel tanpa password (S10).
            return self._json(HTTPStatus.OK, {
                'bot': bot_state(),
                'token_set': bool(data['token']),
                'guild': data['guild'],
                'ytdlp_version': ytdlp_version(),
                'timer': timer_state(),
                'total_guilds': runtime.get('total_guilds', 0),
                'active_voice_count': runtime.get('active_voice_count', 0),
                'total_listeners': runtime.get('total_listeners', 0),
                'guild_count': len(runtime.get('guilds', []) or []),
            })
        if path == '/api/logs':
            if not self._authenticated():
                return self._json(HTTPStatus.UNAUTHORIZED, {'error': 'unauthorized'})
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            fresh = query.get('fresh', [''])[0] in ('1', 'true', 'yes')
            return self._json(HTTPStatus.OK, {
                'bot_logs': read_bot_logs_cached(50, fresh=fresh),
                'update_log': read_last_update_log(),
                'ytdlp_version': ytdlp_version(),
            })
        if path in ('/', '/index.html'):
            if not self._authenticated():
                return self._redirect('/login')
            return self._page()
        return self._send(HTTPStatus.NOT_FOUND, 'Tidak ditemukan')

    def log_exception(self, fmt: str, *args) -> None:
        sys.stderr.write('[panel] error: %s\n' % (fmt % args))
        import traceback
        traceback.print_exc(file=sys.stderr)

    def _server_error(self):
        try:
            return self._send(HTTPStatus.INTERNAL_SERVER_ERROR, 'Kesalahan server internal')
        except Exception:
            return None

    def do_HEAD(self):
        return self.do_GET()

    def do_POST(self):
        try:
            return self._do_post()
        except Exception:
            self.log_exception('POST %s', self.path)
            return self._server_error()

    def _do_post(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == '/login':
            # CSRF ditegakkan untuk /login juga: tanpa ini, situs mana pun bisa
            # membakar kuota rate-limit milik IP korban (S4).
            if not PASSWORD:
                return self._login_page('PANEL_PASSWORD belum dikonfigurasi di environment.',
                                        HTTPStatus.FORBIDDEN)
            fields = self._body()
            if fields is None:
                return  # 413 sudah dikirim oleh _body()
            if not fields:
                return self._login_page('Permintaan tidak valid.', HTTPStatus.BAD_REQUEST)
            if not self._origin_ok(fields):
                return self._json(HTTPStatus.FORBIDDEN, {'error': 'origin'})
            return self._login(fields)
        if path not in ('/save', '/start', '/restart', '/stop', '/update'):
            return self._send(HTTPStatus.NOT_FOUND, 'Tidak ditemukan')
        fields = self._body()
        if fields is None:
            return  # 413 sudah dikirim; jangan jalankan aksi
        if not PASSWORD:
            return self._page('Akses modifikasi ditolak: PANEL_PASSWORD belum dikonfigurasi.',
                              HTTPStatus.FORBIDDEN)
        if not self._authenticated():
            return self._json(HTTPStatus.UNAUTHORIZED, {'error': 'unauthorized'})
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
    def _login_page(self, error='', status=HTTPStatus.OK, extra=None):
        notice = f'<p class="err">{html.escape(error)}</p>' if error else ''
        now = time.monotonic()
        with _lock:
            for key, expiry in list(_form_tokens.items()):
                if expiry <= now:
                    _form_tokens.pop(key, None)
            while len(_form_tokens) > 512:
                _form_tokens.pop(next(iter(_form_tokens)))
            form_token = secrets.token_urlsafe(24)
            _form_tokens[form_token] = now + 900
        page = LOGIN_PAGE.replace('{error}', notice).replace('{form_token}', form_token)
        self._send(status, page, extra=extra)

    def _page(self, message='', status=HTTPStatus.OK):
        global _flash_msg
        data = store().read()
        state = bot_state()
        if not message:
            with _lock:
                if _flash_msg:
                    message = _flash_msg
                    _flash_msg = ''
            if not message and not PASSWORD:
                message = 'PERINGATAN: PANEL_PASSWORD belum dikonfigurasi. Panel dalam mode baca-saja; semua aksi modifikasi dinonaktifkan.'
        banner = f'<div class="msg">{html.escape(message)}</div>' if message else ''
        now = time.monotonic()
        with _lock:
            for key, expiry in list(_form_tokens.items()):
                if expiry <= now:
                    _form_tokens.pop(key, None)
            while len(_form_tokens) > 512:
                _form_tokens.pop(next(iter(_form_tokens)))
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

        runtime = read_bot_runtime_info()
        try:
            total_guilds = int(runtime.get('total_guilds', 0) or 0)
        except (TypeError, ValueError):
            total_guilds = 0
        try:
            active_voice = int(runtime.get('active_voice_count', 0) or 0)
        except (TypeError, ValueError):
            active_voice = 0
        try:
            total_listeners = int(runtime.get('total_listeners', 0) or 0)
        except (TypeError, ValueError):
            total_listeners = 0
        if runtime.get('status') == 'online':
            runtime_badge_class = 'on' if active_voice > 0 else 'badge'
            runtime_badge_text = f'{active_voice} voice aktif' if active_voice > 0 else 'idle'
        else:
            runtime_badge_class = 'off'
            runtime_badge_text = 'offline'

        guilds_html = format_guilds_html(runtime)
        
        bot_id = runtime.get('bot_id')
        if bot_id and str(bot_id).isdigit():
            invite_html = f'<div style="margin-top:14px"><a href="https://discord.com/oauth2/authorize?client_id={bot_id}&permissions=277028595712&scope=bot%20applications.commands" target="_blank" style="display:inline-block;background:#5865F2;color:#fff;border-radius:6px;padding:8px 12px;font-weight:600;text-decoration:none;font-size:13px">Undang Bot ke Server</a></div>'
        else:
            invite_html = ''

        page = (PAGE
                .replace('{form_token}', form_token)
                .replace('{message}', banner)
                .replace('{state_class}', 'on' if state == 'active' else 'off')
                .replace('{state}', html.escape(state))
                .replace('{token_state}', 'tersimpan' if data['token'] else 'belum diatur')
                .replace('{invite_html}', invite_html)
                .replace('{token_placeholder}', 'kosong = pakai token lama'
                         if data['token'] else 'tempel token bot di sini')
                .replace('{guild}', html.escape(data['guild']))
                .replace('{config}', html.escape(CONFIG_PATH))
                .replace('{runtime_badge_class}', runtime_badge_class)
                .replace('{runtime_badge_text}', runtime_badge_text)
                .replace('{total_guilds}', str(total_guilds))
                .replace('{active_voice_count}', str(active_voice))
                .replace('{total_listeners}', str(total_listeners))
                .replace('{guilds_detail_html}', guilds_html)
                .replace('{ytdlp_version}', html.escape(ytdlp_version()))
                .replace('{timer_state}', html.escape(timer_state()))
                .replace('{update_log_section}', update_log_section)
                .replace('{bot_logs}', html.escape(read_bot_logs_cached(35))))
        self._send(status, page)

    # ---- actions -------------------------------------------------
    def _login(self, fields):
        peer = self.client_address[0]
        allowed, retry_after = reserve_login_attempt(peer)
        if not allowed:
            return self._login_page('Terlalu banyak percobaan. Tunggu beberapa menit.',
                                    HTTPStatus.TOO_MANY_REQUESTS,
                                    extra={'Retry-After': str(retry_after)})
        password = fields.get('password', '')
        if PASSWORD and hmac.compare_digest(password, PASSWORD):
            with _lock:
                _attempts.pop(peer, None)
            token = _mint_session()
            cookie = (f'{COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; '
                      f'Max-Age={SESSION_TTL}')
            return self._redirect('/', {'Set-Cookie': cookie})
        # Retry-After menggantikan time.sleep(0.4) yang menahan thread worker.
        return self._login_page(
            'Password salah.',
            HTTPStatus.FORBIDDEN,
            extra={'Retry-After': retry_after},
        )

    def _set_flash(self, message: str) -> None:
        global _flash_msg
        with _lock:
            _flash_msg = message

    def _save(self, fields):
        current = store().read()
        raw_token = fields.get('token', '').strip()
        guild = fields.get('guild', '').strip()

        if raw_token:
            if len(raw_token) > 200 or not DISCORD_TOKEN_RE.match(raw_token):
                return self._page('Format Token Discord tidak valid.', HTTPStatus.BAD_REQUEST)
            token = raw_token
        else:
            token = current['token']

        if guild:
            if not GUILD_ID_RE.match(guild):
                return self._page('Guild ID harus berupa 17-20 digit angka.', HTTPStatus.BAD_REQUEST)
            try:
                guild_val = int(guild)
                if not (0 < guild_val <= MAX_GUILD_INT):
                    raise ValueError()
            except ValueError:
                return self._page('Guild ID di luar batas integer yang diizinkan.', HTTPStatus.BAD_REQUEST)

        try:
            store().write({'token': token, 'guild': guild})
        except ValueError as exc:
            self.log_message('save gagal (nilai tidak valid): %s', exc)
            return self._page('Gagal menyimpan konfigurasi (nilai tidak valid).',
                              HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            # EROFS / ENOSPC / EACCES adalah kesalahan server, bukan klien.
            self.log_exception('save gagal (I/O): %s', exc)
            return self._page('Gagal menyimpan konfigurasi: berkas tidak bisa ditulis. '
                              'Periksa izin / ruang disk.',
                              HTTPStatus.INTERNAL_SERVER_ERROR)
        self.log_message('konfigurasi disimpan (token_set=%s guild_set=%s)',
                         bool(token), bool(guild))
        self._set_flash('Konfigurasi disimpan.')
        return self._redirect('/')

    def _update(self):
        ok, out = run_update()
        if ok:
            self._set_flash(f'Pembaruan yt-dlp berhasil dijalankan.\n{out}')
        else:
            self._set_flash(f'Pembaruan yt-dlp gagal: {out}')
        return self._redirect('/')

    def _service(self, action):
        data = store().read()
        # 'stop' harus selalu boleh: operator perlu bisa mematikan bot walau
        # konfigurasi hilang/kosong (S12).
        if not data['token'] and action != 'stop':
            return self._page('Token Discord belum diisi. Simpan konfigurasi dulu.',
                              HTTPStatus.BAD_REQUEST)
        if SERVICE_RUNNER is not None:
            # Jalur unit test: jangan pernah menyentuh systemd sungguhan.
            ok, detail = SERVICE_RUNNER(action)
        else:
            try:
                result = subprocess.run(['systemctl', action, SERVICE],
                                        capture_output=True, text=True, timeout=15)
            except Exception as exc:
                self.log_exception('systemctl %s gagal: %s', action, exc)
                return self._page(f'Perintah systemctl {action} gagal dijalankan.',
                                  HTTPStatus.INTERNAL_SERVER_ERROR)
            ok = result.returncode == 0
            detail = (result.stderr or result.stdout or '').strip()[:200]
        if not ok:
            self.log_message('systemctl %s rc!=0', action)
            return self._page(f'systemctl {action} gagal: {detail}',
                              HTTPStatus.INTERNAL_SERVER_ERROR)
        labels = {'start': 'Bot dinyalakan.', 'restart': 'Bot dimulai ulang.',
                  'stop': 'Bot dimatikan.'}
        self.log_message('systemctl %s ok', action)
        self._set_flash(labels.get(action, 'Selesai.'))
        return self._redirect('/')


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    timeout = 10


def build_server(host: str, port: int) -> Server:
    return Server((host, port), Handler)


_local_addr_cache: set[str] | None = None
_local_addr_lock = threading.Lock()


def _local_addresses() -> set[str]:
    """Semua alamat IP lokal yang mungkin dipakai klien untuk menjangkau panel."""
    global _local_addr_cache
    with _local_addr_lock:
        if _local_addr_cache is not None:
            return _local_addr_cache
        import socket
        found: set[str] = set()

        # 1. Alamat keluar default (yang dipakai install.sh via `hostname -I`).
        for family, probe in ((socket.AF_INET, '8.8.8.8'), (socket.AF_INET6, '2001:4860:4860::8888')):
            sock = None
            try:
                sock = socket.socket(family, socket.SOCK_DGRAM)
                sock.connect((probe, 53))
                found.add(sock.getsockname()[0])
            except Exception:
                pass
            finally:
                if sock is not None:
                    try:
                        sock.close()
                    except Exception:
                        pass

        # 2. Hasil resolusi hostname (bisa berisi 127.0.1.1 pada Debian, tetap aman).
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None):
                found.add(info[4][0])
        except Exception:
            pass

        _local_addr_cache = {a for a in found if a}
        return _local_addr_cache


def _default_allowed_hosts(host: str, port: int) -> set[str]:
    hosts = {f'127.0.0.1:{port}', f'localhost:{port}', f'[::1]:{port}'}
    if host not in ('0.0.0.0', '::', ''):
        hosts.add(f'{host.lower()}:{port}')
    for addr in _local_addresses():
        hosts.add(f'[{addr}]:{port}' if ':' in addr else f'{addr}:{port}')
    if port in (80, 443):
        # Browser mengirim Host tanpa port pada port default.
        hosts |= {h.rsplit(':', 1)[0] for h in list(hosts)}
    return hosts


def _parse_port(raw: str | None) -> int:
    """F4: parsing PANEL_PORT defensif (filosofi H2) — buruk -> default + warning.

    Tidak SystemExit: unit panel memakai Restart=on-failure, jadi keluar-mati
    akan memicu crash-loop tiap 5 detik. Fallback ke default lebih aman.
    """
    try:
        port = int(raw) if raw is not None else 9130
        if not (1 <= port <= 65535):
            raise ValueError(port)
        return port
    except (TypeError, ValueError):
        print(f"PANEL_PORT={raw!r} tidak valid, memakai default 9130.", flush=True)
        return 9130


def main():
    host = os.environ.get('PANEL_HOST', '0.0.0.0')
    port = _parse_port(os.environ.get('PANEL_PORT', '9130'))
    if not ALLOWED_HOSTS:
        ALLOWED_HOSTS.update(_default_allowed_hosts(host, port))

    if not PASSWORD:
        print(
            '=' * 64 + '\n'
            'PERINGATAN: PANEL_PASSWORD kosong.\n'
            'Panel ini TERBUKA tanpa autentikasi untuk siapa pun yang bisa\n'
            f'menjangkau {host}:{port}. Siapa pun di jaringan itu dapat:\n'
            '  - menimpa token bot di .env\n'
            '  - menjalankan systemctl start/stop/restart sebagai root\n'
            '  - memicu instalasi paket (update yt-dlp)\n'
            'Set PANEL_PASSWORD di /opt/discord-music-panel.env, atau batasi\n'
            'PANEL_HOST=127.0.0.1 dan akses lewat SSH tunnel.\n'
            + '=' * 64,
            flush=True,
        )

    server = build_server(host, port)
    _closing = threading.Event()

    def _close_sockets():
        try:
            server.server_close()
        except Exception:
            pass

    def _shutdown(*_):
        # PENTING: jangan panggil server.shutdown() dari sini.
        # Signal handler berjalan di thread yang sama dengan serve_forever().
        # BaseServer.shutdown() menunggu loop berhenti (__is_shut_down), tapi
        # loop tidak bisa lanjut karena kita masih di dalam handler -> deadlock.
        # systemd menunggu TimeoutStopSec (90 dtk) lalu SIGKILL: setiap
        # restart/stop panel jadi lambat dan tercatat "Failed with result
        # 'timeout'". Cukup tandai berhenti dan tutup socket; SystemExit
        # membatalkan select() yang sedang menunggu.
        if _closing.is_set():
            return
        _closing.set()
        threading.Thread(target=_close_sockets, daemon=True).start()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    print(f'Panel musik di http://{host}:{port}', flush=True)
    try:
        server.serve_forever()
    finally:
        # serve_forever() sudah keluar -> __is_shut_down ter-set, jadi
        # shutdown() di sini tidak memblokir.
        try:
            server.shutdown()
        except Exception:
            pass
        _close_sockets()



if __name__ == '__main__':
    main()
