"""Prefetch stream lagu berikutnya (tanpa jeda hening antar lagu) & intent gateway minimal."""
import asyncio
import atexit
import os
import shutil
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Isolasi path runtime SEBELUM bot diimpor (lihat test_bot.py).
_ISOLATED_RUNTIME = tempfile.mkdtemp(prefix='discord-music-tests-')
atexit.register(shutil.rmtree, _ISOLATED_RUNTIME, True)
for _key, _name in (('QUEUE_STATE_FILE', 'queue_state.json'), ('BOT_STATE_FILE', 'state.json'),
                    ('PANEL_ENV', 'panel.env'), ('BOT_CONFIG', 'bot.env'),
                    ('UPDATE_LOG', 'last_update.log'), ('BOT_VENV', 'venv')):
    os.environ.setdefault(_key, os.path.join(_ISOLATED_RUNTIME, _name))

import bot as bot_module
from bot import (PREFETCH_LEAD_SECONDS, STREAM_EXPIRY_MARGIN, STREAM_URL_TTL, MusicBot, QueueState, Track,
                 _prefetch_delay, _stream_expiry, _stream_fresh)


def _track(name, duration=0):
    return Track(name, f'https://www.youtube.com/watch?v={(name * 11)[:11]}', 'u', duration=duration)


def _env(gid, playing=False):
    guild = MagicMock()
    guild.id = gid
    guild.name = f'G{gid}'
    flag = {'playing': playing}
    vc = MagicMock()
    vc.is_connected.return_value = True
    vc.is_playing.side_effect = lambda: flag['playing']
    vc.is_paused.return_value = False
    vc.stop.side_effect = lambda: flag.update(playing=False)
    vc.play.side_effect = lambda *a, **k: flag.update(playing=True)
    vc.channel.bitrate = 96000
    vc.channel.members = [MagicMock(bot=False)]
    vc.disconnect = AsyncMock()
    guild.voice_client = vc
    return guild, vc, flag


class _Extractions:
    """Pengganti run_extract yang mencatat URL dan bisa ditahan per URL."""

    def __init__(self):
        self.calls = []
        self.gates: dict[str, asyncio.Event] = {}
        self.fail: set[str] = set()

    async def __call__(self, func, url, timeout=60):
        self.calls.append(url)
        if url in self.gates:
            await self.gates[url].wait()
        if url in self.fail:
            raise ValueError('Lagu tidak tersedia.')
        return {'url': f'https://cdn.example/{url[-11:]}'}


class _PrefetchCase(unittest.TestCase):
    def setUp(self):
        self.bot = MusicBot()
        self.extractions = _Extractions()
        for p in (
            patch('bot.run_extract', new=self.extractions),
            patch('bot.source_for', return_value=MagicMock()),
            patch.object(self.bot, 'refresh', new=AsyncMock()),
            patch.object(self.bot, '_announce', new=MagicMock()),
            patch.object(self.bot, '_schedule_idle', new=MagicMock()),
        ):
            p.start()
            self.addCleanup(p.stop)

    @staticmethod
    async def _settle(state):
        task = state.prefetch_task
        if task is not None:
            await asyncio.wait({task}, timeout=5)


class StreamFreshnessTests(unittest.TestCase):
    def test_expiry_parsed_from_query_and_path(self):
        self.assertEqual(_stream_expiry('https://rr1.googlevideo.com/videoplayback?expire=1792300000&ei=x'), 1792300000.0)
        self.assertEqual(_stream_expiry('https://manifest.googlevideo.com/api/manifest/expire/1792300000/ei/x'), 1792300000.0)
        self.assertIsNone(_stream_expiry('https://cdn.example/audio'))
        self.assertIsNone(_stream_expiry(None))

    def test_fresh_uses_expire_instead_of_fixed_ttl(self):
        now = 1_800_000_000.0
        t = _track('A', duration=240)
        t.stream_url = f'https://rr1.googlevideo.com/videoplayback?expire={int(now + 5 * 3600)}'
        t.stream_ts = now - 2 * 3600  # jauh lebih tua dari TTL lama 30 menit
        self.assertTrue(_stream_fresh(t, now=now))

    def test_not_fresh_when_url_expires_before_song_ends(self):
        now = 1_800_000_000.0
        t = _track('A', duration=600)
        t.stream_url = f'https://rr1.googlevideo.com/videoplayback?expire={int(now + 600 + STREAM_EXPIRY_MARGIN - 1)}'
        t.stream_ts = now
        self.assertFalse(_stream_fresh(t, now=now))

    def test_fallback_ttl_without_expire(self):
        now = 1_800_000_000.0
        t = _track('A')
        t.stream_url = 'https://cdn.example/audio'
        t.stream_ts = now - STREAM_URL_TTL + 5
        self.assertTrue(_stream_fresh(t, now=now))
        t.stream_ts = now - STREAM_URL_TTL - 5
        self.assertFalse(_stream_fresh(t, now=now))
        t.stream_url = None
        self.assertFalse(_stream_fresh(t, now=now))

    def test_prefetch_delay_leads_end_of_track(self):
        state = QueueState()
        self.assertEqual(_prefetch_delay(state), 0.0)
        state.current = _track('A', duration=600)
        state.track_started_at = time.monotonic()
        self.assertAlmostEqual(_prefetch_delay(state), 600 - PREFETCH_LEAD_SECONDS, delta=1)
        state.track_started_at = time.monotonic() - 590
        self.assertEqual(_prefetch_delay(state), 0.0)
        state.current = _track('B')  # durasi tak diketahui -> langsung
        self.assertEqual(_prefetch_delay(state), 0.0)


class PrefetchFlowTests(_PrefetchCase):
    def test_next_track_plays_without_extraction_gap(self):
        guild, vc, flag = _env(1)
        a, b = _track('A'), _track('B')
        state = QueueState()
        state.queue.extend([a, b])
        self.bot.states[1] = state

        async def run():
            await self.bot.advance(guild)               # A mulai -> prefetch B dijadwalkan
            self.assertIsNotNone(state.track_started_at)
            await self._settle(state)
            self.assertEqual(self.extractions.calls, [a.url, b.url])
            self.assertTrue(_stream_fresh(b))
            flag['playing'] = False                      # A selesai
            await self.bot.advance(guild)

        asyncio.run(run())
        self.assertIs(state.current, b)
        self.assertEqual(self.extractions.calls, [a.url, b.url], 'B diekstraksi dua kali')
        self.assertEqual(vc.play.call_count, 2)

    def test_advance_joins_in_flight_prefetch(self):
        guild, vc, flag = _env(2)
        a, b = _track('A'), _track('B')
        state = QueueState()
        state.queue.extend([a, b])
        self.bot.states[2] = state

        async def run():
            gate = self.extractions.gates[b.url] = asyncio.Event()
            await self.bot.advance(guild)
            for _ in range(50):                          # tunggu prefetch B mulai
                if state.prefetch_track is b:
                    break
                await asyncio.sleep(0)
            self.assertIs(state.prefetch_track, b)
            flag['playing'] = False                      # A selesai saat prefetch B masih jalan
            advancing = asyncio.ensure_future(self.bot.advance(guild))
            await asyncio.sleep(0.05)
            self.assertFalse(advancing.done(), 'advance() harus menunggu prefetch, bukan ekstraksi sendiri')
            gate.set()
            await advancing

        asyncio.run(run())
        self.assertIs(state.current, b)
        self.assertEqual(self.extractions.calls.count(b.url), 1)

    def test_prefetch_failure_falls_back_to_normal_extraction(self):
        guild, vc, flag = _env(3)
        a, b = _track('A'), _track('B')
        state = QueueState()
        state.queue.extend([a, b])
        self.bot.states[3] = state

        async def run():
            self.extractions.fail.add(b.url)
            await self.bot.advance(guild)
            await self._settle(state)
            self.assertIsNone(b.stream_url)
            self.extractions.fail.discard(b.url)
            flag['playing'] = False
            await self.bot.advance(guild)

        asyncio.run(run())
        self.assertIs(state.current, b)
        self.assertEqual(self.extractions.calls, [a.url, b.url, b.url])

    def test_autoplay_mix_and_stream_prefetched(self):
        guild, vc, flag = _env(4, playing=True)
        state = QueueState(autoplay=True)
        state.current = _track('SEED')
        state.track_started_at = time.monotonic()
        self.bot.states[4] = state
        mix = [Track(f'M{i}', f'https://www.youtube.com/watch?v=M{i:010d}', 'AutoPlay') for i in range(3)]
        fetch = AsyncMock(side_effect=lambda *a, **k: list(mix))

        async def run():
            with patch('bot.fetch_recommendations', new=fetch):
                self.bot._schedule_prefetch(guild, state)
                await self._settle(state)
                self.assertEqual(self.extractions.calls, [mix[0].url])
                flag['playing'] = False
                await self.bot.advance(guild)

        asyncio.run(run())
        self.assertIs(state.current, mix[0])
        self.assertEqual(fetch.await_count, 1, 'Mix diambil ulang saat transisi')
        self.assertEqual(self.extractions.calls, [mix[0].url], 'stream kandidat diekstraksi ulang')

    def test_prefetch_waits_until_near_end_of_long_track(self):
        guild, vc, flag = _env(5)
        a, b = _track('A', duration=600), _track('B')
        state = QueueState()
        state.queue.extend([a, b])
        self.bot.states[5] = state

        async def run():
            await self.bot.advance(guild)
            await asyncio.sleep(0.05)
            self.assertEqual(self.extractions.calls, [a.url], 'prefetch terlalu awal')
            self.assertFalse(state.prefetch_task.done())
            self.bot._schedule_prefetch(guild, state, restart=True)  # lagu baru: jadwal ulang
            await asyncio.sleep(0)
            self.assertFalse(state.prefetch_task.done())

        asyncio.run(run())

    def test_quit_voice_cancels_prefetch(self):
        guild, vc, flag = _env(6)
        a, b = _track('A', duration=600), _track('B')
        state = QueueState()
        state.queue.extend([a, b])
        self.bot.states[6] = state

        async def run():
            await self.bot.advance(guild)
            task = state.prefetch_task
            self.assertFalse(task.done())
            await self.bot.quit_voice(guild, clear_queue=False)
            await asyncio.wait({task}, timeout=1)
            self.assertTrue(task.cancelled())

        asyncio.run(run())
        self.assertIsNone(state.prefetch_task)
        self.assertIsNone(state.track_started_at)
        self.assertEqual(self.extractions.calls, [a.url])

    def test_no_prefetch_when_nothing_playing(self):
        guild, vc, flag = _env(7)
        state = QueueState()
        state.current = _track('Stale')
        state.queue.append(_track('B'))
        self.bot.states[7] = state

        async def run():
            self.bot._schedule_prefetch(guild, state)

        asyncio.run(run())
        self.assertIsNone(state.prefetch_task)

    def test_stale_cached_url_with_valid_expire_is_reused(self):
        guild, vc, flag = _env(8)
        a = _track('A', duration=200)
        a.stream_url = f'https://rr1.googlevideo.com/videoplayback?expire={int(time.time() + 5 * 3600)}'
        a.stream_ts = time.time() - 3600  # >30 menit: dulu memicu ekstraksi ulang
        state = QueueState()
        state.queue.append(a)
        self.bot.states[8] = state

        asyncio.run(self.bot.advance(guild))

        self.assertIs(state.current, a)
        self.assertEqual(self.extractions.calls, [])


class GatewayIntentTests(unittest.TestCase):
    def test_only_needed_intents_enabled(self):
        b = MusicBot()
        enabled = {name for name, value in b.intents if value}
        self.assertEqual(enabled, {'guilds', 'voice_states', 'dm_messages'})

    def test_message_cache_disabled(self):
        b = MusicBot()
        self.assertIsNone(b._connection.max_messages)


if __name__ == '__main__':
    unittest.main()
