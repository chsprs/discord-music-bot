import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

import discord

import bot as bot_module
from bot import (MusicBot, MusicPanel, Track, QueueState, extract_track,
                 extract_tracks, source_for, _cookies_file, _with_cookies)


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
            interaction.response.send_message = AsyncMock(
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
            interaction.response.send_message = AsyncMock(
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


if __name__ == '__main__':
    unittest.main()
