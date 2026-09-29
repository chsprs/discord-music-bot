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
        self.assertEqual(len(view.children), 9)

    def test_source_configures_volume(self):
        class DummyAudio(discord.AudioSource):
            def read(self): return b''
        with patch('bot.discord.FFmpegPCMAudio', return_value=DummyAudio()):
            source = source_for({'url': 'https://example.com/audio'}, volume=0.75)
            self.assertIsInstance(source, discord.PCMVolumeTransformer)
            self.assertEqual(source.volume, 0.75)

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
        expected = {'musik', 'play', 'skip', 'stop', 'antrian', 'pause', 'volume'}
        self.assertTrue(expected.issubset(set(commands)), f'Missing commands in {commands}')

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
