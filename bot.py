"""Minimal Discord music player: slash summon, buttons, modal, streaming voice."""
import asyncio
import logging
import os
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import urlparse

import discord
import yt_dlp

log = logging.getLogger(__name__)


@dataclass
class Track:
    title: str
    url: str  # stable page URL, not an expiring googlevideo URL
    requester: str


@dataclass
class QueueState:
    queue: deque[Track] = field(default_factory=deque)
    current: Track | None = None
    volume: float = 1.0
    generation: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    message: discord.Message | None = None
    idle_task: asyncio.Task | None = None


def checked_query(query: str) -> str:
    query = query.strip()
    if not query or len(query) > 500:
        raise ValueError('Judul atau URL lagu harus 1–500 karakter.')
    parsed = urlparse(query)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme != 'https' or parsed.hostname not in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be'}:
            raise ValueError('Hanya tautan HTTPS YouTube/YouTube Music yang didukung.')
        return query
    return f'ytsearch1:{query}'


_JS_RUNTIME = {'node': {'path': '/usr/local/bin/node'}} if os.path.exists('/usr/local/bin/node') else {}

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
            tracks.append(Track(title, url, requester))
            if len(tracks) >= 100:
                break
    else:
        title = data.get('title') or 'Tanpa judul'
        url = data.get('webpage_url') or data.get('url') or target
        tracks.append(Track(title, url, requester))

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
        if not same_voice(interaction):
            return await interaction.response.send_message('Masuk ke voice channel bot dulu.', ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            tracks = await extract_tracks(str(self.query), interaction.user.display_name)
            guild = interaction.guild
            if not guild or not guild.voice_client:
                return await interaction.followup.send('Bot tidak ada di voice.', ephemeral=True)
            state = self.bot.states.setdefault(guild.id, QueueState())
            async with state.lock:
                state.queue.extend(tracks)
                if not guild.voice_client.is_playing() and not guild.voice_client.is_paused() and not state.current:
                    await self.bot.advance(guild)
            if len(tracks) == 1:
                msg = f'Ditambahkan: **{discord.utils.escape_markdown(tracks[0].title)}**'
            else:
                msg = f'Ditambahkan {len(tracks)} lagu dari playlist. Lagu pertama: **{discord.utils.escape_markdown(tracks[0].title)}**'
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as exc:
            log.warning('Pencarian gagal: %s', exc)
            await interaction.followup.send(f'Gagal memproses lagu: {exc}', ephemeral=True)


class VolumeModal(discord.ui.Modal, title='Atur Volume'):
    level = discord.ui.TextInput(
        label='Tingkat Volume (%)',
        placeholder='Contoh: 80 (antara 0 sampai 200)',
        min_length=1,
        max_length=4
    )

    def __init__(self, bot: 'MusicBot'):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        if not same_voice(interaction):
            return await interaction.response.send_message('Masuk ke voice channel bot dulu.', ephemeral=True)
        try:
            val = int(str(self.level).strip().rstrip('%'))
            if val < 0 or val > 200:
                return await interaction.response.send_message('Volume harus antara 0% sampai 200%.', ephemeral=True)
            await self.bot.change_volume(interaction, val / 100.0)
        except ValueError:
            await interaction.response.send_message('Masukkan angka valid (contoh: 80).', ephemeral=True)


class MusicPanel(discord.ui.View):
    def __init__(self, bot: 'MusicBot'):
        super().__init__(timeout=None)
        self.bot = bot

    async def guard(self, interaction: discord.Interaction) -> bool:
        if not same_voice(interaction):
            await interaction.response.send_message('Masuk ke voice channel bot dulu.', ephemeral=True)
            return False
        state = self.bot.states.setdefault(interaction.guild.id, QueueState())
        state.message = interaction.message
        return True

    @discord.ui.button(label='Cari / Tambah', style=discord.ButtonStyle.success, custom_id='music:add', row=0)
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.guard(interaction):
            await interaction.response.send_modal(SearchModal(self.bot))

    @discord.ui.button(label='Jeda / Lanjut', style=discord.ButtonStyle.secondary, custom_id='music:pause', row=0)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        vc = interaction.guild.voice_client
        if vc.is_playing():
            vc.pause()
            text = 'Dijeda.'
        elif vc.is_paused():
            vc.resume()
            text = 'Dilanjutkan.'
        else:
            text = 'Tidak ada lagu aktif.'
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label='Lewati', style=discord.ButtonStyle.primary, custom_id='music:skip', row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        vc = interaction.guild.voice_client
        if vc.is_playing() or vc.is_paused():
            vc.stop()  # after callback advances exactly once
            text = 'Dilewati.'
        else:
            text = 'Tidak ada lagu aktif.'
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label='Antrian', style=discord.ButtonStyle.secondary, custom_id='music:queue', row=0)
    async def queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        tracks = list(self.bot.states[interaction.guild.id].queue)[:10]
        text = '\n'.join(f'{i}. {discord.utils.escape_markdown(t.title)}' for i, t in enumerate(tracks, 1)) or 'Antrian kosong.'
        await interaction.response.send_message(text[:1900], ephemeral=True)

    @discord.ui.button(label='Stop', style=discord.ButtonStyle.danger, custom_id='music:stop', row=0)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        state = self.bot.states[interaction.guild.id]
        async with state.lock:
            state.generation += 1
            state.queue.clear()
            state.current = None
            if state.idle_task:
                state.idle_task.cancel()
                state.idle_task = None
            vc = interaction.guild.voice_client
            vc.stop()
            await vc.disconnect()
        await self.bot.refresh(state)
        await interaction.followup.send('Berhenti dan keluar voice.', ephemeral=True)

    @discord.ui.button(label='🔉 -10%', style=discord.ButtonStyle.secondary, custom_id='music:voldown', row=1)
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        state = self.bot.states.setdefault(interaction.guild.id, QueueState())
        await self.bot.change_volume(interaction, state.volume - 0.1)

    @discord.ui.button(label='🔊 +10%', style=discord.ButtonStyle.secondary, custom_id='music:volup', row=1)
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        state = self.bot.states.setdefault(interaction.guild.id, QueueState())
        await self.bot.change_volume(interaction, state.volume + 0.1)

    @discord.ui.button(label='Atur Vol', style=discord.ButtonStyle.secondary, custom_id='music:volmodal', row=1)
    async def vol_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.guard(interaction):
            await interaction.response.send_modal(VolumeModal(self.bot))

    @discord.ui.button(label='100%', style=discord.ButtonStyle.secondary, custom_id='music:vol100', row=1)
    async def vol_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        await self.bot.change_volume(interaction, 1.0)


class MusicBot(discord.Client):
    def __init__(self):
        if not discord.opus.is_loaded():
            discord.opus._load_default()
        intents = discord.Intents.default()
        intents.voice_states = True
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.states: dict[int, QueueState] = {}
        self.tree.command(name='musik', description='Tampilkan panel musik interaktif dan panggil bot')(self.summon)
        self.tree.command(name='play', description='Putar lagu atau cari di YouTube')(self.cmd_play)
        self.tree.command(name='skip', description='Lewati lagu yang sedang diputar')(self.cmd_skip)
        self.tree.command(name='stop', description='Hentikan musik dan keluar dari voice')(self.cmd_stop)
        self.tree.command(name='antrian', description='Tampilkan daftar antrian lagu')(self.cmd_queue)
        self.tree.command(name='pause', description='Jeda atau lanjutkan pemutaran')(self.cmd_pause)
        self.tree.command(name='volume', description='Atur tingkat volume lagu (0–200%)')(self.cmd_volume)

    async def setup_hook(self):
        self.add_view(MusicPanel(self))
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

    async def on_ready(self):
        guild_list = [f'{g.name} ({g.id})' for g in self.guilds]
        log.info('Bot login sebagai %s (ID: %s). Terhubung ke %d server: %s',
                 self.user, getattr(self.user, 'id', None), len(self.guilds),
                 ', '.join(guild_list) if guild_list else 'Belum ada server')
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                log.info('Command list tersinkron ke guild: %s (%s)', guild.name, guild.id)
            except Exception as e:
                log.error('Gagal sync command ke guild %s: %s', guild.id, e)

    async def on_guild_join(self, guild: discord.Guild):
        try:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info('Auto sync commands ke server baru: %s (%s)', guild.name, guild.id)
        except Exception as e:
            log.error('Gagal sync command ke server baru %s: %s', guild.id, e)

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
            tracks = await extract_tracks(lagu, interaction.user.display_name)
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
        except Exception as exc:
            log.warning('Pencarian gagal: %s', exc)
            await interaction.followup.send(f'Gagal mencari atau memproses lagu: {exc}', ephemeral=True)

    async def cmd_skip(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        vc = interaction.guild.voice_client
        if not vc or (not vc.is_playing() and not vc.is_paused()):
            return await interaction.response.send_message('Tidak ada lagu yang sedang diputar.', ephemeral=True)
        vc.stop()
        await interaction.response.send_message('Lagu dilewati.')

    async def cmd_stop(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        state = self.states.get(interaction.guild.id)
        vc = interaction.guild.voice_client
        if state:
            async with state.lock:
                state.generation += 1
                state.queue.clear()
                state.current = None
                if state.idle_task:
                    state.idle_task.cancel()
                    state.idle_task = None
        if vc:
            vc.stop()
            await vc.disconnect()
        if state:
            await self.refresh(state)
        await interaction.response.send_message('Musik dihentikan dan bot keluar voice.')

    async def cmd_queue(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        state = self.states.get(interaction.guild.id)
        if not state or not state.queue:
            return await interaction.response.send_message('Antrian lagu kosong.', ephemeral=True)
        tracks = list(state.queue)[:10]
        text = '\n'.join(f'{i}. {discord.utils.escape_markdown(t.title)}' for i, t in enumerate(tracks, 1))
        await interaction.response.send_message(f'**Antrian Lagu:**\n{text}'[:1900], ephemeral=True)

    async def cmd_pause(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message('Bot tidak ada di voice channel.', ephemeral=True)
        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message('Pemutaran dijeda.')
        elif vc.is_paused():
            vc.resume()
            await interaction.response.send_message('Pemutaran dilanjutkan.')
        else:
            await interaction.response.send_message('Tidak ada lagu yang aktif.', ephemeral=True)

    async def cmd_volume(self, interaction: discord.Interaction, tingkat: int):
        voice = getattr(interaction.user, 'voice', None)
        if not interaction.guild or not voice or not voice.channel:
            return await interaction.response.send_message('Masuk voice channel dulu.', ephemeral=True)
        if tingkat < 0 or tingkat > 200:
            return await interaction.response.send_message('Volume harus antara 0% sampai 200%.', ephemeral=True)
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
                await state.message.edit(embed=self.embed(state), view=MusicPanel(self))
                return await interaction.followup.send('Panel musik sudah aktif.', ephemeral=True)
            except discord.HTTPException:
                state.message = None
        state.message = await interaction.channel.send(embed=self.embed(state), view=MusicPanel(self))
        await interaction.followup.send('Panel musik aktif.', ephemeral=True)

    def embed(self, state: QueueState) -> discord.Embed:
        track = state.current
        text = f'**{discord.utils.escape_markdown(track.title)}** · {discord.utils.escape_markdown(track.requester)}' if track else 'Tekan Cari / Tambah untuk memutar lagu.'
        vol_pct = int(round(state.volume * 100))
        return discord.Embed(title='Musik', description=f'{text}\nVolume: **{vol_pct}%** · Antrian: **{len(state.queue)}**', color=0x5865F2)

    async def refresh(self, state: QueueState):
        if state.message:
            try:
                await state.message.edit(embed=self.embed(state))
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
        while state.queue:
            track = state.queue.popleft()
            state.current = track
            try:
                # Refresh signed CDN URL only when track actually starts.
                data = await asyncio.to_thread(extract, track.url)
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
                log.exception('Tidak bisa memutar: %s', track.title)
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
            state = self.states[guild.id]
            async with state.lock:
                if state.generation == generation and state.current is None and not state.queue and guild.voice_client:
                    state.generation += 1
                    await guild.voice_client.disconnect()
        except asyncio.CancelledError:
            pass

    async def on_voice_state_update(self, member, before, after):
        vc = member.guild.voice_client
        if not vc or not vc.channel or any(not m.bot for m in vc.channel.members):
            return
        await asyncio.sleep(15)
        vc = member.guild.voice_client
        if vc and vc.channel and not any(not m.bot for m in vc.channel.members):
            state = self.states.setdefault(member.guild.id, QueueState())
            async with state.lock:
                state.generation += 1
                state.queue.clear()
                state.current = None
                vc.stop()
                await vc.disconnect()
                await self.refresh(state)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        raise SystemExit('DISCORD_TOKEN belum disetel.')
    MusicBot().run(token)
