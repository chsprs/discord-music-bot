"""Minimal Discord music player: slash summon, buttons, modal, streaming voice."""
import asyncio
import json
import logging
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

import discord
import yt_dlp

log = logging.getLogger(__name__)


def _int_env(name: str, default: int, lo: int | None = None, hi: int | None = None) -> int:
    """Baca env var integer dengan aman.

    Satu typo di .env (mis. 'AFK_TIMEOUT_SECONDS=180s') tidak boleh membuat bot
    gagal start saat import: nilai tidak valid -> default + warning (H2). Nilai
    valid tapi di luar rentang dijepit ke [lo, hi] (L5) agar MIX_RESULT_LIMIT=0
    tidak membuat yt-dlp mengembalikan nol lagu dan AFK_TIMEOUT_SECONDS=1 tidak
    memutus bot seketika.
    """
    raw = os.environ.get(name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        log.warning('Nilai env %s=%r tidak valid, memakai default %s', name, raw, default)
        return default
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


def format_duration(seconds: int | float | None) -> str:
    if not seconds or seconds <= 0:
        return "Live / Unknown"
    s = int(seconds)
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    return f"{minutes}m {secs}s"


@dataclass
class Track:
    title: str
    url: str  # stable page URL, not an expiring googlevideo URL
    requester: str
    duration: int = 0
    duration_str: str = "Unknown"
    author: str = "Unknown"
    stream_url: str | None = None
    stream_ts: float | None = None


DEFAULT_VOLUME = 0.5


def get_default_volume() -> float:
    raw = os.getenv('DEFAULT_VOLUME')
    if raw is not None:
        try:
            val = float(raw)
            if 0.0 <= val <= 2.0:
                return val
        except (ValueError, TypeError):
            pass
    return DEFAULT_VOLUME


@dataclass
class QueueState:
    queue: deque[Track] = field(default_factory=deque)
    history: deque[Track] = field(default_factory=deque)
    current: Track | None = None
    volume: float = field(default_factory=get_default_volume)
    loop_mode: str = 'off'  # 'off', 'track', 'queue'
    autoplay: bool = False
    generation: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    message: discord.Message | None = None
    now_message: discord.Message | None = None
    text_channel_id: int | None = None
    _skip_armed: bool = False  # skip/back manual: after() basi, advance manual yang jalan
    _skip_pending: bool = False  # skip ditekan saat advance() sedang ekstraksi (M4)
    _advancing: int = 0  # jumlah advance() yang benar-benar di fase ekstraksi/putar (dipakai skip & guard)
    consecutive_playback_errors: int = 0
    idle_task: asyncio.Task | None = None
    empty_task: asyncio.Task | None = None
    afk_task: asyncio.Task | None = None
    afk_paused: bool = False
    refresh_task: asyncio.Task | None = None
    announce_task: asyncio.Task | None = None
    _advance_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _last_skip_time: float = 0.0
    _last_pause_time: float = 0.0


GuildState = QueueState

# Batas konkurensi ekstraksi yt-dlp agar STB RAM kecil tidak OOM (C4/M3).
EXTRACT_SEM = asyncio.Semaphore(2)
MAX_QUEUE = 500
# Batas kedua lapis untuk stall buffer: mana yang tercapai lebih dulu.
# - MAX_ERROR_STREAK: jumlah miss berurutan (tiap miss = 0,3 dtk queue timeout) ~15 dtk.
# - STALL_EOF_SECONDS: batas wall-clock nyata, tahan jitter CDN sampai 4 dtk
#   sebelum dianggap EOF dan lagu lanjut. 1 dtk terlalu agresif (lagu loncat).
MAX_ERROR_STREAK = 50
STALL_EOF_SECONDS = 4.0
MAX_TRACK_RETRIES = 3
AFK_TIMEOUT_SECONDS = _int_env('AFK_TIMEOUT_SECONDS', 180, lo=1)


def get_afk_timeout() -> float:
    raw = os.getenv('AFK_TIMEOUT_SECONDS')
    if raw is not None:
        try:
            val = float(raw)
            if val > 0:
                return val
        except (ValueError, TypeError):
            pass
    return float(AFK_TIMEOUT_SECONDS)


# --- H3: batas thread yt-dlp yang benar-benar hidup ------------------------
# EXTRACT_SEM membatasi KONKURENSI coroutine. Pembatalan asyncio.wait_for pada
# `async with EXTRACT_SEM` memang mengembalikan slot semaphore (terverifikasi:
# sem._value kembali ke 2 setelah timeout) — jadi klaim "semaphore bocor" tidak
# berlaku untuk pola `async with`. MASALAH NYATA: thread yt-dlp yang menggantung
# tidak bisa dibatalkan; ia terus berjalan dan memakai memori. Karena slot
# semaphore sudah dilepas, pemanggil berikutnya bisa memulai thread BARU,
# sehingga saat YouTube 429 beruntun jumlah thread yt-dlp hidup membengkak
# (puluhan MB per thread di STB RAM kecil -> risiko OOM).
# MAX_EXTRACT_THREADS adalah batas keras thread nyata; dihitung di DALAM thread
# (try/finally) sehingga thread zombie pun tetap terhitung.
MAX_EXTRACT_THREADS = 4
_EXTRACT_THREADS = 0
_EXTRACT_THREADS_LOCK = threading.Lock()


class ExtractionBusy(ValueError):
    """Thread ekstraksi hidup sudah mencapai batas (H3).

    Subclass ValueError agar jalur /play yang sudah menangkap ValueError
    menampilkan pesan ramah ke pengguna tanpa perubahan di pemanggil.
    """


def _reserve_extract_slot() -> bool:
    """F3: reservasi slot secara atomik (check+increment dalam satu lock).

    Versi lama melakukan check-then-act: dua coroutine bisa sama-sama lolos
    pengecekan `_EXTRACT_THREADS >= MAX_EXTRACT_THREADS` sebelum salah satunya
    sempat menaikkan counter, sehingga batas keras bisa terlampaui sesaat.
    Sekarang pengecekan dan penambahan tidak bisa disela.
    """
    global _EXTRACT_THREADS
    with _EXTRACT_THREADS_LOCK:
        if _EXTRACT_THREADS >= MAX_EXTRACT_THREADS:
            return False
        _EXTRACT_THREADS += 1
        return True


def _release_extract_slot() -> None:
    global _EXTRACT_THREADS
    with _EXTRACT_THREADS_LOCK:
        _EXTRACT_THREADS -= 1


def _tracked_extract(func, *args, **kwargs):
    """Jalankan func di thread; slot sudah direservasi pemanggil, lepas di finally.

    Slot dilepas DI DALAM thread (bukan oleh coroutine) supaya thread yt-dlp yang
    menggantung tetap terhitung walau `wait_for` sudah timeout dan coroutine-nya
    dibatalkan.
    """
    try:
        return func(*args, **kwargs)
    finally:
        _release_extract_slot()


async def run_extract(func, *args, timeout: float = 60, **kwargs):
    """Jalankan func di thread dengan timeout + batas thread zombie (H3).

    Menggantikan pola `async with EXTRACT_SEM: await asyncio.wait_for(
    asyncio.to_thread(...))` di semua jalur ekstraksi.
    """
    async with EXTRACT_SEM:
        # Reservasi slot SETELAH semaphore didapat: bila akuisisi semaphore
        # dibatalkan, tidak ada slot yang bocor. Setelah ini thread pasti jalan
        # (to_thread selalu mengeksekusi), jadi finally-nya yang melepas slot.
        if not _reserve_extract_slot():
            with _EXTRACT_THREADS_LOCK:
                alive = _EXTRACT_THREADS
            log.warning('Ekstraksi ditolak: %d thread yt-dlp masih hidup (batas %d).',
                        alive, MAX_EXTRACT_THREADS)
            raise ExtractionBusy('Server sedang sibuk menyiapkan lagu. Coba lagi sebentar lagi.')
        try:
            task = asyncio.to_thread(_tracked_extract, func, *args, **kwargs)
        except Exception:
            _release_extract_slot()
            raise
        return await asyncio.wait_for(task, timeout=timeout)


def _cookies_file() -> str | None:
    """Lokasi cookies.txt opsional untuk video age-restricted / butuh login.

    Tanpa ini, lagu seperti itu gagal dengan 'Sign in to confirm you're not a
    bot'. Berkas diisi operator sendiri (mis. hasil ekstensi 'Get cookies.txt')
    dan hanya dibaca, tidak pernah ditulis bot. Path bisa diubah lewat
    YTDLP_COOKIES di .env.
    """
    candidates = [
        os.environ.get('YTDLP_COOKIES'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt'),
        os.path.join(os.environ.get('XDG_CONFIG_HOME', ''), 'yt-dlp', 'cookies.txt')
        if os.environ.get('XDG_CONFIG_HOME') else None,
    ]
    for path in candidates:
        if path and os.path.isfile(path) and os.path.getsize(path) > 0:
            return path
    return None


def checked_query(query: str) -> str:
    query = query.strip()
    if not query or len(query) > 500:
        raise ValueError('Judul atau URL lagu harus 1–500 karakter.')
    if query.lower().startswith(('youtube.com/', 'www.youtube.com/', 'm.youtube.com/', 'music.youtube.com/', 'youtu.be/')):
        query = 'https://' + query
    if query.startswith(('http://', 'https://')):
        parsed = urlparse(query)
        hostname = (parsed.hostname or '').lower()
        if hostname not in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be'}:
            raise ValueError('Hanya tautan HTTPS YouTube/YouTube Music yang didukung.')
        if query.startswith('http://'):
            query = 'https://' + query[7:]
        return query
    return f'ytsearch1:{query}'


def _js_runtime_works(path: str) -> bool:
    """Cek kandidat JS runtime benar-benar bisa dijalankan (L7).

    `os.path.exists` saja tidak cukup: node rusak / tidak executable di
    /usr/local/bin pernah membayangi node PATH yang sehat sehingga yt-dlp gagal
    menyelesaikan challenge player. Probe `--version` dengan timeout pendek.
    """
    try:
        proc = subprocess.run([path, '--version'], capture_output=True, text=True, timeout=5)
        return proc.returncode == 0
    except Exception:
        return False


def _detect_js_runtime() -> dict:
    candidates = [
        ('node', '/usr/local/bin/node'),
        ('node', shutil.which('node')),
        ('node', '/usr/bin/node'),
        ('deno', shutil.which('deno')),
        ('bun', shutil.which('bun')),
    ]
    seen: set[str] = set()
    for name, path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        if os.path.exists(path) and os.access(path, os.X_OK) and _js_runtime_works(path):
            return {name: {'path': path}}
    return {}


_JS_RUNTIME = _detect_js_runtime()

METADATA_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'extract_flat': 'in_playlist',
    'skip_download': True,
    'socket_timeout': 15,
    'retries': 3,
    'extractor_retries': 3,
    'fragment_retries': 3,
    'js_runtimes': _JS_RUNTIME,
}

STREAM_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'skip_download': True,
    'socket_timeout': 15,
    'retries': 3,
    'extractor_retries': 3,
    'fragment_retries': 3,
    'js_runtimes': _JS_RUNTIME,
}

# YouTube Mix (radio `list=RD<id>`): berapa entri playlist yang diekstrak.
MIX_RESULT_LIMIT = _int_env('MIX_RESULT_LIMIT', 15, lo=1, hi=50)

# Salinan METADATA_OPTIONS + playlistend (tanpa noplaylist) agar yt-dlp mau
# mengikuti playlist Mix. extract_flat='in_playlist' sudah dibawa dari
# METADATA_OPTIONS. Dict dasar ini TIDAK dimutasi; opsi per-panggilan dibuat
# lewat _mix_options(limit).
MIX_OPTIONS = {
    **METADATA_OPTIONS,
    'playlistend': MIX_RESULT_LIMIT,
}

# Cookies opsional (video age-restricted / butuh login). Dibaca ulang di tiap
# ekstraksi lewat _with_cookies(), jadi menaruh cookies.txt langsung terpakai
# tanpa restart bot. Lihat _cookies_file().
if _cookies_file():
    log.info('Cookies yt-dlp terdeteksi dari %s', _cookies_file())


def _with_cookies(options: dict) -> dict:
    """Salinan options + cookiefile bila berkas cookies tersedia saat ini."""
    path = _cookies_file()
    if not path:
        return options
    merged = dict(options)
    merged['cookiefile'] = path
    return merged


def dump_runtime_state(bot) -> None:
    path = os.environ.get('BOT_STATE_FILE')
    if not path:
        if os.path.isdir('/run/discord-music'):
            path = '/run/discord-music/state.json'
        else:
            path = '/tmp/discord-music-state.json'
    try:
        guilds_data = []
        total_listeners = 0
        active_voice_count = 0
        for g in getattr(bot, 'guilds', []):
            vc = getattr(g, 'voice_client', None)
            connected = bool(vc and getattr(vc, 'channel', None))
            channel_name = None
            listeners = []
            is_playing = False
            is_paused = False
            track_title = None
            queue_len = 0

            if connected and vc and vc.channel:
                active_voice_count += 1
                channel_name = getattr(vc.channel, 'name', None)
                channel_members = [m for m in getattr(vc.channel, 'members', []) if not getattr(m, 'bot', False)]
                listeners = [getattr(m, 'display_name', getattr(m, 'name', 'User')) for m in channel_members]
                total_listeners += len(listeners)
                is_playing = getattr(vc, 'is_playing', lambda: False)()
                is_paused = getattr(vc, 'is_paused', lambda: False)()
                state = bot.states.get(g.id) if hasattr(bot, 'states') else None
                if state:
                    if getattr(state, 'current', None):
                        track_title = state.current.title
                    queue_len = len(getattr(state, 'queue', []))

            guilds_data.append({
                'id': str(g.id),
                'name': g.name,
                'member_count': getattr(g, 'member_count', 0),
                'connected': connected,
                'channel_name': channel_name,
                'listeners': listeners,
                'listener_count': len(listeners),
                'is_playing': is_playing,
                'is_paused': is_paused,
                'current_track': track_title,
                'queue_len': queue_len,
            })

        payload = {
            'updated_at': time.time(),
            'bot_user': str(getattr(bot, 'user', '')),
            'bot_id': str(bot.user.id) if getattr(bot, 'user', None) else '',
            'total_guilds': len(guilds_data),
            'active_voice_count': active_voice_count,
            'total_listeners': total_listeners,
            'guilds': guilds_data,
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        listeners_path = os.path.join(os.path.dirname(path), "listeners.json")
        listeners_payload = {"total_listeners": total_listeners, "updated_at": time.time()}
        l_tmp_path = listeners_path + ".tmp"
        with open(l_tmp_path, "w", encoding="utf-8") as f:
            json.dump(listeners_payload, f)
        os.chmod(l_tmp_path, 0o644)
        os.replace(l_tmp_path, listeners_path)

        tmp_path = path + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f)
        os.replace(tmp_path, path)
    except Exception as exc:
        log.debug('Gagal menulis state runtime bot: %s', exc)


def dump_runtime_state_offline() -> None:
    path = os.environ.get('BOT_STATE_FILE')
    if not path:
        if os.path.isdir('/run/discord-music'):
            path = '/run/discord-music/state.json'
        else:
            path = '/tmp/discord-music-state.json'
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _persistent_queue_file() -> str:
    path = os.environ.get('QUEUE_STATE_FILE')
    if path:
        return path
    if os.path.isdir('/run/discord-music') and os.access('/run/discord-music', os.W_OK):
        return '/run/discord-music/queue_state.json'
    return '/tmp/discord-music-queue_state.json'


def _track_to_dict(track) -> dict:
    if track is None:
        return {}
    return {
        'title': str(getattr(track, 'title', '')),
        'url': str(getattr(track, 'url', '')),
        'requester': str(getattr(track, 'requester', 'Unknown')),
        'duration': int(getattr(track, 'duration', 0) or 0),
        'duration_str': str(getattr(track, 'duration_str', 'Unknown')),
        'author': str(getattr(track, 'author', 'Unknown')),
    }


def _dict_to_track(data: dict) -> Track | None:
    if not isinstance(data, dict):
        return None
    url = data.get('url')
    title = data.get('title')
    if not url or not title:
        return None
    try:
        dur = int(data.get('duration', 0) or 0)
    except (ValueError, TypeError):
        dur = 0
    return Track(
        title=str(title),
        url=str(url),
        requester=str(data.get('requester', 'Unknown')),
        duration=dur,
        duration_str=str(data.get('duration_str', 'Unknown')),
        author=str(data.get('author', 'Unknown')),
    )


def clear_cache() -> None:
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            ydl.cache.remove()
    except Exception as exc:
        log.debug('Gagal menghapus cache yt-dlp: %s', exc)

    cache_root = os.environ.get('XDG_CACHE_HOME') or '/run/discord-music'
    cache_dirs = [
        os.path.join(cache_root, 'yt-dlp'),
        os.path.expanduser('~/.cache/yt-dlp'),
        '/tmp/yt-dlp',
    ]
    for c_dir in cache_dirs:
        # Tolak path non-absolut: XDG_CACHE_HOME yang di-set tapi kosong pernah
        # menghasilkan 'yt-dlp' relatif CWD sehingga rmtree menghapus direktori
        # kerja bot (M5).
        if not os.path.isabs(c_dir) or not os.path.isdir(c_dir):
            continue
        try:
            shutil.rmtree(c_dir, ignore_errors=True)
        except Exception:
            pass



def extract_stream(url: str) -> dict:
    max_attempts = 2
    data = None
    for attempt in range(max_attempts):
        try:
            with yt_dlp.YoutubeDL(_with_cookies(STREAM_OPTIONS)) as ydl:
                data = ydl.extract_info(url, download=False)
            break
        except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError) as exc:
            msg = str(exc)
            msg_lower = msg.lower()
            if '429' in msg_lower or 'too many requests' in msg_lower:
                if attempt < max_attempts - 1:
                    log.warning('Rate limit 429 pada extract_stream, retry setelah jeda 2s: %s', url)
                    time.sleep(2.0)
                    continue
                raise ValueError('YouTube sedang membatasi permintaan bot (Rate Limit 429). Mohon tunggu beberapa saat.') from exc
            if any(k in msg_lower for k in ('confirm your age', 'age-restricted', 'age restricted')):
                raise ValueError('Video terkena batasan usia YouTube (age-restricted). Butuh cookies.txt untuk memutar (simpan di direktori bot atau set YTDLP_COOKIES).') from exc
            raise

    if data and 'entries' in data:
        data = next((entry for entry in data['entries'] if entry), None)
    if not data or not data.get('url'):
        raise ValueError('Stream audio tidak tersedia.')
    if data.get('is_live') or data.get('live_status') == 'is_live':
        raise ValueError('Video siaran langsung (livestream) tidak didukung oleh pemutar audio statis.')
    return data


extract = extract_stream


def _fetch_metadata(target: str) -> dict:
    with yt_dlp.YoutubeDL(_with_cookies(METADATA_OPTIONS)) as ydl:
        return ydl.extract_info(target, download=False)


async def extract_tracks(query: str, requester: str) -> list[Track]:
    target = checked_query(query)
    data = None
    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            data = await run_extract(_fetch_metadata, target, timeout=60)
            break
        except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError) as exc:
            msg = str(exc)
            msg_lower = msg.lower()
            if '429' in msg_lower or 'too many requests' in msg_lower:
                # ponytail: batasi retry 429 ke 1x backoff 2s; jika butuh distributed IP rotation, gunakan proxy pool
                if attempt < max_attempts - 1:
                    log.warning('YouTube HTTP 429 rate limit saat ekstraksi metadata, backoff 2s (percobaan %d/%d): %s', attempt + 1, max_attempts, target)
                    await asyncio.sleep(2.0)
                    continue
                raise ValueError('YouTube sedang membatasi permintaan bot (Rate Limit 429). Mohon tunggu beberapa saat.') from exc
            if any(k in msg_lower for k in ('confirm your age', 'age-restricted', 'age restricted')):
                raise ValueError('Video terkena batasan usia YouTube (age-restricted). Butuh cookies.txt untuk memutar (simpan di direktori bot atau set YTDLP_COOKIES).') from exc
            if any(k in msg_lower for k in ('private video', 'video unavailable', 'is unavailable', 'not found')):
                raise ValueError('Lagu tidak tersedia (video privat atau telah dihapus).') from exc
            raise ValueError(f'Gagal mengekstrak lagu: {msg}') from exc

    if not data:
        raise ValueError('Lagu atau playlist tidak ditemukan.')

    return _tracks_from_metadata(data, requester, target)


def _tracks_from_metadata(data: dict, requester: str, target: str) -> list[Track]:
    """Ubah hasil yt-dlp (video tunggal / playlist / hasil pencarian) jadi Track."""
    if data.get('is_live') or data.get('live_status') == 'is_live':
        raise ValueError('Video siaran langsung (livestream) tidak didukung oleh pemutar audio statis.')

    tracks: list[Track] = []
    if 'entries' in data:
        live_skipped = 0
        for entry in data.get('entries') or []:
            if not entry:
                continue
            if entry.get('is_live') or entry.get('live_status') == 'is_live':
                live_skipped += 1
                continue
            title = (entry.get('title') or '').strip()
            # ponytail: saring video private/deleted/unavailable agar tidak mengisi antrean dengan track mati
            if not title or title in ('[Private video]', '[Deleted video]', '[Unavailable video]'):
                continue
            stable_url = entry.get('webpage_url') or entry.get('url')
            if not stable_url or not stable_url.startswith('http'):
                vid_id = entry.get('id') or stable_url
                stable_url = f'https://www.youtube.com/watch?v={vid_id}'
            stream_url = None
            stream_ts = 0.0
            if entry.get('url') and entry.get('url') != stable_url:
                stream_url = entry.get('url')
                stream_ts = time.time()
            dur = entry.get('duration') or 0
            author = entry.get('uploader') or entry.get('channel') or entry.get('artist') or 'Unknown'
            tracks.append(Track(title, stable_url, requester, duration=dur, duration_str=format_duration(dur), author=author, stream_url=stream_url, stream_ts=stream_ts))
            if len(tracks) >= 100:
                break
        if not tracks and live_skipped > 0:
            raise ValueError('Video siaran langsung (livestream) tidak didukung oleh pemutar audio statis.')
    else:
        title = (data.get('title') or '').strip()
        if not title or title in ('[Private video]', '[Deleted video]', '[Unavailable video]'):
            raise ValueError('Lagu tidak tersedia (video privat atau telah dihapus).')
        stable_url = data.get('webpage_url') or target
        stream_url = None
        stream_ts = 0.0
        if data.get('url') and data.get('url') != stable_url:
            stream_url = data.get('url')
            stream_ts = time.time()
        dur = data.get('duration') or 0
        author = data.get('uploader') or data.get('channel') or data.get('artist') or 'Unknown'
        tracks.append(Track(title, stable_url, requester, duration=dur, duration_str=format_duration(dur), author=author, stream_url=stream_url, stream_ts=stream_ts))

    if not tracks:
        raise ValueError('Lagu tidak ditemukan atau stream tidak tersedia.')
    return tracks


async def extract_track(query: str, requester: str) -> Track:
    tracks = await extract_tracks(query, requester)
    return tracks[0]


def build_recommendation_queries(history_titles: list[str], current_title: str | None = None) -> list[str]:
    """Susun kueri pencarian rekomendasi dari beberapa lagu terakhir.

    Lagu paling baru dipakai sebagai seed utama, lalu ditambah seed dari
    riwayat sebelumnya sebagai cadangan bila seed utama tidak menghasilkan
    kandidat baru. Kueri di-dedup agar tidak menembak pencarian yang sama
    berkali-kali.
    """
    seeds: list[str] = []
    for title in list(history_titles or []) + ([current_title] if current_title else []):
        clean = _clean_seed_title(title)
        if clean and clean not in seeds:
            seeds.append(clean)
    # Seed terbaru dulu (paling relevan), batasi agar tidak spam pencarian.
    seeds = list(reversed(seeds))[:3]
    queries: list[str] = []
    for seed in seeds:
        queries.append(f'ytsearch5:{seed} related songs mix')
    return queries


def _clean_seed_title(title: str | None) -> str:
    """Bersihkan judul lagu dari noise umum agar pencarian rekomendasi relevan."""
    if not title:
        return ''
    text = str(title)
    # Hapus dulu frasa panjang supaya sisa potongannya tidak tertinggal.
    for noise in ('Official Music Video', 'Official Video', 'Official Audio',
                  'Lyric Video', 'Lyrics Video', 'Music Video', 'Audio Only',
                  'Official', 'Lyrics', 'Audio', 'MV', 'HD', '4K', 'HQ'):
        text = re.sub(re.escape(noise), ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'[\(\)\[\]\{\}]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip(' -–—|,')
    return text[:200]


async def fetch_recommendations(history_titles: list[str], exclude_urls: set[str],
                                requester: str = 'AutoPlay',
                                seed_urls: list[str] | None = None) -> list[Track]:
    """Ambil kandidat lagu rekomendasi berbasis riwayat lagu sebelumnya.

    Bila seed_urls diisi, utamakan YouTube Mix (radio nyata = paling relevan):
    iterasi seed terbaru dulu, kembalikan kandidat pertama yang non-kosong.
    Bila seed_urls kosong / semua mix kosong, fallback ke pencarian teks lama
    (kueri ytsearch5: dari build_recommendation_queries). Menyaring URL yang
    sudah pernah diputar (exclude_urls) supaya AutoPlay tidak mengulang lagu.
    """
    seen: set[str] = set(exclude_urls or set())

    # --- Prioritas 1: YouTube Mix dari seed URL (terbaru dulu) ---
    for seed_url in reversed(seed_urls or []):
        video_id = extract_video_id(seed_url)
        if not video_id:
            continue
        mix_tracks = await fetch_youtube_mix(video_id, seen, requester)
        candidates: list[Track] = []
        for track in mix_tracks:
            if track.url in seen:
                continue
            seen.add(track.url)
            candidates.append(track)
        if candidates:
            return candidates

    # --- Prioritas 2 (fallback): pencarian teks lama ---
    queries = build_recommendation_queries(history_titles)
    candidates = []
    for query in queries:
        try:
            data = await run_extract(_fetch_metadata, query, timeout=60)
        except Exception as exc:
            log.warning('Rekomendasi gagal untuk kueri %r: %s', query, exc)
            continue
        if not data:
            continue
        try:
            found = _tracks_from_metadata(data, requester, query)
        except ValueError:
            continue
        for track in found:
            if track.url in seen:
                continue
            seen.add(track.url)
            candidates.append(track)
        if candidates:
            # Kueri seed pertama sudah menghasilkan kandidat: cukup, hemat kuota.
            break
    return candidates


def _mix_options(limit: int) -> dict:
    """Opsi yt-dlp untuk YouTube Mix, dihitung ulang per-panggilan.

    Menyalin METADATA_OPTIONS (membawa extract_flat='in_playlist') dan
    menambahkan playlistend=limit agar ekstraksi cepat (~1.5s, bukan ~20s).
    TIDAK memutasi dict global, jadi limit berbeda aman dipakai bersamaan.
    """
    return {**METADATA_OPTIONS, 'playlistend': int(limit)}


def _fetch_mix_metadata(url: str, limit: int) -> dict:
    """Ekstraksi sinkron satu halaman YouTube Mix (dipanggil via to_thread)."""
    with yt_dlp.YoutubeDL(_with_cookies(_mix_options(limit))) as ydl:
        return ydl.extract_info(url, download=False)


# Regex videoId YouTube (11 karakter) untuk path non-query (youtu.be, /embed, dst).
_VIDEO_ID_RE = re.compile(r'[A-Za-z0-9_-]{11}')
_VIDEO_ID_PATHS = ('embed', 'shorts', 'live', 'v')


def extract_video_id(url: str | None) -> str | None:
    """Ambil videoId YouTube (11 char) dari URL. None bila tidak bisa.

    Dukung: /watch?v=ID, youtu.be/ID, /embed/ID, /shorts/ID, /live/ID,
    music.youtube.com. Abaikan parameter list= / start_radio=.
    """
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    host = (parsed.hostname or '').lower()
    if not host:
        return None
    if host.startswith('www.'):
        host = host[4:]
    if host not in ('youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be'):
        return None

    # Bentuk query: /watch?v=ID (parameter list=/start_radio= diabaikan).
    if parsed.query:
        try:
            values = parse_qs(parsed.query).get('v')
        except ValueError:
            values = None
        if values:
            candidate = values[0].strip()
            match = _VIDEO_ID_RE.fullmatch(candidate)
            if match:
                return candidate

    # Bentuk path: youtu.be/ID, /embed/ID, /shorts/ID, /live/ID, /v/ID.
    segments = [seg for seg in parsed.path.split('/') if seg]
    if not segments:
        return None
    if host == 'youtu.be':
        candidate = segments[0]
    elif segments[0] in _VIDEO_ID_PATHS and len(segments) >= 2:
        candidate = segments[1]
    else:
        return None
    match = _VIDEO_ID_RE.fullmatch(candidate.strip())
    return candidate.strip() if match else None


def build_mix_url(video_id: str) -> str:
    """URL YouTube Mix (radio) untuk sebuah videoId."""
    return f'https://www.youtube.com/watch?v={video_id}&list=RD{video_id}&start_radio=1'


async def fetch_youtube_mix(video_id: str, exclude_urls: set[str] | None = None,
                            requester: str = 'AutoPlay',
                            limit: int | None = None) -> list[Track]:
    """Ambil lagu dari YouTube Mix untuk videoId.

    - limit default = MIX_RESULT_LIMIT (playlistend).
    - WAJIB playlistend=limit (tanpa ini ekstraksi ~20s).
    - Pakai _with_cookies(...) + js_runtimes.
    - Buang track yang url-nya ada di exclude_urls.
    - Buang livestream/dead entry (lewat _tracks_from_metadata).
    - Kembalikan list[Track]; KOSONG bila gagal (JANGAN raise ke pemanggil).
    """
    if not video_id:
        return []
    effective_limit = MIX_RESULT_LIMIT if limit is None else limit
    url = build_mix_url(video_id)
    try:
        data = await run_extract(_fetch_mix_metadata, url, effective_limit, timeout=60)
    except Exception as exc:
        log.warning('YouTube Mix gagal untuk videoId %s: %s', video_id, exc)
        return []
    if not data:
        return []
    try:
        tracks = _tracks_from_metadata(data, requester, url)
    except ValueError:
        return []
    excluded = exclude_urls or set()
    return [t for t in tracks if t.url not in excluded]


class BufferedAudioSource(discord.AudioSource):
    """Menyangga audio PCM ke dalam memori untuk mencegah fluktuasi kecepatan saat terjadi jitter jaringan."""
    def __init__(self, source: discord.AudioSource, buffer_size: int = 150):
        self.source = source
        self.queue: queue.Queue[bytes | None] = queue.Queue(maxsize=buffer_size)
        self.stop_event = threading.Event()
        self.ready_event = threading.Event()
        self._cleaned = False
        self._current_error: Exception | None = None
        self._misses = 0
        self._consecutive_hits = 0
        self._stall_deadline: float | None = None
        self.worker = threading.Thread(target=self._reader, daemon=True)
        self.worker.start()

    def _enqueue(self, item: bytes | None) -> bool:
        # put non-blocking ber-timeout agar stop/cleanup bangunkan thread (C5).
        while not self.stop_event.is_set():
            try:
                self.queue.put(item, timeout=1.0)
                return True
            except queue.Full:
                continue
        return False

    def _reader(self):
        count = 0
        try:
            while not self.stop_event.is_set():
                data = self.source.read()
                if not data:
                    self._enqueue(None)
                    break
                if not self._enqueue(data):
                    break
                count += 1
                if count >= 25 and not self.ready_event.is_set():
                    self.ready_event.set()
        except Exception as exc:
            self._current_error = exc
            self._enqueue(None)
        finally:
            self.ready_event.set()

    def read(self) -> bytes:
        if not self.ready_event.is_set():
            self.ready_event.wait(timeout=2.0)
            self.ready_event.set()
        if self.stop_event.is_set():
            return b''
        now = time.monotonic()
        if self._stall_deadline is not None and now >= self._stall_deadline and self.queue.empty():
            return b''
        try:
            data = self.queue.get(timeout=0.3)
            if data is None:
                return b''
            self._consecutive_hits += 1
            if self._consecutive_hits >= 3 or self.queue.qsize() >= 2:
                self._stall_deadline = None
                self._misses = 0
            elif self._stall_deadline is not None:
                # ponytail: deadline diperpanjang 0.1s per chunk saat jitter; jika butuh adaptive window berbasis bitrate, hitung frame duration dinamis
                self._stall_deadline += 0.1
            return data
        except queue.Empty:
            # Stall ffmpeg/network: jangan samarkan jadi hening selamanya (C6).
            # Hitungan miss berurutan tidak cukup — producer yang tersendat-sendat
            # (1 chunk per >0.3s) selalu mereset counter, sehingga EOF tak pernah
            # terjadi dan lagu tidak pernah lanjut. Pakai batas waktu nyata.
            now = time.monotonic()
            if self._stall_deadline is None:
                # Toleransi nyata untuk jitter CDN: 4 detik, bukan 1 detik.
                # Batas 1 detik terlalu agresif — CDN YouTube yang tersendat
                # sesaat membuat lagu loncat tanpa alasan.
                self._stall_deadline = now + STALL_EOF_SECONDS
            self._misses += 1
            self._consecutive_hits = 0
            if self._misses >= MAX_ERROR_STREAK or now >= self._stall_deadline:
                return b''
            return b'\x00' * 3840

    def cleanup(self):
        if self._cleaned:
            return
        self._cleaned = True
        self.stop_event.set()
        self.ready_event.set()
        try:
            self.source.cleanup()
        except Exception:
            pass
        try:
            while True:
                self.queue.get_nowait()
        except queue.Empty:
            pass
        if self.worker.is_alive() and threading.current_thread() is not self.worker:
            self.worker.join(timeout=2.0)

    def is_opus(self) -> bool:
        return self.source.is_opus()


def _source_error(source) -> Exception | None:
    """Telusuri rantai wrapper AudioSource untuk menemukan _current_error.

    discord.py hanya memeriksa getattr(self.source, '_current_error', None).
    Di sini source adalah PCMVolumeTransformer yang membungkus
    BufferedAudioSource -> FFmpegPCMAudio; error ffmpeg ada di elemen terdalam,
    sehingga tanpa penelusuran ini kegagalan ffmpeg selalu senyap.
    """
    seen: set[int] = set()
    current = source
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        error = getattr(current, '_current_error', None)
        if error:
            return error
        current = getattr(current, 'original', None) or getattr(current, 'source', None)
    return None


def patch_audio_player():
    # Guard versi discord.py agar monkeypatch tidak diam-diam basi (C-note).
    if getattr(discord.player.AudioPlayer, '_vita_patched', False):
        return

    def _steady_do_run(self):
        self.loops = 0
        self._start = time.perf_counter()

        client = self.client
        play_audio = client.send_audio_packet
        self._speak(discord.player.SpeakingState.voice)

        while not self._end.is_set():
            if not self._resumed.is_set():
                self.send_silence()
                self._resumed.wait()
                continue

            data = self.source.read()

            if not data:
                if self._current_error is None:
                    source_error = _source_error(self.source)
                    if source_error:
                        self._current_error = source_error
                self.stop()
                break

            if not client.is_connected():
                connected = client.wait_until_connected(client.timeout)
                if self._end.is_set():
                    return
                if not connected:
                    if self._current_error is None:
                        self._current_error = discord.ClientException('Voice connection lost.')
                    return
                self._speak(discord.player.SpeakingState.voice)
                self.loops = 0
                self._start = time.perf_counter()

            play_audio(data, encode=not self.source.is_opus())
            self.loops += 1
            now = time.perf_counter()
            next_time = self._start + self.DELAY * self.loops
            diff = next_time - now
            # Jika timing tertinggal > 40ms (2 frame) akibat lag jaringan / read stall:
            # Reset clock reference agar tidak burst-send paket (kecepatan / chipmunk effect).
            if diff < -0.04:
                self.loops = 0
                self._start = now
                delay = self.DELAY
            else:
                delay = max(0, self.DELAY + diff)
            time.sleep(delay)

        if client.is_connected():
            self.send_silence()

    discord.player.AudioPlayer._do_run = _steady_do_run
    discord.player.AudioPlayer._vita_patched = True


patch_audio_player()


def source_for(data: dict, volume: float | None = None) -> discord.PCMVolumeTransformer:
    if volume is None:
        volume = get_default_volume()
    pcm = discord.FFmpegPCMAudio(
        data['url'],
        before_options='-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_on_network_error 1 -reconnect_on_http_error 4xx,5xx -reconnect_delay_max 5',
        options='-vn'
    )
    try:
        buffered = BufferedAudioSource(pcm)
        return discord.PCMVolumeTransformer(buffered, volume=volume)
    except Exception:
        try:
            pcm.cleanup()
        except Exception:
            pass
        raise


def _check_same_voice(interaction: discord.Interaction) -> tuple[bool, str]:
    """Cek user di voice yang sama dengan bot; return (ok, pesan)."""
    guild = interaction.guild
    if not guild:
        return False, 'Hanya di server.'
    vc = guild.voice_client
    vc_channel_id = getattr(getattr(vc, 'channel', None), 'id', None)
    voice = getattr(interaction.user, 'voice', None)
    user_ch = getattr(voice, 'channel', None)
    if not vc or vc_channel_id is None:
        return False, 'Bot tidak ada di voice channel.'
    if not user_ch or user_ch.id != vc_channel_id:
        return False, 'Kamu harus di voice channel yang sama dengan bot.'
    return True, ''


def same_voice(interaction: discord.Interaction) -> bool:
    ok, _ = _check_same_voice(interaction)
    return ok


def _check_guild_only(interaction: discord.Interaction) -> bool:
    return interaction.guild is not None


class SearchModal(discord.ui.Modal, title='Putar lagu'):
    query = discord.ui.TextInput(label='Judul atau URL YouTube Music', max_length=500)

    def __init__(self, bot: 'MusicBot'):
        super().__init__(timeout=60)
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        self.stop()
        voice = getattr(interaction.user, 'voice', None)
        if not interaction.guild or not voice or not voice.channel:
            return await interaction.response.send_message('Masuk ke voice channel dulu.', ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        vc = guild.voice_client
        if not vc or getattr(vc, 'channel', None) is None:
            try:
                vc = await voice.channel.connect(timeout=20, self_deaf=True)
            except (asyncio.TimeoutError, TimeoutError):
                try:
                    cur = guild.voice_client
                    if cur:
                        await cur.disconnect(force=True)
                except Exception:
                    pass
                return await interaction.followup.send('Timeout masuk voice. Coba lagi.', ephemeral=True)
            except discord.ClientException:
                return await interaction.followup.send('Bot sudah dipakai di voice lain.', ephemeral=True)
            except Exception as exc:
                return await interaction.followup.send(f'Gagal masuk voice: {exc}', ephemeral=True)
        elif getattr(getattr(vc, 'channel', None), 'id', None) != voice.channel.id:
            return await interaction.followup.send('Bot sedang dipakai di voice channel lain.', ephemeral=True)

        try:
            tracks = await extract_tracks(str(self.query), interaction.user.mention)
            if not await self.bot._enqueue_tracks(guild, tracks):
                return await interaction.followup.send(f'Antrian penuh (maks {MAX_QUEUE} lagu).', ephemeral=True)
            if len(tracks) == 1:
                msg = f'Ditambahkan: **{discord.utils.escape_markdown(tracks[0].title)}**'
            else:
                msg = f'Ditambahkan {len(tracks)} lagu dari playlist. Lagu pertama: **{discord.utils.escape_markdown(tracks[0].title)}**'
            await interaction.followup.send(msg, ephemeral=True)
            state = self.bot.states.get(guild.id)
            if state:
                await self.bot.refresh(state)
        except Exception as exc:
            log.warning('Pencarian gagal: %s', exc)
            await interaction.followup.send(f'Gagal memproses lagu: {exc}', ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        self.stop()
        log.error('Search modal error: %s', error, exc_info=error)
        msg = f'Terjadi kesalahan saat memproses lagu: {error}'
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


class PlaylistView(discord.ui.View):
    def __init__(self, bot: 'MusicBot'):
        super().__init__(timeout=120)
        self.bot = bot

    @discord.ui.button(label='Tambah Lagu', emoji='➕', style=discord.ButtonStyle.primary, row=0)
    async def add_song(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchModal(self.bot))

    @discord.ui.button(label='Refresh', emoji='🔄', style=discord.ButtonStyle.secondary, row=0)
    async def refresh_playlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            return await interaction.followup.send('Hanya di server.', ephemeral=True)
        state = self.bot.states.setdefault(interaction.guild.id, QueueState())
        tracks = list(state.queue)[:10]
        header = f"**Sedang Diputar:** {discord.utils.escape_markdown(state.current.title)}\n\n" if state.current else ""
        if tracks:
            list_text = '\n'.join(f'{i}. {discord.utils.escape_markdown(t.title)} ({t.duration_str})' for i, t in enumerate(tracks, 1))
            more = f"\n*...dan {len(state.queue) - 10} lagu lainnya*" if len(state.queue) > 10 else ""
            msg = f"{header}**Antrian ({len(state.queue)} lagu):**\n{list_text}{more}"
        else:
            msg = f"{header}Antrian berikutnya kosong."
        await interaction.followup.send(msg[:1900], view=PlaylistView(self.bot), ephemeral=True)

    @discord.ui.button(label='Kosongkan Antrian', emoji='🗑️', style=discord.ButtonStyle.danger, row=0)
    async def clear_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            return await interaction.followup.send('Hanya di server.', ephemeral=True)
        vc = interaction.guild.voice_client
        vc_channel_id = getattr(getattr(vc, 'channel', None), 'id', None)
        user_vc = getattr(interaction.user, 'voice', None)
        user_ch = getattr(user_vc, 'channel', None)
        if not user_ch or (vc_channel_id is not None and user_ch.id != vc_channel_id):
            return await interaction.followup.send('Kamu harus di voice channel yang sama dengan bot.', ephemeral=True)
        state = self.bot.states.setdefault(interaction.guild.id, QueueState())
        async with state.lock:
            count = len(state.queue)
            state.queue.clear()
        self.bot._save_persistent_queue()
        await self.bot.refresh(state)
        await interaction.followup.send(f'Antrian berhasil dikosongkan ({count} lagu dihapus).', ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        log.error('PlaylistView error: %s', error, exc_info=error)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f'Terjadi kesalahan: {error}', ephemeral=True)
            else:
                await interaction.response.send_message(f'Terjadi kesalahan: {error}', ephemeral=True)
        except Exception:
            pass


AddSongView = PlaylistView


def _get_msg_id(msg) -> int | None:
    """Ekstrak ID pesan baik dari Message object maupun int/str."""
    if msg is None or isinstance(msg, bool):
        return None
    if isinstance(msg, int):
        return msg
    msg_id = getattr(msg, 'id', None)
    if msg_id is not None:
        try:
            return int(msg_id)
        except (ValueError, TypeError):
            return msg_id
    try:
        return int(msg)
    except (ValueError, TypeError):
        return None


class MusicPanel(discord.ui.View):
    def __init__(self, bot: 'MusicBot'):
        super().__init__(timeout=None)
        self.bot = bot

    async def guard(self, interaction: discord.Interaction, require_voice: bool = False) -> bool:
        voice = getattr(interaction.user, 'voice', None)
        if not interaction.guild or not voice or not voice.channel:
            if not interaction.response.is_done():
                await interaction.response.send_message('Masuk ke voice channel dulu.', ephemeral=True)
            else:
                await interaction.followup.send('Masuk ke voice channel dulu.', ephemeral=True)
            return False

        vc = interaction.guild.voice_client
        vc_channel_id = getattr(getattr(vc, 'channel', None), 'id', None)
        if not vc or vc_channel_id is None:
            # Tombol non-playback (volume/shuffle/loop/playlist) jangan auto-connect (M10).
            if require_voice:
                pass
            else:
                if not interaction.response.is_done():
                    await interaction.response.send_message('Bot belum ada di voice. Putar lagu dulu via /play.', ephemeral=True)
                else:
                    await interaction.followup.send('Bot belum ada di voice. Putar lagu dulu via /play.', ephemeral=True)
                return False
            try:
                perms = voice.channel.permissions_for(interaction.guild.me) if interaction.guild.me else None
                if perms is not None and (not getattr(perms, 'connect', True) or not getattr(perms, 'speak', True)):
                    msg = 'Bot butuh izin Connect + Speak di channel ini.'
                    if not interaction.response.is_done():
                        await interaction.response.send_message(msg, ephemeral=True)
                    else:
                        await interaction.followup.send(msg, ephemeral=True)
                    return False
                if not interaction.response.is_done():
                    try:
                        await interaction.response.defer(ephemeral=True)
                    except Exception:
                        pass
                vc = await voice.channel.connect(timeout=20, self_deaf=True)
            except (asyncio.TimeoutError, TimeoutError):
                log.warning('Timeout connect voice dari panel')
                msg = 'Timeout masuk voice. Coba lagi.'
                if not interaction.response.is_done():
                    await interaction.response.send_message(msg, ephemeral=True)
                else:
                    await interaction.followup.send(msg, ephemeral=True)
                return False
            except discord.ClientException as exc:
                log.warning('ClientException connect voice: %s', exc)
                msg = 'Bot sudah dipakai di voice lain.'
                if not interaction.response.is_done():
                    await interaction.response.send_message(msg, ephemeral=True)
                else:
                    await interaction.followup.send(msg, ephemeral=True)
                return False
            except Exception as exc:
                log.exception('Gagal connect voice dari panel: %s', exc)
                if not interaction.response.is_done():
                    await interaction.response.send_message('Gagal masuk voice channel bot. Cek izin bot.', ephemeral=True)
                else:
                    await interaction.followup.send('Gagal masuk voice channel bot. Cek izin bot.', ephemeral=True)
                return False
        elif vc_channel_id != voice.channel.id:
            if not interaction.response.is_done():
                await interaction.response.send_message('Bot sedang dipakai di voice channel lain.', ephemeral=True)
            else:
                await interaction.followup.send('Bot sedang dipakai di voice channel lain.', ephemeral=True)
            return False

        state = self.bot.states.setdefault(interaction.guild.id, QueueState())
        if interaction.message and state.message and _get_msg_id(state.message) != _get_msg_id(interaction.message):
            try:
                await interaction.message.delete()
            except Exception:
                pass
            msg = 'Panel ini sudah tidak aktif. Gunakan panel terbaru atau ketik /musik.'
            if not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.followup.send(msg, ephemeral=True)
            return False
        state.message = interaction.message
        if getattr(interaction, 'channel_id', None):
            state.text_channel_id = interaction.channel_id
        elif getattr(interaction, 'channel', None) and hasattr(interaction.channel, 'id'):
            state.text_channel_id = interaction.channel.id
        return True

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        log.error('Panel error on %s: %s', getattr(item, 'custom_id', item), error, exc_info=error)
        msg = f'Terjadi kesalahan: {error}'
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    # ROW 0: Down, Back, Pause, Skip, Up
    @discord.ui.button(label='Down', emoji='🔉', style=discord.ButtonStyle.secondary, custom_id='music:down', row=0)
    async def down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.guard(interaction):
            return
        state = self.bot.states.setdefault(interaction.guild.id, QueueState())
        await self.bot.change_volume(interaction, state.volume - 0.1)

    @discord.ui.button(label='Back', emoji='⏮️', style=discord.ButtonStyle.secondary, custom_id='music:back', row=0)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.guard(interaction, require_voice=True):
            return
        state = self.bot.states[interaction.guild.id]
        vc = interaction.guild.voice_client
        vc_channel_id = getattr(getattr(vc, 'channel', None), 'id', None)
        user_vc = getattr(interaction.user, 'voice', None)
        user_ch = getattr(user_vc, 'channel', None)
        if not vc or vc_channel_id is None or not user_ch or user_ch.id != vc_channel_id:
            return await interaction.followup.send('Kamu harus di voice channel yang sama dengan bot.', ephemeral=True)
        # Semua mutasi di dalam lock; semua await di luar lock agar followup.send
        # yang lambat tidak memblokir advance()/enqueue.
        async with state.lock:
            if not state.history and not state.current:
                had_prev = False
            else:
                had_prev = True
                if state.history:
                    prev = state.history.pop()
                    if state.current:
                        state.queue.appendleft(state.current)
                    state.queue.appendleft(prev)
                    state.current = None
                elif state.current:
                    state.queue.appendleft(state.current)
                    state.current = None
        if not had_prev:
            return await interaction.followup.send('Tidak ada riwayat lagu sebelumnya.', ephemeral=True)
        await self.bot._stop_player(interaction.guild)
        await self.bot.advance(interaction.guild)
        # removed # removed self.bot._save_persistent_queue()
        await interaction.followup.send('Memutar lagu sebelumnya.', ephemeral=True)

    @discord.ui.button(label='Pause', emoji='⏸️', style=discord.ButtonStyle.secondary, custom_id='music:pause', row=0)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.guard(interaction, require_voice=True):
            return
        vc = interaction.guild.voice_client
        vc_channel_id = getattr(getattr(vc, 'channel', None), 'id', None)
        user_vc = getattr(interaction.user, 'voice', None)
        user_ch = getattr(user_vc, 'channel', None)
        if not vc or vc_channel_id is None or not user_ch or user_ch.id != vc_channel_id:
            return await interaction.followup.send('Kamu harus di voice channel yang sama dengan bot.', ephemeral=True)
        if not vc:
            return await interaction.followup.send('Bot tidak ada di voice channel.', ephemeral=True)
        state = self.bot.states.setdefault(interaction.guild.id, QueueState())
        now = time.monotonic()
        if now - getattr(state, '_last_pause_time', 0.0) < 0.5:
            return await interaction.followup.send('Mohon tunggu sebentar sebelum menekan pause/resume lagi.', ephemeral=True)
        state._last_pause_time = now
        if vc.is_playing():
            vc.pause()
            text = 'Dijeda.'
        elif vc.is_paused():
            vc.resume()
            text = 'Dilanjutkan.'
        elif state.queue:
            await self.bot.advance(interaction.guild)
            text = 'Melanjutkan pemutaran antrian lagu.'
        else:
            text = 'Tidak ada lagu aktif atau antrian kosong.'
        await interaction.followup.send(text, ephemeral=True)
        await self.bot.refresh(state)

    @discord.ui.button(label='Skip', emoji='⏭️', style=discord.ButtonStyle.secondary, custom_id='music:skip', row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.guard(interaction, require_voice=True):
            return
        vc = interaction.guild.voice_client
        vc_channel_id = getattr(getattr(vc, 'channel', None), 'id', None)
        user_vc = getattr(interaction.user, 'voice', None)
        user_ch = getattr(user_vc, 'channel', None)
        if not vc or vc_channel_id is None or not user_ch or user_ch.id != vc_channel_id:
            return await interaction.followup.send('Kamu harus di voice channel yang sama dengan bot.', ephemeral=True)
        state = self.bot.states.setdefault(interaction.guild.id, QueueState())
        now = time.monotonic()
        if now - getattr(state, '_last_skip_time', 0.0) < 0.5:
            return await interaction.followup.send('Mohon tunggu sebentar sebelum menekan skip lagi.', ephemeral=True)
        state._last_skip_time = now
        if vc and (vc.is_playing() or vc.is_paused()):
            await self.bot._stop_player(interaction.guild)
            async with state.lock:
                if state.current:
                    state.history.append(state.current)
                    if len(state.history) > 20:
                        state.history.popleft()
                    state.current = None
            await self.bot.advance(interaction.guild)
            # removed # removed # removed self.bot._save_persistent_queue()
            text = 'Dilewati.'
        elif state._advancing > 0:
            # M4: belum ada audio yang berputar tetapi advance() sedang
            # mengekstraksi. Rekam permintaan skip; advance() yang sedang jalan
            # akan membuang track itu alih-alih memutarnya.
            async with state.lock:
                state._skip_pending = True
            text = 'Dilewati.'
        elif state.queue:
            async with state.lock:
                if state.current:
                    state.history.append(state.current)
                    if len(state.history) > 20:
                        state.history.popleft()
                    state.current = None
            await self.bot.advance(interaction.guild)
            # removed self.bot._save_persistent_queue()
            text = 'Memutar lagu berikutnya dari antrian.'
        else:
            text = 'Tidak ada lagu aktif.'
        await interaction.followup.send(text, ephemeral=True)

    @discord.ui.button(label='Up', emoji='🔊', style=discord.ButtonStyle.secondary, custom_id='music:up', row=0)
    async def up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.guard(interaction):
            return
        state = self.bot.states.setdefault(interaction.guild.id, QueueState())
        await self.bot.change_volume(interaction, state.volume + 0.1)

    # ROW 1: Shuffle, Loop, Stop, AutoPlay, Playlist
    @discord.ui.button(label='Shuffle', emoji='🔀', style=discord.ButtonStyle.secondary, custom_id='music:shuffle', row=1)
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.guard(interaction):
            return
        state = self.bot.states[interaction.guild.id]
        async with state.lock:
            if len(state.queue) < 2:
                too_few = True
            else:
                too_few = False
                import random
                items = list(state.queue)
                random.shuffle(items)
                state.queue.clear()
                state.queue.extend(items)
            shuffled_len = len(state.queue)
        self.bot._save_persistent_queue()
        if too_few:
            # await di luar lock (lihat catatan di back()).
            return await interaction.followup.send('Antrian kurang dari 2 lagu untuk diacak.', ephemeral=True)
        await interaction.followup.send(f'Antrian berhasil diacak ({shuffled_len} lagu).', ephemeral=True)
        await self.bot.refresh(state)

    @discord.ui.button(label='Loop', emoji='🔁', style=discord.ButtonStyle.secondary, custom_id='music:loop', row=1)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.guard(interaction):
            return
        state = self.bot.states[interaction.guild.id]
        cycle = {'off': 'track', 'track': 'queue', 'queue': 'off'}
        async with state.lock:
            state.loop_mode = cycle.get(state.loop_mode, 'off')
            loop_mode = state.loop_mode
        self.bot._save_persistent_queue()
        mode_text = {'track': 'Ulang Lagu Ini (Track)', 'queue': 'Ulang Seluruh Antrian (Queue)', 'off': 'Mati (Off)'}
        await interaction.followup.send(f'Mode Loop: **{mode_text[loop_mode]}**', ephemeral=True)
        await self.bot.refresh(state)

    @discord.ui.button(label='Stop', emoji='⏹️', style=discord.ButtonStyle.secondary, custom_id='music:stop', row=1)
    async def button_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.guard(interaction):
            return
        if interaction.guild:
            await self.bot.quit_voice(interaction.guild, clear_queue=True)
        await interaction.followup.send('Berhenti, antrian direset, dan keluar voice.', ephemeral=True)

    @discord.ui.button(label='AutoPlay', emoji='🔄', style=discord.ButtonStyle.secondary, custom_id='music:autoplay', row=1)
    async def autoplay(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.guard(interaction):
            return
        state = self.bot.states[interaction.guild.id]
        async with state.lock:
            state.autoplay = not state.autoplay
            autoplay_on = state.autoplay
        self.bot._save_persistent_queue()
        status = 'Aktif' if autoplay_on else 'Nonaktif'
        await interaction.followup.send(f'AutoPlay sekarang: **{status}**', ephemeral=True)
        await self.bot.refresh(state)

    @discord.ui.button(label='Playlist', emoji='🎵', style=discord.ButtonStyle.secondary, custom_id='music:playlist', row=1)
    async def playlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.bot.states.setdefault(interaction.guild.id, QueueState())
        if not state.queue and not state.current:
            return await interaction.response.send_modal(SearchModal(self.bot))

        await interaction.response.defer(ephemeral=True)
        if not await self.guard(interaction):
            return
        tracks = list(state.queue)[:10]
        header = f"**Sedang Diputar:** {discord.utils.escape_markdown(state.current.title)}\n\n" if state.current else ""
        if tracks:
            list_text = '\n'.join(f'{i}. {discord.utils.escape_markdown(t.title)} ({t.duration_str})' for i, t in enumerate(tracks, 1))
            more = f"\n*...dan {len(state.queue) - 10} lagu lainnya*" if len(state.queue) > 10 else ""
            msg = f"{header}**Antrian ({len(state.queue)} lagu):**\n{list_text}{more}"
        else:
            msg = f"{header}Antrian berikutnya kosong."
        view = PlaylistView(self.bot)
        await interaction.followup.send(msg[:1900], view=view, ephemeral=True)


class MusicBot(discord.Client):
    def __init__(self):
        try:
            if not discord.opus.is_loaded():
                try:
                    discord.opus.load_opus('libopus.so.0')
                except OSError:
                    # _load_default() menelan exception dan mengembalikan False
                    # alih-alih raise; periksa return-nya agar kegagalan libopus
                    # terdeteksi di sini, bukan nanti saat vc.play().
                    if not discord.opus._load_default():
                        raise SystemExit('libopus tidak ditemukan. Install libopus0.')
            if not discord.opus.is_loaded():
                raise SystemExit('libopus tidak ditemukan. Install libopus0.')
        except SystemExit:
            raise
        except Exception as exc:
            log.critical('libopus tidak tersedia, voice tidak bisa jalan: %s', exc)
            raise SystemExit('libopus tidak ditemukan. Install libopus0.') from exc
        intents = discord.Intents.default()
        intents.voice_states = True
        super().__init__(intents=intents)
        self._exporter_task: asyncio.Task | None = None
        self._panel_view: MusicPanel | None = None
        self._synced_guilds: set[int] = set()
        self.tree = discord.app_commands.CommandTree(self)
        self.tree.on_error = self.on_tree_error
        self.states: dict[int, QueueState] = {}
        self.tree.command(name='musik', description='Tampilkan panel musik interaktif dan panggil bot')(self.summon)
        self.tree.command(name='play', description='Putar lagu atau cari di YouTube')(self.cmd_play)
        self.tree.command(name='skip', description='Lewati lagu yang sedang diputar')(self.cmd_skip)
        self.tree.command(name='back', description='Putar lagu sebelumnya')(self.cmd_back)
        self.tree.command(name='stop', description='Hentikan musik dan keluar dari voice')(self.cmd_stop)
        self.tree.command(name='quit', description='Keluarkan bot dari voice channel, reset antrian, dan bersihkan cache')(self.cmd_quit)
        self.tree.command(name='antrian', description='Tampilkan daftar antrian lagu')(self.cmd_queue)
        self.tree.command(name='pause', description='Jeda atau lanjutkan pemutaran')(self.cmd_pause)
        self.tree.command(name='volume', description='Atur tingkat volume lagu (0–200%)')(self.cmd_volume)
        self.tree.command(name='shuffle', description='Acak daftar antrian lagu')(self.cmd_shuffle)
        self.tree.command(name='loop', description='Atur mode pengulangan (off, track, queue)')(self.cmd_loop)
        self.tree.command(name='autoplay', description='Aktifkan atau nonaktifkan putar otomatis (AutoPlay)')(self.cmd_autoplay)
        self.tree.command(name='help', description='Tampilkan daftar perintah dan cara pakai bot')(self.cmd_help)
        self._queue_state_file: str | None = None

    def _save_persistent_queue(self) -> None:
        path = getattr(self, '_queue_state_file', None) or _persistent_queue_file()
        try:
            payload = {}
            for gid, st in list(self.states.items()):
                curr = _track_to_dict(st.current) if getattr(st, 'current', None) else None
                q = [_track_to_dict(t) for t in getattr(st, 'queue', [])]
                if curr or q:
                    g_entry = {
                        'current': curr,
                        'queue': q,
                        'volume': getattr(st, 'volume', get_default_volume()),
                        'loop_mode': getattr(st, 'loop_mode', 'off'),
                        'autoplay': getattr(st, 'autoplay', False),
                    }
                    msg = getattr(st, 'message', None)
                    msg_id = getattr(msg, 'id', msg if isinstance(msg, int) else None)
                    if msg_id is not None:
                        g_entry['panel_message_id'] = msg_id
                    ch_id = getattr(getattr(msg, 'channel', None), 'id', None) or getattr(st, 'text_channel_id', None)
                    if ch_id is not None:
                        g_entry['text_channel_id'] = ch_id
                    payload[str(gid)] = g_entry
            if not payload:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                return

            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp_path = path + ".tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f)
            os.replace(tmp_path, path)
        except Exception as exc:
            log.debug('Gagal menyimpan persistent queue: %s', exc)

    def _restore_persistent_queue(self) -> None:
        path = getattr(self, '_queue_state_file', None) or _persistent_queue_file()
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as exc:
            log.warning('Gagal membaca persistent queue (rusak/tidak valid): %s', exc)
            try:
                os.remove(path)
            except Exception:
                pass
            return

        try:
            os.remove(path)
        except Exception:
            pass

        if not isinstance(data, dict):
            log.warning('Data persistent queue bukan format dict, dilewati.')
            return

        restored_guilds = 0
        for gid_str, g_data in data.items():
            try:
                gid = int(gid_str)
            except (ValueError, TypeError):
                continue
            if not isinstance(g_data, dict):
                continue
            state = self.states.setdefault(gid, QueueState())
            has_restored = False
            curr_data = g_data.get('current')
            if curr_data and isinstance(curr_data, dict) and state.current is None:
                track = _dict_to_track(curr_data)
                if track:
                    state.current = track
                    has_restored = True
            queue_data = g_data.get('queue', [])
            if isinstance(queue_data, list):
                for item in queue_data:
                    track = _dict_to_track(item)
                    if track:
                        state.queue.append(track)
                        has_restored = True
            panel_message_id = g_data.get('panel_message_id')
            if panel_message_id is not None and state.message is None:
                state.message = panel_message_id
            text_channel_id = g_data.get('text_channel_id')
            if text_channel_id is not None and getattr(state, 'text_channel_id', None) is None:
                state.text_channel_id = text_channel_id
            if 'volume' in g_data:
                try:
                    vol = float(g_data['volume'])
                    if not (vol != vol):
                        state.volume = round(max(0.0, min(vol, 2.0)), 2)
                        has_restored = True
                except (ValueError, TypeError):
                    pass
            if 'loop_mode' in g_data:
                loop_mode = str(g_data['loop_mode']).lower()
                if loop_mode in {'off', 'track', 'queue'}:
                    state.loop_mode = loop_mode
                    has_restored = True
            if 'autoplay' in g_data:
                state.autoplay = bool(g_data['autoplay'])
                has_restored = True
            if has_restored:
                restored_guilds += 1
        if restored_guilds > 0:
            log.info('Persistent queue berhasil dipulihkan untuk %d guild.', restored_guilds)

    async def _stop_player(self, guild: discord.Guild) -> None:
        """Hentikan player + bump generation agar after() basi tidak fire (C7)."""
        state = self.states.get(guild.id)
        vc = guild.voice_client
        was_playing = bool(vc and (vc.is_playing() or vc.is_paused()))
        if state:
            async with state.lock:
                state.generation += 1
                state._skip_armed = was_playing
                state.consecutive_playback_errors = 0
        if was_playing:
            try:
                vc.stop()
            except Exception:
                pass
        self._save_persistent_queue()

    async def _enqueue_tracks(self, guild: discord.Guild, tracks: list[Track]) -> bool:
        """Tambah track dengan cap total; return False bila penuh."""
        state = self.states.setdefault(guild.id, QueueState())
        vc = guild.voice_client
        playing = bool(vc and (vc.is_playing() or vc.is_paused()))
        async with state.lock:
            if len(state.queue) + len(tracks) > MAX_QUEUE:
                return False
            state.queue.extend(tracks)
            state.consecutive_playback_errors = 0
            # Keputusan memutar ditentukan oleh kondisi voice client nyata, bukan
            # hanya state.current. Kalau tidak ada yang benar-benar berputar,
            # state.current dianggap basi (mis. sisa track yang gagal diputar
            # atau koneksi voice putus diam-diam) agar antrian tidak macet.
            if not playing and state.current is not None:
                state.history.append(state.current)
                if len(state.history) > 20:
                    state.history.popleft()
                state.current = None
            need_advance = not playing
        self._save_persistent_queue()
        if need_advance and vc and not vc.is_playing() and not vc.is_paused():
            await self.advance(guild)
        return True

    async def on_interaction(self, interaction: discord.Interaction):
        name = None
        custom_id = None
        if hasattr(interaction, 'data') and isinstance(interaction.data, dict):
            name = interaction.data.get('name')
            custom_id = interaction.data.get('custom_id')
        log.debug('Interaction: type=%s name=%s custom_id=%s user=%s guild=%s',
                 getattr(interaction.type, 'name', interaction.type),
                 name, custom_id, interaction.user, getattr(interaction.guild, 'name', None))

    async def on_tree_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        log.error('CommandTree error: %s', error, exc_info=error)
        msg = f'Terjadi kesalahan saat memproses perintah: {error}'
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    async def _sync_guild(self, guild) -> None:
        gid = getattr(guild, 'id', None)
        if gid in self._synced_guilds:
            return
        self.tree.copy_global_to(guild=guild)
        try:
            await self.tree.sync(guild=guild)
        except discord.Forbidden as exc:
            log.error('Gagal sync ke %s: Missing Access %s', gid, exc)
            return
        except discord.HTTPException as exc:
            if getattr(exc, 'status', None) == 429:
                await asyncio.sleep(2)
                try:
                    await self.tree.sync(guild=guild)
                except Exception as exc2:
                    log.warning('Retry sync %s gagal: %s', gid, exc2)
                    return
            else:
                log.exception('Gagal sync ke %s', gid)
                return
        except Exception:
            log.exception('Gagal sync ke %s', gid)
            return
        self._synced_guilds.add(gid)
        log.info('Slash commands tersinkron ke server: %s (%s)', getattr(guild, 'name', gid), gid)

    async def setup_hook(self):
        self._register_signals()
        self._panel_view = MusicPanel(self)
        self.add_view(self._panel_view)
        try:
            self._exporter_task = asyncio.get_running_loop().create_task(self._state_exporter_loop())
        except RuntimeError:
            pass
        guild_id = os.getenv('DISCORD_GUILD_ID')
        if guild_id:
            if not guild_id.isdigit():
                log.error('DISCORD_GUILD_ID tidak valid: %r', guild_id)
            else:
                await self._sync_guild(discord.Object(id=int(guild_id)))

    async def _state_exporter_loop(self):
        try:
            await self.wait_until_ready()
            while not self.is_closed():
                try:
                    dump_runtime_state(self)
                except Exception as exc:
                    log.debug('Gagal menulis state runtime: %s', exc)
                await asyncio.sleep(30)
        except (asyncio.CancelledError, RuntimeError):
            pass

    async def on_ready(self):
        self._restore_persistent_queue()
        dump_runtime_state(self)
        guild_list = [f'{g.name} ({g.id})' for g in self.guilds]
        log.info('Bot login sebagai %s (ID: %s). Terhubung ke %d server: %s',
                 self.user, getattr(self.user, 'id', None), len(self.guilds),
                 ', '.join(guild_list) if guild_list else 'Belum ada server')

        # Sinkronkan command guild yang belum tersinkron (sekali per guild, C8).
        for guild in self.guilds:
            if guild.id not in self._synced_guilds:
                await self._sync_guild(guild)
                await asyncio.sleep(1)

    async def on_resumed(self):
        self._restore_persistent_queue()
        dump_runtime_state(self)

    async def on_guild_join(self, guild: discord.Guild):
        self._restore_persistent_queue()
        dump_runtime_state(self)
        await self._sync_guild(guild)

    async def on_guild_remove(self, guild: discord.Guild):
        dump_runtime_state(self)
        state = self.states.pop(guild.id, None)
        if state:
            for task in (state.idle_task, state.empty_task, state.afk_task, state.refresh_task, state.announce_task):
                if task and not task.done():
                    task.cancel()
            state.idle_task = state.empty_task = state.afk_task = state.refresh_task = state.announce_task = None
            state.afk_paused = False
        self._save_persistent_queue()

    def _register_signals(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, lambda s=sig: self._handle_signal(s))
            except (NotImplementedError, RuntimeError, ValueError, AttributeError):
                pass

    def _handle_signal(self, sig: int) -> None:
        signame = signal.Signals(sig).name if hasattr(signal, 'Signals') else str(sig)
        log.info('Menerima sinyal %s, menjadwalkan graceful shutdown...', signame)
        if getattr(self, '_stopping', False):
            return
        self._stopping = True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = getattr(self, 'loop', None)
        if loop and not loop.is_closed():
            self._close_task = loop.create_task(self.close())

    async def _safe_delete_msg(self, msg, channel: discord.abc.Messageable | None = None, guild: discord.Guild | None = None) -> None:
        """Hapus pesan Discord secara aman dan idempoten.

        Mendukung Message object dan fallback PartialMessage bila hanya tersisa ID.
        Menoleransi NotFound, Forbidden, HTTPException.
        """
        if msg is None:
            return
        if hasattr(msg, 'delete') and callable(msg.delete):
            try:
                res = msg.delete()
                if hasattr(res, '__await__'):
                    await res
                return
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                log.debug('Gagal menghapus pesan: %s', exc)
                return
            except Exception:
                log.debug('Gagal menghapus pesan (unexpected)', exc_info=True)
                return

        # Fallback bila pesan hanya berupa ID (misal int/str setelah restart atau obj tanpa delete)
        target_channel = channel or getattr(msg, 'channel', None)
        if not target_channel and guild and hasattr(guild, 'get_channel'):
            ch_id = getattr(msg, 'channel_id', None)
            if ch_id:
                try:
                    target_channel = guild.get_channel(int(ch_id))
                except (ValueError, TypeError):
                    pass
        if not target_channel and guild and hasattr(guild, 'text_channels') and guild.text_channels:
            target_channel = guild.text_channels[0]

        msg_id = getattr(msg, 'id', msg)
        if target_channel and hasattr(target_channel, 'get_partial_message'):
            try:
                msg_id_int = int(msg_id)
                partial = target_channel.get_partial_message(msg_id_int)
                if hasattr(partial, 'delete') and callable(partial.delete):
                    res = partial.delete()
                    if hasattr(res, '__await__'):
                        await res
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                log.debug('Gagal menghapus partial message: %s', exc)
            except Exception:
                log.debug('Gagal menghapus partial message (unexpected)', exc_info=True)

    async def _delete_all_panels(self) -> None:
        """Hapus semua pesan panel agar chat bersih saat bot mati.

        Dipanggil dari close() selagi koneksi HTTP masih hidup —
        super().close() menutup http/ws setelahnya.
        """
        targets = []
        for gid, st in list(self.states.items()):
            if getattr(st, 'message', None) is not None:
                targets.append((gid, st.message))
            if getattr(st, 'now_message', None) is not None:
                targets.append((gid, st.now_message))
        if not targets:
            return

        async def _del(gid: int, msg) -> None:
            state = self.states.get(gid)
            guild = self.get_guild(gid) if hasattr(self, 'get_guild') else None
            ch = getattr(msg, 'channel', None)
            if not ch and state and getattr(state, 'text_channel_id', None) and guild and hasattr(guild, 'get_channel'):
                ch = guild.get_channel(state.text_channel_id)
            if not ch and guild and hasattr(guild, 'text_channels') and guild.text_channels:
                ch = guild.text_channels[0]
            await self._safe_delete_msg(msg, channel=ch, guild=guild)

        try:
            await asyncio.wait_for(
                asyncio.gather(*(_del(gid, m) for gid, m in targets), return_exceptions=True),
                timeout=15,
            )
        except (asyncio.TimeoutError, TimeoutError):
            log.warning('Timeout hapus panel saat shutdown')
        for gid, _ in targets:
            state = self.states.get(gid)
            if state is not None:
                state.message = None
                state.now_message = None

    async def close(self):
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                try:
                    loop.remove_signal_handler(sig)
                except (NotImplementedError, RuntimeError, ValueError, AttributeError):
                    pass
        except RuntimeError:
            pass
        try:
            self._save_persistent_queue()
        except Exception as exc:
            log.debug('Gagal menyimpan persistent queue saat close: %s', exc)
        try:
            dump_runtime_state_offline()
        except Exception:
            pass
        for state in list(self.states.values()):
            for task in (state.idle_task, state.empty_task, state.afk_task, state.refresh_task, state.announce_task):
                if task and not task.done():
                    task.cancel()
            state.idle_task = state.empty_task = state.afk_task = state.refresh_task = state.announce_task = None
            state.afk_paused = False
        try:
            await self._delete_all_panels()
        except Exception:
            pass
        for view in list(getattr(self, 'persistent_views', [])):
            try:
                view.stop()
            except Exception:
                pass
        if getattr(self, '_panel_view', None):
            try:
                self._panel_view.stop()
            except Exception:
                pass
        if self._exporter_task and not self._exporter_task.done():
            self._exporter_task.cancel()
        await super().close()

    async def cmd_play(self, interaction: discord.Interaction, lagu: str):
        voice = getattr(interaction.user, 'voice', None)
        if not interaction.guild or not voice or not voice.channel:
            return await interaction.response.send_message('Masuk voice channel dulu.', ephemeral=True)
        await interaction.response.defer(thinking=True)
        vc = interaction.guild.voice_client
        if vc and getattr(getattr(vc, 'channel', None), 'id', None) != voice.channel.id:
            return await interaction.followup.send('Bot sedang dipakai di voice channel lain.', ephemeral=True)
        if not vc or getattr(vc, 'channel', None) is None:
            try:
                perms = voice.channel.permissions_for(interaction.guild.me) if interaction.guild.me else None
                if perms is not None and (not getattr(perms, 'connect', True) or not getattr(perms, 'speak', True)):
                    return await interaction.followup.send('Bot butuh izin Connect + Speak di channel ini.', ephemeral=True)
                vc = await voice.channel.connect(timeout=20, self_deaf=True)
            except (asyncio.TimeoutError, TimeoutError):
                try:
                    cur = interaction.guild.voice_client
                    if cur:
                        await cur.disconnect(force=True)
                except Exception:
                    pass
                return await interaction.followup.send('Timeout masuk voice. Coba lagi.', ephemeral=True)
            except discord.ClientException:
                return await interaction.followup.send('Bot sudah dipakai di voice lain.', ephemeral=True)
            except Exception:
                log.exception('Gagal masuk voice')
                return await interaction.followup.send('Gagal masuk voice. Cek izin Connect/Speak.', ephemeral=True)
        try:
            tracks = await extract_tracks(lagu, interaction.user.mention)
            if not await self._enqueue_tracks(interaction.guild, tracks):
                return await interaction.followup.send(f'Antrian penuh (maks {MAX_QUEUE} lagu).', ephemeral=True)
            state = self.states[interaction.guild.id]
            if len(tracks) == 1:
                msg = f'Ditambahkan ke antrian: **{discord.utils.escape_markdown(tracks[0].title)}**'
            else:
                msg = f'Ditambahkan {len(tracks)} lagu dari playlist ke antrian. Lagu pertama: **{discord.utils.escape_markdown(tracks[0].title)}**'
            await interaction.followup.send(msg)

            channel = interaction.channel
            if channel and hasattr(channel, 'send'):
                existing = state.message
                existing_channel_id = getattr(getattr(existing, 'channel', None), 'id', None)
                if existing is None or existing_channel_id != channel.id:
                    if existing:
                        state.message = None
                        try:
                            await existing.delete()
                        except Exception:
                            pass
                    try:
                        state.message = await channel.send(embed=self.embed(state), view=MusicPanel(self))
                        if hasattr(channel, 'id'):
                            state.text_channel_id = channel.id
                    except Exception:
                        log.exception('Gagal memunculkan panel otomatis saat play')
        except Exception as exc:
            log.warning('Pencarian gagal: %s', exc)
            await interaction.followup.send(f'Gagal mencari atau memproses lagu: {exc}', ephemeral=True)

    async def cmd_skip(self, interaction: discord.Interaction):
        if not _check_guild_only(interaction):
            return await interaction.response.send_message('Hanya di server.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, msg = _check_same_voice(interaction)
        if not ok:
            return await interaction.followup.send(msg, ephemeral=True)
        state = self.states.setdefault(interaction.guild.id, QueueState())
        now = time.monotonic()
        if now - getattr(state, '_last_skip_time', 0.0) < 0.5:
            return await interaction.followup.send('Mohon tunggu sebentar sebelum lewati lagu lagi.', ephemeral=True)
        state._last_skip_time = now
        # M4: advance() sedang ekstraksi dan belum ada audio yang berputar ->
        # rekam skip; advance() yang jalan akan membuang track head.
        vc = interaction.guild.voice_client
        if state._advancing > 0 and not (vc and (vc.is_playing() or vc.is_paused())):
            async with state.lock:
                state._skip_pending = True
            return await interaction.followup.send('Lagu dilewati.', ephemeral=True)
        await self._stop_player(interaction.guild)
        async with state.lock:
            if state.current:
                state.history.append(state.current)
                if len(state.history) > 20:
                    state.history.popleft()
                state.current = None
        await self.advance(interaction.guild)
        # removed # removed self._save_persistent_queue()
        await interaction.followup.send('Lagu dilewati.', ephemeral=True)

    async def cmd_back(self, interaction: discord.Interaction):
        if not _check_guild_only(interaction):
            return await interaction.response.send_message('Hanya di server.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, msg = _check_same_voice(interaction)
        if not ok:
            return await interaction.followup.send(msg, ephemeral=True)
        state = self.states.get(interaction.guild.id)
        if not state or (not state.history and not state.current):
            return await interaction.followup.send('Tidak ada riwayat lagu sebelumnya.', ephemeral=True)
        async with state.lock:
            if state.history:
                prev = state.history.pop()
                if state.current:
                    state.queue.appendleft(state.current)
                state.queue.appendleft(prev)
                state.current = None
            elif state.current:
                state.queue.appendleft(state.current)
                state.current = None
        await self._stop_player(interaction.guild)
        await self.advance(interaction.guild)
        # removed # removed self._save_persistent_queue()
        await interaction.followup.send('Memutar lagu sebelumnya.', ephemeral=True)

    async def cmd_shuffle(self, interaction: discord.Interaction):
        if not _check_guild_only(interaction):
            return await interaction.response.send_message('Hanya di server.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, msg = _check_same_voice(interaction)
        if not ok:
            return await interaction.followup.send(msg, ephemeral=True)
        state = self.states.get(interaction.guild.id)
        if not state or len(state.queue) < 2:
            return await interaction.followup.send('Antrian kurang dari 2 lagu untuk diacak.', ephemeral=True)
        async with state.lock:
            import random
            items = list(state.queue)
            random.shuffle(items)
            state.queue.clear()
            state.queue.extend(items)
            shuffled_len = len(state.queue)
        self._save_persistent_queue()
        await interaction.followup.send(f'Antrian berhasil diacak ({shuffled_len} lagu).', ephemeral=True)
        await self.refresh(state)

    async def cmd_loop(self, interaction: discord.Interaction, mode: str | None = None):
        if not _check_guild_only(interaction):
            return await interaction.response.send_message('Hanya di server.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        state = self.states.setdefault(interaction.guild.id, QueueState())
        async with state.lock:
            if mode and mode.lower() in {'off', 'track', 'queue'}:
                state.loop_mode = mode.lower()
            else:
                cycle = {'off': 'track', 'track': 'queue', 'queue': 'off'}
                state.loop_mode = cycle.get(state.loop_mode, 'off')
            loop_mode = state.loop_mode
        self._save_persistent_queue()
        mode_text = {'track': 'Ulang Lagu Ini (Track)', 'queue': 'Ulang Seluruh Antrian (Queue)', 'off': 'Mati (Off)'}
        await interaction.followup.send(f'Mode Loop: **{mode_text[loop_mode]}**', ephemeral=True)
        await self.refresh(state)

    async def cmd_autoplay(self, interaction: discord.Interaction):
        if not _check_guild_only(interaction):
            return await interaction.response.send_message('Hanya di server.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        state = self.states.setdefault(interaction.guild.id, QueueState())
        async with state.lock:
            state.autoplay = not state.autoplay
            autoplay_on = state.autoplay
        self._save_persistent_queue()
        status = 'Aktif' if autoplay_on else 'Nonaktif'
        await interaction.followup.send(f'AutoPlay sekarang: **{status}**', ephemeral=True)
        await self.refresh(state)

    async def quit_voice(self, guild: discord.Guild, clear_queue: bool = False, delete_panel: bool = True) -> None:
        state = self.states.get(guild.id)
        old_now_message = None
        old_message = None
        current = asyncio.current_task()
        if state:
            async with state.lock:
                state.generation += 1
                if clear_queue:
                    state.queue.clear()
                    state.history.clear()
                state.current = None
                # Jangan cancel task yang sedang menjalankan quit_voice (mis. afk_task atau idle_task).
                # Bila task meng-cancel dirinya sendiri, await berikutnya langsung melempar CancelledError
                # sehingga vc.disconnect() tidak pernah terpanggil dan bot tersangkut di voice.
                for task in (state.idle_task, state.empty_task, state.afk_task, state.refresh_task):
                    if task and not task.done() and task is not current:
                        task.cancel()
                state.idle_task = state.empty_task = state.afk_task = state.refresh_task = None
                state.afk_paused = False
                announce_task = state.announce_task
                state.announce_task = None
                old_now_message = state.now_message
                state.now_message = None
                if delete_panel:
                    old_message = state.message
                    state.message = None
            if announce_task and not announce_task.done() and announce_task is not current:
                announce_task.cancel()
            if old_now_message is not None:
                await self._safe_delete_msg(old_now_message, guild=guild)
            if delete_panel and old_message is not None:
                ch = getattr(old_message, 'channel', None)
                if not ch and getattr(state, 'text_channel_id', None) and hasattr(guild, 'get_channel'):
                    ch = guild.get_channel(state.text_channel_id)
                if not ch and hasattr(guild, 'text_channels') and guild.text_channels:
                    ch = guild.text_channels[0]
                await self._safe_delete_msg(old_message, channel=ch, guild=guild)
        vc = getattr(guild, 'voice_client', None)
        if vc:
            try:
                source = getattr(vc, 'source', None)
                if getattr(vc, 'is_playing', lambda: False)() or getattr(vc, 'is_paused', lambda: False)():
                    vc.stop()
                if source and hasattr(source, 'cleanup'):
                    try:
                        source.cleanup()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                await asyncio.wait_for(vc.disconnect(force=True), timeout=10.0)
            except Exception:
                pass
        if state and not delete_panel:
            await self.refresh(state)
        self._save_persistent_queue()
        dump_runtime_state(self)
        if clear_queue:
            try:
                await asyncio.to_thread(clear_cache)
            except Exception as exc:
                log.debug('Gagal membersihkan cache: %s', exc)

    async def cmd_stop(self, interaction: discord.Interaction):
        if not _check_guild_only(interaction):
            return await interaction.response.send_message('Hanya di server.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, msg = _check_same_voice(interaction)
        if not ok:
            return await interaction.followup.send(msg, ephemeral=True)
        await self.quit_voice(interaction.guild, clear_queue=True)
        await interaction.followup.send('Musik dihentikan, antrian direset, dan bot keluar voice.', ephemeral=True)

    async def cmd_quit(self, interaction: discord.Interaction):
        if not _check_guild_only(interaction):
            return await interaction.response.send_message('Hanya di server.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, msg = _check_same_voice(interaction)
        if not ok:
            return await interaction.followup.send(msg, ephemeral=True)
        await self.quit_voice(interaction.guild, clear_queue=True)
        await interaction.followup.send('Bot keluar dari voice channel, antrian direset, dan cache dibersihkan.', ephemeral=True)

    async def cmd_queue(self, interaction: discord.Interaction):
        if not _check_guild_only(interaction):
            return await interaction.response.send_message('Hanya di server.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        state = self.states.get(interaction.guild.id)
        if not state or (not state.queue and not state.current):
            return await interaction.followup.send('Antrian lagu kosong.', ephemeral=True)
        tracks = list(state.queue)[:10]
        header = f"**Sedang Diputar:** {discord.utils.escape_markdown(state.current.title)}\n\n" if state.current else ""
        if tracks:
            text = '\n'.join(f'{i}. {discord.utils.escape_markdown(t.title)} ({t.duration_str})' for i, t in enumerate(tracks, 1))
            more = f"\n*...dan {len(state.queue) - 10} lagu lainnya*" if len(state.queue) > 10 else ""
            msg = f"{header}**Antrian Lagu ({len(state.queue)} lagu):**\n{text}{more}"
        else:
            msg = f"{header}Antrian berikutnya kosong."
        await interaction.followup.send(msg[:1900], view=PlaylistView(self), ephemeral=True)

    async def cmd_pause(self, interaction: discord.Interaction):
        if not _check_guild_only(interaction):
            return await interaction.response.send_message('Hanya di server.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok, msg = _check_same_voice(interaction)
        if not ok:
            return await interaction.followup.send(msg, ephemeral=True)
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.followup.send('Bot tidak ada di voice channel.', ephemeral=True)
        state = self.states.setdefault(interaction.guild.id, QueueState())
        now = time.monotonic()
        if now - getattr(state, '_last_pause_time', 0.0) < 0.5:
            return await interaction.followup.send('Mohon tunggu sebentar sebelum menekan pause/resume lagi.', ephemeral=True)
        state._last_pause_time = now
        if vc.is_playing():
            vc.pause()
            await interaction.followup.send('Pemutaran dijeda.', ephemeral=True)
        elif vc.is_paused():
            vc.resume()
            await interaction.followup.send('Pemutaran dilanjutkan.', ephemeral=True)
        else:
            if state and state.queue:
                await self.advance(interaction.guild)
                await interaction.followup.send('Melanjutkan pemutaran antrian lagu.', ephemeral=True)
            else:
                await interaction.followup.send('Tidak ada lagu yang aktif atau antrian kosong.', ephemeral=True)
        await self.refresh(state)

    async def cmd_volume(self, interaction: discord.Interaction, tingkat: int):
        voice = getattr(interaction.user, 'voice', None)
        if not interaction.guild or not voice or not voice.channel:
            return await interaction.response.send_message('Masuk voice channel dulu.', ephemeral=True)
        if tingkat < 0 or tingkat > 200:
            return await interaction.response.send_message('Volume harus antara 0% sampai 200%.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        await self.change_volume(interaction, tingkat / 100.0)

    async def change_volume(self, interaction: discord.Interaction, target_vol: float):
        if not interaction.guild:
            return await interaction.followup.send('Hanya di server.', ephemeral=True)
        state = self.states.setdefault(interaction.guild.id, QueueState())
        async with state.lock:
            state.volume = round(max(0.0, min(target_vol, 2.0)), 2)
            vol = state.volume
        self._save_persistent_queue()
        vc = interaction.guild.voice_client
        if vc and getattr(vc, 'source', None):
            source = vc.source
            if isinstance(source, discord.PCMVolumeTransformer):
                source.volume = vol
        pct = int(round(vol * 100))
        msg = f'Volume diatur ke **{pct}%**.'
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        await self.refresh(state)

    async def cmd_help(self, interaction: discord.Interaction):
        """Daftar perintah. Ephemeral agar tidak mengotori channel."""
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        except Exception as exc:
            log.debug('Gagal defer /help: %s', exc)
        embed = discord.Embed(
            title='Perintah Bot Musik',
            description='Semua perintah bisa dipakai setelah bot masuk voice channel.',
            color=0x5865F2,
        )
        embed.add_field(
            name='▶️ Memutar',
            value=(
                '`/musik` — buka panel musik & panggil bot ke voice\n'
                '`/play <judul atau URL>` — putar lagu atau playlist\n'
                '`/pause` — jeda atau lanjutkan pemutaran\n'
                '`/skip` — lewati lagu sekarang\n'
                '`/back` — putar lagu sebelumnya\n'
                '`/stop` — hentikan musik dan keluar dari voice'
            ),
            inline=False,
        )
        embed.add_field(
            name='📋 Antrian',
            value=(
                '`/antrian` — lihat daftar antrian lagu\n'
                '`/shuffle` — acak antrian\n'
                '`/loop <off|track|queue>` — atur mode pengulangan\n'
                '`/autoplay` — rekomendasi otomatis berbasis YouTube Mix saat antrian habis'
            ),
            inline=False,
        )
        embed.add_field(
            name='⚙️ Lainnya',
            value=(
                '`/volume <0-200>` — atur volume\n'
                '`/quit` — keluarkan bot, reset antrian, bersihkan cache\n'
                '`/help` — tampilkan pesan ini'
            ),
            inline=False,
        )
        embed.set_footer(text='Panel tombol juga tersedia lewat /musik')
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException as exc:
            log.debug('Gagal kirim /help: %s', exc)

    async def summon(self, interaction: discord.Interaction):
        voice = getattr(interaction.user, 'voice', None)
        if not interaction.guild or not voice or not voice.channel:
            return await interaction.response.send_message('Masuk voice channel dulu.', ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        vc = interaction.guild.voice_client
        if vc and getattr(getattr(vc, 'channel', None), 'id', None) != voice.channel.id:
            return await interaction.followup.send('Bot sedang dipakai di voice channel lain.', ephemeral=True)
        if not vc or getattr(vc, 'channel', None) is None:
            try:
                perms = voice.channel.permissions_for(interaction.guild.me) if interaction.guild.me else None
                if perms is not None and (not getattr(perms, 'connect', True) or not getattr(perms, 'speak', True)):
                    return await interaction.followup.send('Bot butuh izin Connect + Speak di channel ini.', ephemeral=True)
                vc = await voice.channel.connect(timeout=20, self_deaf=True)
            except (asyncio.TimeoutError, TimeoutError):
                try:
                    cur = interaction.guild.voice_client
                    if cur:
                        await cur.disconnect(force=True)
                except Exception:
                    pass
                return await interaction.followup.send('Timeout masuk voice. Coba lagi.', ephemeral=True)
            except discord.ClientException:
                return await interaction.followup.send('Bot sudah dipakai di voice lain.', ephemeral=True)
            except Exception:
                log.exception('Gagal masuk voice')
                return await interaction.followup.send('Gagal masuk voice. Cek izin Connect/Speak.', ephemeral=True)
        state = self.states.setdefault(interaction.guild.id, QueueState())
        if state.message:
            old_msg = state.message
            state.message = None
            try:
                await old_msg.delete()
            except Exception:
                pass

        channel = interaction.channel
        if channel is None and interaction.channel_id and interaction.guild:
            channel = interaction.guild.get_channel(interaction.channel_id)

        if not channel or not hasattr(channel, 'send'):
            return await interaction.followup.send('Tidak dapat menemukan text channel untuk menampilkan panel.', ephemeral=True)

        try:
            state.message = await channel.send(embed=self.embed(state), view=MusicPanel(self))
            if hasattr(channel, 'id'):
                state.text_channel_id = channel.id
            await interaction.followup.send('Panel musik aktif di channel ini.', ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send('Bot butuh izin Send Messages + Embed Links di channel ini.', ephemeral=True)
        except Exception:
            log.exception('Gagal mengirim panel musik')
            await interaction.followup.send('Gagal memunculkan panel. Coba lagi.', ephemeral=True)

    def embed(self, state: QueueState) -> discord.Embed:
        embed = discord.Embed(color=0x2b2d31)
        avatar_url = self.user.display_avatar.url if self.user else None
        embed.set_author(name="MUSIC PANEL", icon_url=avatar_url)

        track = state.current
        if track:
            embed.description = f"💿 `{track.title}`"
            embed.add_field(name="🎧 Requested By", value=track.requester, inline=True)
            embed.add_field(name="⏱ Music Duration", value=f"`{track.duration_str}`", inline=True)
            embed.add_field(name="🎙 Music Author", value=f"`{track.author}`", inline=True)
        else:
            embed.description = "💿 `Tekan Playlist / ketik /play untuk memutar lagu`"
            vol_pct = int(round(state.volume * 100))
            embed.add_field(name="🎧 Status", value="`Idle`", inline=True)
            embed.add_field(name="🔊 Volume", value=f"`{vol_pct}%`", inline=True)
            embed.add_field(name="📑 Antrian", value=f"`{len(state.queue)} lagu`", inline=True)

        return embed

    async def refresh(self, state: QueueState):
        # Coalesce refresh beruntun agar tidak spam edit Discord (M15).
        if state.refresh_task and not state.refresh_task.done():
            return
        async def _do():
            await asyncio.sleep(0.5)
            msg = state.message
            if not (msg and hasattr(msg, 'edit')):
                return
            try:
                async with state.lock:
                    embed = self.embed(state)
                await msg.edit(embed=embed)
            except discord.HTTPException:
                if state.message is msg:
                    state.message = None
            except Exception:
                # state.message bisa di-null-kan coroutine lain di sela await;
                # jangan biarkan AttributeError jadi "task exception never
                # retrieved" (L1).
                log.debug('Refresh panel gagal', exc_info=True)
                if state.message is msg:
                    state.message = None
        try:
            state.refresh_task = asyncio.get_running_loop().create_task(_do())
        except RuntimeError:
            pass

    async def advance(self, guild: discord.Guild):
        """Pilih track berikutnya dan putar. Lock hanya untuk mutasi deque (C4)."""
        state = self.states[guild.id]
        vc = guild.voice_client
        if not vc or not getattr(vc, 'is_connected', lambda: False)():
            log.warning('advance() dibatalkan: voice client tidak terhubung.')
            asyncio.create_task(self.quit_voice(guild, clear_queue=False))
            return
        if state._advance_lock.locked():
            return
        async with state._advance_lock:
            async with state.lock:
                if state.idle_task and not state.idle_task.done():
                    state.idle_task.cancel()
                state.idle_task = None
                if vc.is_playing() or vc.is_paused():
                    return
        # M4: tandai bahwa advance() benar-benar berjalan (fase ekstraksi/putar).
        # Handler Skip memakai flag ini untuk merekam _skip_pending. Memakai
        # _advance_lock.locked() SALAH: lock hanya dipegang di guard di atas,
        # sudah dilepas sebelum loop -> flag M4 dulu tak pernah aktif (dead code).
        # Counter (bukan bool): /play saat ekstraksi bisa memicu advance() kedua
        # yang berjalan bersamaan; bool akan di-reset oleh yang selesai duluan.
        async with state.lock:
            state._advancing += 1
        try:
            await self._advance_loop(guild, state, vc)
        finally:
            async with state.lock:
                state._advancing = max(0, state._advancing - 1)

    async def _advance_loop(self, guild: discord.Guild, state: QueueState, vc) -> None:
        """Inti advance(): pilih, ekstraksi, putar. Selalu dipanggil dari advance()."""
        gen0 = state.generation  # F2: deteksi /stop atau reconnect di tengah jalan
        loop = asyncio.get_running_loop()
        consecutive_errors = 0
        while True:
            if consecutive_errors >= MAX_TRACK_RETRIES:
                log.error('3 lagu berturut-turut gagal diputar di guild %s. Pemutaran dihentikan agar sisa %d lagu di antrian tidak hilang.', guild.name, len(state.queue))
                break

            # --- fase 1: pilih kandidat di dalam lock (cepat, tanpa I/O) ---
            async with state.lock:
                if vc.is_playing() or vc.is_paused():
                    return
                next_track = None
                if state.loop_mode == 'track' and state.current:
                    next_track = state.current
                elif state.queue:
                    next_track = state.queue[0]
                elif state.loop_mode == 'queue' and state.current:
                    next_track = state.current
                elif state.autoplay and (state.current or state.history):
                    next_track = None  # resolve di luar lock (M9)
                if not next_track and not (state.autoplay and (state.current or state.history)):
                    break

            # --- fase 2: autoplay resolve di luar lock (M9) ---
            if next_track is None and state.autoplay and (state.current or state.history):
                try:
                    async with state.lock:
                        seed_titles = [t.title for t in list(state.history)[-5:]]
                        seed_urls = [t.url for t in list(state.history)[-5:]]
                        if state.current:
                            seed_titles.append(state.current.title)
                            seed_urls.append(state.current.url)
                        played_urls = {t.url for t in list(state.history)[-20:]}
                        if state.current:
                            played_urls.add(state.current.url)
                    candidates = await fetch_recommendations(
                        seed_titles, played_urls, seed_urls=seed_urls)
                    next_track = next((c for c in candidates
                                       if c.url not in played_urls), None)
                    if next_track is None:
                        log.info('AutoPlay: tidak ada rekomendasi baru, pemutaran berhenti.')
                        break
                    log.info('AutoPlay (Mix) memilih: %s', next_track.title)
                except Exception as exc:
                    log.warning('AutoPlay failed: %s', exc)
                    break
                if not next_track:
                    break

            # --- fase 3: extract stream di luar lock (C4) + batas thread (H3) ---
            try:
                if next_track.stream_url and next_track.stream_ts and (time.time() - next_track.stream_ts) < 1800:
                    data = {'url': next_track.stream_url, 'title': next_track.title}
                else:
                    data = await run_extract(extract, next_track.url, timeout=60)
                # F2: /stop atau reconnect selama ekstraksi membump generation dan
                # mengganti voice client. Lanjut memutar = memakai vc lama yang
                # sudah putus (ClientException) dan lagu baru tak pernah diputar.
                # Batalkan advance basi ini; advance baru dari /play yang jalan.
                if state.generation != gen0 or guild.voice_client is not vc:
                    log.info('advance() basi (generation/voice berubah) saat ekstraksi %s; dibatalkan.',
                             next_track.title)
                    state._skip_pending = False
                    return
                # M4: user menekan Skip selama ekstraksi -> jangan putar track ini;
                # buang head queue (bila berasal dari queue) lalu pilih kandidat
                # berikutnya. Jangan sentuh history/current: track ini belum
                # pernah diputar.
                skip_now = False
                async with state.lock:
                    if state._skip_pending:
                        state._skip_pending = False
                        skip_now = True
                        if state.queue and state.queue[0] is next_track:
                            state.queue.popleft()
                        elif state.loop_mode == 'track' and state.current is next_track:
                            # Loop track: skip manual harus keluar dari track yang
                            # sama, bukan mengulangnya lagi.
                            state.current = None
                if skip_now:
                    log.info('Skip saat ekstraksi: %s dilewati.', next_track.title)
                    continue
                if isinstance(data, dict) and (data.get('is_live') or data.get('live_status') == 'is_live'):
                    log.warning('Live stream dilewati: %s', next_track.title)
                    async with state.lock:
                        if state.queue and state.queue[0] is next_track:
                            state.queue.popleft()
                    consecutive_errors += 1
                    continue
                channel = getattr(vc, 'channel', None)
                raw_bitrate = getattr(channel, 'bitrate', 96000)
                try:
                    bitrate_kbps = int(raw_bitrate) // 1000
                    bitrate_kbps = min(max(bitrate_kbps, 64), 160)
                except (TypeError, ValueError):
                    bitrate_kbps = 96
                source = None
                try:
                    source = source_for(data, volume=state.volume)
                    async with state.lock:
                        if vc.is_playing() or vc.is_paused():
                            try:
                                source.cleanup()
                            except Exception:
                                pass
                            return
                        generation = state.generation

                    def after(error, _gen=generation):
                        if error:
                            log.error('Audio playback error: %s', error)
                        # Skip/back manual: after() dari vc.stop() diabaikan,
                        # advance manual di handler yang jalan — anti dobel.
                        async def _after_dispatch():
                            st = self.states.get(guild.id)
                            if st is None:
                                return
                            skip = False
                            async with st.lock:
                                if getattr(st, '_skip_armed', False):
                                    if _gen != st.generation:
                                        skip = True
                                    st._skip_armed = False
                            if skip:
                                return
                            if error:
                                circuit_broken = False
                                async with st.lock:
                                    st.consecutive_playback_errors = getattr(st, 'consecutive_playback_errors', 0) + 1
                                    if st.consecutive_playback_errors >= MAX_TRACK_RETRIES:
                                        circuit_broken = True
                                        log.error(
                                            '%d lagu berturut-turut gagal diputar di guild %s akibat stream error. '
                                            'Circuit breaker aktif, pemutaran dihentikan agar antrian aman.',
                                            st.consecutive_playback_errors, guild.name
                                        )
                                        if st.current and (not st.queue or st.queue[0] is not st.current):
                                            st.queue.appendleft(st.current)
                                        st.current = None
                                if circuit_broken:
                                    self._save_persistent_queue()
                                    await self.refresh(st)
                                    self._schedule_idle(guild, st.generation)
                                    return
                                await asyncio.sleep(1.0)
                            else:
                                async with st.lock:
                                    st.consecutive_playback_errors = 0
                            await self.finished(guild, _gen)
                        try:
                            fut = asyncio.run_coroutine_threadsafe(_after_dispatch(), loop)
                        except RuntimeError:
                            return
                        def _cb(f):
                            if f.cancelled():
                                return
                            try:
                                exc = f.exception()
                            except Exception:
                                return
                            if exc:
                                log.error('Queue advance failed: %s', exc)
                        fut.add_done_callback(_cb)

                    try:
                        vc.play(source, after=after, application='audio', bitrate=bitrate_kbps, signal_type='music')
                    except discord.ClientException as exc:
                        if 'Not connected to voice' in str(exc):
                            log.error('vc.play gagal: %s', exc)
                            asyncio.create_task(self.quit_voice(guild, clear_queue=False))
                        # L2: TOCTOU — player lain menang balapan di sela await.
                        # Jangan salahkan track ini (bukan kegagalan stream).
                        try:
                            source.cleanup()
                        except Exception:
                            pass
                        return
                except Exception:
                    if source is not None:
                        try:
                            source.cleanup()
                        except Exception:
                            pass
                    raise
                # --- fase 4: commit sukses di dalam lock (C1/C2/C3) ---
                # played harus selalu terdefinisi: mode loop 'track' atau 'queue'
                # (saat antrian kosong) mengulang track yang sama tanpa menyentuh
                # queue/history, tetapi tetap butuh objek track untuk pengumuman now-playing.
                played = next_track
                async with state.lock:
                    state._skip_armed = False
                    state._skip_pending = False
                    if (state.loop_mode == 'track' or (state.loop_mode == 'queue' and not state.queue)) and state.current is next_track:
                        pass
                    else:
                        if state.queue and state.queue[0] is next_track:
                            state.queue.popleft()
                        if state.current and state.current is not next_track:
                            state.history.append(state.current)
                            if len(state.history) > 20:
                                state.history.popleft()
                            if state.loop_mode == 'queue':
                                state.queue.append(state.current)
                        state.current = next_track
                self._save_persistent_queue()
                await self.refresh(state)
                self._announce(guild, played)
                return
            except Exception as exc:
                consecutive_errors += 1
                log.warning('Tidak bisa memutar (%d/3): %s (penyebab: %s)', consecutive_errors, next_track.title, exc)
                async with state.lock:
                    # F1: konsumsi _skip_pending apa pun. Bila tidak, skip yang
                    # menargetkan track gagal ini tetap "menggantung" dan ikut
                    # membuang track BERIKUTNYA (satu skip = dua lagu hilang).
                    state._skip_pending = False
                    if consecutive_errors >= MAX_TRACK_RETRIES:
                        break
                    # Gagal: jangan sentuh history/queue (C3); biarkan track di head untuk retry manual.
                    # Putar kandidat berikutnya hanya bila masih ada track lain.
                    if state.queue and state.queue[0] is next_track and len(state.queue) > 1:
                        state.queue.popleft()
                        state.queue.append(next_track)
                    else:
                        break

        await self.refresh(state)
        async with state.lock:
            # Kalau loop berhenti tanpa ada yang berputar, `current` tidak boleh
            # dianggap masih diputar: kalau tidak, /play berikutnya akan mengira
            # sudah ada track aktif dan tidak pernah memajukan antrian, dan
            # idle-disconnect tidak akan pernah terjadwal (bot tertahan di voice).
            if not (vc.is_playing() or vc.is_paused()):
                state._skip_armed = False
                state._skip_pending = False
                if state.current is not None:
                    state.history.append(state.current)
                    if len(state.history) > 20:
                        state.history.popleft()
                    state.current = None
            self._save_persistent_queue()
            schedule_idle = state.current is None and not state.queue
            gen = state.generation
        if schedule_idle:
            self._schedule_idle(guild, gen)

    async def _announce_now_playing(self, guild: discord.Guild, track) -> None:
        """Kirim pesan judul lagu baru; hapus pesan judul lama biar chat bersih."""
        state = self.states.get(guild.id)
        if state is None or track is None:
            return
        old = getattr(state, 'now_message', None)
        if old is not None:
            try:
                await old.delete()
            except Exception:
                pass
            state.now_message = None
        panel_msg = getattr(state, 'message', None)
        if panel_msg is None:
            return
        try:
            channel = getattr(panel_msg, 'channel', None)
            if channel is None:
                return
            state.now_message = await channel.send(
                f'Now playing: **{discord.utils.escape_markdown(track.title)}**')
        except discord.HTTPException:
            state.now_message = None
        except Exception:
            log.debug('Gagal kirim now-playing', exc_info=True)

    def _announce(self, guild: discord.Guild, track) -> None:
        """Jadwalkan pengumuman now-playing dengan referensi task yang disimpan.

        create_task tanpa referensi bisa di-GC sebelum selesai, dan exception di
        dalamnya hilang tanpa jejak.
        """
        state = self.states.get(guild.id)
        if state is None or track is None:
            return
        previous = state.announce_task
        if previous is not None and previous is not asyncio.current_task() and not previous.done():
            previous.cancel()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(self._announce_now_playing(guild, track))
        state.announce_task = task

        def _done(fut):
            if fut.cancelled():
                return
            try:
                exc = fut.exception()
            except Exception:
                return
            if exc:
                log.error('Gagal mengumumkan now-playing: %s', exc)

        task.add_done_callback(_done)

    def _schedule_idle(self, guild: discord.Guild, generation: int) -> None:
        state = self.states.get(guild.id)
        if not state:
            return
        if state.idle_task and not state.idle_task.done():
            state.idle_task.cancel()
        try:
            state.idle_task = asyncio.get_running_loop().create_task(self.idle_disconnect(guild, generation))
        except RuntimeError:
            pass

    async def finished(self, guild: discord.Guild, generation: int):
        state = self.states.get(guild.id)
        if not state:
            return
        # finished() tidak null-kan current di sini (C1); advance() yang commit history.
        await self.advance(guild) if generation == state.generation else None

    async def idle_disconnect(self, guild: discord.Guild, generation: int):
        try:
            await asyncio.sleep(180)
            state = self.states.get(guild.id)
            if not state:
                return
            should_quit = False
            async with state.lock:
                if state.generation == generation and state.current is None and not state.queue and guild.voice_client:
                    should_quit = True
            if should_quit:
                log.info('Idle 3 menit tanpa antrian di guild %s, bot keluar.', guild.name)
                await self.quit_voice(guild, clear_queue=False)
        except asyncio.CancelledError:
            pass

    async def on_voice_state_update(self, member, before, after):
        guild = getattr(member, 'guild', None)
        if not guild:
            return

        state = self.states.setdefault(guild.id, QueueState())
        bot_user_id = getattr(getattr(self, 'user', None), 'id', None)
        is_bot = (bot_user_id is not None and member.id == bot_user_id)

        # L7: optimisasi aman (bukan debounce). Bila member BUKAN bot dan
        # channel-nya tidak berubah, event ini hanya toggle mute/deaf/stream —
        # jumlah pendengar manusia di channel bot IDENTIK, sehingga keputusan
        # AFK/auto-pause/auto-resume pasti sama. Lewati pekerjaan mahal
        # (dump_runtime_state = tulis file tiap event, refresh UI) agar eMMC STB
        # tidak aus oleh event mute/deaf yang berisik. Event join/leave/pindah
        # selalu punya channel berbeda, jadi tidak pernah dilewati.
        if not is_bot and before.channel is not None and before.channel == after.channel:
            return

        dump_runtime_state(self)

        # 1. Edge case: bot itu sendiri dikeluarkan atau terputus dari voice
        if is_bot and before.channel is not None and after.channel is None:
            if state.afk_task and not state.afk_task.done():
                state.afk_task.cancel()
            state.afk_task = state.empty_task = None
            state.afk_paused = False

            await asyncio.sleep(2)
            vc = getattr(guild, 'voice_client', None)
            if not vc or not getattr(vc, 'is_connected', lambda: False)() or not getattr(vc, 'channel', None):
                log.info('Bot dikeluarkan atau terputus dari voice di guild %s (%s)', getattr(guild, 'name', 'unknown'), guild.id)
                await self.quit_voice(guild, clear_queue=False)
            return

        # 2. Cek apakah bot terhubung ke voice channel di guild ini
        vc = getattr(guild, 'voice_client', None)
        if not vc or not getattr(vc, 'is_connected', lambda: False)() or not getattr(vc, 'channel', None):
            if state.afk_task and not state.afk_task.done():
                state.afk_task.cancel()
            state.afk_task = state.empty_task = None
            state.afk_paused = False
            return

        bot_channel = vc.channel

        # 3. Hitung jumlah pendengar manusia (bukan bot) di channel bot
        human_listeners = [m for m in getattr(bot_channel, 'members', []) if not getattr(m, 'bot', False)]
        num_humans = len(human_listeners)

        if num_humans == 0:
            # Tidak ada pendengar manusia di room tempat bot berada
            # Auto-pause jika sedang memutar audio
            if getattr(vc, 'is_playing', lambda: False)():
                try:
                    vc.pause()
                    state.afk_paused = True
                except Exception:
                    pass
                await self.refresh(state)
                dump_runtime_state(self)

            # Mulai timer AFK jika belum berjalan
            async with state.lock:
                if state.afk_task and not state.afk_task.done():
                    return
                timeout = get_afk_timeout()
                try:
                    state.afk_task = state.empty_task = asyncio.get_running_loop().create_task(
                        self._afk_disconnect(guild, state.generation, timeout)
                    )
                except RuntimeError:
                    pass
        else:
            # Ada pendengar manusia di channel bot
            # Batalkan timer AFK
            if state.afk_task and not state.afk_task.done():
                state.afk_task.cancel()
            state.afk_task = state.empty_task = None

            # Lanjutkan pemutaran jika sebelumnya di-pause oleh AFK Guard
            if state.afk_paused:
                if getattr(vc, 'is_paused', lambda: False)():
                    try:
                        vc.resume()
                    except Exception:
                        pass
                state.afk_paused = False
                await self.refresh(state)
                dump_runtime_state(self)

    async def _afk_disconnect(self, guild: discord.Guild, generation: int, timeout: float | None = None):
        if timeout is None:
            timeout = get_afk_timeout()
        try:
            await asyncio.sleep(timeout)
            vc = getattr(guild, 'voice_client', None)
            if vc and getattr(vc, 'channel', None):
                humans = [m for m in getattr(vc.channel, 'members', []) if not getattr(m, 'bot', False)]
                if not humans:
                    state = self.states.get(guild.id)
                    if state and generation != state.generation and generation != 0:
                        return
                    dur_str = "3 menit" if timeout == 180 else (f"{int(timeout // 60)} menit" if timeout >= 60 else f"{int(timeout)} detik")
                    log.info("AFK timeout: room kosong selama %s, bot keluar dari voice channel", dur_str)
                    await self.quit_voice(guild, clear_queue=False)
        except asyncio.CancelledError:
            pass
        finally:
            state = self.states.get(guild.id)
            if state:
                try:
                    if state.afk_task and state.afk_task.done():
                        state.afk_task = state.empty_task = None
                    elif state.afk_task is asyncio.current_task():
                        state.afk_task = state.empty_task = None
                except Exception:
                    pass

    async def _empty_disconnect(self, guild: discord.Guild, generation: int):
        await self._afk_disconnect(guild, generation)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        raise SystemExit('DISCORD_TOKEN belum disetel.')
    MusicBot().run(token)
