"""Minimal Discord music player: slash summon, buttons, modal, streaming voice."""
import asyncio
import json
import logging
import os
import shutil
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
    'js_runtimes': _JS_RUNTIME,
}

STREAM_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'skip_download': True,
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
    data = await asyncio.to_thread(_fetch_metadata, target)
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


def source_for(data: dict, volume: float = 1.0) -> discord.PCMVolumeTransformer:
    pcm = discord.FFmpegPCMAudio(
        data['url'],
        before_options='-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        options='-vn'
    )
    return discord.PCMVolumeTransformer(pcm, volume=volume)


def same_voice(interaction: discord.Interaction) -> bool:
    guild = interaction.guild
    voice = getattr(interaction.user, 'voice', None)
    return bool(guild and voice and voice.channel and guild.voice_client and voice.channel.id == guild.voice_client.channel.id)


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
        if not vc:
            try:
                vc = await voice.channel.connect(timeout=20, self_deaf=True)
            except Exception as exc:
                return await interaction.followup.send(f'Gagal masuk voice: {exc}', ephemeral=True)
        elif vc.channel.id != voice.channel.id:
            return await interaction.followup.send('Bot sedang dipakai di voice channel lain.', ephemeral=True)

        try:
            tracks = await extract_tracks(str(self.query), interaction.user.mention)
            state = self.bot.states.setdefault(guild.id, QueueState())
            async with state.lock:
                state.queue.extend(tracks)
                if not vc.is_playing() and not vc.is_paused() and not state.current:
                    await self.bot.advance(guild)
            if len(tracks) == 1:
                msg = f'Ditambahkan: **{discord.utils.escape_markdown(tracks[0].title)}**'
            else:
                msg = f'Ditambahkan {len(tracks)} lagu dari playlist. Lagu pertama: **{discord.utils.escape_markdown(tracks[0].title)}**'
            await interaction.followup.send(msg, ephemeral=True)
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
            return
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
            return
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

    async def guard(self, interaction: discord.Interaction) -> bool:
        voice = getattr(interaction.user, 'voice', None)
        if not interaction.guild or not voice or not voice.channel:
            if not interaction.response.is_done():
                await interaction.response.send_message('Masuk ke voice channel dulu.', ephemeral=True)
            else:
                await interaction.followup.send('Masuk ke voice channel dulu.', ephemeral=True)
            return False

        vc = interaction.guild.voice_client
        if not vc:
            try:
                await voice.channel.connect(timeout=20, self_deaf=True)
            except Exception as exc:
                log.exception('Gagal connect voice dari panel: %s', exc)
                if not interaction.response.is_done():
                    await interaction.response.send_message('Gagal masuk voice channel bot. Cek izin bot.', ephemeral=True)
                else:
                    await interaction.followup.send('Gagal masuk voice channel bot. Cek izin bot.', ephemeral=True)
                return False
        elif vc.channel.id != voice.channel.id:
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
        if not await self.guard(interaction):
            return
        state = self.bot.states[interaction.guild.id]
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
            vc = interaction.guild.voice_client
            if vc and (vc.is_playing() or vc.is_paused()):
                vc.stop()
            else:
                await self.bot.advance(interaction.guild)
        await interaction.followup.send('Memutar lagu sebelumnya.', ephemeral=True)

    @discord.ui.button(label='Pause', emoji='⏸️', style=discord.ButtonStyle.secondary, custom_id='music:pause', row=0)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.guard(interaction):
            return
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.followup.send('Bot tidak ada di voice channel.', ephemeral=True)
        if vc.is_playing():
            vc.pause()
            text = 'Dijeda.'
        elif vc.is_paused():
            vc.resume()
            text = 'Dilanjutkan.'
        else:
            text = 'Tidak ada lagu aktif.'
        await interaction.followup.send(text, ephemeral=True)
        await self.bot.refresh(self.bot.states[interaction.guild.id])

    @discord.ui.button(label='Skip', emoji='⏭️', style=discord.ButtonStyle.secondary, custom_id='music:skip', row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.guard(interaction):
            return
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            text = 'Dilewati.'
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
            await self.bot.quit_voice(interaction.guild)
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
        if not discord.opus.is_loaded():
            discord.opus._load_default()
        intents = discord.Intents.default()
        intents.voice_states = True
        super().__init__(intents=intents)
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

    async def on_interaction(self, interaction: discord.Interaction):
        name = None
        custom_id = None
        if hasattr(interaction, 'data') and isinstance(interaction.data, dict):
            name = interaction.data.get('name')
            custom_id = interaction.data.get('custom_id')
        log.info('Interaction: type=%s name=%s custom_id=%s user=%s guild=%s',
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

    async def setup_hook(self):
        self.add_view(MusicPanel(self))
        try:
            asyncio.get_running_loop().create_task(self._state_exporter_loop())
        except RuntimeError:
            pass
        guild_id = os.getenv('DISCORD_GUILD_ID')
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            try:
                await self.tree.sync(guild=guild)
                log.info('Slash command /musik tersinkron ke guild %s', guild_id)
            except discord.Forbidden as exc:
                log.error('Gagal sync command ke guild %s: %s (Missing Access). '
                          'Pastikan bot diundang dengan scope "applications.commands" dan ID adalah Server ID.',
                          guild_id, exc)
            except Exception:
                log.exception('Gagal sync slash command ke guild %s', guild_id)
        else:
            try:
                await self.tree.sync()
                log.info('Slash command /musik tersinkron global')
            except discord.Forbidden as exc:
                log.error('Gagal sync command global: %s', exc)
            except Exception:
                log.exception('Gagal sync slash command global')

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

    async def on_guild_join(self, guild: discord.Guild):
        dump_runtime_state(self)
        try:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info('Auto sync commands ke server baru: %s (%s)', guild.name, guild.id)
        except Exception as e:
            log.error('Gagal sync command ke server baru %s: %s', guild.id, e)

    async def on_guild_remove(self, guild: discord.Guild):
        dump_runtime_state(self)

    async def close(self):
        try:
            dump_runtime_state_offline()
        except Exception:
            pass
        await super().close()

    async def cmd_play(self, interaction: discord.Interaction, lagu: str):
        voice = getattr(interaction.user, 'voice', None)
        if not interaction.guild or not voice or not voice.channel:
            return await interaction.response.send_message('Masuk voice channel dulu.', ephemeral=True)
        await interaction.response.defer(thinking=True)
        vc = interaction.guild.voice_client
        if vc and vc.channel.id != voice.channel.id:
            return await interaction.followup.send('Bot sedang dipakai di voice channel lain.', ephemeral=True)
        if not vc:
            try:
                vc = await voice.channel.connect(timeout=20, self_deaf=True)
            except Exception:
                log.exception('Gagal masuk voice')
                return await interaction.followup.send('Gagal masuk voice. Cek izin Connect/Speak.', ephemeral=True)
        try:
            tracks = await extract_tracks(lagu, interaction.user.mention)
            state = self.states.setdefault(interaction.guild.id, QueueState())
            async with state.lock:
                state.queue.extend(tracks)
                if not vc.is_playing() and not vc.is_paused() and not state.current:
                    await self.advance(interaction.guild)
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
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
        vc = interaction.guild.voice_client
        if not vc or (not vc.is_playing() and not vc.is_paused()):
            return await interaction.followup.send('Tidak ada lagu yang sedang diputar.', ephemeral=True)
        vc.stop()
        await interaction.followup.send('Lagu dilewati.', ephemeral=True)

    async def cmd_back(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
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
            vc = interaction.guild.voice_client
            if vc and (vc.is_playing() or vc.is_paused()):
                vc.stop()
            else:
                await self.advance(interaction.guild)
        await interaction.followup.send('Memutar lagu sebelumnya.', ephemeral=True)

    async def cmd_shuffle(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
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
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
        state = self.states.setdefault(interaction.guild.id, QueueState())
        if mode and mode.lower() in {'off', 'track', 'queue'}:
            state.loop_mode = mode.lower()
        else:
            cycle = {'off': 'track', 'track': 'queue', 'queue': 'off'}
            state.loop_mode = cycle.get(state.loop_mode, 'off')
        mode_text = {'track': 'Ulang Lagu Ini (Track)', 'queue': 'Ulang Seluruh Antrian (Queue)', 'off': 'Mati (Off)'}
        await interaction.followup.send(f'Mode Loop: **{mode_text[state.loop_mode]}**', ephemeral=True)
        await self.refresh(state)

    async def cmd_autoplay(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
        state = self.states.setdefault(interaction.guild.id, QueueState())
        state.autoplay = not state.autoplay
        status = 'Aktif' if state.autoplay else 'Nonaktif'
        await interaction.followup.send(f'AutoPlay sekarang: **{status}**', ephemeral=True)
        await self.refresh(state)

    async def quit_voice(self, guild: discord.Guild) -> None:
        state = self.states.get(guild.id)
        if state:
            async with state.lock:
                state.generation += 1
                state.queue.clear()
                state.history.clear()
                state.current = None
                if state.idle_task:
                    state.idle_task.cancel()
                    state.idle_task = None
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
        try:
            await asyncio.to_thread(clear_cache)
        except Exception as exc:
            log.warning('Gagal membersihkan cache: %s', exc)
        if state:
            await self.refresh(state)
        dump_runtime_state(self)

    async def cmd_stop(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
        await self.quit_voice(interaction.guild)
        await interaction.followup.send('Musik dihentikan, antrian direset, dan bot keluar voice.', ephemeral=True)

    async def cmd_quit(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
        await self.quit_voice(interaction.guild)
        await interaction.followup.send('Bot keluar dari voice channel, antrian direset, dan cache dibersihkan.', ephemeral=True)

    async def cmd_queue(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
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
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
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
            await interaction.followup.send('Tidak ada lagu yang aktif.', ephemeral=True)
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
            return
        state = self.states.setdefault(interaction.guild.id, QueueState())
        state.volume = round(max(0.0, min(target_vol, 2.0)), 2)
        vc = interaction.guild.voice_client
        if vc and getattr(vc, 'source', None):
            source = vc.source
            if isinstance(source, discord.PCMVolumeTransformer):
                source.volume = state.volume
        pct = int(round(state.volume * 100))
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
        if vc and vc.channel.id != voice.channel.id:
            return await interaction.followup.send('Bot sedang dipakai di voice channel lain.', ephemeral=True)
        if not vc:
            try:
                vc = await voice.channel.connect(timeout=20, self_deaf=True)
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
        except Exception as exc:
            log.exception('Gagal mengirim panel musik: %s', exc)
            await interaction.followup.send(f'Gagal memunculkan panel: {exc}', ephemeral=True)

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
        if state.message:
            try:
                await state.message.edit(embed=self.embed(state), view=MusicPanel(self))
            except discord.HTTPException:
                state.message = None

    async def advance(self, guild: discord.Guild):
        """Call while state.lock is held; after callback marshals back to event loop."""
        state = self.states[guild.id]
        vc = guild.voice_client
        if not vc or not vc.is_connected():
            state.current = None
            return
        if state.idle_task:
            state.idle_task.cancel()
            state.idle_task = None

        while True:
            next_track = None
            if state.loop_mode == 'track' and state.current:
                next_track = state.current
            elif state.queue:
                if state.current:
                    state.history.append(state.current)
                    if len(state.history) > 20:
                        state.history.popleft()
                    if state.loop_mode == 'queue':
                        state.queue.append(state.current)
                next_track = state.queue.popleft()
            elif state.autoplay and state.current:
                try:
                    query = f"ytsearch1:{state.current.title} related song"
                    auto_tracks = await extract_tracks(query, "AutoPlay")
                    if auto_tracks:
                        next_track = auto_tracks[0]
                        log.info("AutoPlay selected: %s", next_track.title)
                except Exception as exc:
                    log.warning("AutoPlay failed: %s", exc)

            if not next_track and state.current:
                state.history.append(state.current)
                if len(state.history) > 20:
                    state.history.popleft()

            if not next_track:
                break

            state.current = next_track
            try:
                data = await asyncio.to_thread(extract, next_track.url)
                bitrate_kbps = getattr(vc.channel, 'bitrate', 96000) // 1000
                bitrate_kbps = min(max(bitrate_kbps, 64), 160)
                source = source_for(data, volume=state.volume)
                generation = state.generation

                def after(error):
                    if error:
                        log.error('Audio playback error: %s', error)
                    future = asyncio.run_coroutine_threadsafe(self.finished(guild, generation), self.loop)
                    future.add_done_callback(lambda f: log.error('Queue advance failed: %s', f.exception()) if f.exception() else None)

                vc.play(source, after=after, application='audio', bitrate=bitrate_kbps, signal_type='music')
                await self.refresh(state)
                return
            except Exception:
                log.exception('Tidak bisa memutar: %s', next_track.title)

        state.current = None
        await self.refresh(state)
        state.idle_task = asyncio.create_task(self.idle_disconnect(guild, state.generation))

    async def finished(self, guild: discord.Guild, generation: int):
        state = self.states.get(guild.id)
        if not state:
            return
        async with state.lock:
            if generation == state.generation:
                state.current = None
                await self.advance(guild)

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
                await self.quit_voice(guild)
        except asyncio.CancelledError:
            pass

    async def on_voice_state_update(self, member, before, after):
        dump_runtime_state(self)
        # 1. Jika bot itu sendiri dikeluarkan atau terputus dari voice
        if member.id == getattr(self.user, 'id', None):
            if before.channel is not None and after.channel is None:
                log.info('Bot dikeluarkan atau terputus dari voice di guild %s (%s)', member.guild.name, member.guild.id)
                await self.quit_voice(member.guild)
                return

        # 2. Jika seluruh user keluar dari channel (hanya tersisa bot)
        vc = member.guild.voice_client
        if not vc or not vc.channel or any(not m.bot for m in vc.channel.members):
            return
        await asyncio.sleep(15)
        vc = member.guild.voice_client
        if vc and vc.channel and not any(not m.bot for m in vc.channel.members):
            log.info('Voice channel kosong di guild %s, bot keluar.', member.guild.name)
            await self.quit_voice(member.guild)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        raise SystemExit('DISCORD_TOKEN belum disetel.')
    MusicBot().run(token)
