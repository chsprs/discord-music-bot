import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

import discord

from bot import MusicBot, MusicPanel, Track, QueueState, extract_track, extract_tracks, source_for


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
        state = QueueState()  # message None
        bot.states = {555: state}
        bot._exporter_task = None
        with patch('bot.dump_runtime_state_offline'):
            with patch.object(MusicBot.__bases__[0], 'close', new=AsyncMock()):
                asyncio.run(bot.close())
        self.assertIsNone(state.message)

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


if __name__ == '__main__':
    unittest.main()
