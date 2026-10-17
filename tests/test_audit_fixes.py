"""Regresi untuk temuan audit bug-hunter (antrean, AutoPlay, ekstraksi, panel)."""
import asyncio
import atexit
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Isolasi path runtime SEBELUM bot/panel diimpor (lihat test_bot.py).
_ISOLATED_RUNTIME = tempfile.mkdtemp(prefix='discord-music-tests-')
atexit.register(shutil.rmtree, _ISOLATED_RUNTIME, True)
for _key, _name in (('QUEUE_STATE_FILE', 'queue_state.json'), ('BOT_STATE_FILE', 'state.json'),
                    ('PANEL_ENV', 'panel.env'), ('BOT_CONFIG', 'bot.env'),
                    ('UPDATE_LOG', 'last_update.log'), ('BOT_VENV', 'venv')):
    os.environ.setdefault(_key, os.path.join(_ISOLATED_RUNTIME, _name))

import discord
import yt_dlp

import bot as bot_module
import panel
from bot import (MAX_PLAYLIST_TRACKS, METADATA_OPTIONS, MIX_RESULT_LIMIT, ExtractionBusy, MusicBot,
                 QueueState, Track, TransientExtractionError, _mix_options, _skip_queue_head,
                 _tracks_from_metadata)


def _track(name):
    return Track(name, f'https://www.youtube.com/watch?v={(name * 11)[:11]}', 'u')


def _env(gid, playing=False):
    """Guild + voice client palsu yang is_playing-nya mengikuti play()/stop()."""
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
    vc.channel.id = 555
    vc.channel.bitrate = 96000
    vc.channel.members = [MagicMock(bot=False)]
    guild.voice_client = vc
    interaction = MagicMock()
    interaction.guild = guild
    interaction.user.voice.channel.id = 555
    interaction.response.defer = AsyncMock()
    interaction.response.is_done.return_value = True
    interaction.followup.send = AsyncMock()
    interaction.delete_original_response = AsyncMock()
    return guild, vc, interaction, flag


class _BotCase(unittest.TestCase):
    def setUp(self):
        self.bot = MusicBot()
        patches = [
            patch('bot.extract', return_value={'url': 'https://cdn/audio'}),
            patch('bot.source_for', return_value=MagicMock()),
            patch.object(self.bot, 'refresh', new=AsyncMock()),
            patch.object(self.bot, '_announce', new=MagicMock()),
            patch.object(self.bot, '_schedule_idle', new=MagicMock()),
            patch.object(bot_module, 'TRANSIENT_RETRY_DELAY', 0),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)


class LoopQueueSkipTests(_BotCase):
    def test_skip_keeps_track_in_loop_queue_rotation(self):
        guild, vc, interaction, _ = _env(1, playing=True)
        a, b, c = _track('A'), _track('B'), _track('C')
        state = QueueState(loop_mode='queue')
        state.current = a
        state.queue.extend([b, c])
        self.bot.states[1] = state

        asyncio.run(self.bot.cmd_skip(interaction))

        self.assertIs(state.current, b)
        self.assertEqual([t.title for t in state.queue], ['C', 'A'])
        self.assertIn(a, list(state.history))

    def test_skip_single_track_loop_queue_still_exits(self):
        guild, vc, interaction, _ = _env(2, playing=True)
        only = _track('X')
        state = QueueState(loop_mode='queue')
        state.current = only
        self.bot.states[2] = state

        asyncio.run(self.bot.cmd_skip(interaction))

        self.assertIsNone(state.current)
        self.assertEqual(list(state.queue), [])

    def test_skip_queue_head_rotates_in_loop_queue(self):
        state = QueueState(loop_mode='queue')
        state.queue.extend([_track('A'), _track('B')])
        _skip_queue_head(state)
        self.assertEqual([t.title for t in state.queue], ['B', 'A'])
        state.loop_mode = 'off'
        _skip_queue_head(state)
        self.assertEqual([t.title for t in state.queue], ['A'])

    def test_skip_during_extraction_keeps_track_in_loop_queue(self):
        guild, vc, interaction, _ = _env(3)
        a, b = _track('A'), _track('B')
        state = QueueState(loop_mode='queue')
        state.queue.extend([a, b])
        self.bot.states[3] = state
        calls = []

        async def fake_run_extract(func, url, timeout=60):
            calls.append(url)
            if len(calls) == 1:
                state._skip_pending = True  # user menekan Skip saat A diekstraksi
            return {'url': 'https://cdn/audio'}

        with patch('bot.run_extract', side_effect=fake_run_extract):
            asyncio.run(self.bot.advance(guild))

        self.assertIs(state.current, b)
        self.assertEqual([t.title for t in state.queue], ['A'])


class RestoredQueueTests(_BotCase):
    def _restored_bot_state(self, gid):
        saved = MusicBot()
        saved._queue_state_file = os.path.join(_ISOLATED_RUNTIME, f'restore-{gid}.json')
        st = QueueState()
        st.current = _track('R')
        saved.states[gid] = st
        saved._save_persistent_queue()
        self.bot._queue_state_file = saved._queue_state_file
        self.bot._restore_persistent_queue()
        return self.bot.states[gid]

    def test_restored_current_goes_to_queue_head(self):
        state = self._restored_bot_state(10)
        self.assertIsNone(state.current)
        self.assertEqual([t.title for t in state.queue], ['R'])

    def test_restored_track_plays_first_on_play(self):
        state = self._restored_bot_state(11)
        guild, vc, interaction, _ = _env(11)
        new = _track('N')

        asyncio.run(self.bot._enqueue_tracks(guild, [new]))

        self.assertEqual(state.current.title, 'R')
        self.assertEqual([t.title for t in state.queue], ['N'])

    def test_restored_track_resumes_on_pause(self):
        state = self._restored_bot_state(12)
        guild, vc, interaction, _ = _env(12)

        asyncio.run(self.bot.cmd_pause(interaction))

        vc.play.assert_called_once()
        self.assertEqual(state.current.title, 'R')
        self.assertEqual(interaction.followup.send.call_args[0][0], 'Melanjutkan pemutaran antrian lagu.')

    def test_pause_does_not_claim_resume_when_nothing_plays(self):
        guild, vc, interaction, _ = _env(13)
        state = QueueState()
        state.current = _track('Done')  # lagu selesai, loop off, antrean kosong
        self.bot.states[13] = state

        asyncio.run(self.bot.cmd_pause(interaction))

        vc.play.assert_not_called()
        self.assertEqual(interaction.followup.send.call_args[0][0],
                         'Tidak ada lagu yang bisa diputar dari antrian.')


class QuitVoiceTests(_BotCase):
    def test_quit_without_reset_requeues_current(self):
        guild, vc, interaction, _ = _env(20, playing=True)
        vc.disconnect = AsyncMock()
        state = QueueState()
        state.current = _track('Playing')
        state.queue.append(_track('Next'))
        self.bot.states[20] = state

        asyncio.run(self.bot.quit_voice(guild, clear_queue=False))

        self.assertIsNone(state.current)
        self.assertEqual([t.title for t in state.queue], ['Playing', 'Next'])

    def test_quit_with_reset_clears_autoplay_candidates(self):
        guild, vc, interaction, _ = _env(21)
        vc.disconnect = AsyncMock()
        state = QueueState()
        state.autoplay_candidates = [_track('M')]
        self.bot.states[21] = state
        with patch('bot.clear_cache'):
            asyncio.run(self.bot.quit_voice(guild, clear_queue=True))
        self.assertEqual(state.autoplay_candidates, [])


class AutoplayCacheTests(_BotCase):
    def test_mix_fetched_once_for_consecutive_autoplay_tracks(self):
        guild, vc, interaction, flag = _env(30)
        state = QueueState(autoplay=True)
        state.history.append(_track('SEED'))
        self.bot.states[30] = state
        candidates = [Track(f'M{i}', f'https://www.youtube.com/watch?v=M{i:010d}', 'AutoPlay') for i in range(15)]
        fetch = AsyncMock(side_effect=lambda *a, **k: list(candidates))

        async def run():
            with patch('bot.fetch_recommendations', new=fetch):
                for _ in range(3):
                    flag['playing'] = False
                    await self.bot.advance(guild)

        asyncio.run(run())
        self.assertEqual(fetch.await_count, 1)
        self.assertEqual(state.current.title, 'M2')
        self.assertEqual(len(state.autoplay_candidates), 12)

    def test_user_enqueue_invalidates_cached_candidates(self):
        guild, vc, interaction, flag = _env(31, playing=True)
        state = QueueState(autoplay=True)
        state.autoplay_candidates = [_track('M')]
        self.bot.states[31] = state
        asyncio.run(self.bot._enqueue_tracks(guild, [_track('U')]))
        self.assertEqual(state.autoplay_candidates, [])


class TransientExtractionTests(_BotCase):
    def test_transient_failure_retries_head_without_reordering(self):
        for exc in (ExtractionBusy('sibuk'), TransientExtractionError('429')):
            with self.subTest(exc=type(exc).__name__):
                self.bot = MusicBot()
                self.bot.refresh = AsyncMock()
                self.bot._announce = MagicMock()
                guild, vc, interaction, _ = _env(40)
                a, b, c = _track('A'), _track('B'), _track('C')
                state = QueueState()
                state.queue.extend([a, b, c])
                self.bot.states[40] = state
                calls = []

                async def fake_run_extract(func, url, timeout=60, _exc=exc):
                    calls.append(url)
                    if len(calls) == 1:
                        raise _exc
                    return {'url': 'https://cdn/audio'}

                with patch('bot.run_extract', side_effect=fake_run_extract):
                    asyncio.run(self.bot.advance(guild))

                self.assertIs(state.current, a, 'lagu yang sama harus dicoba ulang')
                self.assertEqual([t.title for t in state.queue], ['B', 'C'])
                self.assertEqual(calls, [a.url, a.url])

    def test_persistent_transient_failure_stops_with_queue_intact(self):
        guild, vc, interaction, _ = _env(41)
        a, b = _track('A'), _track('B')
        state = QueueState()
        state.queue.extend([a, b])
        self.bot.states[41] = state

        with patch('bot.run_extract', side_effect=ExtractionBusy('sibuk')) as run_extract:
            asyncio.run(self.bot.advance(guild))

        vc.play.assert_not_called()
        self.assertEqual(run_extract.call_count, bot_module.MAX_TRACK_RETRIES)
        self.assertEqual([t.title for t in state.queue], ['A', 'B'])

    def test_permanent_failure_and_timeout_still_move_track_to_tail(self):
        # Timeout tidak di-retry: thread yt-dlp yang timeout tetap hidup (zombie).
        for exc in (ValueError('Lagu tidak tersedia (video privat atau telah dihapus).'), asyncio.TimeoutError()):
            with self.subTest(exc=type(exc).__name__):
                guild, vc, interaction, _ = _env(42)
                a, b = _track('A'), _track('B')
                state = QueueState()
                state.queue.extend([a, b])
                self.bot.states[42] = state

                async def fake_run_extract(func, url, timeout=60, _exc=exc):
                    if url == a.url:
                        raise _exc
                    return {'url': 'https://cdn/audio'}

                with patch('bot.run_extract', side_effect=fake_run_extract):
                    asyncio.run(self.bot.advance(guild))

                self.assertIs(state.current, b)
                self.assertEqual([t.title for t in state.queue], ['A'])

    def test_rate_limit_is_transient(self):
        self.assertTrue(issubclass(TransientExtractionError, ValueError))
        self.assertTrue(issubclass(ExtractionBusy, TransientExtractionError))
        ydl = MagicMock()
        ydl.__enter__.return_value.extract_info.side_effect = yt_dlp.utils.DownloadError('HTTP Error 429: Too Many Requests')
        with patch('bot.yt_dlp.YoutubeDL', return_value=ydl), patch('bot.time.sleep'):
            with self.assertRaises(TransientExtractionError):
                bot_module.extract_stream('https://www.youtube.com/watch?v=aaaaaaaaaaa')


class PlaylistLimitTests(unittest.TestCase):
    def test_metadata_extraction_stops_paging_at_limit(self):
        self.assertEqual(METADATA_OPTIONS['playlistend'], MAX_PLAYLIST_TRACKS)
        self.assertEqual(_mix_options(MIX_RESULT_LIMIT)['playlistend'], MIX_RESULT_LIMIT)

    def test_tracks_capped(self):
        data = {'entries': [{'title': f'T{i}', 'id': f'{i:011d}'} for i in range(MAX_PLAYLIST_TRACKS + 50)]}
        self.assertEqual(len(_tracks_from_metadata(data, 'u', 'x')), MAX_PLAYLIST_TRACKS)


class MiscHardeningTests(_BotCase):
    def test_client_disables_mentions(self):
        mentions = self.bot.allowed_mentions
        self.assertIsNotNone(mentions)
        self.assertFalse(mentions.everyone)
        self.assertFalse(mentions.users)
        self.assertFalse(mentions.roles)

    def test_exporter_dumps_state_on_loop_thread(self):
        seen = []

        def fake_dump(bot):
            seen.append(threading.get_ident())
            bot._stopping = True

        self.bot.wait_until_ready = AsyncMock()
        with patch('bot.dump_runtime_state', side_effect=fake_dump), \
             patch('bot.asyncio.sleep', new=AsyncMock()):
            asyncio.run(self.bot._state_exporter_loop())
        self.assertEqual(seen, [threading.get_ident()])

    def test_play_error_is_private(self):
        guild, vc, interaction, _ = _env(50)
        interaction.user.voice.channel = vc.channel
        interaction.response.defer = AsyncMock()
        with patch('bot.extract_tracks', new=AsyncMock(side_effect=ValueError('Lagu tidak ditemukan.'))):
            asyncio.run(self.bot.cmd_play(interaction, 'xyz'))
        interaction.delete_original_response.assert_awaited()
        args, kwargs = interaction.followup.send.call_args
        self.assertIn('Lagu tidak ditemukan.', args[0])
        self.assertTrue(kwargs.get('ephemeral'))

    def test_tests_never_touch_live_runtime_dir(self):
        self.assertFalse(bot_module._persistent_queue_file().startswith('/run/discord-music'))
        self.assertFalse(os.environ['BOT_STATE_FILE'].startswith('/run/discord-music'))
        self.assertFalse(panel.PANEL_ENV_PATH.startswith('/opt/'))


class PanelPasswordQuotingTests(unittest.TestCase):
    def test_password_round_trips_through_env_file(self):
        if not shutil.which('bash'):
            self.skipTest('bash tidak tersedia')
        passwords = ['simple123', '"abc"', "it's $HOME `x` \\end\\", ' spaced ', 'back\\slash', 'a#b;c']
        with tempfile.TemporaryDirectory() as tmp:
            env_file = os.path.join(tmp, 'panel.env')
            with open(env_file, 'w', encoding='utf-8') as fh:
                fh.write('PANEL_HOST=0.0.0.0\n')
            try:
                for password in passwords:
                    panel.update_panel_password(password, env_path=env_file)
                    # Kutip/escape EnvironmentFile systemd mengikuti aturan shell.
                    got = subprocess.run(
                        ['bash', '-c', 'set -a; . "$1"; printf %s "$PANEL_PASSWORD"', '_', env_file],
                        capture_output=True, text=True, timeout=10, check=True).stdout
                    self.assertEqual(got, password)
            finally:
                panel.PASSWORD = ''

    def test_simple_password_left_unquoted(self):
        self.assertEqual(panel._env_quote('newpassword123'), 'newpassword123')
        self.assertEqual(panel._env_quote(''), '')


if __name__ == '__main__':
    unittest.main()
