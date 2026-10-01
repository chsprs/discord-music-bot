"""Minimal Discord music player: slash summon, buttons, modal, streaming voice."""
import asyncio
import json
import logging
import os
import queue
import shutil
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import urlparse

import discord
import yt_dlp

log = logging.getLogger(__name__)


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


@dataclass
class QueueState:
    queue: deque[Track] = field(default_factory=deque)
    history: deque[Track] = field(default_factory=deque)
    current: Track | None = None
    volume: float = 1.0
    loop_mode: str = 'off'  # 'off', 'track', 'queue'
    autoplay: bool = False
    generation: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    message: discord.Message | None = None
    idle_task: asyncio.Task | None = None
    empty_task: asyncio.Task | None = None
    refresh_task: asyncio.Task | None = None


# Batas konkurensi ekstraksi yt-dlp agar STB RAM kecil tidak OOM (C4/M3).
EXTRACT_SEM = asyncio.Semaphore(2)
MAX_QUEUE = 500
MAX_ERROR_STREAK = 50  # ~10 detik stall (50 x 20ms frame) lalu EOF agar after fire (C6)
MAX_TRACK_RETRIES = 3


def checked_query(query: str) -> str:
    query = query.strip()
    if not query or len(query) > 500:
        raise ValueError('Judul atau URL lagu harus 1–500 karakter.')
    if query.startswith(('http://', 'https://')):
        parsed = urlparse(query)
        hostname = (parsed.hostname or '').lower()
        if hostname not in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be'}:
            raise ValueError('Hanya tautan HTTPS YouTube/YouTube Music yang didukung.')
        if query.startswith('http://'):
            query = 'https://' + query[7:]
        return query
    return f'ytsearch1:{query}'


def _detect_js_runtime() -> dict:
    candidates = [
        ('node', '/usr/local/bin/node'),
        ('node', shutil.which('node')),
        ('node', '/usr/bin/node'),
        ('deno', shutil.which('deno')),
        ('bun', shutil.which('bun')),
    ]
    for name, path in candidates:
        if path and os.path.exists(path):
            return {name: {'path': path}}
    return {}


_JS_RUNTIME = _detect_js_runtime()

METADATA_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'extract_flat': 'in_playlist',
    'ignoreerrors': True,
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
            'total_guilds': len(guilds_data),
            'active_voice_count': active_voice_count,
            'total_listeners': total_listeners,
            'guilds': guilds_data,
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = path + '.tmp'
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


def clear_cache() -> None:
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            ydl.cache.remove()
    except Exception as exc:
        log.debug('Gagal menghapus cache yt-dlp: %s', exc)

    cache_dirs = [
        os.path.join(os.environ.get('XDG_CACHE_HOME', '/run/discord-music'), 'yt-dlp'),
        os.path.expanduser('~/.cache/yt-dlp'),
        '/tmp/yt-dlp',
    ]
    for c_dir in cache_dirs:
        if os.path.isdir(c_dir):
            try:
                shutil.rmtree(c_dir, ignore_errors=True)
            except Exception:
                pass



def extract_stream(url: str) -> dict:
    with yt_dlp.YoutubeDL(STREAM_OPTIONS) as ydl:
        data = ydl.extract_info(url, download=False)
    if data and 'entries' in data:
        data = next((entry for entry in data['entries'] if entry), None)
    if not data or not data.get('url'):
        raise ValueError('Stream audio tidak tersedia.')
    return data


extract = extract_stream


def _fetch_metadata(target: str) -> dict:
    with yt_dlp.YoutubeDL(METADATA_OPTIONS) as ydl:
        return ydl.extract_info(target, download=False)


async def extract_tracks(query: str, requester: str) -> list[Track]:
    target = checked_query(query)
    async with EXTRACT_SEM:
        data = await asyncio.wait_for(asyncio.to_thread(_fetch_metadata, target), timeout=60)
    if not data:
        raise ValueError('Lagu atau playlist tidak ditemukan.')

    tracks: list[Track] = []
    if 'entries' in data:
        for entry in data.get('entries') or []:
            if not entry:
                continue
            title = entry.get('title') or 'Tanpa judul'
            url = entry.get('url') or entry.get('webpage_url')
            if not url or not url.startswith('http'):
                vid_id = entry.get('id') or url
                url = f'https://www.youtube.com/watch?v={vid_id}'
            dur = entry.get('duration') or 0
            author = entry.get('uploader') or entry.get('channel') or entry.get('artist') or 'Unknown'
            tracks.append(Track(title, url, requester, duration=dur, duration_str=format_duration(dur), author=author))
            if len(tracks) >= 100:
                break
    else:
        title = data.get('title') or 'Tanpa judul'
        url = data.get('webpage_url') or data.get('url') or target
        dur = data.get('duration') or 0
        author = data.get('uploader') or data.get('channel') or data.get('artist') or 'Unknown'
        tracks.append(Track(title, url, requester, duration=dur, duration_str=format_duration(dur), author=author))

    if not tracks:
        raise ValueError('Lagu tidak ditemukan atau stream tidak tersedia.')
    return tracks


async def extract_track(query: str, requester: str) -> Track:
    tracks = await extract_tracks(query, requester)
    return tracks[0]


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
        if self.stop_event.is_set():
            return b''
        try:
            data = self.queue.get(timeout=0.3)
            if data is None:
                return b''
            self._misses = 0
            return data
        except queue.Empty:
            # Stall ffmpeg: jangan samarkan jadi hening selamanya (C6).
            self._misses += 1
            if self._misses >= MAX_ERROR_STREAK:
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
                    source_error = getattr(self.source, '_current_error', None)
                    if source_error:
                        self._current_error = source_error
                self.stop()
                break

            if not client.is_connected():
                connected = client.wait_until_connected(client.timeout)
                if self._end.is_set() or not connected:
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


def source_for(data: dict, volume: float = 1.0) -> discord.PCMVolumeTransformer:
    pcm = discord.FFmpegPCMAudio(
        data['url'],
        before_options='-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_at_eof 1 -reconnect_on_network_error 1 -reconnect_on_http_error 4xx,5xx -reconnect_delay_max 5',
        options='-vn'
    )
    buffered = BufferedAudioSource(pcm)
    return discord.PCMVolumeTransformer(buffered, volume=volume)


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
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
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
        state.message = interaction.message
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
        async with state.lock:
            if not state.history and not state.current:
                return await interaction.followup.send('Tidak ada riwayat lagu sebelumnya.', ephemeral=True)
            if state.history:
                prev = state.history.pop()
                if state.current:
                    state.queue.appendleft(state.current)
                state.queue.appendleft(prev)
                state.current = None
            elif state.current:
                state.queue.appendleft(state.current)
                state.current = None
        await self.bot._stop_player(interaction.guild)
        if not interaction.guild.voice_client:
            await self.bot.advance(interaction.guild)
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
        if vc and (vc.is_playing() or vc.is_paused()):
            await self.bot._stop_player(interaction.guild)
            text = 'Dilewati.'
        elif state.queue:
            await self.bot.advance(interaction.guild)
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
                return await interaction.followup.send('Antrian kurang dari 2 lagu untuk diacak.', ephemeral=True)
            import random
            items = list(state.queue)
            random.shuffle(items)
            state.queue = deque(items)
        await interaction.followup.send(f'Antrian berhasil diacak ({len(state.queue)} lagu).', ephemeral=True)
        await self.bot.refresh(state)

    @discord.ui.button(label='Loop', emoji='🔁', style=discord.ButtonStyle.secondary, custom_id='music:loop', row=1)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.guard(interaction):
            return
        state = self.bot.states[interaction.guild.id]
        cycle = {'off': 'track', 'track': 'queue', 'queue': 'off'}
        state.loop_mode = cycle.get(state.loop_mode, 'off')
        mode_text = {'track': 'Ulang Lagu Ini (Track)', 'queue': 'Ulang Seluruh Antrian (Queue)', 'off': 'Mati (Off)'}
        await interaction.followup.send(f'Mode Loop: **{mode_text[state.loop_mode]}**', ephemeral=True)
        await self.bot.refresh(state)

    @discord.ui.button(label='Stop', emoji='⏹️', style=discord.ButtonStyle.secondary, custom_id='music:stop', row=1)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
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
        state.autoplay = not state.autoplay
        status = 'Aktif' if state.autoplay else 'Nonaktif'
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
                    discord.opus._load_default()
        except Exception as exc:
            log.critical('libopus tidak tersedia, voice tidak bisa jalan: %s', exc)
            raise SystemExit('libopus tidak ditemukan. Install libopus0.') from exc
        intents = discord.Intents.default()
        intents.voice_states = True
        super().__init__(intents=intents)
        self._exporter_task: asyncio.Task | None = None
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

    async def _stop_player(self, guild: discord.Guild) -> None:
        """Hentikan player + bump generation agar after() basi tidak fire (C7)."""
        state = self.states.get(guild.id)
        if state:
            async with state.lock:
                state.generation += 1
        vc = guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            try:
                vc.stop()
            except Exception:
                pass

    async def _enqueue_tracks(self, guild: discord.Guild, tracks: list[Track]) -> bool:
        """Tambah track dengan cap total; return False bila penuh."""
        state = self.states.setdefault(guild.id, QueueState())
        async with state.lock:
            if len(state.queue) + len(tracks) > MAX_QUEUE:
                return False
            state.queue.extend(tracks)
            need_advance = not state.current
        vc = guild.voice_client
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
        self.add_view(MusicPanel(self))
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
                await asyncio.sleep(5)
        except (asyncio.CancelledError, RuntimeError):
            pass

    async def on_ready(self):
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

    async def on_guild_join(self, guild: discord.Guild):
        dump_runtime_state(self)
        await self._sync_guild(guild)

    async def on_guild_remove(self, guild: discord.Guild):
        dump_runtime_state(self)

    async def _delete_all_panels(self) -> None:
        """Hapus semua pesan panel agar chat bersih saat bot mati.

        Dipanggil dari close() selagi koneksi HTTP masih hidup —
        super().close() menutup http/ws setelahnya.
        """
        targets = [(gid, st.message) for gid, st in list(self.states.items())
                   if getattr(st, 'message', None) is not None]
        if not targets:
            return

        async def _del(msg) -> None:
            try:
                await msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                log.debug('Gagal hapus panel saat shutdown: %s', exc)
            except Exception:
                log.debug('Gagal hapus panel saat shutdown', exc_info=True)

        try:
            await asyncio.wait_for(
                asyncio.gather(*(_del(m) for _, m in targets), return_exceptions=True),
                timeout=15,
            )
        except (asyncio.TimeoutError, TimeoutError):
            log.warning('Timeout hapus panel saat shutdown')
        for gid, _ in targets:
            state = self.states.get(gid)
            if state is not None:
                state.message = None

    async def close(self):
        try:
            dump_runtime_state_offline()
        except Exception:
            pass
        for state in list(self.states.values()):
            for task in (state.idle_task, state.empty_task, state.refresh_task):
                if task and not task.done():
                    task.cancel()
            state.idle_task = state.empty_task = state.refresh_task = None
        try:
            await self._delete_all_panels()
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
                if state.message is None or state.message.channel.id != channel.id:
                    if state.message:
                        try:
                            await state.message.delete()
                        except Exception:
                            pass
                    try:
                        state.message = await channel.send(embed=self.embed(state), view=MusicPanel(self))
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
        await self._stop_player(interaction.guild)
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
        if not interaction.guild.voice_client:
            await self.advance(interaction.guild)
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
            state.queue = deque(items)
        await interaction.followup.send(f'Antrian berhasil diacak ({len(state.queue)} lagu).', ephemeral=True)
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
        status = 'Aktif' if autoplay_on else 'Nonaktif'
        await interaction.followup.send(f'AutoPlay sekarang: **{status}**', ephemeral=True)
        await self.refresh(state)

    async def quit_voice(self, guild: discord.Guild, clear_queue: bool = False) -> None:
        state = self.states.get(guild.id)
        if state:
            async with state.lock:
                state.generation += 1
                if clear_queue:
                    state.queue.clear()
                    state.history.clear()
                state.current = None
                for task in (state.idle_task, state.empty_task):
                    if task and not task.done():
                        task.cancel()
                state.idle_task = state.empty_task = None
        vc = getattr(guild, 'voice_client', None)
        if vc:
            try:
                if getattr(vc, 'is_playing', lambda: False)() or getattr(vc, 'is_paused', lambda: False)():
                    vc.stop()
            except Exception:
                pass
            try:
                await vc.disconnect(force=True)
            except Exception:
                pass
        if state:
            await self.refresh(state)
        dump_runtime_state(self)

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
        if vc.is_playing():
            vc.pause()
            await interaction.followup.send('Pemutaran dijeda.', ephemeral=True)
        elif vc.is_paused():
            vc.resume()
            await interaction.followup.send('Pemutaran dilanjutkan.', ephemeral=True)
        else:
            state = self.states.get(interaction.guild.id)
            if state and state.queue:
                await self.advance(interaction.guild)
                await interaction.followup.send('Melanjutkan pemutaran antrian lagu.', ephemeral=True)
            else:
                await interaction.followup.send('Tidak ada lagu yang aktif atau antrian kosong.', ephemeral=True)
        state = self.states.get(interaction.guild.id)
        if state:
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
            try:
                await state.message.delete()
            except Exception:
                pass
            state.message = None

        channel = interaction.channel
        if channel is None and interaction.channel_id and interaction.guild:
            channel = interaction.guild.get_channel(interaction.channel_id)

        if not channel or not hasattr(channel, 'send'):
            return await interaction.followup.send('Tidak dapat menemukan text channel untuk menampilkan panel.', ephemeral=True)

        try:
            state.message = await channel.send(embed=self.embed(state), view=MusicPanel(self))
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
            if state.message:
                try:
                    async with state.lock:
                        embed = self.embed(state)
                    await state.message.edit(embed=embed, view=MusicPanel(self))
                except discord.HTTPException:
                    state.message = None
        try:
            state.refresh_task = asyncio.get_running_loop().create_task(_do())
        except RuntimeError:
            pass

    async def advance(self, guild: discord.Guild):
        """Pilih track berikutnya dan putar. Lock hanya untuk mutasi deque (C4)."""
        state = self.states[guild.id]
        vc = guild.voice_client
        if not vc or not vc.is_connected():
            return
        async with state.lock:
            if state.idle_task and not state.idle_task.done():
                state.idle_task.cancel()
            state.idle_task = None
            if vc.is_playing() or vc.is_paused():
                return

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
                elif state.autoplay and state.current:
                    next_track = None  # resolve di luar lock (M9)
                if not next_track and not (state.autoplay and state.current):
                    break

            # --- fase 2: autoplay resolve di luar lock (M9) ---
            if next_track is None and state.autoplay and state.current:
                try:
                    query = f"ytsearch1:{state.current.title} related song"
                    auto_tracks = await extract_tracks(query, "AutoPlay")
                    if auto_tracks:
                        picked = auto_tracks[0]
                        if state.current and picked.url == state.current.url:
                            break
                        next_track = picked
                        log.info("AutoPlay selected: %s", next_track.title)
                except Exception as exc:
                    log.warning("AutoPlay failed: %s", exc)
                    break
                if not next_track:
                    break

            # --- fase 3: extract stream di luar lock (C4) + semaphore/timeout (M3) ---
            try:
                async with EXTRACT_SEM:
                    data = await asyncio.wait_for(asyncio.to_thread(extract, next_track.url), timeout=60)
                if isinstance(data, dict) and data.get('is_live'):
                    log.warning('Live stream dilewati: %s', next_track.title)
                    async with state.lock:
                        if state.queue and state.queue[0] is next_track:
                            state.queue.popleft()
                    consecutive_errors += 1
                    continue
                bitrate_kbps = getattr(getattr(vc, 'channel', None), 'bitrate', 96000) // 1000
                bitrate_kbps = min(max(bitrate_kbps, 64), 160)
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
                    fut = asyncio.run_coroutine_threadsafe(self.finished(guild, _gen), loop)
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

                vc.play(source, after=after, application='audio', bitrate=bitrate_kbps, signal_type='music')
                # --- fase 4: commit sukses di dalam lock (C1/C2/C3) ---
                async with state.lock:
                    if state.loop_mode == 'track' and state.current is next_track:
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
                await self.refresh(state)
                return
            except Exception as exc:
                consecutive_errors += 1
                log.warning('Tidak bisa memutar (%d/3): %s (penyebab: %s)', consecutive_errors, next_track.title, exc)
                async with state.lock:
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
            schedule_idle = state.current is None and not state.queue
            gen = state.generation
        if schedule_idle:
            self._schedule_idle(guild, gen)

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
        dump_runtime_state(self)
        # 1. Jika bot itu sendiri dikeluarkan atau terputus dari voice
        if member.id == getattr(self.user, 'id', None):
            if before.channel is not None and after.channel is None:
                await asyncio.sleep(2)
                vc = member.guild.voice_client
                if not vc or not vc.is_connected() or not vc.channel:
                    log.info('Bot dikeluarkan atau terputus dari voice di guild %s (%s)', member.guild.name, member.guild.id)
                    await self.quit_voice(member.guild, clear_queue=False)
                return

        # 2. Jika seluruh user keluar dari channel (hanya tersisa bot) — single task per guild.
        vc = member.guild.voice_client
        if not vc or not vc.channel or any(not m.bot for m in vc.channel.members):
            return
        state = self.states.get(member.guild.id)
        if state:
            async with state.lock:
                if state.empty_task and not state.empty_task.done():
                    return
                try:
                    state.empty_task = asyncio.get_running_loop().create_task(
                        self._empty_disconnect(member.guild, state.generation))
                except RuntimeError:
                    pass
        else:
            try:
                asyncio.get_running_loop().create_task(
                    self._empty_disconnect(member.guild, 0))
            except RuntimeError:
                pass

    async def _empty_disconnect(self, guild: discord.Guild, generation: int):
        try:
            await asyncio.sleep(30)
            vc = guild.voice_client
            if vc and vc.channel and not any(not m.bot for m in vc.channel.members):
                state = self.states.get(guild.id)
                if state and generation != state.generation and generation != 0:
                    return
                log.info('Voice channel kosong di guild %s, bot keluar.', guild.name)
                await self.quit_voice(guild, clear_queue=False)
        except asyncio.CancelledError:
            pass
        finally:
            state = self.states.get(guild.id)
            if state:
                try:
                    if state.empty_task and state.empty_task.done():
                        state.empty_task = None
                    elif state.empty_task is asyncio.current_task():
                        state.empty_task = None
                except Exception:
                    pass


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        raise SystemExit('DISCORD_TOKEN belum disetel.')
    MusicBot().run(token)
