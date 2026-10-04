import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

import discord

import bot as bot_module
from bot import (MusicBot, MusicPanel, Track, QueueState, GuildState, get_afk_timeout,
                 extract_track, extract_tracks, source_for, _cookies_file, _with_cookies, SearchModal)


class MusicTests(unittest.TestCase):
    def test_queue_fifo_and_stop_generation(self):
        state = QueueState()
        a, b = Track('a', 'https://www.youtube.com/watch?v=aaaa', 'u'), Track('b', 'https://www.youtube.com/watch?v=bbbb', 'v')
        state.queue.extend((a, b))
        self.assertEqual(state.queue.popleft(), a)
        self.assertEqual(state.queue.popleft(), b)
        state.queue.append(a)
        state.generation += 1
        state.queue.clear()
        state.current = None
        self.assertFalse(state.queue)

    def test_panel_is_persistent(self):
        bot = MusicBot()
        view = MusicPanel(bot)
        self.assertTrue(view.is_persistent())
        self.assertEqual(len(view.children), 10)
        expected_ids = [
            'music:down', 'music:back', 'music:pause', 'music:skip', 'music:up',
            'music:shuffle', 'music:loop', 'music:stop', 'music:autoplay', 'music:playlist'
        ]
        self.assertEqual([c.custom_id for c in view.children], expected_ids)

    def test_embed_formatting_matches_spec(self):
        bot = MusicBot()
        state = QueueState()
        track = Track(
            title="MANGKU PUREL - Pakdhe Kabul , Mukidi - OM ADELLA",
            url="https://youtube.com/watch?v=123",
            requester="@Han aja",
            duration=302,
            duration_str="5m 2s",
            author="Henny Adella"
        )
        state.current = track
        emb = bot.embed(state)
        self.assertEqual(emb.author.name, "MUSIC PANEL")
        self.assertIn("MANGKU PUREL", emb.description)
        self.assertEqual(len(emb.fields), 3)
        self.assertEqual(emb.fields[0].name, "🎧 Requested By")
        self.assertEqual(emb.fields[0].value, "@Han aja")
        self.assertEqual(emb.fields[1].name, "⏱ Music Duration")
        self.assertEqual(emb.fields[1].value, "`5m 2s`")
        self.assertEqual(emb.fields[2].name, "🎙 Music Author")
        self.assertEqual(emb.fields[2].value, "`Henny Adella`")

    def test_source_configures_volume(self):
        class DummyAudio(discord.AudioSource):
            def read(self): return b''
        with patch('bot.discord.FFmpegPCMAudio', return_value=DummyAudio()):
            source = source_for({'url': 'https://example.com/audio'}, volume=0.75)
            self.assertIsInstance(source, discord.PCMVolumeTransformer)
            self.assertEqual(source.volume, 0.75)

    def test_buffered_audio_source_fallback_and_cleanup(self):
        from bot import BufferedAudioSource
        class ChunkAudio(discord.AudioSource):
            def __init__(self):
                self.calls = 0
            def read(self):
                self.calls += 1
                if self.calls <= 3:
                    return b'\x01' * 3840
                return b''
            def cleanup(self):
                pass

        inner = ChunkAudio()
        buf = BufferedAudioSource(inner, buffer_size=10)
        chunk1 = buf.read()
        self.assertEqual(len(chunk1), 3840)
        self.assertEqual(chunk1, b'\x01' * 3840)
        buf.cleanup()
        self.assertTrue(buf.stop_event.is_set())

    def test_volume_clamping_and_change(self):
        bot = MusicBot()
        interaction = MagicMock()
        interaction.guild.id = 12345
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        asyncio.run(bot.change_volume(interaction, 0.85))
        state = bot.states[12345]
        self.assertEqual(state.volume, 0.85)
        # test clamp over 2.0
        asyncio.run(bot.change_volume(interaction, 2.5))
        self.assertEqual(state.volume, 2.0)
        # test clamp under 0.0
        asyncio.run(bot.change_volume(interaction, -0.5))
        self.assertEqual(state.volume, 0.0)

    def test_search_rejects_bad_urls(self):
        with self.assertRaises(ValueError):
            asyncio.run(extract_track('https://example.com/notyoutube', 'vito'))

    def test_checked_query_allows_colons_in_search(self):
        from bot import checked_query
        self.assertEqual(checked_query('OST: Attack on Titan'), 'ytsearch1:OST: Attack on Titan')
        self.assertEqual(checked_query('http://youtube.com/watch?v=123'), 'https://youtube.com/watch?v=123')

    def test_search_missing_result(self):
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            downloader.return_value.__enter__.return_value.extract_info.return_value = {'entries': []}
            with self.assertRaises(ValueError):
                asyncio.run(extract_track('impossible song', 'vito'))

    def test_setup_hook_handles_sync_forbidden(self):
        bot = MusicBot()
        mock_resp = unittest.mock.MagicMock()
        mock_resp.status = 403
        mock_resp.reason = 'Forbidden'
        with patch.object(bot.tree, 'sync', side_effect=discord.Forbidden(mock_resp, 'Missing Access')):
            with patch('bot.os.getenv', return_value='12345'):
                # Should not raise exception
                asyncio.run(bot.setup_hook())

    def test_command_tree_has_all_music_commands(self):
        bot = MusicBot()
        commands = [c.name for c in bot.tree.get_commands()]
        expected = {'musik', 'play', 'skip', 'back', 'stop', 'quit', 'antrian', 'pause', 'volume', 'shuffle', 'loop', 'autoplay'}
        self.assertTrue(expected.issubset(set(commands)), f'Missing commands in {commands}')

    def test_quit_voice_clears_queue_and_resets_state(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 99999
        vc = MagicMock()
        vc.is_playing.return_value = True
        vc.disconnect = AsyncMock()
        guild.voice_client = vc
        state = QueueState()
        state.queue.append(Track('track1', 'https://example.com/1', 'user'))
        state.current = Track('track0', 'https://example.com/0', 'user')
        state.generation = 1
        bot.states[99999] = state

        with patch.object(bot, 'refresh', new=AsyncMock()) as mock_refresh:
            asyncio.run(bot.quit_voice(guild, clear_queue=True))
            self.assertEqual(len(state.queue), 0)
            self.assertIsNone(state.current)
            self.assertEqual(state.generation, 2)
            vc.stop.assert_called_once()
            vc.disconnect.assert_called_once_with(force=True)
            mock_refresh.assert_called_once_with(state)

    def test_close_deletes_all_panels_and_clears_state(self):
        bot = MusicBot()
        states = {}
        msgs = {}
        for gid in (111, 222, 333):
            state = QueueState()
            if gid != 222:  # 222: tanpa panel
                msg = MagicMock()
                msg.delete = AsyncMock()
                state.message = msg
                msgs[gid] = msg
            states[gid] = state
        bot.states = states
        bot._exporter_task = None
        with patch('bot.dump_runtime_state_offline'):
            with patch.object(MusicBot.__bases__[0], 'close', new=AsyncMock()) as super_close:
                asyncio.run(bot.close())
                super_close.assert_called_once_with()
        msgs[111].delete.assert_called_once_with()
        msgs[333].delete.assert_called_once_with()
        self.assertIsNone(states[111].message)
        self.assertIsNone(states[333].message)

    def test_close_tolerates_panel_delete_failure(self):
        bot = MusicBot()
        state = QueueState()
        bad = MagicMock()
        bad.delete = AsyncMock(side_effect=discord.NotFound(MagicMock(), 'gone'))
        state.message = bad
        bot.states = {444: state}
        bot._exporter_task = None
        with patch('bot.dump_runtime_state_offline'):
            with patch.object(MusicBot.__bases__[0], 'close', new=AsyncMock()):
                asyncio.run(bot.close())  # tidak boleh raise
        self.assertIsNone(state.message)

    def test_close_without_panels_skips_delete(self):
        bot = MusicBot()
        state = QueueState()  # message None, now_message None
        self.assertFalse(state._skip_armed)
        bot.states = {555: state}
        bot._exporter_task = None
        with patch('bot.dump_runtime_state_offline'):
            with patch.object(MusicBot.__bases__[0], 'close', new=AsyncMock()):
                asyncio.run(bot.close())
        self.assertIsNone(state.message)
        self.assertIsNone(state.now_message)

    def test_announce_now_playing_sends_and_replaces_old(self):
        bot = MusicBot()
        state = QueueState()
        old = MagicMock()
        old.delete = AsyncMock()
        state.now_message = old
        panel_msg = MagicMock()
        channel = MagicMock()
        channel.send = AsyncMock(return_value=MagicMock())
        panel_msg.channel = channel
        state.message = panel_msg
        bot.states = {666: state}
        track = Track('Lagu Baru', 'https://youtube.com/watch?v=x', 'user')
        asyncio.run(bot._announce_now_playing(MagicMock(id=666), track))
        old.delete.assert_called_once_with()
        channel.send.assert_called_once()
        sent_text = channel.send.call_args[0][0]
        self.assertIn('Lagu Baru', sent_text)
        self.assertIsNotNone(state.now_message)

    def test_announce_now_playing_without_panel_sends_nothing(self):
        bot = MusicBot()
        state = QueueState()  # message None
        bot.states = {667: state}
        track = Track('Lagu X', 'https://youtube.com/watch?v=y', 'user')
        asyncio.run(bot._announce_now_playing(MagicMock(id=667), track))
        self.assertIsNone(state.now_message)

    def test_skip_arms_flag_and_advances_next(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 668
        vc = MagicMock()
        vc.is_playing.return_value = True
        vc.is_paused.return_value = False
        guild.voice_client = vc
        state = QueueState()
        bot.states[668] = state
        played = []

        async def fake_advance(g):
            played.append(g.id)

        with patch.object(bot, 'advance', new=AsyncMock(side_effect=fake_advance)):
            interaction = MagicMock()
            interaction.guild = guild
            interaction.response.send_message = AsyncMock()
            interaction.response.defer = AsyncMock()
            interaction.followup.send = AsyncMock()
            with patch('bot._check_guild_only', return_value=True), \
                 patch('bot._check_same_voice', return_value=(True, '')):
                asyncio.run(bot.cmd_skip(interaction))
        self.assertEqual(played, [668])  # advance manual selalu jalan
        self.assertTrue(state._skip_armed)  # after() basi dibuang
        vc.stop.assert_called_once()

    def test_back_advances_after_stop(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 669
        vc = MagicMock()
        vc.is_playing.return_value = True
        vc.is_paused.return_value = False
        guild.voice_client = vc
        state = QueueState()
        state.history.append(Track('prev', 'https://example.com/prev', 'u'))
        state.current = Track('now', 'https://example.com/now', 'u')
        bot.states[669] = state
        played = []

        async def fake_advance(g):
            played.append(g.id)

        with patch.object(bot, 'advance', new=AsyncMock(side_effect=fake_advance)):
            interaction = MagicMock()
            interaction.guild = guild
            interaction.response.send_message = AsyncMock()
            interaction.response.defer = AsyncMock()
            interaction.followup.send = AsyncMock()
            with patch('bot._check_guild_only', return_value=True), \
                 patch('bot._check_same_voice', return_value=(True, '')):
                asyncio.run(bot.cmd_back(interaction))
        self.assertEqual(played, [669])  # tidak tergantung voice_client hilang
        self.assertTrue(state.queue)  # current lama balik ke head antrian

    def test_quit_voice_default_preserves_queue(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 99998
        vc = MagicMock()
        vc.is_playing.return_value = False
        vc.disconnect = AsyncMock()
        guild.voice_client = vc
        state = QueueState()
        state.queue.append(Track('track1', 'https://example.com/1', 'user'))
        state.current = Track('track0', 'https://example.com/0', 'user')
        bot.states[99998] = state

        with patch.object(bot, 'refresh', new=AsyncMock()):
            asyncio.run(bot.quit_voice(guild, clear_queue=False))
            self.assertEqual(len(state.queue), 1)
            self.assertIsNone(state.current)

    def test_cmd_quit_invokes_quit_voice(self):
        bot = MusicBot()
        interaction = MagicMock()
        interaction.guild = MagicMock()
        interaction.guild.id = 88888
        interaction.guild.voice_client = MagicMock()
        interaction.guild.voice_client.channel = MagicMock()
        interaction.guild.voice_client.channel.id = 111
        interaction.user.voice.channel.id = 111
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        with patch.object(bot, 'quit_voice', new=AsyncMock()) as mock_quit:
            asyncio.run(bot.cmd_quit(interaction))
            interaction.response.defer.assert_called_once_with(ephemeral=True)
            mock_quit.assert_called_once_with(interaction.guild, clear_queue=True)
            interaction.followup.send.assert_called_once()

    def test_on_voice_state_update_bot_kicked(self):
        bot = MusicBot()
        bot_user = MagicMock()
        bot_user.id = 123456
        bot._connection.user = bot_user
        member = MagicMock()
        member.id = 123456
        member.guild = MagicMock()
        member.guild.voice_client = None
        before = MagicMock()
        before.channel = MagicMock()
        after = MagicMock()
        after.channel = None

        with patch.object(bot, 'quit_voice', new=AsyncMock()) as mock_quit:
            with patch('bot.dump_runtime_state'):
                with patch('asyncio.sleep', new=AsyncMock()):
                    asyncio.run(bot.on_voice_state_update(member, before, after))
                    mock_quit.assert_called_once_with(member.guild, clear_queue=False)

    def test_advance_stops_on_consecutive_errors_preserving_queue(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 77777
        guild.name = 'TestGuild'
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        guild.voice_client = vc

        state = QueueState()
        for i in range(5):
            state.queue.append(Track(f'track{i}', f'https://example.com/{i}', 'user'))
        bot.states[77777] = state

        with patch('bot.extract', side_effect=RuntimeError('Network down')):
            with patch.object(bot, 'refresh', new=AsyncMock()):
                asyncio.run(bot.advance(guild))
                # Gagal 3x beruntun: queue utuh (tidak ada track hilang),
                # track gagal di-rotate ke ekor agar retry manual masih bisa.
                self.assertEqual(len(state.queue), 5)
                self.assertEqual(state.queue[0].title, 'track2')
                self.assertIsNone(state.current)

    def test_advance_success_commits_queue_and_history(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 77778
        guild.name = 'TestGuild2'
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        vc.channel.bitrate = 96000
        guild.voice_client = vc

        state = QueueState()
        state.current = Track('now', 'https://example.com/now', 'user')
        nxt = Track('next', 'https://example.com/next', 'user')
        state.queue.append(nxt)
        bot.states[77778] = state

        with patch('bot.extract', return_value={'url': 'https://cdn/audio'}):
            with patch('bot.source_for', return_value=MagicMock()):
                with patch.object(bot, 'refresh', new=AsyncMock()):
                    asyncio.run(bot.advance(guild))
                    vc.play.assert_called_once()
                    self.assertEqual(state.current.title, 'next')
                    self.assertEqual(len(state.queue), 0)
                    self.assertEqual(len(state.history), 1)
                    self.assertEqual(state.history[0].title, 'now')

    def test_skip_bumps_generation(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 77779
        vc = MagicMock()
        vc.is_playing.return_value = True
        vc.is_paused.return_value = False
        guild.voice_client = vc
        state = QueueState()
        bot.states[77779] = state
        gen0 = state.generation
        asyncio.run(bot._stop_player(guild))
        self.assertEqual(state.generation, gen0 + 1)
        vc.stop.assert_called_once()

    def test_enqueue_rejects_full_queue(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 77780
        guild.voice_client = None
        from bot import MAX_QUEUE
        state = QueueState()
        for i in range(MAX_QUEUE):
            state.queue.append(Track(f't{i}', f'https://example.com/{i}', 'u'))
        bot.states[77780] = state
        ok = asyncio.run(bot._enqueue_tracks(guild, [Track('x', 'https://example.com/x', 'u')]))
        self.assertFalse(ok)
        self.assertEqual(len(state.queue), MAX_QUEUE)

    def test_buffered_source_eof_after_stall(self):
        from bot import BufferedAudioSource, MAX_ERROR_STREAK
        import threading as _th
        block = _th.Event()
        class StallAudio(discord.AudioSource):
            def __init__(self):
                self.calls = 0
            def read(self):
                self.calls += 1
                if self.calls <= 2:
                    return b'\x02' * 3840
                block.wait(timeout=60)  # stall: ffmpeg macet
                return b''
            def cleanup(self):
                pass
        inner = StallAudio()
        buf = BufferedAudioSource(inner, buffer_size=2)
        buf.ready_event.set()
        # Kuras 2 chunk awal, lalu stall: setelah MAX_ERROR_STREAK miss harus EOF (b'').
        for _ in range(5):
            buf.read()
        eof = False
        for _ in range(MAX_ERROR_STREAK + 5):
            if buf.read() == b'':
                eof = True
                break
        self.assertTrue(eof)
        buf.cleanup()

    def test_play_respects_voice_guard(self):
        bot = MusicBot()
        interaction = MagicMock()
        interaction.guild = MagicMock()
        interaction.guild.id = 99991
        interaction.guild.voice_client = MagicMock()
        interaction.guild.voice_client.channel.id = 111
        interaction.user.voice.channel.id = 222  # beda channel
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        asyncio.run(bot.cmd_skip(interaction))
        interaction.followup.send.assert_called_once()
        args = interaction.followup.send.call_args[0][0]
        self.assertIn('sama dengan bot', args)

    def test_extract_tracks_playlist_skips_none_and_caps(self):
        mock_entries = [
            {'title': f'Song {i}', 'url': f'https://youtube.com/watch?v=s{i}'}
            for i in range(110)
        ]
        mock_entries[2] = None  # simulate private video skipped by ignoreerrors
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            downloader.return_value.__enter__.return_value.extract_info.return_value = {
                '_type': 'playlist',
                'title': 'Test Playlist',
                'entries': mock_entries
            }
            tracks = asyncio.run(extract_tracks('https://www.youtube.com/playlist?list=PL123', 'vito'))
            self.assertEqual(len(tracks), 100)
            self.assertEqual(tracks[0].title, 'Song 0')
            self.assertEqual(tracks[1].title, 'Song 1')
            self.assertEqual(tracks[2].title, 'Song 3')  # index 2 was skipped

    def test_extract_tracks_single_video(self):
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            downloader.return_value.__enter__.return_value.extract_info.return_value = {
                'title': 'Single Track',
                'webpage_url': 'https://youtube.com/watch?v=abc',
                'url': 'https://googlevideo.com/audio'
            }
            tracks = asyncio.run(extract_tracks('https://www.youtube.com/watch?v=abc', 'vito'))
            self.assertEqual(len(tracks), 1)
            self.assertEqual(tracks[0].title, 'Single Track')
            self.assertEqual(tracks[0].url, 'https://youtube.com/watch?v=abc')

    def test_extract_tracks_rejects_livestream(self):
        # 1. Single video dengan is_live=True
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            downloader.return_value.__enter__.return_value.extract_info.return_value = {
                'title': 'Live Stream Video',
                'webpage_url': 'https://youtube.com/watch?v=live1',
                'is_live': True
            }
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(extract_tracks('https://youtube.com/watch?v=live1', 'vito'))
            self.assertIn('livestream', str(ctx.exception).lower())

        # 2. Single video dengan live_status='is_live'
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            downloader.return_value.__enter__.return_value.extract_info.return_value = {
                'title': 'Live Stream Video 2',
                'webpage_url': 'https://youtube.com/watch?v=live2',
                'live_status': 'is_live'
            }
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(extract_tracks('https://youtube.com/watch?v=live2', 'vito'))
            self.assertIn('livestream', str(ctx.exception).lower())

        # 3. Search query yang hanya menghasilkan livestream
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            downloader.return_value.__enter__.return_value.extract_info.return_value = {
                'entries': [
                    {'title': 'Search Live', 'url': 'https://youtube.com/watch?v=slive', 'live_status': 'is_live'}
                ]
            }
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(extract_tracks('search live query', 'vito'))
            self.assertIn('livestream', str(ctx.exception).lower())

    def test_extract_tracks_filters_dead_and_live_playlist_items(self):
        entries = [
            {'title': 'Track 1', 'url': 'https://youtube.com/watch?v=t1'},
            {'title': None, 'id': 'dead1', 'url': None},
            {'title': '[Private video]', 'id': 'priv1', 'url': 'https://youtube.com/watch?v=priv1'},
            {'title': '[Deleted video]', 'id': 'del1', 'url': 'https://youtube.com/watch?v=del1'},
            {'title': 'Live in playlist', 'url': 'https://youtube.com/watch?v=live', 'is_live': True},
            {'title': 'Track 2', 'url': 'https://youtube.com/watch?v=t2'},
        ]
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            downloader.return_value.__enter__.return_value.extract_info.return_value = {
                '_type': 'playlist',
                'title': 'Test Playlist Mixed',
                'entries': entries
            }
            tracks = asyncio.run(extract_tracks('https://youtube.com/playlist?list=PLmixed', 'vito'))
            self.assertEqual(len(tracks), 2)
            self.assertEqual(tracks[0].title, 'Track 1')
            self.assertEqual(tracks[1].title, 'Track 2')
            for t in tracks:
                self.assertNotIn('Tanpa judul', t.title)
                self.assertNotIn('Private', t.title)

    def test_extract_tracks_age_restricted_shows_cookies_hint(self):
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            downloader.return_value.__enter__.return_value.extract_info.side_effect = (
                bot_module.yt_dlp.utils.DownloadError("ERROR: [youtube] xyz: Sign in to confirm your age")
            )
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(extract_tracks('https://youtube.com/watch?v=xyz', 'vito'))
            self.assertIn('age-restricted', str(ctx.exception).lower())
            self.assertIn('cookies.txt', str(ctx.exception))

    def test_extract_tracks_rate_limit_429_backoff_and_retry(self):
        with patch('bot.yt_dlp.YoutubeDL') as downloader, patch('bot.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            downloader.return_value.__enter__.return_value.extract_info.side_effect = [
                bot_module.yt_dlp.utils.DownloadError("HTTP Error 429: Too Many Requests"),
                {'title': 'Success After 429', 'webpage_url': 'https://youtube.com/watch?v=rec', 'url': 'https://cdn'}
            ]
            tracks = asyncio.run(extract_tracks('https://youtube.com/watch?v=rec', 'vito'))
            self.assertEqual(len(tracks), 1)
            self.assertEqual(tracks[0].title, 'Success After 429')
            mock_sleep.assert_awaited_once_with(2.0)

    def test_extract_tracks_rate_limit_429_exhausted(self):
        with patch('bot.yt_dlp.YoutubeDL') as downloader, patch('bot.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            downloader.return_value.__enter__.return_value.extract_info.side_effect = (
                bot_module.yt_dlp.utils.DownloadError("HTTP Error 429: Too Many Requests")
            )
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(extract_tracks('https://youtube.com/watch?v=rec', 'vito'))
            self.assertIn('429', str(ctx.exception))
            self.assertEqual(mock_sleep.await_count, 1)

    def test_extract_stream_edge_cases(self):
        # 1. Livestream ditolak
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            downloader.return_value.__enter__.return_value.extract_info.return_value = {
                'url': 'https://manifest.googlevideo.com/hls.m3u8',
                'is_live': True
            }
            with self.assertRaises(ValueError) as ctx:
                bot_module.extract_stream('https://youtube.com/watch?v=live')
            self.assertIn('livestream', str(ctx.exception).lower())

        # 2. 429 retry lalu berhasil
        with patch('bot.yt_dlp.YoutubeDL') as downloader, patch('bot.time.sleep') as mock_sleep:
            downloader.return_value.__enter__.return_value.extract_info.side_effect = [
                bot_module.yt_dlp.utils.DownloadError("HTTP Error 429: Too Many Requests"),
                {'url': 'https://cdn.googlevideo.com/audio.webm'}
            ]
            res = bot_module.extract_stream('https://youtube.com/watch?v=stream429')
            self.assertEqual(res['url'], 'https://cdn.googlevideo.com/audio.webm')
            mock_sleep.assert_called_once_with(2.0)

        # 3. Age-restricted memberikan instruksi cookies.txt
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            downloader.return_value.__enter__.return_value.extract_info.side_effect = (
                bot_module.yt_dlp.utils.DownloadError("ERROR: [youtube] Sign in to confirm your age")
            )
            with self.assertRaises(ValueError) as ctx:
                bot_module.extract_stream('https://youtube.com/watch?v=stream18')
            self.assertIn('cookies.txt', str(ctx.exception))

    # --- Regresi hasil audit -------------------------------------------------

    def test_advance_track_loop_replay_does_not_raise_nameerror(self):
        """Mode loop 'track' mengulang track tanpa menyentuh queue/history.

        Regresi: `played` hanya di-assign di cabang else sehingga jalur replay
        melempar NameError dan pengumuman now-playing hilang.
        """
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 88001
        guild.name = 'LoopGuild'
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        vc.channel.bitrate = 96000
        guild.voice_client = vc

        state = QueueState()
        track = Track('ulang', 'https://example.com/loop', 'user')
        state.current = track
        state.loop_mode = 'track'
        bot.states[88001] = state

        announced = []
        with patch('bot.extract', return_value={'url': 'https://cdn/audio'}):
            with patch('bot.source_for', return_value=MagicMock()):
                with patch.object(bot, 'refresh', new=AsyncMock()):
                    with patch.object(bot, '_announce_now_playing', new=AsyncMock(
                            side_effect=lambda g, t: announced.append(t))) as mock_ann:
                        asyncio.run(bot.advance(guild))
        vc.play.assert_called_once()
        self.assertIs(state.current, track)
        self.assertEqual(announced, [track])
        self.assertIsNotNone(mock_ann)

    def test_advance_schedules_idle_when_nothing_playing(self):
        """Setelah gagal putar, current harus cleared agar idle-disconnect jalan."""
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 88002
        guild.name = 'IdleGuild'
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        guild.voice_client = vc

        state = QueueState()
        state.current = Track('stale', 'https://example.com/stale', 'user')
        bot.states[88002] = state

        scheduled = []
        with patch.object(bot, 'refresh', new=AsyncMock()):
            with patch.object(bot, '_schedule_idle', side_effect=lambda g, gen: scheduled.append(g.id)):
                asyncio.run(bot.advance(guild))
        self.assertIsNone(state.current)
        self.assertEqual(scheduled, [88002])

    def test_enqueue_clears_stale_current_and_advances(self):
        """current basi tanpa playback nyata tidak boleh menahan antrian."""
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 88003
        vc = MagicMock()
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        guild.voice_client = vc
        state = QueueState()
        state.current = Track('stale', 'https://example.com/stale', 'user')
        bot.states[88003] = state

        advanced = []
        with patch.object(bot, 'advance', new=AsyncMock(side_effect=lambda g: advanced.append(g.id))):
            ok = asyncio.run(bot._enqueue_tracks(
                guild, [Track('new', 'https://example.com/new', 'user')]))
        self.assertTrue(ok)
        self.assertIsNone(state.current)
        self.assertEqual(advanced, [88003])
        self.assertEqual(state.history[-1].title, 'stale')

    def test_enqueue_keeps_current_while_playing(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 88004
        vc = MagicMock()
        vc.is_playing.return_value = True
        vc.is_paused.return_value = False
        guild.voice_client = vc
        state = QueueState()
        state.current = Track('live', 'https://example.com/live', 'user')
        bot.states[88004] = state

        with patch.object(bot, 'advance', new=AsyncMock()) as mock_advance:
            asyncio.run(bot._enqueue_tracks(
                guild, [Track('new', 'https://example.com/new', 'user')]))
        self.assertEqual(state.current.title, 'live')
        mock_advance.assert_not_called()

    def test_shuffle_button_does_not_hold_lock_across_send(self):
        """await followup.send harus di luar state.lock (anti-stall playback)."""
        bot = MusicBot()
        interaction = MagicMock()
        interaction.guild.id = 88005
        state = QueueState()
        state.queue.extend(
            Track(f't{i}', f'https://example.com/{i}', 'u') for i in range(4))
        state.current = Track('now', 'https://example.com/now', 'u')
        bot.states[88005] = state
        interaction.message = MagicMock()

        observed = {}

        async def slow_send(*args, **kwargs):
            observed['locked_during_send'] = state.lock.locked()

        interaction.followup.send = AsyncMock(side_effect=slow_send)
        interaction.response.defer = AsyncMock()
        interaction.response.is_done.return_value = True

        view = MusicPanel(bot)
        with patch.object(bot, 'refresh', new=AsyncMock()):
            with patch.object(view, 'guard', new=AsyncMock(return_value=True)):
                asyncio.run(view.shuffle.callback(interaction))
        self.assertFalse(observed.get('locked_during_send', True),
                         'state.lock masih dipegang saat followup.send')

    def test_back_button_does_not_hold_lock_across_send(self):
        bot = MusicBot()
        interaction = MagicMock()
        interaction.guild.id = 88006
        vc = MagicMock()
        vc.channel.id = 5
        interaction.guild.voice_client = vc
        interaction.user.voice.channel.id = 5
        state = QueueState()
        state.current = Track('now', 'https://example.com/now', 'u')
        bot.states[88006] = state
        interaction.message = MagicMock()

        observed = {}

        async def slow_send(*args, **kwargs):
            observed['locked_during_send'] = state.lock.locked()

        interaction.followup.send = AsyncMock(side_effect=slow_send)
        interaction.response.defer = AsyncMock()
        interaction.response.is_done.return_value = True

        view = MusicPanel(bot)
        with patch.object(bot, '_stop_player', new=AsyncMock()):
            with patch.object(bot, 'advance', new=AsyncMock()):
                with patch.object(view, 'guard', new=AsyncMock(return_value=True)):
                    asyncio.run(view.back.callback(interaction))
        self.assertFalse(observed.get('locked_during_send', True),
                         'state.lock masih dipegang saat followup.send')

    def test_buffered_source_eof_on_intermittent_stall(self):
        """Producer tersendat-sendat tidak boleh menahan EOF selamanya.

        Regresi: counter miss berurutan selalu ter-reset oleh chunk yang datang
        jarang, sehingga lagu tidak pernah lanjut.
        """
        from bot import BufferedAudioSource
        import threading as _th
        import time as _time
        stop = _th.Event()

        class TrickleAudio(discord.AudioSource):
            def __init__(self):
                self.first = True
            def read(self):
                if self.first:
                    self.first = False
                    return b'\x03' * 3840
                stop.wait(timeout=5)
                return b''

        buf = BufferedAudioSource(TrickleAudio(), buffer_size=2)
        buf.ready_event.set()
        buf.read()  # kuras chunk pertama
        eof = False
        deadline = _time.monotonic() + 15
        while _time.monotonic() < deadline:
            if buf.read() == b'':
                eof = True
                break
        self.assertTrue(eof, 'tidak pernah EOF pada stall berkepanjangan')
        buf.cleanup()

    def test_buffered_source_stall_tolerance_not_premature(self):
        """Stall sesaat (< STALL_EOF_SECONDS) TIDAK boleh langsung EOF.

        Regresi: deadline 1 detik terlalu agresif — CDN YouTube yang tersendat
        sedetik membuat lagu loncat ke track berikutnya tanpa alasan.
        """
        from bot import BufferedAudioSource, STALL_EOF_SECONDS
        import threading as _th
        import time as _time

        self.assertGreaterEqual(STALL_EOF_SECONDS, 3.0,
                                'toleransi stall terlalu pendek untuk jitter CDN')

        stop = _th.Event()

        class StallAudio(discord.AudioSource):
            def __init__(self):
                self.first = True
            def read(self):
                if self.first:
                    self.first = False
                    return b'\x04' * 3840
                stop.wait(timeout=30)
                return b''
            def cleanup(self):
                pass

        buf = BufferedAudioSource(StallAudio(), buffer_size=2)
        buf.ready_event.set()
        buf.read()  # kuras chunk pertama

        # Fase 1: stall lebih pendek dari toleransi -> belum boleh EOF.
        window = min(STALL_EOF_SECONDS, 3.0) - 0.5
        deadline = _time.monotonic() + window
        while _time.monotonic() < deadline:
            self.assertNotEqual(
                buf.read(), b'',
                f'EOF prematur sebelum {window:.1f} dtk stall')

        # Fase 2: teruskan sampai toleransi terlampaui -> harus EOF.
        eof = False
        hard_deadline = _time.monotonic() + STALL_EOF_SECONDS + 10
        while _time.monotonic() < hard_deadline:
            if buf.read() == b'':
                eof = True
                break
        self.assertTrue(eof, 'stall berkepanjangan tidak pernah EOF')
        stop.set()
        buf.cleanup()

    def test_source_error_walks_wrapper_chain(self):
        """_current_error pada FFmpeg terdalam harus ketemu lewat wrapper."""
        from bot import _source_error, BufferedAudioSource

        class Inner(discord.AudioSource):
            def __init__(self):
                self._current_error = RuntimeError('ffmpeg mati')
            def read(self):
                return b''
            def cleanup(self):
                pass

        class Wrapper(discord.AudioSource):
            def __init__(self, original):
                self.original = original
            def read(self):
                return self.original.read()
            def cleanup(self):
                self.original.cleanup()

        inner = Inner()
        buffered = BufferedAudioSource(inner, buffer_size=2)
        wrapped = Wrapper(buffered)
        err = _source_error(wrapped)
        self.assertIsInstance(err, RuntimeError)
        buffered.cleanup()

    def test_announce_keeps_task_reference(self):
        """Referensi task disimpan agar tidak di-GC sebelum selesai."""
        bot = MusicBot()
        state = QueueState()
        bot.states = {88007: state}
        guild = MagicMock(id=88007)
        track = Track('t', 'https://example.com/t', 'u')

        async def scenario():
            with patch.object(bot, '_announce_now_playing', new=AsyncMock()):
                bot._announce(guild, track)
                await asyncio.sleep(0)
            return state.announce_task

        task = asyncio.run(scenario())
        self.assertIsNotNone(task)

    def test_announce_cancels_previous_task(self):
        """Announce berturut-turut (loop track) tidak boleh menumpuk task."""
        bot = MusicBot()
        state = QueueState()
        bot.states = {88008: state}
        guild = MagicMock(id=88008)
        track = Track('t', 'https://example.com/t', 'u')

        async def slow_announce(g, t):
            await asyncio.sleep(30)

        async def scenario():
            with patch.object(bot, '_announce_now_playing', new=slow_announce):
                bot._announce(guild, track)
                first = state.announce_task
                bot._announce(guild, track)
                second = state.announce_task
                await asyncio.sleep(0)
                return first, second

        first, second = asyncio.run(scenario())
        self.assertIsNot(first, second)
        self.assertTrue(first.cancelled() or first.done(),
                        'task announce sebelumnya harus dibatalkan')

    def test_quit_voice_clears_announce_task_and_now_message(self):
        """Stop/quit harus membatalkan announce & membersihkan pesan now-playing."""
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 88009
        guild.voice_client = None
        state = QueueState()
        old_msg = MagicMock()
        old_msg.delete = AsyncMock()
        state.now_message = old_msg
        bot.states[88009] = state

        async def scenario():
            with patch.object(bot, 'refresh', new=AsyncMock()), \
                 patch('bot.dump_runtime_state'):
                bot._announce(guild, Track('t', 'https://example.com/t', 'u'))
                pending = state.announce_task
                await asyncio.sleep(0)
                await bot.quit_voice(guild, clear_queue=True)
                return pending

        pending = asyncio.run(scenario())
        self.assertIsNone(state.announce_task)
        self.assertIsNone(state.now_message)
        old_msg.delete.assert_awaited()
        self.assertTrue(pending.cancelled() or pending.done())


class CookiesTests(unittest.TestCase):
    """P3: cookies.txt opsional untuk video age-restricted / butuh login."""

    def test_missing_cookies_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'YTDLP_COOKIES': os.path.join(tmp, 'nope.txt')},
                            clear=False):
                self.assertIsNone(_cookies_file())

    def test_empty_cookies_file_is_ignored(self):
        """Berkas kosong (sisa sentuhan) tidak boleh dipakai."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cookies.txt')
            open(path, 'w').close()
            with patch.dict(os.environ, {'YTDLP_COOKIES': path}, clear=False):
                self.assertIsNone(_cookies_file())

    def test_env_var_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cookies.txt')
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write('# Netscape HTTP Cookie File\n')
            with patch.dict(os.environ, {'YTDLP_COOKIES': path}, clear=False):
                self.assertEqual(_cookies_file(), path)

    def test_with_cookies_returns_copy_without_file(self):
        """Tanpa berkas cookies, options asli harus dikembalikan apa adanya."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'YTDLP_COOKIES': os.path.join(tmp, 'nope.txt')},
                            clear=False):
                options = {'format': 'bestaudio'}
                self.assertIs(_with_cookies(options), options)
                self.assertNotIn('cookiefile', options)

    def test_with_cookies_merges_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cookies.txt')
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write('# Netscape HTTP Cookie File\n')
            with patch.dict(os.environ, {'YTDLP_COOKIES': path}, clear=False):
                options = {'format': 'bestaudio'}
                merged = _with_cookies(options)
                self.assertEqual(merged['cookiefile'], path)
                self.assertNotIn('cookiefile', options,
                                 'options asli tidak boleh dimutasi')

    def test_cookies_picked_up_without_restart(self):
        """Berkas yang muncul setelah import harus langsung terpakai."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cookies.txt')
            with patch.dict(os.environ, {'YTDLP_COOKIES': path}, clear=False):
                self.assertIsNone(_cookies_file())
                with open(path, 'w', encoding='utf-8') as handle:
                    handle.write('# Netscape HTTP Cookie File\n')
                self.assertEqual(_cookies_file(), path,
                                 'cookies baru tidak terpakai tanpa restart bot')

    def test_gitignore_covers_cookies(self):
        """cookies.txt berisi sesi login: jangan pernah masuk git."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, '.gitignore'), encoding='utf-8') as handle:
            ignored = handle.read()
        self.assertIn('cookies.txt', ignored,
                      'cookies.txt harus ada di .gitignore (berisi sesi login)')


class HelpCommandTests(unittest.TestCase):
    """P4: /help harus terdaftar dan menyebut semua perintah penting."""

    def _help_text(self) -> str:
        bot = MusicBot()
        sent = {}

        async def scenario():
            interaction = MagicMock()
            interaction.response.defer = AsyncMock()
            interaction.response.send_message = AsyncMock(
                side_effect=lambda **kw: sent.update(kw))
            interaction.followup.send = AsyncMock(
                side_effect=lambda **kw: sent.update(kw))
            await bot.cmd_help(interaction)

        asyncio.run(scenario())
        embed = sent.get('embed')
        self.assertIsNotNone(embed, '/help tidak mengirim embed')
        text = embed.title + '\n'
        text += embed.description or ''
        for field in embed.fields:
            text += '\n' + field.name + '\n' + field.value
        return text

    def test_help_is_registered_in_command_tree(self):
        bot = MusicBot()
        names = {cmd.name for cmd in bot.tree.get_commands()}
        self.assertIn('help', names, '/help tidak terdaftar di CommandTree')

    def test_help_is_ephemeral(self):
        bot = MusicBot()
        sent = {}

        async def scenario():
            interaction = MagicMock()
            interaction.response.defer = AsyncMock()
            interaction.response.send_message = AsyncMock(
                side_effect=lambda **kw: sent.update(kw))
            interaction.followup.send = AsyncMock(
                side_effect=lambda **kw: sent.update(kw))
            await bot.cmd_help(interaction)

        asyncio.run(scenario())
        self.assertTrue(sent.get('ephemeral'),
                        '/help harus ephemeral agar channel tidak kotor')

    def test_help_lists_every_command(self):
        text = self._help_text()
        for name in ('musik', 'play', 'pause', 'skip', 'back', 'stop',
                     'antrian', 'shuffle', 'loop', 'autoplay',
                     'volume', 'quit', 'help'):
            self.assertIn(f'/{name}', text,
                          f'perintah /{name} tidak disebut di /help')

    def test_help_matches_registered_commands(self):
        """Setiap command yang terdaftar harus ada di teks /help."""
        bot = MusicBot()
        registered = {cmd.name for cmd in bot.tree.get_commands()}
        text = self._help_text()
        missing = sorted(name for name in registered if f'/{name}' not in text)
        self.assertEqual(missing, [],
                         f'command terdaftar tapi tidak ada di /help: {missing}')


class AudioPipelineHardeningTests(unittest.TestCase):
    """Pengujian temuan audit audio pipeline (t_c1458af6)."""

    def test_play_exception_cleans_up_source(self):
        """vc.play gagal harus memanggil source.cleanup() agar ffmpeg tidak bocor."""
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 88801
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        vc.play.side_effect = discord.ClientException('Simulated play error')
        guild.voice_client = vc

        state = QueueState()
        track = Track('t1', 'https://example.com/1', 'user')
        state.queue.append(track)
        bot.states[guild.id] = state

        mock_source = MagicMock()
        with patch('bot.extract', return_value={'url': 'http://cdn/1'}), \
             patch('bot.source_for', return_value=mock_source), \
             patch.object(bot, 'refresh', new=AsyncMock()):
            asyncio.run(bot.advance(guild))

        mock_source.cleanup.assert_called_once()

    def test_after_error_circuit_breaker_prevents_queue_burn(self):
        """after(error) berturut-turut harus mengaktifkan circuit breaker sebelum antrean habis."""
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 88802
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        guild.voice_client = vc

        state = QueueState()
        for i in range(10):
            state.queue.append(Track(f't{i}', f'https://example.com/{i}', 'user'))
        bot.states[guild.id] = state

        async def scenario():
            after_cb = None
            def fake_play(src, after=None, **kwargs):
                nonlocal after_cb
                after_cb = after
            vc.play.side_effect = fake_play

            with patch('bot.extract', return_value={'url': 'http://cdn/audio'}), \
                 patch('bot.source_for', return_value=MagicMock()), \
                 patch.object(bot, 'refresh', new=AsyncMock()):
                await bot.advance(guild)
                self.assertIsNotNone(after_cb)

                for i in range(3):
                    cur_cb = after_cb
                    self.assertIsNotNone(cur_cb)
                    cur_cb(RuntimeError(f'Stream drop {i+1}'))
                    for _ in range(50):
                        await asyncio.sleep(0.05)
                        if state.consecutive_playback_errors >= i + 1:
                            break

                self.assertEqual(state.consecutive_playback_errors, 3)
                self.assertIsNone(state.current)
                self.assertGreaterEqual(len(state.queue), 7)

        asyncio.run(scenario())

    def test_buffered_source_trickle_stall_eof(self):
        """BufferedAudioSource harus EOF saat paket masuk teramat lambat (trickle-stall)."""
        from bot import BufferedAudioSource
        import time as _time
        class TrickleSlowAudio(discord.AudioSource):
            def __init__(self):
                self.count = 0
            def read(self):
                self.count += 1
                _time.sleep(0.35)
                return b'\x05' * 3840

        buf = BufferedAudioSource(TrickleSlowAudio(), buffer_size=2)
        buf.ready_event.set()
        eof = False
        start = _time.monotonic()
        while _time.monotonic() - start < 10.0:
            frame = buf.read()
            if frame == b'':
                eof = True
                break
        self.assertTrue(eof, 'Trickle stream tidak memicu stall EOF')
        buf.cleanup()

    def test_skip_armed_latch_does_not_poison_natural_finish(self):
        """_skip_armed yang stale tidak boleh menggagalkan advance saat track selesai alami."""
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 88804
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        guild.voice_client = vc

        state = QueueState()
        t1 = Track('t1', 'https://example.com/1', 'user')
        t2 = Track('t2', 'https://example.com/2', 'user')
        state.queue.extend([t1, t2])
        bot.states[guild.id] = state

        async def scenario():
            after_cb = None
            def fake_play(src, after=None, **kwargs):
                nonlocal after_cb
                after_cb = after
            vc.play.side_effect = fake_play

            with patch('bot.extract', return_value={'url': 'http://cdn/audio'}), \
                 patch('bot.source_for', return_value=MagicMock()), \
                 patch.object(bot, 'refresh', new=AsyncMock()):
                await bot.advance(guild)
                self.assertEqual(state.current.title, 't1')
                self.assertFalse(state._skip_armed)

                # Simulasikan latch stale ter-set True karena race condition
                state._skip_armed = True

                # t1 selesai alami
                after_cb(None)
                await asyncio.sleep(0.05)

                self.assertFalse(state._skip_armed)
                self.assertEqual(state.current.title, 't2')

        asyncio.run(scenario())

    def test_stop_player_only_arms_skip_when_playing(self):
        """_stop_player hanya men-set _skip_armed jika voice client sedang aktif."""
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 88805
        vc = MagicMock()
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        guild.voice_client = vc

        state = QueueState()
        bot.states[guild.id] = state

        asyncio.run(bot._stop_player(guild))
        self.assertFalse(state._skip_armed)
        vc.stop.assert_not_called()


class ConcurrencyAndLifecycleTests(unittest.TestCase):
    def test_button_skip_debounce(self):
        """Spam klik skip dalam <500ms ditolak debounce dan tidak memicu advance ganda."""
        bot = MusicBot()
        guild = MagicMock(id=123)
        vc = MagicMock()
        vc.channel.id = 1
        vc.is_playing.return_value = True
        vc.is_paused.return_value = False
        guild.voice_client = vc

        state = QueueState()
        bot.states[123] = state

        view = MusicPanel(bot)
        interaction = MagicMock(guild=guild)
        interaction.user.voice.channel.id = 1
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        with patch.object(bot, '_stop_player', new=AsyncMock()), \
             patch.object(bot, 'advance', new=AsyncMock()) as mock_advance:
            with patch.object(view, 'guard', new=AsyncMock(return_value=True)):
                asyncio.run(view.skip.callback(interaction))
                mock_advance.assert_called_once()
                mock_advance.reset_mock()
                interaction.followup.send.reset_mock()

                # Klik kedua <500ms
                asyncio.run(view.skip.callback(interaction))
                mock_advance.assert_not_called()
                msg = interaction.followup.send.call_args[0][0]
                self.assertIn('tunggu sebentar', msg.lower())

    def test_button_pause_debounce(self):
        """Spam klik pause dalam <500ms ditolak debounce dan tidak memicu toggle ganda."""
        bot = MusicBot()
        guild = MagicMock(id=124)
        vc = MagicMock()
        vc.channel.id = 1
        vc.is_playing.return_value = True
        vc.is_paused.return_value = False
        guild.voice_client = vc

        state = QueueState()
        bot.states[124] = state

        view = MusicPanel(bot)
        interaction = MagicMock(guild=guild)
        interaction.user.voice.channel.id = 1
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        with patch.object(bot, 'refresh', new=AsyncMock()):
            with patch.object(view, 'guard', new=AsyncMock(return_value=True)):
                asyncio.run(view.pause.callback(interaction))
                vc.pause.assert_called_once()
                vc.pause.reset_mock()
                interaction.followup.send.reset_mock()

                # Klik kedua <500ms
                asyncio.run(view.pause.callback(interaction))
                vc.pause.assert_not_called()
                vc.resume.assert_not_called()
                msg = interaction.followup.send.call_args[0][0]
                self.assertIn('tunggu sebentar', msg.lower())

    def test_advance_single_flight_lock(self):
        """advance() tidak berjalan paralel jika _advance_lock sedang dipegang."""
        bot = MusicBot()
        guild = MagicMock(id=125)
        vc = MagicMock(is_connected=lambda: True)
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        guild.voice_client = vc

        state = QueueState()
        state.queue.append(Track('song1', 'https://youtube.com/watch?v=1', 'u'))
        bot.states[125] = state

        async def scenario():
            await state._advance_lock.acquire()
            try:
                with patch('bot.extract') as mock_extract:
                    await bot.advance(guild)
                    mock_extract.assert_not_called()
            finally:
                state._advance_lock.release()

        asyncio.run(scenario())

    def test_help_defers_safely(self):
        """Perintah /help melakukan deferral aman terlebih dahulu."""
        bot = MusicBot()
        interaction = MagicMock()
        is_done = False
        def fake_defer(**kw):
            nonlocal is_done
            is_done = True
        interaction.response.defer = AsyncMock(side_effect=fake_defer)
        interaction.response.is_done = MagicMock(side_effect=lambda: is_done)
        interaction.followup.send = AsyncMock()

        asyncio.run(bot.cmd_help(interaction))
        interaction.response.defer.assert_called_once_with(ephemeral=True)
        interaction.followup.send.assert_called_once()

    def test_guard_defers_before_voice_connect(self):
        """guard() melakukan deferral aman sebelum connect voice channel."""
        bot = MusicBot()
        view = MusicPanel(bot)
        interaction = MagicMock()
        interaction.guild.voice_client = None
        interaction.user.voice.channel = MagicMock()
        interaction.response.is_done.return_value = False
        interaction.response.defer = AsyncMock()
        interaction.user.voice.channel.connect = AsyncMock()

        with patch('bot.log'):
            asyncio.run(view.guard(interaction, require_voice=True))
        interaction.response.defer.assert_called_once_with(ephemeral=True)
        interaction.user.voice.channel.connect.assert_called_once()

    def test_guard_cleans_up_stale_panel_message(self):
        """guard() mendeteksi dan menghapus panel lama yang stale agar tidak split-brain."""
        bot = MusicBot()
        view = MusicPanel(bot)
        interaction = MagicMock()
        interaction.guild.id = 126
        vc = MagicMock()
        vc.channel.id = 1
        interaction.guild.voice_client = vc
        interaction.user.voice.channel.id = 1

        active_msg = MagicMock(id=100)
        stale_msg = MagicMock(id=90)
        stale_msg.delete = AsyncMock()

        state = QueueState(message=active_msg)
        bot.states[126] = state

        interaction.message = stale_msg
        interaction.response.is_done.return_value = True
        interaction.followup.send = AsyncMock()

        res = asyncio.run(view.guard(interaction))
        self.assertFalse(res)
        stale_msg.delete.assert_called_once()
        self.assertEqual(state.message.id, 100)

    def test_panel_stop_and_bot_close_lifecycle(self):
        """view.stop() dapat dipanggil pada persistent view dan dibersihkan saat close()."""
        bot = MusicBot()
        panel = MusicPanel(bot)
        self.assertTrue(callable(panel.stop), 'panel.stop harus method View.stop, bukan Button')
        bot.add_view(panel)
        bot._panel_view = panel
        self.assertIn(panel, bot.persistent_views)

        with patch('bot.dump_runtime_state_offline'), patch.object(MusicBot.__bases__[0], 'close', new=AsyncMock()):
            asyncio.run(bot.close())

        self.assertNotIn(panel, bot.persistent_views)

    def test_search_modal_lifecycle(self):
        """SearchModal memiliki timeout eksplisit 60 detik dan stop() saat submit."""
        bot = MusicBot()
        modal = SearchModal(bot)
        self.assertEqual(modal.timeout, 60)
        self.assertTrue(callable(modal.stop))


class AFKGuardTests(unittest.TestCase):
    def test_afk_timer_starts_and_pauses_when_human_members_zero(self):
        """AFK Guard: Timer aktif & audio dipause saat human members = 0."""
        bot = MusicBot()
        bot_user = MagicMock(id=999)
        bot._connection.user = bot_user
        guild = MagicMock(id=112233, name='GuildAFK')
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = True
        vc.is_paused.return_value = False
        channel = MagicMock()
        bot_member = MagicMock(bot=True, id=999)
        channel.members = [bot_member]
        vc.channel = channel
        guild.voice_client = vc

        member = MagicMock(id=123, bot=False, guild=guild)
        before = MagicMock(channel=channel)
        after = MagicMock(channel=None)

        async def run_test():
            await bot.on_voice_state_update(member, before, after)
            state = bot.states[guild.id]
            self.assertIsNotNone(state.afk_task)
            self.assertFalse(state.afk_task.done())
            self.assertTrue(state.afk_paused)
            vc.pause.assert_called_once()
            state.afk_task.cancel()

        with patch('bot.dump_runtime_state'):
            asyncio.run(run_test())

    def test_afk_timer_idempotent_no_duplicate_task(self):
        """Timer AFK tidak dibuat berulang kali jika sudah ada timer berjalan."""
        bot = MusicBot()
        bot_user = MagicMock(id=999)
        bot._connection.user = bot_user
        guild = MagicMock(id=112234, name='GuildAFK')
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = True
        vc.is_paused.return_value = False
        channel = MagicMock()
        bot_member = MagicMock(bot=True, id=999)
        channel.members = [bot_member]
        vc.channel = channel
        guild.voice_client = vc

        state = QueueState()
        mock_task = MagicMock()
        mock_task.done.return_value = False
        state.afk_task = state.empty_task = mock_task
        bot.states[guild.id] = state

        member = MagicMock(id=124, bot=False, guild=guild)
        before = MagicMock(channel=channel)
        after = MagicMock(channel=None)

        async def run_test():
            with patch('asyncio.get_running_loop') as mock_loop:
                await bot.on_voice_state_update(member, before, after)
                mock_loop.return_value.create_task.assert_not_called()
                self.assertIs(state.afk_task, mock_task)

        with patch('bot.dump_runtime_state'):
            asyncio.run(run_test())

    def test_afk_timer_cancelled_and_resumed_when_human_joins(self):
        """AFK Guard: Timer dibatalkan & audio di-resume saat human member masuk kembali."""
        bot = MusicBot()
        bot_user = MagicMock(id=999)
        bot._connection.user = bot_user
        guild = MagicMock(id=112233, name='GuildAFK')
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = True
        channel = MagicMock()
        bot_member = MagicMock(bot=True, id=999)
        human_member = MagicMock(bot=False, id=123, guild=guild)
        channel.members = [bot_member, human_member]
        vc.channel = channel
        guild.voice_client = vc

        state = QueueState()
        mock_task = MagicMock()
        mock_task.done.return_value = False
        state.afk_task = state.empty_task = mock_task
        state.afk_paused = True
        bot.states[guild.id] = state

        before = MagicMock(channel=None)
        after = MagicMock(channel=channel)

        async def run_test():
            await bot.on_voice_state_update(human_member, before, after)
            mock_task.cancel.assert_called_once()
            self.assertIsNone(state.afk_task)
            self.assertFalse(state.afk_paused)
            vc.resume.assert_called_once()

        with patch('bot.dump_runtime_state'):
            asyncio.run(run_test())

    def test_afk_timer_cancelled_no_resume_if_not_afk_paused(self):
        """Jika lagu dipause manual oleh user, masuknya human tidak memicu auto-resume."""
        bot = MusicBot()
        bot_user = MagicMock(id=999)
        bot._connection.user = bot_user
        guild = MagicMock(id=112235, name='GuildAFK')
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = True
        channel = MagicMock()
        bot_member = MagicMock(bot=True, id=999)
        human_member = MagicMock(bot=False, id=123, guild=guild)
        channel.members = [bot_member, human_member]
        vc.channel = channel
        guild.voice_client = vc

        state = QueueState()
        mock_task = MagicMock()
        mock_task.done.return_value = False
        state.afk_task = state.empty_task = mock_task
        state.afk_paused = False
        bot.states[guild.id] = state

        before = MagicMock(channel=None)
        after = MagicMock(channel=channel)

        async def run_test():
            await bot.on_voice_state_update(human_member, before, after)
            mock_task.cancel.assert_called_once()
            self.assertIsNone(state.afk_task)
            self.assertFalse(state.afk_paused)
            vc.resume.assert_not_called()

        with patch('bot.dump_runtime_state'):
            asyncio.run(run_test())

    def test_afk_disconnect_called_when_timer_expires(self):
        """AFK Guard: Disconnect terpanggil saat timer selesai dan channel tetap kosong."""
        bot = MusicBot()
        guild = MagicMock(id=112233, name='GuildAFK')
        vc = MagicMock()
        vc.channel = MagicMock()
        vc.channel.members = [MagicMock(bot=True, id=999)]
        guild.voice_client = vc
        state = QueueState()
        bot.states[guild.id] = state

        async def run_test():
            with patch.object(bot, 'quit_voice', new=AsyncMock()) as mock_quit:
                with patch('bot.log') as mock_log:
                    await bot._afk_disconnect(guild, state.generation, timeout=0.01)
                    mock_quit.assert_called_once_with(guild, clear_queue=False)
                    mock_log.info.assert_called_once()
                    log_text = str(mock_log.info.call_args)
                    self.assertIn('AFK timeout: room kosong', log_text)

        asyncio.run(run_test())

    def test_afk_disconnect_aborted_if_human_joined_before_timeout(self):
        """Jika human masuk sebelum timer timeout berakhir, bot tidak disconnect."""
        bot = MusicBot()
        guild = MagicMock(id=112236, name='GuildAFK')
        vc = MagicMock()
        vc.channel = MagicMock()
        vc.channel.members = [MagicMock(bot=True, id=999), MagicMock(bot=False, id=101)]
        guild.voice_client = vc
        state = QueueState()
        bot.states[guild.id] = state

        async def run_test():
            with patch.object(bot, 'quit_voice', new=AsyncMock()) as mock_quit:
                await bot._afk_disconnect(guild, state.generation, timeout=0.01)
                mock_quit.assert_not_called()

        asyncio.run(run_test())

    def test_afk_disconnect_aborted_if_generation_changed(self):
        """Jika generation state berubah saat timer berjalan, disconnect dibatalkan."""
        bot = MusicBot()
        guild = MagicMock(id=112237, name='GuildAFK')
        vc = MagicMock()
        vc.channel = MagicMock()
        vc.channel.members = [MagicMock(bot=True, id=999)]
        guild.voice_client = vc
        state = QueueState()
        state.generation = 5
        bot.states[guild.id] = state

        async def run_test():
            with patch.object(bot, 'quit_voice', new=AsyncMock()) as mock_quit:
                await bot._afk_disconnect(guild, generation=4, timeout=0.01)
                mock_quit.assert_not_called()

        asyncio.run(run_test())

    def test_afk_bot_moved_to_empty_channel(self):
        """Bot dipindahkan ke voice channel kosong mengaktifkan timer AFK dan pause audio."""
        bot = MusicBot()
        bot_user = MagicMock(id=999)
        bot._connection.user = bot_user
        guild = MagicMock(id=112233, name='GuildAFK')
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = True
        channel_old = MagicMock(id=1)
        channel_new = MagicMock(id=2)
        bot_member = MagicMock(bot=True, id=999, guild=guild)
        channel_new.members = [bot_member]
        vc.channel = channel_new
        guild.voice_client = vc

        before = MagicMock(channel=channel_old)
        after = MagicMock(channel=channel_new)

        async def run_test():
            await bot.on_voice_state_update(bot_member, before, after)
            state = bot.states[guild.id]
            self.assertIsNotNone(state.afk_task)
            self.assertFalse(state.afk_task.done())
            self.assertTrue(state.afk_paused)
            vc.pause.assert_called_once()
            state.afk_task.cancel()

        with patch('bot.dump_runtime_state'):
            asyncio.run(run_test())

    def test_afk_bot_moved_to_channel_with_humans(self):
        """Bot dipindahkan ke voice channel yang ada manusia membatalkan timer AFK dan resume audio."""
        bot = MusicBot()
        bot_user = MagicMock(id=999)
        bot._connection.user = bot_user
        guild = MagicMock(id=112233, name='GuildAFK')
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = True
        channel_old = MagicMock(id=1)
        channel_new = MagicMock(id=2)
        bot_member = MagicMock(bot=True, id=999, guild=guild)
        human_member = MagicMock(bot=False, id=123, guild=guild)
        channel_new.members = [bot_member, human_member]
        vc.channel = channel_new
        guild.voice_client = vc

        state = QueueState()
        mock_task = MagicMock()
        mock_task.done.return_value = False
        state.afk_task = state.empty_task = mock_task
        state.afk_paused = True
        bot.states[guild.id] = state

        before = MagicMock(channel=channel_old)
        after = MagicMock(channel=channel_new)

        async def run_test():
            await bot.on_voice_state_update(bot_member, before, after)
            mock_task.cancel.assert_called_once()
            self.assertIsNone(state.afk_task)
            self.assertFalse(state.afk_paused)
            vc.resume.assert_called_once()

        with patch('bot.dump_runtime_state'):
            asyncio.run(run_test())

    def test_afk_bot_disconnected_cleans_up_afk_state(self):
        """Bot terputus dari voice membatalkan afk_task dan reset afk_paused."""
        bot = MusicBot()
        bot_user = MagicMock(id=999)
        bot._connection.user = bot_user
        guild = MagicMock(id=112238, name='GuildAFK')
        guild.voice_client = None
        bot_member = MagicMock(id=999, bot=True, guild=guild)

        state = QueueState()
        mock_task = MagicMock()
        mock_task.done.return_value = False
        state.afk_task = state.empty_task = mock_task
        state.afk_paused = True
        bot.states[guild.id] = state

        before = MagicMock(channel=MagicMock())
        after = MagicMock(channel=None)

        async def run_test():
            with patch.object(bot, 'quit_voice', new=AsyncMock()), patch('asyncio.sleep', new=AsyncMock()):
                await bot.on_voice_state_update(bot_member, before, after)
                mock_task.cancel.assert_called_once()
                self.assertIsNone(state.afk_task)
                self.assertFalse(state.afk_paused)

        with patch('bot.dump_runtime_state'):
            asyncio.run(run_test())

    def test_afk_get_timeout_env(self):
        """get_afk_timeout mengembalikan nilai dari environment variable atau fallback 180s."""
        with patch.dict(os.environ, {'AFK_TIMEOUT_SECONDS': '45'}):
            self.assertEqual(get_afk_timeout(), 45.0)
        with patch.dict(os.environ, {'AFK_TIMEOUT_SECONDS': 'invalid'}):
            self.assertEqual(get_afk_timeout(), 180.0)
        with patch.dict(os.environ, {'AFK_TIMEOUT_SECONDS': '-10'}):
            self.assertEqual(get_afk_timeout(), 180.0)


class PersistentQueueTests(unittest.TestCase):
    def test_persistent_queue_save_and_restore_guild_state(self):
        """Persistent Queue: Simpan queue ke JSON saat ada antrean & muat kembali ke GuildState."""
        bot = MusicBot()
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, 'queue_state.json')
            bot._queue_state_file = queue_file

            guild_id = 99999
            state = GuildState()
            state.current = Track('Lagu Aktif', 'https://youtube.com/watch?v=active', 'User1', 180, '3m 0s', 'Artis 1')
            state.queue.append(Track('Lagu Antri 1', 'https://youtube.com/watch?v=q1', 'User2', 200, '3m 20s', 'Artis 2'))
            state.queue.append(Track('Lagu Antri 2', 'https://youtube.com/watch?v=q2', 'User3', 240, '4m 0s', 'Artis 3'))
            bot.states[guild_id] = state

            # 1. Simpan persistent queue
            bot._save_persistent_queue()
            self.assertTrue(os.path.exists(queue_file))

            # Verifikasi isi JSON
            with open(queue_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.assertIn(str(guild_id), data)
            self.assertEqual(data[str(guild_id)]['current']['title'], 'Lagu Aktif')
            self.assertEqual(len(data[str(guild_id)]['queue']), 2)
            self.assertEqual(data[str(guild_id)]['queue'][0]['title'], 'Lagu Antri 1')

            # 2. Muat kembali ke GuildState bot baru
            bot2 = MusicBot()
            bot2._queue_state_file = queue_file
            bot2._restore_persistent_queue()

            # Verifikasi dipulihkan ke GuildState
            self.assertIn(guild_id, bot2.states)
            restored_state = bot2.states[guild_id]
            self.assertIsInstance(restored_state, GuildState)
            self.assertIsNotNone(restored_state.current)
            self.assertEqual(restored_state.current.title, 'Lagu Aktif')
            self.assertEqual(restored_state.current.url, 'https://youtube.com/watch?v=active')
            self.assertEqual(restored_state.current.requester, 'User1')
            self.assertEqual(restored_state.current.duration, 180)
            self.assertEqual(len(restored_state.queue), 2)
            self.assertEqual(restored_state.queue[0].title, 'Lagu Antri 1')
            self.assertEqual(restored_state.queue[1].title, 'Lagu Antri 2')

            # Berkas harus dihapus/dibersihkan setelah restore berhasil
            self.assertFalse(os.path.exists(queue_file))

    def test_persistent_queue_corrupt_json_fallback(self):
        """Persistent Queue: Handling JSON corrupt ditangani anggun tanpa crash dan berkas dibersihkan."""
        bot = MusicBot()
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, 'corrupt_queue.json')
            bot._queue_state_file = queue_file

            with open(queue_file, 'w', encoding='utf-8') as f:
                f.write('{this is definitely not valid json:::')

            bot._restore_persistent_queue()

            self.assertFalse(os.path.exists(queue_file))
            self.assertEqual(len(bot.states), 0)

    def test_persistent_queue_missing_file_fallback(self):
        """Persistent Queue: Handling berkas tidak ada tidak menimbulkan error."""
        bot = MusicBot()
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, 'nonexistent.json')
            bot._queue_state_file = queue_file

            bot._restore_persistent_queue()
            self.assertEqual(len(bot.states), 0)

    def test_persistent_queue_invalid_json_type(self):
        """File JSON dengan root bukan dict (misal list/string) ditangani aman."""
        bot = MusicBot()
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, 'list_queue.json')
            bot._queue_state_file = queue_file

            with open(queue_file, 'w', encoding='utf-8') as f:
                json.dump([1, 2, 3], f)

            bot._restore_persistent_queue()
            self.assertFalse(os.path.exists(queue_file))
            self.assertEqual(len(bot.states), 0)

    def test_persistent_queue_skips_malformed_tracks(self):
        """Track yang tidak memiliki title atau url diskip tanpa membatalkan track lainnya."""
        bot = MusicBot()
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, 'queue_state.json')
            bot._queue_state_file = queue_file
            payload = {
                '55555': {
                    'current': {'title': '', 'url': ''},
                    'queue': [
                        {'title': 'Valid Track', 'url': 'https://youtube.com/watch?v=valid'},
                        {'corrupt': 'data'},
                        'not-a-dict',
                    ]
                }
            }
            with open(queue_file, 'w', encoding='utf-8') as f:
                json.dump(payload, f)

            bot._restore_persistent_queue()
            self.assertIn(55555, bot.states)
            state = bot.states[55555]
            self.assertIsNone(state.current)
            self.assertEqual(len(state.queue), 1)
            self.assertEqual(state.queue[0].title, 'Valid Track')

    def test_persistent_queue_preserves_existing_in_memory_current_track(self):
        """Jika bot sudah memiliki track aktif di memory, restore tidak menimpa state.current."""
        bot = MusicBot()
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, 'queue_state.json')
            bot._queue_state_file = queue_file
            gid = 88888
            existing_track = Track('Mem Current', 'https://youtube.com/watch?v=mem', 'user')
            bot.states[gid] = GuildState(current=existing_track)

            payload = {
                str(gid): {
                    'current': {'title': 'Disk Current', 'url': 'https://youtube.com/watch?v=disk'},
                    'queue': [{'title': 'Queued 1', 'url': 'https://youtube.com/watch?v=q1'}]
                }
            }
            with open(queue_file, 'w', encoding='utf-8') as f:
                json.dump(payload, f)

            bot._restore_persistent_queue()
            state = bot.states[gid]
            self.assertEqual(state.current.title, 'Mem Current')
            self.assertEqual(len(state.queue), 1)
            self.assertEqual(state.queue[0].title, 'Queued 1')

    def test_persistent_queue_empty_queue_removes_file(self):
        """Saat antrean kosong, penyimpanan membersihkan berkas agar tidak menyimpan sampah."""
        bot = MusicBot()
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, 'queue_state.json')
            bot._queue_state_file = queue_file

            with open(queue_file, 'w', encoding='utf-8') as f:
                json.dump({'123': {'current': None, 'queue': []}}, f)
            self.assertTrue(os.path.exists(queue_file))

            bot.states.clear()
            bot._save_persistent_queue()
            self.assertFalse(os.path.exists(queue_file))

    def test_persistent_queue_multi_guild(self):
        """Menyimpan dan memulihkan antrean untuk beberapa guild sekaligus."""
        bot = MusicBot()
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, 'multi_queue.json')
            bot._queue_state_file = queue_file

            s1 = GuildState()
            s1.current = Track('G1 Track', 'https://youtube.com/watch?v=g1', 'user1')
            s2 = GuildState()
            s2.queue.append(Track('G2 Queue', 'https://youtube.com/watch?v=g2', 'user2'))
            bot.states[101] = s1
            bot.states[102] = s2

            bot._save_persistent_queue()

            bot2 = MusicBot()
            bot2._queue_state_file = queue_file
            bot2._restore_persistent_queue()

            self.assertIn(101, bot2.states)
            self.assertIn(102, bot2.states)
            self.assertEqual(bot2.states[101].current.title, 'G1 Track')
            self.assertEqual(len(bot2.states[102].queue), 1)
            self.assertEqual(bot2.states[102].queue[0].title, 'G2 Queue')


if __name__ == '__main__':
    unittest.main()
