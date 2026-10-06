import asyncio
import json
import os
import signal
import tempfile
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

import discord

import bot as bot_module
from bot import (MusicBot, MusicPanel, Track, QueueState, GuildState, get_afk_timeout,
                 DEFAULT_VOLUME, get_default_volume,
                 build_recommendation_queries, _clean_seed_title, fetch_recommendations,
                 extract_track, extract_tracks, source_for, _cookies_file, _with_cookies, SearchModal,
                 extract_video_id, build_mix_url, fetch_youtube_mix, MIX_RESULT_LIMIT)


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

    def test_source_for_ffmpeg_options_no_reconnect_at_eof(self):
        class DummyAudio(discord.AudioSource):
            def read(self): return b''
        with patch('bot.discord.FFmpegPCMAudio', return_value=DummyAudio()) as mock_ffmpeg:
            source_for({'url': 'https://example.com/audio'})
            mock_ffmpeg.assert_called_once()
            _, kwargs = mock_ffmpeg.call_args
            before_options = kwargs.get('before_options', '')
            self.assertIn('-reconnect 1', before_options)
            self.assertIn('-reconnect_streamed 1', before_options)
            self.assertNotIn('-reconnect_at_eof', before_options)
            self.assertIn('-reconnect_on_network_error 1', before_options)

    def test_default_volume_is_fifty_percent(self):
        state = QueueState()
        self.assertEqual(state.volume, 0.5)
        self.assertEqual(DEFAULT_VOLUME, 0.5)
        self.assertEqual(get_default_volume(), 0.5)
        class DummyAudio(discord.AudioSource):
            def read(self): return b''
        with patch('bot.discord.FFmpegPCMAudio', return_value=DummyAudio()):
            source = source_for({'url': 'https://example.com/audio'})
            self.assertIsInstance(source, discord.PCMVolumeTransformer)
            self.assertEqual(source.volume, 0.5)

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
            asyncio.run(bot.quit_voice(guild, clear_queue=True, delete_panel=False))
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

    def test_quit_voice_clears_cache_when_clear_queue_true(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 99997
        guild.voice_client = None
        state = QueueState()
        bot.states[99997] = state

        with patch('bot.clear_cache') as mock_clear:
            asyncio.run(bot.quit_voice(guild, clear_queue=True))
            mock_clear.assert_called_once()

    def test_quit_voice_does_not_clear_cache_when_clear_queue_false(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 99996
        guild.voice_client = None
        state = QueueState()
        bot.states[99996] = state

        with patch('bot.clear_cache') as mock_clear:
            asyncio.run(bot.quit_voice(guild, clear_queue=False))
            mock_clear.assert_not_called()

    def test_quit_voice_clear_cache_handles_exception_gracefully(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 99995
        guild.voice_client = None
        state = QueueState()
        bot.states[99995] = state

        with patch('bot.clear_cache', side_effect=RuntimeError('disk failure')):
            # Should not raise
            asyncio.run(bot.quit_voice(guild, clear_queue=True))

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

    def test_advance_queue_loop_replays_single_track_when_queue_empty(self):
        """Mode loop 'queue' mengulang state.current saat antrian kosong (1 lagu)."""
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 88005
        guild.name = 'QueueLoopGuild'
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        vc.channel.bitrate = 96000
        guild.voice_client = vc

        state = QueueState()
        track = Track('single_loop', 'https://example.com/single', 'user')
        state.current = track
        state.loop_mode = 'queue'
        bot.states[88005] = state

        announced = []
        with patch('bot.extract', return_value={'url': 'https://cdn/audio'}):
            with patch('bot.source_for', return_value=MagicMock()):
                with patch.object(bot, 'refresh', new=AsyncMock()):
                    with patch.object(bot, '_announce_now_playing', new=AsyncMock(
                            side_effect=lambda g, t: announced.append(t))):
                        asyncio.run(bot.advance(guild))
        vc.play.assert_called_once()
        self.assertIs(state.current, track)
        self.assertEqual(len(state.queue), 0)
        self.assertEqual(announced, [track])

    def test_advance_queue_loop_with_multiple_tracks_rotates(self):
        """Mode loop 'queue' memutar track berikutnya dan mengembalikan current ke queue."""
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 88006
        guild.name = 'QueueLoopMultiGuild'
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        vc.channel.bitrate = 96000
        guild.voice_client = vc

        state = QueueState()
        track1 = Track('track1', 'https://example.com/1', 'user')
        track2 = Track('track2', 'https://example.com/2', 'user')
        state.current = track1
        state.queue.append(track2)
        state.loop_mode = 'queue'
        bot.states[88006] = state

        with patch('bot.extract', return_value={'url': 'https://cdn/audio'}):
            with patch('bot.source_for', return_value=MagicMock()):
                with patch.object(bot, 'refresh', new=AsyncMock()):
                    asyncio.run(bot.advance(guild))
        vc.play.assert_called_once()
        self.assertIs(state.current, track2)
        self.assertEqual(list(state.queue), [track1])

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


class AutoplayRecommendationTests(unittest.TestCase):
    """Rekomendasi lagu saat antrian/playlist habis (berbasis lagu sebelumnya)."""

    def test_clean_seed_title_strips_noise(self):
        self.assertEqual(
            _clean_seed_title('Song A (Official Music Video)'),
            'Song A')
        self.assertEqual(_clean_seed_title('Song B [Lyric Video] HD'), 'Song B')
        self.assertEqual(_clean_seed_title(None), '')
        self.assertEqual(_clean_seed_title(''), '')

    def test_build_queries_uses_latest_history_first(self):
        queries = build_recommendation_queries(
            ['A', 'B', 'C', 'D'], current_title='E')
        self.assertEqual(len(queries), 3)
        self.assertIn('E', queries[0])
        self.assertIn('D', queries[1])
        self.assertIn('C', queries[2])
        self.assertTrue(all(q.startswith('ytsearch5:') for q in queries))

    def test_build_queries_dedups_seeds(self):
        queries = build_recommendation_queries(['Same', 'Same'], 'Same')
        self.assertEqual(len(queries), 1)

    def test_fetch_recommendations_filters_already_played(self):
        played = {'https://youtube.com/watch?v=played'}
        with patch('bot._fetch_metadata') as fetch:
            fetch.return_value = {
                'entries': [
                    {'title': 'Sudah diputar', 'url': 'https://youtube.com/watch?v=played'},
                    {'title': 'Lagu Baru', 'url': 'https://youtube.com/watch?v=new1'},
                    {'title': 'Lagu Baru 2', 'url': 'https://youtube.com/watch?v=new2'},
                ]
            }
            recs = asyncio.run(fetch_recommendations(['Seed Lagu'], played))
        self.assertEqual([t.title for t in recs], ['Lagu Baru', 'Lagu Baru 2'])
        self.assertTrue(all(t.requester == 'AutoPlay' for t in recs))

    def test_fetch_recommendations_falls_back_to_older_seed(self):
        calls = []

        def fake_fetch(target):
            calls.append(target)
            if len(calls) == 1:
                raise bot_module.yt_dlp.utils.DownloadError('boom')
            return {'entries': [{'title': 'Hasil Cadangan',
                                 'url': 'https://youtube.com/watch?v=fallback'}]}

        with patch('bot._fetch_metadata', side_effect=fake_fetch):
            recs = asyncio.run(fetch_recommendations(['Seed Baru', 'Seed Lama'], set()))
        self.assertEqual([t.title for t in recs], ['Hasil Cadangan'])
        self.assertGreaterEqual(len(calls), 2)

    def test_advance_autoplay_picks_recommendation_and_avoids_repeat(self):
        """Antrian habis + AutoPlay aktif: ambil rekomendasi baru, bukan ulang lagu lama."""
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 88901
        guild.name = 'AutoGuild'
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        vc.channel.bitrate = 96000
        guild.voice_client = vc

        state = QueueState()
        state.autoplay = True
        state.current = Track('Lagu Sekarang', 'https://youtube.com/watch?v=cur', 'u')
        state.history.append(Track('Lagu Lama', 'https://youtube.com/watch?v=old', 'u'))
        bot.states[guild.id] = state

        rec = Track('Rekomendasi Baru', 'https://youtube.com/watch?v=rec', 'AutoPlay')
        with patch('bot.fetch_recommendations', new=AsyncMock(return_value=[rec])) as mock_rec, \
             patch('bot.extract', return_value={'url': 'https://cdn/audio'}), \
             patch('bot.source_for', return_value=MagicMock()), \
             patch.object(bot, 'refresh', new=AsyncMock()):
            asyncio.run(bot.advance(guild))

        mock_rec.assert_awaited_once()
        # Seed memuat riwayat + lagu sekarang.
        seeds, played = mock_rec.await_args.args[0], mock_rec.await_args.args[1]
        self.assertIn('Lagu Sekarang', seeds)
        self.assertIn('Lagu Lama', seeds)
        self.assertIn('https://youtube.com/watch?v=cur', played)
        self.assertEqual(state.current.title, 'Rekomendasi Baru')

    def test_advance_autoplay_stops_when_no_new_recommendation(self):
        """Bila semua rekomendasi sudah pernah diputar, bot berhenti (tidak mengulang)."""
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 88902
        guild.name = 'AutoGuild2'
        vc = MagicMock()
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        guild.voice_client = vc

        state = QueueState()
        state.autoplay = True
        state.current = Track('Lagu', 'https://youtube.com/watch?v=x', 'u')
        bot.states[guild.id] = state

        # Kandidat hanya berisi URL yang sudah diputar (lagu sekarang).
        dup = Track('Duplikat', 'https://youtube.com/watch?v=x', 'AutoPlay')
        with patch('bot.fetch_recommendations', new=AsyncMock(return_value=[dup])), \
             patch('bot.extract') as mock_extract, \
             patch.object(bot, 'refresh', new=AsyncMock()):
            asyncio.run(bot.advance(guild))

        mock_extract.assert_not_called()
        vc.play.assert_not_called()


class YouTubeMixTests(unittest.TestCase):
    """KAN-5: YouTube Mix (radio `list=RD`) — helper + integrasi AutoPlay.

    Semua tes mem-mock `yt_dlp.YoutubeDL` / `bot._fetch_metadata` sehingga
    tidak pernah menyentuh jaringan nyata.
    """

    # ID 11 karakter yang valid untuk helper (regex fullmatch).
    _VIDEO_ID = 'dQw4w9WgXcQ'
    _SEED_URL = 'https://youtube.com/watch?v=dQw4w9WgXcQ'

    def test_extract_video_id_variants(self):
        """Semua bentuk URL YouTube yang didukung mengembalikan videoId yang sama."""
        vid = self._VIDEO_ID
        cases = {
            f'https://www.youtube.com/watch?v={vid}': vid,
            f'https://youtube.com/watch?v={vid}': vid,
            f'https://youtu.be/{vid}': vid,
            f'https://www.youtube.com/shorts/{vid}': vid,
            f'https://www.youtube.com/embed/{vid}': vid,
            f'https://music.youtube.com/watch?v={vid}': vid,
            # Parameter list=/start_radio= harus diabaikan.
            f'https://www.youtube.com/watch?v={vid}&list=RD{vid}&start_radio=1': vid,
        }
        for url, expected in cases.items():
            self.assertEqual(extract_video_id(url), expected, f'gagal untuk {url}')

    def test_extract_video_id_invalid_returns_none(self):
        self.assertIsNone(extract_video_id('bukan url'))
        self.assertIsNone(extract_video_id(''))
        self.assertIsNone(extract_video_id(None))
        # ID bukan 11 karakter / host non-YouTube.
        self.assertIsNone(extract_video_id('https://youtube.com/watch?v=abc'))
        self.assertIsNone(extract_video_id('https://example.com/watch?v=dQw4w9WgXcQ'))

    def test_build_mix_url_format(self):
        self.assertEqual(
            build_mix_url('abc'),
            'https://www.youtube.com/watch?v=abc&list=RDabc&start_radio=1')

    def test_fetch_youtube_mix_parses_entries(self):
        """Entri playlist diubah jadi Track dan `playlistend` wajib dipakai."""
        mock_entries = [
            {'title': f'Song {i}', 'url': f'https://youtube.com/watch?v=s{i}', 'id': f's{i}'}
            for i in range(30)
        ]
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            downloader.return_value.__enter__.return_value.extract_info.return_value = {
                '_type': 'playlist',
                'entries': mock_entries,
            }
            tracks = asyncio.run(fetch_youtube_mix(self._VIDEO_ID))

        self.assertEqual(len(tracks), 30)
        self.assertEqual(tracks[0].title, 'Song 0')
        self.assertEqual(tracks[0].url, 'https://youtube.com/watch?v=s0')
        self.assertEqual(tracks[0].requester, 'AutoPlay')

        # Opsi yt-dlp harus membawa playlistend (hemat waktu) = MIX_RESULT_LIMIT.
        opts = downloader.call_args[0][0]
        self.assertIn('playlistend', opts)
        self.assertEqual(opts['playlistend'], MIX_RESULT_LIMIT)
        # URL yang diekstrak harus bentuk Mix yang benar.
        self.assertEqual(downloader.return_value.__enter__.return_value.extract_info.call_args[0][0],
                         build_mix_url(self._VIDEO_ID))

    def test_fetch_youtube_mix_respects_custom_limit(self):
        """Limit yang diminta harus diteruskan sebagai playlistend."""
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            downloader.return_value.__enter__.return_value.extract_info.return_value = {
                'entries': [{'title': 'S', 'url': 'https://youtube.com/watch?v=s0'}],
            }
            asyncio.run(fetch_youtube_mix(self._VIDEO_ID, limit=7))
        self.assertEqual(downloader.call_args[0][0]['playlistend'], 7)

    def test_fetch_youtube_mix_returns_empty_on_error(self):
        """DownloadError tidak boleh bocor ke pemanggil: hasilnya []."""
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            downloader.return_value.__enter__.return_value.extract_info.side_effect = (
                bot_module.yt_dlp.utils.DownloadError('boom'))
            result = asyncio.run(fetch_youtube_mix(self._VIDEO_ID))
        self.assertEqual(result, [])

    def test_fetch_youtube_mix_empty_video_id_short_circuits(self):
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            self.assertEqual(asyncio.run(fetch_youtube_mix('')), [])
            downloader.assert_not_called()

    def test_fetch_youtube_mix_filters_exclude_urls(self):
        entries = [
            {'title': 'Keep', 'url': 'https://youtube.com/watch?v=keep'},
            {'title': 'Drop', 'url': 'https://youtube.com/watch?v=drop'},
        ]
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            downloader.return_value.__enter__.return_value.extract_info.return_value = {
                'entries': entries,
            }
            tracks = asyncio.run(fetch_youtube_mix(
                self._VIDEO_ID, exclude_urls={'https://youtube.com/watch?v=drop'}))
        self.assertEqual([t.title for t in tracks], ['Keep'])

    def test_fetch_youtube_mix_builds_url_from_id(self):
        """URL Mix dibentuk dari videoId lewat build_mix_url."""
        with patch('bot.yt_dlp.YoutubeDL') as downloader:
            downloader.return_value.__enter__.return_value.extract_info.return_value = {
                'entries': [{'title': 'S', 'url': 'https://youtube.com/watch?v=s0'}],
            }
            asyncio.run(fetch_youtube_mix(self._VIDEO_ID))
        called_url = downloader.return_value.__enter__.return_value.extract_info.call_args[0][0]
        self.assertEqual(called_url, build_mix_url(self._VIDEO_ID))

    def test_fetch_recommendations_prefers_mix_when_seed_urls(self):
        """Ada seed URL valid + Mix menghasilkan track → pakai Mix, bukan pencarian teks."""
        rec = Track('Mix Song', 'https://youtube.com/watch?v=mix00000001', 'AutoPlay')
        with patch('bot.fetch_youtube_mix', new=AsyncMock(return_value=[rec])) as mock_mix, \
             patch('bot._fetch_metadata') as mock_fetch:
            recs = asyncio.run(fetch_recommendations(
                ['Seed Lagu'], set(), seed_urls=[self._SEED_URL]))

        self.assertEqual(recs, [rec])
        mock_mix.assert_awaited_once()
        # videoId dari seed URL diteruskan ke fetch_youtube_mix.
        self.assertEqual(mock_mix.await_args.args[0], self._VIDEO_ID)
        # Jalur teks TIDAK boleh dipakai saat Mix berhasil.
        mock_fetch.assert_not_called()

    def test_fetch_recommendations_falls_back_to_text_when_mix_empty(self):
        """Mix kosong → fallback ke pencarian teks lama tetap menghasilkan kandidat."""
        with patch('bot.fetch_youtube_mix', new=AsyncMock(return_value=[])) as mock_mix, \
             patch('bot._fetch_metadata') as mock_fetch:
            mock_fetch.return_value = {
                'entries': [{'title': 'Hasil Teks',
                             'url': 'https://youtube.com/watch?v=text0000001'}],
            }
            recs = asyncio.run(fetch_recommendations(
                ['Seed Lagu'], set(), seed_urls=[self._SEED_URL]))

        self.assertEqual([t.title for t in recs], ['Hasil Teks'])
        mock_mix.assert_awaited_once()
        mock_fetch.assert_called()

    def test_fetch_recommendations_skips_invalid_seed_url(self):
        """Seed URL tanpa videoId valid → Mix dilewati, langsung fallback teks."""
        with patch('bot.fetch_youtube_mix', new=AsyncMock(return_value=[])) as mock_mix, \
             patch('bot._fetch_metadata') as mock_fetch:
            mock_fetch.return_value = {
                'entries': [{'title': 'Hasil Teks',
                             'url': 'https://youtube.com/watch?v=text0000002'}],
            }
            recs = asyncio.run(fetch_recommendations(
                ['Seed Lagu'], set(), seed_urls=['https://youtube.com/watch?v=abc']))

        self.assertEqual([t.title for t in recs], ['Hasil Teks'])
        mock_mix.assert_not_called()

    def test_fetch_recommendations_filters_exclude_urls_from_mix(self):
        """Track Mix yang URL-nya sudah pernah diputar harus tersaring."""
        played_url = 'https://youtube.com/watch?v=played00001'
        dup = Track('Sudah Diputar', played_url, 'AutoPlay')
        fresh = Track('Baru', 'https://youtube.com/watch?v=fresh000001', 'AutoPlay')
        with patch('bot.fetch_youtube_mix', new=AsyncMock(return_value=[dup, fresh])):
            recs = asyncio.run(fetch_recommendations(
                ['Seed Lagu'], {played_url}, seed_urls=[self._SEED_URL]))

        self.assertEqual([t.title for t in recs], ['Baru'])
        self.assertTrue(all(t.requester == 'AutoPlay' for t in recs))


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

    def test_buffered_source_recovering_stream_after_jitter_not_premature_eof(self):
        """BufferedAudioSource tidak boleh memotong lagu saat data mengalir perlahan (<10 hits) pasca jitter."""
        from bot import BufferedAudioSource
        import time as _time

        class RecoveringAudio(discord.AudioSource):
            def __init__(self):
                self.count = 0
            def read(self):
                self.count += 1
                if self.count == 1:
                    return b'A' * 3840
                if self.count == 2:
                    # Simulasikan jitter CDN mendekati batas stall deadline (misal 3.6s)
                    _time.sleep(3.6)
                    return b'B' * 3840
                if self.count <= 8:
                    # Aliran audio masuk perlahan (70ms per paket, <10 hits)
                    _time.sleep(0.07)
                    return b'C' * 3840
                return b''

        buf = BufferedAudioSource(RecoveringAudio(), buffer_size=10)
        buf.ready_event.set()
        received = []
        start = _time.monotonic()
        while _time.monotonic() - start < 8.0:
            frame = buf.read()
            if frame == b'':
                break
            if frame != b'\x00' * 3840:
                received.append(frame[:1])
            _time.sleep(0.02)
        self.assertEqual(len(received), 8, f'Semua 8 frame harus terputar lengkap, terputar: {len(received)}')
        self.assertEqual(received[0], b'A')
        self.assertEqual(received[1], b'B')
        self.assertEqual(received[2:], [b'C'] * 6)
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

    def test_persistent_queue_save_and_restore_volume_loop_autoplay(self):
        """Persistent Queue: Menyimpan dan memulihkan volume, loop_mode, dan autoplay."""
        bot = MusicBot()
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, 'queue_state.json')
            bot._queue_state_file = queue_file

            gid = 12345
            state = GuildState()
            state.current = Track('Track 1', 'https://youtube.com/watch?v=t1', 'User')
            state.volume = 0.85
            state.loop_mode = 'queue'
            state.autoplay = True
            bot.states[gid] = state

            bot._save_persistent_queue()

            with open(queue_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.assertIn(str(gid), data)
            self.assertEqual(data[str(gid)]['volume'], 0.85)
            self.assertEqual(data[str(gid)]['loop_mode'], 'queue')
            self.assertEqual(data[str(gid)]['autoplay'], True)

            bot2 = MusicBot()
            bot2._queue_state_file = queue_file
            bot2._restore_persistent_queue()

            self.assertIn(gid, bot2.states)
            restored = bot2.states[gid]
            self.assertEqual(restored.volume, 0.85)
            self.assertEqual(restored.loop_mode, 'queue')
            self.assertTrue(restored.autoplay)

    def test_persistent_queue_restore_invalid_volume_loop_autoplay(self):
        """Persistent Queue: Nilai volume dan loop_mode tidak valid diabaikan dan kembali default."""
        bot = MusicBot()
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, 'queue_state.json')
            bot._queue_state_file = queue_file
            payload = {
                '12345': {
                    'current': {'title': 'Track A', 'url': 'https://example.com/a'},
                    'queue': [],
                    'volume': 'bukan-angka',
                    'loop_mode': 'invalid-mode',
                }
            }
            with open(queue_file, 'w', encoding='utf-8') as f:
                json.dump(payload, f)

            bot._restore_persistent_queue()
            state = bot.states[12345]
            self.assertEqual(state.volume, 0.5)
            self.assertEqual(state.loop_mode, 'off')

    def test_change_volume_triggers_save_persistent_queue(self):
        """change_volume memicu pemanggilan _save_persistent_queue."""
        bot = MusicBot()
        interaction = MagicMock()
        interaction.guild.id = 1111
        interaction.response.is_done.return_value = True
        interaction.followup.send = AsyncMock()
        with patch.object(bot, '_save_persistent_queue') as mock_save:
            asyncio.run(bot.change_volume(interaction, 0.75))
            mock_save.assert_called_once()
            self.assertEqual(bot.states[1111].volume, 0.75)

    def test_cmd_loop_triggers_save_persistent_queue(self):
        """cmd_loop memicu pemanggilan _save_persistent_queue."""
        bot = MusicBot()
        interaction = MagicMock()
        interaction.guild.id = 2222
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        with patch.object(bot, '_save_persistent_queue') as mock_save:
            asyncio.run(bot.cmd_loop(interaction, 'track'))
            mock_save.assert_called_once()
            self.assertEqual(bot.states[2222].loop_mode, 'track')

    def test_button_loop_triggers_save_persistent_queue(self):
        """Tombol loop pada MusicPanel memodifikasi state di dalam state.lock dan memanggil _save_persistent_queue."""
        bot = MusicBot()
        state = QueueState()

        class LockSpy:
            def __init__(self, real):
                self._real = real
                self.acquired = False
            async def __aenter__(self):
                self.acquired = True
                return await self._real.__aenter__()
            async def __aexit__(self, *args):
                return await self._real.__aexit__(*args)
            def locked(self):
                return self._real.locked()

        spy = LockSpy(state.lock)
        state.lock = spy
        bot.states[3333] = state
        panel = MusicPanel(bot)
        interaction = MagicMock()
        interaction.guild.id = 3333
        interaction.response.defer = AsyncMock()

        observed = {}

        async def mock_send(*args, **kwargs):
            observed['locked_during_send'] = state.lock.locked()

        interaction.followup.send = AsyncMock(side_effect=mock_send)

        with patch.object(panel, 'guard', new=AsyncMock(return_value=True)), \
             patch.object(bot, '_save_persistent_queue') as mock_save, \
             patch.object(bot, 'refresh', new=AsyncMock()):
            asyncio.run(panel.loop.callback(interaction))
            self.assertTrue(spy.acquired, 'state.lock tidak di-acquire saat loop_mode diubah')
            self.assertFalse(observed.get('locked_during_send', True), 'state.lock masih dipegang saat followup.send')
            mock_save.assert_called_once()
            self.assertEqual(bot.states[3333].loop_mode, 'track')

    def test_cmd_autoplay_triggers_save_persistent_queue(self):
        """cmd_autoplay memicu pemanggilan _save_persistent_queue."""
        bot = MusicBot()
        interaction = MagicMock()
        interaction.guild.id = 4444
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        with patch.object(bot, '_save_persistent_queue') as mock_save:
            asyncio.run(bot.cmd_autoplay(interaction))
            mock_save.assert_called_once()
            self.assertTrue(bot.states[4444].autoplay)

    def test_button_autoplay_triggers_save_persistent_queue(self):
        """Tombol autoplay pada MusicPanel memodifikasi state di dalam state.lock dan memanggil _save_persistent_queue."""
        bot = MusicBot()
        state = QueueState()

        class LockSpy:
            def __init__(self, real):
                self._real = real
                self.acquired = False
            async def __aenter__(self):
                self.acquired = True
                return await self._real.__aenter__()
            async def __aexit__(self, *args):
                return await self._real.__aexit__(*args)
            def locked(self):
                return self._real.locked()

        spy = LockSpy(state.lock)
        state.lock = spy
        bot.states[5555] = state
        panel = MusicPanel(bot)
        interaction = MagicMock()
        interaction.guild.id = 5555
        interaction.response.defer = AsyncMock()

        observed = {}

        async def mock_send(*args, **kwargs):
            observed['locked_during_send'] = state.lock.locked()

        interaction.followup.send = AsyncMock(side_effect=mock_send)

        with patch.object(panel, 'guard', new=AsyncMock(return_value=True)), \
             patch.object(bot, '_save_persistent_queue') as mock_save, \
             patch.object(bot, 'refresh', new=AsyncMock()):
            asyncio.run(panel.autoplay.callback(interaction))
            self.assertTrue(spy.acquired, 'state.lock tidak di-acquire saat autoplay diubah')
            self.assertFalse(observed.get('locked_during_send', True), 'state.lock masih dipegang saat followup.send')
            mock_save.assert_called_once()
            self.assertTrue(bot.states[5555].autoplay)

    def test_button_down_triggers_change_volume_and_save(self):
        """Tombol down pada MusicPanel menurunkan volume dan memicu persistensi."""
        bot = MusicBot()
        state = QueueState()
        state.volume = 0.8
        bot.states[6666] = state
        panel = MusicPanel(bot)
        interaction = MagicMock()
        interaction.guild.id = 6666
        interaction.response.defer = AsyncMock()
        interaction.response.is_done.return_value = True
        interaction.followup.send = AsyncMock()
        with patch.object(panel, 'guard', new=AsyncMock(return_value=True)), \
             patch.object(bot, '_save_persistent_queue') as mock_save, \
             patch.object(bot, 'refresh', new=AsyncMock()):
            asyncio.run(panel.down.callback(interaction))
            mock_save.assert_called_once()
            self.assertEqual(state.volume, 0.7)

    def test_button_up_triggers_change_volume_and_save(self):
        """Tombol up pada MusicPanel menaikkan volume dan memicu persistensi."""
        bot = MusicBot()
        state = QueueState()
        state.volume = 0.5
        bot.states[7777] = state
        panel = MusicPanel(bot)
        interaction = MagicMock()
        interaction.guild.id = 7777
        interaction.response.defer = AsyncMock()
        interaction.response.is_done.return_value = True
        interaction.followup.send = AsyncMock()
        with patch.object(panel, 'guard', new=AsyncMock(return_value=True)), \
             patch.object(bot, '_save_persistent_queue') as mock_save, \
             patch.object(bot, 'refresh', new=AsyncMock()):
            asyncio.run(panel.up.callback(interaction))
            mock_save.assert_called_once()
            self.assertEqual(state.volume, 0.6)


class VoiceExitPanelCleanupTests(unittest.TestCase):
    """Test suite untuk memastikan pesan panel & now-playing dibersihkan saat bot keluar voice."""

    def test_quit_voice_deletes_panel_and_now_playing_by_default(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 70001
        vc = MagicMock()
        vc.is_playing.return_value = False
        vc.disconnect = AsyncMock()
        guild.voice_client = vc

        state = QueueState()
        panel_msg = MagicMock()
        panel_msg.delete = AsyncMock()
        state.message = panel_msg

        now_msg = MagicMock()
        now_msg.delete = AsyncMock()
        state.now_message = now_msg
        state.current = Track('Lagu', 'https://example.com/lagu', 'user')
        state.queue.append(Track('Next', 'https://example.com/next', 'user'))
        bot.states[guild.id] = state

        with patch.object(bot, 'refresh', new=AsyncMock()) as mock_refresh, \
             patch('bot.dump_runtime_state'):
            asyncio.run(bot.quit_voice(guild, clear_queue=True))

        panel_msg.delete.assert_awaited_once()
        now_msg.delete.assert_awaited_once()
        self.assertIsNone(state.message)
        self.assertIsNone(state.now_message)
        self.assertIsNone(state.current)
        self.assertEqual(len(state.queue), 0)
        mock_refresh.assert_not_called()

    def test_quit_voice_delete_panel_false_preserves_panel_and_refreshes(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 70002
        vc = MagicMock()
        vc.is_playing.return_value = False
        vc.disconnect = AsyncMock()
        guild.voice_client = vc

        state = QueueState()
        panel_msg = MagicMock()
        panel_msg.delete = AsyncMock()
        state.message = panel_msg

        now_msg = MagicMock()
        now_msg.delete = AsyncMock()
        state.now_message = now_msg
        bot.states[guild.id] = state

        with patch.object(bot, 'refresh', new=AsyncMock()) as mock_refresh, \
             patch('bot.dump_runtime_state'):
            asyncio.run(bot.quit_voice(guild, clear_queue=False, delete_panel=False))

        panel_msg.delete.assert_not_called()
        now_msg.delete.assert_awaited_once()
        self.assertEqual(state.message, panel_msg)
        self.assertIsNone(state.now_message)
        mock_refresh.assert_called_once_with(state)

    def test_quit_voice_fallback_to_partial_message_when_only_id(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 70003
        vc = MagicMock()
        vc.disconnect = AsyncMock()
        guild.voice_client = vc

        channel = MagicMock()
        mock_partial = MagicMock()
        mock_partial.delete = AsyncMock()
        channel.get_partial_message.return_value = mock_partial
        guild.get_channel.return_value = channel

        state = QueueState()
        state.message = 99887766  # hanya int ID sisa restart
        state.text_channel_id = 554433
        bot.states[guild.id] = state

        with patch('bot.dump_runtime_state'):
            asyncio.run(bot.quit_voice(guild))

        guild.get_channel.assert_called_once_with(554433)
        channel.get_partial_message.assert_called_once_with(99887766)
        mock_partial.delete.assert_awaited_once()
        self.assertIsNone(state.message)

    def test_quit_voice_tolerates_not_found_on_panel_and_now_message(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 70004
        guild.voice_client = None

        state = QueueState()
        resp = MagicMock()
        resp.status = 404
        panel_msg = MagicMock()
        panel_msg.delete = AsyncMock(side_effect=discord.NotFound(resp, 'Message not found'))
        now_msg = MagicMock()
        now_msg.delete = AsyncMock(side_effect=discord.NotFound(resp, 'Message not found'))
        state.message = panel_msg
        state.now_message = now_msg
        bot.states[guild.id] = state

        with patch('bot.dump_runtime_state'):
            asyncio.run(bot.quit_voice(guild))

        self.assertIsNone(state.message)
        self.assertIsNone(state.now_message)

    def test_idle_disconnect_deletes_panel(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 70005
        guild.name = "TestGuild"
        vc = MagicMock()
        vc.disconnect = AsyncMock()
        guild.voice_client = vc

        state = QueueState()
        state.generation = 3
        state.current = None
        state.queue.clear()
        panel_msg = MagicMock()
        panel_msg.delete = AsyncMock()
        state.message = panel_msg
        bot.states[guild.id] = state

        with patch('asyncio.sleep', new=AsyncMock()), \
             patch('bot.dump_runtime_state'):
            asyncio.run(bot.idle_disconnect(guild, generation=3))

        panel_msg.delete.assert_awaited_once()
        self.assertIsNone(state.message)

    def test_on_voice_state_update_kick_deletes_panel(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 70006
        guild.name = "KickGuild"
        guild.voice_client = None

        state = QueueState()
        panel_msg = MagicMock()
        panel_msg.delete = AsyncMock()
        now_msg = MagicMock()
        now_msg.delete = AsyncMock()
        state.message = panel_msg
        state.now_message = now_msg
        bot.states[guild.id] = state

        bot_user = MagicMock()
        bot_user.id = 1234
        bot._connection.user = bot_user

        member = MagicMock()
        member.id = 1234
        member.guild = guild
        before = MagicMock(channel=MagicMock(id=991))
        after = MagicMock(channel=None)

        with patch('asyncio.sleep', new=AsyncMock()), \
             patch('bot.dump_runtime_state'):
            asyncio.run(bot.on_voice_state_update(member, before, after))

        panel_msg.delete.assert_awaited_once()
        now_msg.delete.assert_awaited_once()
        self.assertIsNone(state.message)
        self.assertIsNone(state.now_message)

    def test_afk_disconnect_deletes_panel(self):
        bot = MusicBot()
        guild = MagicMock()
        guild.id = 70007
        vc = MagicMock()
        vc.channel = MagicMock(members=[])
        vc.disconnect = AsyncMock()
        guild.voice_client = vc

        state = QueueState()
        panel_msg = MagicMock()
        panel_msg.delete = AsyncMock()
        state.message = panel_msg
        bot.states[guild.id] = state

        with patch('asyncio.sleep', new=AsyncMock()), \
             patch('bot.dump_runtime_state'):
            asyncio.run(bot._afk_disconnect(guild, generation=state.generation, timeout=0.1))

        panel_msg.delete.assert_awaited_once()
        self.assertIsNone(state.message)

    def test_signal_handler_sigterm_graceful_close(self):
        bot = MusicBot()
        async def run_test():
            with patch.object(bot, 'close', new=AsyncMock()) as mock_close:
                bot._handle_signal(signal.SIGTERM)
                self.assertTrue(bot._stopping)
                await asyncio.sleep(0.01)
                mock_close.assert_awaited_once()
        asyncio.run(run_test())

    def test_persistent_queue_saves_and_restores_panel_message_id(self):
        bot = MusicBot()
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = os.path.join(tmpdir, 'queue_panel.json')
            bot._queue_state_file = queue_file

            gid = 70008
            state = QueueState()
            state.current = Track('Track A', 'https://example.com/a', 'user')
            msg = MagicMock()
            msg.id = 11223344
            msg.channel = MagicMock(id=556677)
            state.message = msg
            state.text_channel_id = 556677
            bot.states[gid] = state

            bot._save_persistent_queue()

            with open(queue_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.assertEqual(data[str(gid)]['panel_message_id'], 11223344)
            self.assertEqual(data[str(gid)]['text_channel_id'], 556677)

            bot2 = MusicBot()
            bot2._queue_state_file = queue_file
            bot2._restore_persistent_queue()

            self.assertIn(gid, bot2.states)
            self.assertEqual(bot2.states[gid].message, 11223344)
            self.assertEqual(bot2.states[gid].text_channel_id, 556677)

    def test_delete_all_panels_with_partial_message_fallback(self):
        bot = MusicBot()
        guild = MagicMock()
        bot.get_guild = MagicMock(return_value=guild)
        channel = MagicMock()
        mock_partial = MagicMock()
        mock_partial.delete = AsyncMock()
        channel.get_partial_message.return_value = mock_partial
        guild.get_channel.return_value = channel

        state = QueueState()
        state.message = 1234567
        state.text_channel_id = 9988
        bot.states = {8888: state}

        asyncio.run(bot._delete_all_panels())
        channel.get_partial_message.assert_called_once_with(1234567)
        mock_partial.delete.assert_awaited_once()
        self.assertIsNone(state.message)

    def test_setup_hook_registers_signals(self):
        bot = MusicBot()
        with patch.object(bot, '_register_signals') as mock_reg, \
             patch.object(bot, '_sync_guild', new=AsyncMock()):
            asyncio.run(bot.setup_hook())
            mock_reg.assert_called_once()


if __name__ == '__main__':
    unittest.main()
