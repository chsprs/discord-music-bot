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
    generation: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    message: discord.Message | None = None
    idle_task: asyncio.Task | None = None


def checked_query(query: str) -> str:
    query = query.strip()
    if not query or len(query) > 200:
        raise ValueError('Judul lagu harus 1–200 karakter.')
    parsed = urlparse(query)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme != 'https' or parsed.hostname not in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be'}:
            raise ValueError('Hanya tautan HTTPS YouTube/YouTube Music yang didukung.')
        return query
    return f'ytsearch1:{query}'


OPTIONS = {'format': 'bestaudio[acodec=opus]/bestaudio', 'noplaylist': True,
           'quiet': True, 'js_runtimes': {'node': {}}, 'skip_download': True}


def extract(query: str) -> dict:
    with yt_dlp.YoutubeDL(OPTIONS) as ydl:
        data = ydl.extract_info(query, download=False)
    if data and 'entries' in data:
        data = next((entry for entry in data['entries'] if entry), None)
    if not data or not data.get('url'):
        raise ValueError('Lagu tidak ditemukan atau stream tidak tersedia.')
    return data


async def extract_track(query: str, requester: str) -> Track:
    data = await asyncio.to_thread(extract, checked_query(query))
    return Track(data.get('title') or 'Tanpa judul', data.get('webpage_url') or query, requester)


def source_for(data: dict) -> discord.FFmpegOpusAudio:
    codec = 'copy' if data.get('acodec') == 'opus' else 'libopus'
    return discord.FFmpegOpusAudio(data['url'], codec=codec,
        before_options='-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        options='-vn')


def same_voice(interaction: discord.Interaction) -> bool:
    guild = interaction.guild
    voice = getattr(interaction.user, 'voice', None)
    return bool(guild and voice and voice.channel and guild.voice_client and voice.channel.id == guild.voice_client.channel.id)


class SearchModal(discord.ui.Modal, title='Putar lagu'):
    query = discord.ui.TextInput(label='Judul atau URL YouTube Music', max_length=200)

    def __init__(self, bot: 'MusicBot'):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        if not same_voice(interaction):
            return await interaction.response.send_message('Masuk ke voice channel bot dulu.', ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            track = await extract_track(str(self.query), interaction.user.display_name)
            guild = interaction.guild
            state = self.bot.states.setdefault(guild.id, QueueState())
            async with state.lock:
                state.queue.append(track)
                if not guild.voice_client.is_playing() and not guild.voice_client.is_paused() and not state.current:
                    await self.bot.advance(guild)
            await interaction.followup.send(f'Ditambahkan: **{discord.utils.escape_markdown(track.title)}**', ephemeral=True)
        except Exception as exc:
            log.warning('Pencarian gagal: %s', exc)
            await interaction.followup.send('Gagal mencari atau memutar lagu. Coba judul/URL lain.', ephemeral=True)


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

    @discord.ui.button(label='Cari / Tambah', style=discord.ButtonStyle.success, custom_id='music:add')
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.guard(interaction):
            await interaction.response.send_modal(SearchModal(self.bot))

    @discord.ui.button(label='Jeda / Lanjut', style=discord.ButtonStyle.secondary, custom_id='music:pause')
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

    @discord.ui.button(label='Lewati', style=discord.ButtonStyle.primary, custom_id='music:skip')
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

    @discord.ui.button(label='Antrian', style=discord.ButtonStyle.secondary, custom_id='music:queue')
    async def queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        tracks = list(self.bot.states[interaction.guild.id].queue)[:10]
        text = '\n'.join(f'{i}. {discord.utils.escape_markdown(t.title)}' for i, t in enumerate(tracks, 1)) or 'Antrian kosong.'
        await interaction.response.send_message(text[:1900], ephemeral=True)

    @discord.ui.button(label='Stop', style=discord.ButtonStyle.danger, custom_id='music:stop')
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


class MusicBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.states: dict[int, QueueState] = {}
        self.tree.command(name='musik', description='Tampilkan panel musik dan panggil bot')(self.summon)

    async def setup_hook(self):
        self.add_view(MusicPanel(self))
        guild_id = os.getenv('DISCORD_GUILD_ID')
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

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
                await voice.channel.connect(timeout=20)
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
        return discord.Embed(title='Musik', description=f'{text}\nAntrian: {len(state.queue)}', color=0x5865F2)

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
                source = source_for(data)
                generation = state.generation
                def after(error):
                    if error:
                        log.error('Audio playback error: %s', error)
                    future = asyncio.run_coroutine_threadsafe(self.finished(guild, generation), self.loop)
                    future.add_done_callback(lambda f: log.error('Queue advance failed: %s', f.exception()) if f.exception() else None)
                vc.play(source, after=after)
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
