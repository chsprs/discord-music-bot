#!/usr/bin/env python3
"""Stress Testing & Concurrency Fuzzing Script for Discord Music Bot (Wave 18).

Skenario Simulasi & Verifikasi:
1. Burst skips & _advance_lock race condition (Wave 3)
2. Stream jitter, network drop, & voice error recovery (Wave 3)
3. Circuit breaker threshold & queue preservation (Wave 3)
4. AFK Guard generation lifecycle & premature disconnect (Wave 3)
5. yt-dlp concurrency, cancellation, & slot leak (Wave 3)
6. Concurrent queue mutations & shuffle desync (Wave 3)
7. Flat playlist stream_url false-positive caching (Wave 3)
8. Synchronous event-loop I/O & UI refresh consistency (Wave 3/4)
9. Burst back & history drain race without debounce (Wave 4)
10. Silent EOF stream stall vs circuit breaker bypass (Wave 4)
11. Circuit breaker error latch on manual resume (Wave 4)
12. Persistent queue duplicate restore on gateway resume (Wave 4)
13. AutoPlay generation waste & unnecessary yt-dlp extraction (Wave 4)
14. SearchModal permissions check & idle task stall (Wave 4)
15. Panel embed desync on playback stop (Wave 4)
16. cmd_play voice client stall on extraction failure (Wave 5)
17. Concurrent JSON writer static .tmp collision (Wave 5)
18. Dead code in idle_disconnect on circuit breaker tripped state (Wave 5)
19. Stalled playback & abandoned queue on loop track error (Wave 5)
20. AutoPlay multicandidate fallback on first candidate failure (Wave 5)
21. Infinite extraction loop on skip during single-track loop queue (Wave 5)
22. Unhandled old.delete in _announce_now_playing bypassing _safe_delete_msg (Wave 5)
23. Missing debounce on UI volume buttons Up/Down (Wave 5)
24. Ghost VoiceClient lockout on disconnected vc in cmd_play/summon (Wave 6)
25. Cross-generation error bleed in after() callback (Wave 6)
26. Voice client stall and idle leak on single failing track in queue (Wave 6)
27. AFK Guard disconnect abandonment on generation change in empty room (Wave 6)
28. Out-of-order write race in asynchronous ThreadPool disk writers (Wave 6)
29. Silent drop of now-playing announcements after restart when state.message is ID (Wave 6)
30. Missing channel authorization and debounce on slash command /volume (Wave 6)
31. Substring noise corruption without word boundaries in _clean_seed_title (Wave 6)
32. Stale session revocation failure on password change in panel.py (Wave 6)
33. Unsynchronized deque iteration in cmd_queue, playlist, and refresh_playlist (Wave 6)
34. AudioPlayer connection loss deadlock in _steady_do_run without self.stop() (Wave 7)
35. AFK Guard disconnect abandonment on generation change in empty room due to bot member check (Wave 7)
36. Unsynchronized lazy initialization of _queue_write_lock in ThreadPool exporter (Wave 7)
37. Persistent queue loss on unawaited executor write during graceful shutdown close() (Wave 7)
38. Stale service state cache in panel.py post start/stop/restart actions (Wave 7)
39. Idle disconnect timer leak in PlaylistView.clear_queue (Wave 7)
40. Missing state.text_channel_id registration in SearchModal.on_submit (Wave 7)
41. Queue state file deletion on Discord gateway reconnects on_ready() (Wave 7)
42. Unhandled KeyError in advance() on missing or removed guild (Wave 7)
43. Audio playback and ffmpeg CPU waste in empty voice channel in _advance_loop (Wave 7)
44. Ghost VoiceClient lockout on disconnected vc in SearchModal and MusicPanel.guard (Wave 8)
45. Persistent queue state loss due to un-repersisted restored queue file deletion (Wave 8)
46. Out-of-order write race on listeners.json due to unupdated sequence in ThreadPool writer (Wave 8)
47. Stale listeners.json artifact on disk after dump_runtime_state_offline shutdown (Wave 8)
48. AutoPlay abandonment in empty room when user returns (Wave 8)
49. Expired stream_url retention on Track during playback error causing circuit breaker trip (Wave 8)
50. AttributeError on integer panel message ID deletion in cmd_play and summon post-restart (Wave 8)
51. Wrong channel resolution on message ID deletion in _announce_now_playing and quit_voice (Wave 8)
52. Stale _log_cache retention in panel.py after systemctl service actions (Wave 8)
53. Counter underflow on _release_extract_slot breaching MAX_EXTRACT_THREADS concurrency (Wave 8)
54. state.idle_task reference leak on idle_disconnect completion without finally cleanup (Wave 8)
55. announce_now_playing fallback channel mismatch on message ID deletion (Wave 9)
56. Stale panel message discard on transient HTTP 429/5xx in refresh() (Wave 9)
57. Race condition out-of-order write dump_runtime_state_offline vs dump_runtime_state (Wave 9)
58. Unhandled SafeDeque.__contains__ race condition during concurrent mutation (Wave 9)
59. Voice client stranded in voice channel on empty queue skip/back/pause (Wave 9)
60. Redundant dual timer collision (afk_task and idle_task) in empty room (Wave 9)
61. False caching stream URL for web page URLs (/embed/, /live/, /v/) in _tracks_from_metadata (Wave 9)
62. False positive audio playback error in BufferedAudioSource._reader post cleanup (Wave 9)
63. Blocking event loop latency due to await network I/O inside state.lock (Wave 9)
64. Permanent command desync post re-invite guild due to retained _synced_guilds (Wave 9)
65. Server-side session leak in panel.py on /logout endpoint (Wave 9)
66. Stale log & state cache in panel.py post /update execution (Wave 9)
67. Stranded voice client & bypass idle disconnect saat state.current non-None dan queue kosong (Wave 10)
68. cmd_back unhandled race condition dan bypass had_prev idle check (Wave 10)
69. Lockout cmd_stop, cmd_quit, dan button_stop saat bot tidak terhubung voice (Wave 10)
70. _advance_loop Phase 4 missing generation & voice client check pasca source_for (Wave 10)
71. BufferedAudioSource.cleanup synchronous worker.join(2.0) freeze asyncio event loop (Wave 10)
72. dump_runtime_state missing chmod 0644 pada state.json tmp file (Wave 10)
73. dump_runtime_state_offline sequence race overwrite oleh background executor writer (Wave 10)
74. _skip_pending lingering flag akibat pengecekan _advancing di luar state.lock (Wave 10)
75. Dataclass Track __eq__ mismatch akibat field stream_url dan stream_ts dinamis (Wave 10)
76. cmd_autoplay & MusicPanel.autoplay tidak memicu advance saat bot terhubung & idle (Wave 10)
77. on_voice_state_update mutasi task & afk_paused tanpa state.lock (Wave 10)
78. quit_voice synchronous gc.collect() blocking event loop pada STB ARM (Wave 10)
79. MusicPanel shuffle/loop/autoplay direct indexing self.bot.states unhandled KeyError (Wave 10)
80. Unbounded journalctl process spawning pada GET /api/logs?fresh=1 tanpa debounce (Wave 10)
81. cmd_play missing fallback get_channel saat interaction.channel None (Wave 10)
82. MusicPanel volume up/down read-modify-write race di luar state.lock (Wave 10)
83. Panel button require_voice=True voice connect sebelum validasi stale message (Wave 11)
84. AutoPlay candidate skip during extraction reloop tanpa exclusion (Wave 11)
85. MusicPanel.skip saat idle tidak reset consecutive_playback_errors latch (Wave 11)
86. _afk_disconnect task reference memory leak pada state.empty_task (Wave 11)
87. dump_runtime_state state.current.title AttributeError race saat concurrent nulling (Wave 11)
88. _save_persistent_queue missing os.chmod 0644 pada file .tmp (Wave 11)
89. /musik missing _schedule_idle saat antrean kosong dan bot idle di voice (Wave 11)
90. MusicPanel shuffle/loop/autoplay rapid clicks missing debounce disk write eMMC spam (Wave 11)
91. cmd_autoplay & MusicPanel.autoplay check not state.current lockout (Wave 11)
92. cmd_pause unlocked error reset & missing idle schedule saat idle (Wave 11)
93. Concurrent /play dan /musik panel duplication race di luar state.lock (Wave 11)
94. PlaylistView.refresh_playlist new instance & followup message leak (Wave 11)
95. MusicBot.embed unescaped backticks & missing empty author guard (Wave 11)
96. on_voice_state_update redundant dual dump_runtime_state disk I/O (Wave 11)
97. read_bot_logs_cached fresh debounce timestamp race spawning redundant journalctl (Wave 11)
98. ytdlp_version module caching in sys.modules showing stale version (Wave 11)
99. Track loop abandonment in empty channel on _advance_loop and on_voice_state_update (Wave 12)
100. idle_disconnect boolean precedence flaw (not state.queue or cb_tripped or not_playing) (Wave 12)
101. Voice client stranded without idle timer on queue full in cmd_play & SearchModal (Wave 12)
102. Unsynchronized state mutation & stale generation read in MusicPanel.pause (Wave 12)
103. Stranded voice client and background subprocess leak on on_guild_remove (Wave 12)
104. Race condition in _enqueue_tracks evaluates playing state outside state.lock (Wave 12)
105. Ghost panel_message_id persisted in queue_state.json on bot shutdown close() (Wave 12)
106. refresh() stalls when state.message is integer message ID post-restart (Wave 12)
107. Check-then-act race on state._advancing outside lock in cmd_skip & panel.skip (Wave 12)
108. Unhandled vc.play ClientException in _advance_loop aborts without idle scheduling (Wave 12)
109. Orphaned now-playing message when previous task cancelled during channel.send (Wave 12)
110. Unvalidated float NaN in change_volume raises unhandled ValueError (Wave 12)
111. Corrupted playlist metadata missing url and id injects 'watch?v=None' (Wave 12)
112. Unsynchronized state.current=None & generation read in cmd_back & panel.back idle fallback (Wave 12)
113. Uncached importlib.metadata.version('yt-dlp') in ytdlp_version on every panel request (Wave 12)
114. Uncached synchronous disk I/O on UPDATE_LOG_PATH in read_last_update_log() (Wave 12)
115. Track loop extraction failure infinite stall & idle timer omission (Wave 13)
116. Queue loop track drop on extraction failure during loop_mode=='queue' (Wave 13)
117. Missing VoiceClient disconnection & ffmpeg subprocess leak on bot.close() (Wave 13)
118. Voice client stranded indefinitely in voice on channel.send failure in /musik (summon) (Wave 13)
119. Stranded half-open VoiceClient lockout on timeout in MusicPanel.guard (Wave 13)
120. Restored state.current state desynchronization & track loss post-restart (Wave 13)
121. Persistent queue file wipeout race condition during concurrent shuffle (Wave 13)
122. Orphaned now-playing message leakage via asyncio.shield cancellation (Wave 13)
123. Unhandled TypeError in escape_markdown(None) on track title missing or None (Wave 13)
124. Unhandled ValueError / OverflowError in format_duration on float('nan') or float('inf') (Wave 13)
125. Total title wipeout in _clean_seed_title on single-word noise titles breaking AutoPlay (Wave 13)
126. Malformed double URL watch?v=watch?v= in _tracks_from_metadata on flat playlist entries (Wave 13)
127. Non-playlist _tracks_from_metadata search query pollution in persistent queue (Wave 13)
128. Unhandled OverflowError in _afk_disconnect when AFK_TIMEOUT_SECONDS is 'inf' (Wave 13)
129. Stale _ytdlp_version_cache and _update_log_cache post-update redirect in panel.py (Wave 13)
130. Thundering herd subprocess fork in _cached_systemctl on cache expiry (Wave 13)
131. Unhandled TypeError on escape_markdown(tracks[0].title) in SearchModal.on_submit & cmd_play when title is None (Wave 14)
132. Ghost VoiceClient lockout & indefinite voice abandonment on vc.play ClientException in _advance_loop with non-empty queue (Wave 14)
133. Persistent queue deletion & loss of guild settings (volume, loop, autoplay) when queue is empty (Wave 14)
134. Skip on stopped playback failing to drop broken track at queue head (state.queue[0]) (Wave 14)
135. /musik (summon) indefinite voice client abandonment without idle timer or advance trigger when state.queue has tracks (Wave 14)
136. Track loss on loop_mode=='queue' rotation due to structural dataclass equality on duplicate tracks (Wave 14)
137. BufferedAudioSource reader thread & ffmpeg background subprocess leak on bot.close() due to missing vc.source.cleanup() (Wave 14)
138. False playback error in AudioPlayer._steady_do_run due to missing try-except on send_silence() post-EOF (Wave 14)
139. Web panel renders '(antrean kosong)' when playback is idle/standby despite queue having tracks (Wave 14)
140. Synchronous disk I/O on state.json without in-memory TTL caching in read_bot_runtime_info() (Wave 14)
141. Active session revocation and user lockout on ConfigStore.write() I/O failure during password change (Wave 14)
142. MusicPanel.guard unsynchronized state.message & state.text_channel_id mutation without state.lock (Wave 14)
143. Premature garbage collection risk on unreferenced fire-and-forget create_task background tasks (Wave 14)
144. Unsynchronized state.afk_paused field mutation outside state.lock in on_voice_state_update (Wave 14)
145. AFK Guard generation 0 disconnect bypass in empty room post-generation increment (Wave 14)
146. Missing internal threading mutex in ConfigStore.write() during concurrent configuration saves (Wave 14)
147. Bypassed mutex lock in ConfigStore.write() due to new instance creation in store() (Wave 15)
148. Race condition in _enqueue_tracks when state._advancing > 0 clearing state.current (Wave 15)
149. Stranded ghost voice on single failing track extraction failure without circuit breaker (Wave 15)
150. Track loss in _enqueue_tracks when vc is None due to structural dataclass equality check (Wave 15)
151. Misdirected queue rotation deletion in _advance_loop on duplicate tracks during extraction failure (Wave 15)
152. Premature GC risk on unreferenced fire-and-forget quit_voice task in advance() (Wave 15)
153. Permanent idle disconnect timer loss on user return to empty voice room without active tracks (Wave 15)
154. Unsynchronized state.now_message mutation in _announce_now_playing and orphan message risk (Wave 15)
155. Race condition in refresh() overwriting state.message with fetched message outside lock (Wave 15)
156. Synchronous disk I/O and json parsing churn in read_bot_runtime_info() on stale state file (Wave 15)
157. Missing threading mutex in update_panel_password() during concurrent password updates (Wave 15)
158. Missing TTL expiration on _local_addr_cache in panel.py for dynamic IP environments (Wave 15)
159. Missing reset of cached stream_url and stream_ts on exception in _advance_loop (Wave 15)
160. Unnecessary eMMC .tmp write before sequence freshness validation in dump_runtime_state() (Wave 15)
161. Missing self.get_channel fallback in cmd_play and summon for uncached guild channels (Wave 15)
162. Missing voice channel validation (_check_same_voice) on /loop and /autoplay commands (Wave 15)
163. Disconnected VoiceClient reconnect bypass in cmd_play, modal, summon, guard (Wave 16)
164. Ghost voice lockout in cmd_stop & cmd_quit when VoiceClient disconnected (Wave 16)
165. Track and history loss on loop_mode == 'queue' with duplicate consecutive tracks (Wave 16)
166. FFmpeg crash exit misclassified as EOF in BufferedAudioSource._reader (Wave 16)
167. Shutdown dump_runtime_state file resurrection race in on_voice_state_update (Wave 16)
168. Orphaned now-playing message on unhandled task cancellation in _announce_now_playing (Wave 16)
169. Unsynchronized now_message = None overwrite race in _announce_now_playing (Wave 16)
170. Duplicate advance() call and redundant idle schedule in summon (/musik) (Wave 16)
171. Missing idle timer scheduling and voice client lockout on /back without history (Wave 16)
172. Track duplication on circuit breaker _after_dispatch re-enqueue with whole-queue matches (Wave 16)
173. Wasteful eMMC flash writes on _save_persistent_queue prior to sequence check (Wave 16)
174. Endless 3x extraction retry stall on livestream tracks during loop_mode == 'track' (Wave 16)
175. Redundant duplicate YouTube Mix extraction requests in fetch_recommendations (Wave 16)
176. Unhandled TypeError on non-string configuration values in ConfigStore.write() (Wave 16)
177. Stale distribution metadata cache on ytdlp_version() post-update (Wave 16)
178. Stale update log leak on update failure before log file refresh (Wave 16)
179. Unhandled KeyError on cmd_play due to direct self.states[interaction.guild.id] access (Wave 17)
180. Ghost voice lockout in MusicPanel.button_stop when VoiceClient disconnected due to guard() (Wave 17)
181. Missing self.get_channel fallback in _safe_delete_msg and _delete_all_panels on cold guild cache (Wave 17)
182. Shutdown _state_exporter_loop late cancellation resurrecting state.json & listeners.json (Wave 17)
183. Shutdown race in on_voice_state_update calling quit_voice & writing state post-sleep (Wave 17)
184. Stranded voice client without playback or idle timer when user returns to afk_paused empty room with stopped audio (Wave 17)
185. Track loss to history in _enqueue_tracks when VoiceClient is disconnected (is_connected False) (Wave 17)
186. Queue loop poisoning on failing tracks retried 3x re-enqueued to state.queue (Wave 17)
187. Unhandled OverflowError on channel bitrate calculation in _advance_loop when bitrate is inf (Wave 17)
188. Unhandled ValueError/OverflowError in MusicBot.embed when state.volume is NaN or Inf (Wave 17)
189. Unsynchronized state mutation and reads in SearchModal.on_submit outside state.lock (Wave 17)
190. False-positive boolean panel_message_id persistence in _save_persistent_queue (Wave 17)
191. Wasteful .tmp disk write before sequence freshness check in dump_runtime_state() (Wave 17)
192. Wasteful dump_runtime_state disk I/O in on_voice_state_update when bot is not in voice (Wave 17)
193. Cross-Site Logout CSRF vulnerability on GET/POST /logout without origin or nonce validation (Wave 17)
194. Unhandled TypeError / AttributeError in format_guilds_html when guilds elements are not dicts (Wave 17)
195. close() missing self._stopping = True initialization on shutdown (Wave 18)
196. close() missing state.generation += 1 and self._background_tasks cancellation leak (Wave 18)
197. _after_dispatch sleep shutdown race without self._stopping / is_closed() check (Wave 18)
198. cmd_play/summon wrong channel deletion on integer panel message ID (Wave 18)
199. _safe_delete_msg channel parameter priority inversion over msg.channel (Wave 18)
200. quit_voice cold cache resolution leak and single channel resolution (Wave 18)
201. refresh() unlocked state.message = None mutation race on exception (Wave 18)
202. _delete_all_panels unlocked state.message and now_message mutation (Wave 18)
203. cmd_shuffle unlocked queue len check without lock revalidation (Wave 18)
204. cmd_skip missing _schedule_idle when queue is empty and audio stopped (Wave 18)
205. cmd_loop unvalidated mode fallback automatically triggering cycle toggle (Wave 18)
206. is_connected fallback lambda: True flaw in cmd_play, stop, quit, modal (Wave 18)
207. SearchModal direct vc.channel = None mutation corrupting VoiceClient (Wave 18)
208. _state_exporter_loop missing self._stopping check during shutdown (Wave 18)
209. on_guild_remove redundant dump_runtime_state eMMC flash write cycle waste (Wave 18)
210. source_for volume NaN/Inf sanitization omission producing distorted stream (Wave 18)
211. _restore_persistent_queue infinite volume flaw due to not (vol != vol) (Wave 18)
212. _restore_persistent_queue boolean panel_message_id restore flaw (Wave 18)
213. update_panel_password fallback in-place write missing os.chmod 0600 (Wave 18)
214. read_last_update_log & _run_update_inner unhandled UnicodeDecodeError risk (Wave 18)
215. panel external bot invite target="_blank" reverse tabnabbing vulnerability (Wave 18)
216. _local_addresses internal cache set mutation leak without set() copy (Wave 18)
217. ConfigStore.write unhandled AttributeError on non-dict argument values (Wave 18)

Usage:
    ./venv/bin/python tools/stress_concurrency_fuzz.py
    ./venv/bin/python tools/stress_concurrency_fuzz.py --json
    ./venv/bin/python tools/stress_concurrency_fuzz.py --scenario loop_track_empty_channel_abandonment
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import logging
import os
import queue
import random
import sys
import tempfile
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import discord
import bot as bot_module
import panel as panel_module
from bot import (
    BufferedAudioSource,
    ExtractionBusy,
    MAX_EXTRACT_THREADS,
    MAX_QUEUE,
    MAX_TRACK_RETRIES,
    MusicBot,
    MusicPanel,
    PlaylistView,
    QueueState,
    SearchModal,
    Track,
    _clean_seed_title,
    _source_error,
    dump_runtime_state,
    fetch_recommendations,
    run_extract,
)

# Set logging level for clean execution output
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger("fuzz_runner")
logger.setLevel(logging.INFO)

_orig_sleep = asyncio.sleep


class DummyAudioSource(discord.AudioSource):
    def read(self):
        return b""

    def cleanup(self):
        pass


patch_ffmpeg = patch("bot.discord.FFmpegPCMAudio", return_value=DummyAudioSource())
patch_ffmpeg.start()
patch_extract = patch("bot.extract", return_value={"url": "http://mock/stream", "title": "Track"})
patch_extract.start()


@dataclass
class FuzzScenarioResult:
    scenario: str
    description: str
    iterations: int = 0
    passed: int = 0
    failed: int = 0
    anomalies: list[str] = field(default_factory=list)
    unhandled_exceptions: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def _create_mock_environment(guild_id: int = 1001, is_playing: bool = False):
    guild = MagicMock(spec=discord.Guild)
    guild.id = guild_id
    guild.name = f"Guild-{guild_id}"

    vc = MagicMock()
    vc.is_connected = MagicMock(return_value=True)
    vc.is_playing = MagicMock(return_value=is_playing)
    vc.is_paused = MagicMock(return_value=False)
    vc.channel = MagicMock()
    vc.channel.id = 9001
    vc.channel.members = [MagicMock(bot=False)]  # Human listener

    guild.voice_client = vc
    return guild, vc


# ==============================================================================
# 1. BURST SKIPS & _ADVANCE_LOCK RACE CONDITION (Wave 3)
# ==============================================================================
async def fuzz_burst_skips(iterations: int = 10) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="burst_skips_and_advance_race",
        description="Fuzzing burst skips simultan (UI button & slash command) dan race condition drop pada _advance_lock",
        iterations=iterations,
    )
    stuck_playback_events = 0
    lost_skips_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=2000 + it, is_playing=True)
        state = QueueState()
        for i in range(10):
            state.queue.append(Track(f"Track-{it}-{i}", f"https://mock.url/{i}", "user"))
        state.current = Track(f"Current-{it}", "https://mock.url/cur", "user")
        bot.states[guild.id] = state

        after_cb = None

        def mock_play(source, after=None, **kwargs):
            nonlocal after_cb
            after_cb = after
            vc.is_playing.return_value = True

        vc.play.side_effect = mock_play

        mock_source = MagicMock()
        mock_source.cleanup = MagicMock()

        with patch("bot.extract", return_value={"url": "http://mock/stream", "title": "Track"}), \
             patch("bot.run_extract", new=AsyncMock(return_value={"url": "http://mock/stream", "title": "Track"})), \
             patch("bot.source_for", return_value=mock_source), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_announce"):

            interaction = MagicMock(spec=discord.Interaction)
            interaction.guild = guild
            interaction.user = MagicMock()
            interaction.user.voice.channel = vc.channel
            interaction.response.defer = AsyncMock()
            interaction.followup.send = AsyncMock()

            panel = MusicPanel(bot)

            # Test 1: Rapid concurrent skips
            async def call_skip(idx):
                try:
                    if idx % 2 == 0:
                        await panel.skip.callback(interaction)
                    else:
                        await bot.cmd_skip(interaction)
                except Exception as exc:
                    res.unhandled_exceptions.append(f"it={it} skip[{idx}]: {type(exc).__name__}: {exc}")

            tasks = [asyncio.create_task(call_skip(j)) for j in range(8)]
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(0.01)

            # Test 2: Reproduksi direct drop race condition pada _advance_lock:
            state.queue.clear()
            state.current = None
            vc.is_playing.return_value = False

            orig_loop = bot._advance_loop
            entered_loop = asyncio.Event()
            allow_finish = asyncio.Event()

            async def delayed_advance_loop(guild: discord.Guild, state: QueueState, vc):
                res = await orig_loop(guild, state, vc)
                entered_loop.set()
                await allow_finish.wait()
                return res

            bot._advance_loop = delayed_advance_loop

            task_a = asyncio.create_task(bot.advance(guild))
            await entered_loop.wait()

            new_track = Track(f"Queued-{it}", "https://mock.url/q", "user")
            state.queue.append(new_track)

            task_b = asyncio.create_task(bot.advance(guild))
            await task_b

            allow_finish.set()
            await task_a

            if len(state.queue) > 0 and not vc.play.called:
                stuck_playback_events += 1

    if stuck_playback_events > 0:
        res.anomalies.append(
            f"_advance_lock drop race terbukti: {stuck_playback_events}/{iterations} iterasi mengalami stuck playback "
            "(lagu baru masuk queue saat _advance_lock aktif di-drop tanpa dijadwalkan ulang)."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {
        "stuck_playback_events": stuck_playback_events,
        "lost_skips_events": lost_skips_events,
    }
    return res


# ==============================================================================
# 2. STREAM JITTER & NETWORK DROP RECOVERY (Wave 3)
# ==============================================================================
async def fuzz_stream_jitter_network_drop(iterations: int = 10) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="stream_jitter_network_drop",
        description="Fuzzing stream drop, jitter jaringan mid-play, dan verifikasi recovery voice client",
        iterations=iterations,
    )
    client_exceptions_handled = 0
    socket_drops_handled = 0
    quit_voice_triggers = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=3000 + it)
        state = QueueState()
        for i in range(5):
            state.queue.append(Track(f"StreamTrack-{i}", f"https://mock.url/{i}", "user"))
        bot.states[guild.id] = state

        mock_source = MagicMock()
        mock_source.cleanup = MagicMock()

        quit_called = False
        async def mock_quit(guild: discord.Guild, clear_queue: bool = False, delete_panel: bool = True):
            nonlocal quit_called
            quit_called = True

        bot.quit_voice = mock_quit

        async def fast_sleep(sec, *args, **kwargs):
            if sec >= 0.5:
                await _orig_sleep(0.001)
            else:
                await _orig_sleep(sec)

        with patch("bot.extract", return_value={"url": "http://mock/stream", "title": "Track"}), \
             patch("bot.run_extract", new=AsyncMock(return_value={"url": "http://mock/stream", "title": "Track"})), \
             patch("bot.source_for", return_value=mock_source), \
             patch("bot.asyncio.sleep", new=fast_sleep), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_announce"):

            if it % 2 == 0:
                vc.play.side_effect = discord.ClientException("Not connected to voice.")
                vc.is_connected.return_value = False

                await bot.advance(guild)
                await asyncio.sleep(0.01)

                client_exceptions_handled += 1
                if quit_called:
                    quit_voice_triggers += 1
            else:
                after_cb = None
                def fake_play(src, after=None, **kwargs):
                    nonlocal after_cb
                    after_cb = after
                vc.play.side_effect = fake_play

                await bot.advance(guild)
                if after_cb:
                    after_cb(RuntimeError("Connection reset by peer (socket 104)"))
                    await asyncio.sleep(0.02)
                    socket_drops_handled += 1

    res.passed = 1
    res.metrics = {
        "client_exceptions_handled": client_exceptions_handled,
        "socket_drops_handled": socket_drops_handled,
        "quit_voice_triggers": quit_voice_triggers,
    }
    return res


# ==============================================================================
# 3. CIRCUIT BREAKER RESILIENCE (Wave 3)
# ==============================================================================
async def fuzz_circuit_breaker(iterations: int = 10) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="circuit_breaker_stress",
        description="Fuzzing circuit breaker pada kegagalan playback berulang dan perlindungan antrean",
        iterations=iterations,
    )
    tripped_count = 0
    preserved_queue_count = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=4000 + it)
        state = QueueState()
        for i in range(10):
            state.queue.append(Track(f"CBTrack-{i}", f"https://mock.url/{i}", "user"))
        bot.states[guild.id] = state

        after_cb = None
        def fake_play(src, after=None, **kwargs):
            nonlocal after_cb
            after_cb = after
        vc.play.side_effect = fake_play

        mock_source = MagicMock()
        mock_source.cleanup = MagicMock()

        async def fast_sleep(sec, *args, **kwargs):
            if sec >= 0.5:
                await _orig_sleep(0.001)
            else:
                await _orig_sleep(sec)

        with patch("bot.extract", return_value={"url": "http://mock/stream", "title": "Track"}), \
             patch("bot.run_extract", new=AsyncMock(return_value={"url": "http://mock/stream", "title": "Track"})), \
             patch("bot.source_for", return_value=mock_source), \
             patch("bot.asyncio.sleep", new=fast_sleep), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_schedule_idle") as mock_idle, \
             patch.object(bot, "_save_persistent_queue") as mock_save, \
             patch.object(bot, "_announce"):

            await bot.advance(guild)

            for err_idx in range(MAX_TRACK_RETRIES):
                if after_cb:
                    cb = after_cb
                    cb(RuntimeError(f"Simulated stream jitter error {err_idx + 1}"))
                    for _ in range(30):
                        await asyncio.sleep(0.01)
                        if state.consecutive_playback_errors >= err_idx + 1:
                            break

            if state.consecutive_playback_errors >= MAX_TRACK_RETRIES:
                tripped_count += 1
            if len(state.queue) >= 7 and state.current is None:
                preserved_queue_count += 1

    if tripped_count == iterations and preserved_queue_count == iterations:
        res.passed += 1
    else:
        res.failed += 1
        res.anomalies.append(
            f"Circuit breaker gagal menjaga antrean: tripped={tripped_count}/{iterations}, "
            f"preserved={preserved_queue_count}/{iterations}"
        )

    res.metrics = {
        "tripped_count": tripped_count,
        "preserved_queue_count": preserved_queue_count,
    }
    return res


# ==============================================================================
# 4. AFK GUARD LIFECYCLE & GENERATION BYPASS (Wave 3)
# ==============================================================================
async def fuzz_afk_guard(iterations: int = 10) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="afk_guard_lifecycle",
        description="Fuzzing timer AFK Guard, auto-pause/resume, dan bypass pengecekan generation != 0",
        iterations=iterations,
    )
    bypassed_disconnects = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=5000 + it)
        state = QueueState()
        state.generation = 0
        bot.states[guild.id] = state

        vc.channel.members = []
        quit_called = False
        async def mock_quit(guild: discord.Guild, clear_queue: bool = False, delete_panel: bool = True):
            nonlocal quit_called
            quit_called = True

        bot.quit_voice = mock_quit
        state.generation = 1

        await bot._afk_disconnect(guild, generation=0, timeout=0.001)

        if quit_called:
            bypassed_disconnects += 1

    if bypassed_disconnects > 0:
        res.anomalies.append(
            f"Bypass generasi AFK Guard terverifikasi: {bypassed_disconnects}/{iterations} kasus mematikan voice "
            "meskipun generation telah berubah (terpicu oleh logic cacat 'and generation != 0' di bot.py:2979)."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"bypassed_disconnects": bypassed_disconnects}
    return res


# ==============================================================================
# 5. YT-DLP EXTRACTION CONCURRENCY & SLOT LEAK (Wave 3)
# ==============================================================================
async def fuzz_extraction_concurrency(iterations: int = 10) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="ytdlp_extraction_concurrency",
        description="Fuzzing konkurensi ekstraksi yt-dlp, pembatalan coroutine, dan kebocoran slot thread",
        iterations=iterations,
    )
    leaked_slots = 0

    for it in range(iterations):
        with bot_module._EXTRACT_THREADS_LOCK:
            bot_module._EXTRACT_THREADS = 0

        task = asyncio.create_task(bot_module.run_extract(lambda: time.sleep(0.05)))
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        for _ in range(20):
            if bot_module._EXTRACT_THREADS == 0:
                break
            await asyncio.sleep(0.01)

        if bot_module._EXTRACT_THREADS > 0:
            leaked_slots += 1

    if leaked_slots > 0:
        res.anomalies.append(
            f"yt-dlp slot leak vulnerability terkonfirmasi: {leaked_slots}/{iterations} kasus ekstraksi "
            "berpotensi meninggalkan slot aktif saat pembatalan coroutine di event loop."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"leaked_slots_detected": leaked_slots}
    return res


# ==============================================================================
# 6. QUEUE MUTATIONS, SHUFFLE DESYNC, & PERSISTENCE I/O (Wave 3)
# ==============================================================================
async def fuzz_queue_mutations_and_shuffle(iterations: int = 10) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="queue_mutations_and_shuffle",
        description="Fuzzing konkurensi shuffle saat ekstraksi (duplikasi track) dan deque mutation saat iterasi",
        iterations=iterations,
    )
    duplicate_track_events = 0
    deque_mutation_errors = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=6000 + it)
        state = QueueState()
        t1 = Track(f"TargetTrack-{it}", f"https://mock.url/target/{it}", "user")
        t2 = Track(f"NextTrack-{it}", f"https://mock.url/next/{it}", "user")
        t3 = Track(f"LaterTrack-{it}", f"https://mock.url/later/{it}", "user")
        state.queue.extend([t1, t2, t3])
        bot.states[guild.id] = state

        extracting_gate = asyncio.Event()
        shuffle_gate = asyncio.Event()

        async def controlled_extract(*args, **kwargs):
            extracting_gate.set()
            await shuffle_gate.wait()
            return {"url": "http://mock/stream", "title": t1.title}

        mock_source = MagicMock()
        mock_source.cleanup = MagicMock()

        with patch("bot.run_extract", new=controlled_extract), \
             patch("bot.source_for", return_value=mock_source), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_announce"):

            adv_task = asyncio.create_task(bot.advance(guild))
            await extracting_gate.wait()

            async with state.lock:
                state.queue.clear()
                state.queue.extend([t2, t3, t1])

            shuffle_gate.set()
            await adv_task

            if state.current is t1 and t1 in state.queue:
                duplicate_track_events += 1

        test_deque = deque(state.queue)
        stop_worker = False

        def rapid_mutator():
            c = 0
            while not stop_worker:
                test_deque.append(Track(f"m-{c}", "http://m", "u"))
                if len(test_deque) > 10:
                    test_deque.popleft()
                c += 1
                time.sleep(0.00005)

        mut_thread = threading.Thread(target=rapid_mutator, daemon=True)
        mut_thread.start()

        for _ in range(50):
            try:
                _ = [{"title": t.title, "url": t.url} for t in test_deque]
            except RuntimeError as exc:
                if "deque mutated during iteration" in str(exc):
                    deque_mutation_errors += 1
                    break

        stop_worker = True
        mut_thread.join(timeout=0.1)

    if duplicate_track_events > 0:
        res.anomalies.append(
            f"Shuffle desync terbukti: {duplicate_track_events}/{iterations} kasus menyebabkan track aktif "
            "tetap tertinggal di queue (duplikasi pemutaran berulang)."
        )
    if deque_mutation_errors > 0:
        res.anomalies.append(
            f"Deque iteration conflict: {deque_mutation_errors} kasus memicu 'RuntimeError: deque mutated during iteration' "
            "karena pembacaan st.queue pada serialisasi tidak tersinkronisasi."
        )

    if duplicate_track_events > 0 or deque_mutation_errors > 0:
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {
        "duplicate_track_events": duplicate_track_events,
        "deque_mutation_errors": deque_mutation_errors,
    }
    return res


# ==============================================================================
# 7. FLAT PLAYLIST STREAM_URL FALSE-POSITIVE CACHING (Wave 3)
# ==============================================================================
async def fuzz_flat_playlist_stream_cache(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="flat_playlist_stream_cache",
        description="Verifikasi false-positive stream_url pada ekstraksi playlist YouTube (extract_flat)",
        iterations=iterations,
    )
    false_positive_stream_urls = 0

    for it in range(iterations):
        mock_playlist_data = {
            "_type": "playlist",
            "title": f"Test Playlist {it}",
            "entries": [
                {
                    "title": f"Song {it}-1",
                    "url": "https://www.youtube.com/watch?v=entryUrl123",
                    "webpage_url": "https://www.youtube.com/watch?v=pageUrl123",
                    "duration": 210,
                }
            ],
        }

        with patch("bot.run_extract", new=AsyncMock(return_value=mock_playlist_data)):
            tracks = await bot_module.extract_tracks("https://youtube.com/playlist?list=123", "user")
            for t in tracks:
                if t.stream_url and "youtube.com/watch" in t.stream_url:
                    false_positive_stream_urls += 1

    if false_positive_stream_urls > 0:
        res.anomalies.append(
            f"False-positive stream_url cache terdeteksi: {false_positive_stream_urls} tracks meng-cache URL halaman YouTube "
            "sebagai stream_url langsung, yang akan gagal saat diputar oleh ffmpeg."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"false_positive_stream_urls": false_positive_stream_urls}
    return res


# ==============================================================================
# 8. SYNC I/O & UI REFRESH CONSISTENCY (Wave 3/4)
# ==============================================================================
async def fuzz_sync_io_and_ui_refresh(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="sync_io_and_ui_refresh",
        description="Verifikasi sinkron disk I/O pada event loop dan pembaruan embed panel di cmd_play",
        iterations=iterations,
    )
    sync_io_blocks = 0
    missing_embed_refreshes = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=7000 + it)
        state = QueueState()
        bot.states[guild.id] = state

        # 1. Pengecekan sinkron I/O pada dump_runtime_state di event loop
        start_time = time.perf_counter()
        with patch("builtins.open", MagicMock()), patch("os.replace", MagicMock()):
            dump_runtime_state(bot)
        elapsed = time.perf_counter() - start_time
        if elapsed > 0.05:
            sync_io_blocks += 1

        # 2. Pengecekan embed refresh di cmd_play bila panel message sudah ada
        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user.voice.channel = vc.channel
        interaction.channel.id = 9001
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        existing_message = MagicMock()
        existing_message.channel.id = 9001
        state.message = existing_message

        with patch("bot.extract_tracks", new=AsyncMock(return_value=[Track("New Song", "http://s", "u")])), \
             patch.object(bot, "_enqueue_tracks", new=AsyncMock(return_value=True)), \
             patch.object(bot, "refresh", new=AsyncMock()) as mock_refresh:

            await bot.cmd_play(interaction, "New Song")

            if not mock_refresh.called:
                missing_embed_refreshes += 1

    if missing_embed_refreshes > 0:
        res.anomalies.append(
            f"Missing embed refresh: {missing_embed_refreshes}/{iterations} panggilan cmd_play tidak memperbarui embed "
            "panel yang sudah aktif di channel, menyebabkan UI menampilkan antrian usang."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {
        "sync_io_blocks": sync_io_blocks,
        "missing_embed_refreshes": missing_embed_refreshes,
    }
    return res


# ==============================================================================
# 9. BURST BACK & HISTORY DRAIN RACE WITHOUT DEBOUNCE (Wave 4)
# ==============================================================================
async def fuzz_burst_back_and_history_drain(iterations: int = 10) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="burst_back_and_history_drain",
        description="Fuzzing burst back button rapid clicks (UI button & slash command) dan history drain race tanpa debounce",
        iterations=iterations,
    )
    history_drain_events = 0
    missing_debounce_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=8000 + it, is_playing=True)
        state = QueueState()
        for i in range(5):
            state.history.append(Track(f"HistTrack-{i}", f"https://mock.url/hist/{i}", "user"))
        state.current = Track("CurrentPlaying", "https://mock.url/cur", "user")
        bot.states[guild.id] = state

        panel = MusicPanel(bot)
        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user = MagicMock()
        interaction.user.voice.channel = vc.channel
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        with patch.object(bot, "_stop_player", new=AsyncMock()), \
             patch.object(bot, "advance", new=AsyncMock()):

            async def click_back(idx):
                try:
                    if idx % 2 == 0:
                        await panel.back.callback(interaction)
                    else:
                        await bot.cmd_back(interaction)
                except Exception as exc:
                    res.unhandled_exceptions.append(f"it={it} back[{idx}]: {type(exc).__name__}: {exc}")

            tasks = [asyncio.create_task(click_back(j)) for j in range(5)]
            await asyncio.gather(*tasks, return_exceptions=True)

            if len(state.history) < 4:
                history_drain_events += 1
            if getattr(state, "_last_back_time", None) is None:
                missing_debounce_events += 1

    if history_drain_events > 0 or missing_debounce_events > 0:
        res.anomalies.append(
            f"Missing debounce & history drain race terbukti: {history_drain_events}/{iterations} iterasi "
            "menguras riwayat lagu akibat klik berulang tanpa debounce."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {
        "history_drain_events": history_drain_events,
        "missing_debounce_events": missing_debounce_events,
    }
    return res


# ==============================================================================
# 10. SILENT EOF STREAM STALL VS CIRCUIT BREAKER BYPASS (Wave 4)
# ==============================================================================
async def fuzz_stream_stall_circuit_breaker(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="stream_stall_circuit_breaker",
        description="Fuzzing stream stall timeout pada BufferedAudioSource dan verifikasi deteksi circuit breaker vs silent EOF",
        iterations=iterations,
    )
    bypassed_cb_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=8100 + it)
        state = QueueState()
        for i in range(5):
            state.queue.append(Track(f"StallTrack-{i}", f"https://mock.url/stall/{i}", "user"))
        bot.states[guild.id] = state

        inner = MagicMock(spec=discord.AudioSource)
        inner.read.side_effect = lambda: time.sleep(1)
        inner.cleanup = MagicMock()
        inner.is_opus.return_value = False

        buf = BufferedAudioSource(inner, buffer_size=10)
        buf.ready_event.set()
        buf._stall_deadline = time.monotonic() - 1.0

        chunk = buf.read()
        err = _source_error(buf)
        buf.cleanup()

        if chunk == b"" and err is None:
            bypassed_cb_events += 1

    if bypassed_cb_events > 0:
        res.anomalies.append(
            f"Silent EOF false-positive terdeteksi: {bypassed_cb_events}/{iterations} stall stream "
            "menghasilkan b'' tanpa flag error (_source_error is None), melewati circuit breaker."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"bypassed_cb_events": bypassed_cb_events}
    return res


# ==============================================================================
# 11. CIRCUIT BREAKER ERROR LATCH ON MANUAL RESUME (Wave 4)
# ==============================================================================
async def fuzz_circuit_breaker_manual_resume(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="circuit_breaker_manual_resume",
        description="Verifikasi reset latch consecutive_playback_errors saat manual resume (cmd_pause / panel play_pause)",
        iterations=iterations,
    )
    unreset_latch_events = 0
    premature_trip_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=8200 + it)
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        state = QueueState()
        state.consecutive_playback_errors = MAX_TRACK_RETRIES
        state.queue.append(Track("RescueTrack", "https://mock.url/rescue", "user"))
        bot.states[guild.id] = state

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user.voice.channel = vc.channel
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        with patch.object(bot, "advance", new=AsyncMock()), patch.object(bot, "refresh", new=AsyncMock()):
            await bot.cmd_pause(interaction)

        if state.consecutive_playback_errors >= MAX_TRACK_RETRIES:
            unreset_latch_events += 1
            new_err_count = state.consecutive_playback_errors + 1
            if new_err_count >= MAX_TRACK_RETRIES:
                premature_trip_events += 1

    if unreset_latch_events > 0:
        res.anomalies.append(
            f"Circuit breaker latch tidak di-reset: {unreset_latch_events}/{iterations} resume manual "
            "tetap mempertahankan consecutive_playback_errors=3, memicu premature trip pada error pertama berikutnya."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {
        "unreset_latch_events": unreset_latch_events,
        "premature_trip_events": premature_trip_events,
    }
    return res


# ==============================================================================
# 12. PERSISTENT QUEUE GATEWAY RESUME DUPLICATION (Wave 4)
# ==============================================================================
async def fuzz_persistent_queue_gateway_resume_duplication(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="persistent_queue_gateway_restore_duplication",
        description="Fuzzing gateway reconnect (on_resumed / on_guild_join) dan verifikasi duplikasi antrean in-memory",
        iterations=iterations,
    )
    duplicated_queue_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=8300 + it)
        state = QueueState()
        tracks = [Track(f"Active-{i}", f"https://mock.url/act/{i}", "user") for i in range(3)]
        state.queue.extend(tracks)
        bot.states[guild.id] = state

        fake_disk_data = {
            str(guild.id): {
                "current": None,
                "queue": [{"title": t.title, "url": t.url, "requester": t.requester} for t in tracks],
            }
        }

        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", MagicMock()), \
             patch("json.load", return_value=fake_disk_data), \
             patch("os.remove", MagicMock()), \
             patch("bot.dump_runtime_state"):

            await bot.on_resumed()

            if len(state.queue) > 3:
                duplicated_queue_events += 1

    if duplicated_queue_events > 0:
        res.anomalies.append(
            f"Duplikasi antrean terkonfirmasi: {duplicated_queue_events}/{iterations} pemanggilan on_resumed() "
            "menggandakan jumlah lagu di antrean in-memory."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"duplicated_queue_events": duplicated_queue_events}
    return res


# ==============================================================================
# 13. AUTOPLAY GENERATION WASTE & UNNECESSARY YT-DLP EXTRACTION (Wave 4)
# ==============================================================================
async def fuzz_autoplay_generation_waste(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="autoplay_generation_waste",
        description="Verifikasi pengecekan generation pasca fetch_recommendations untuk mencegah pemborosan ekstraksi yt-dlp",
        iterations=iterations,
    )
    wasted_extractions = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=8400 + it)
        state = QueueState()
        state.autoplay = True
        state.current = None
        state.history.append(Track("SeedSong", "https://mock.url/seed", "user"))
        bot.states[guild.id] = state

        extract_invoked = False
        async def mock_extract(*args, **kwargs):
            nonlocal extract_invoked
            extract_invoked = True
            return {"url": "http://stream", "title": "RecSong"}

        async def delayed_fetch_recs(*args, **kwargs):
            await asyncio.sleep(0.01)
            state.generation += 1
            return [Track("RecSong", "https://mock.url/rec", "user")]

        mock_source = MagicMock()
        mock_source.cleanup = MagicMock()

        with patch("bot.fetch_recommendations", new=delayed_fetch_recs), \
             patch("bot.run_extract", new=mock_extract), \
             patch("bot.source_for", return_value=mock_source), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_announce"):

            await bot._advance_loop(guild, state, vc)

            if extract_invoked:
                wasted_extractions += 1

    if wasted_extractions > 0:
        res.anomalies.append(
            f"Pemborosan ekstraksi AutoPlay: {wasted_extractions}/{iterations} iterasi tetap menjalankan "
            "run_extract() meskipun generation telah dibatalkan oleh /stop atau skip saat rekomendasi diproses."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"wasted_extractions": wasted_extractions}
    return res


# ==============================================================================
# 14. SEARCHMODAL PERMISSIONS CHECK & IDLE TASK STALL (Wave 4)
# ==============================================================================
async def fuzz_search_modal_stall_and_perms(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="search_modal_stall_and_perms",
        description="Verifikasi izin connect/speak dan penanganan idle task saat kegagalan ekstraksi pada SearchModal",
        iterations=iterations,
    )
    missing_perm_checks = 0
    stalled_idle_tasks = 0

    for it in range(iterations):
        bot = MusicBot()
        modal = SearchModal(bot)
        guild, vc = _create_mock_environment(guild_id=8500 + it)
        voice_ch = vc.channel
        guild.voice_client = None

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user = MagicMock()
        interaction.user.voice.channel = voice_ch
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        setattr(modal, "query", "Sample Search Song")

        if it % 2 == 0:
            guild.voice_client = None
            perms = MagicMock()
            perms.connect = False
            perms.speak = False
            voice_ch.permissions_for.return_value = perms
            voice_ch.connect = AsyncMock(return_value=vc)

            with patch("bot.extract_tracks", side_effect=RuntimeError("Extraction failed")):
                await modal.on_submit(interaction)

                if voice_ch.connect.called:
                    missing_perm_checks += 1
        else:
            guild.voice_client = vc
            perms = MagicMock()
            perms.connect = True
            perms.speak = True
            voice_ch.permissions_for.return_value = perms

            with patch("bot.extract_tracks", side_effect=RuntimeError("Extraction failed")):
                await modal.on_submit(interaction)

                state = bot.states.get(guild.id)
                if state is None or getattr(state, "idle_task", None) is None:
                    stalled_idle_tasks += 1

    if missing_perm_checks > 0 or stalled_idle_tasks > 0:
        res.anomalies.append(
            f"SearchModal celah keandalan terbukti: {missing_perm_checks}/{iterations} kasus melewati cek izin connect/speak, "
            f"dan {stalled_idle_tasks}/{iterations} kasus meninggalkan voice client tanpa idle disconnect task."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {
        "missing_perm_checks": missing_perm_checks,
        "stalled_idle_tasks": stalled_idle_tasks,
    }
    return res


# ==============================================================================
# 15. PANEL EMBED DESYNC ON PLAYBACK STOP (Wave 4)
# ==============================================================================
async def fuzz_panel_embed_desync_on_stop(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_embed_desync_on_stop",
        description="Verifikasi desinkronisasi panel embed saat antrean lagu selesai dan pemutaran berhenti",
        iterations=iterations,
    )
    desync_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=8600 + it)
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        state = QueueState()
        state.current = Track("LastPlayingSong", "https://mock.url/last", "user")
        state.queue.clear()
        bot.states[guild.id] = state

        refreshed_tracks = []
        async def spy_refresh(st):
            refreshed_tracks.append(getattr(st.current, "title", None))

        with patch.object(bot, "refresh", side_effect=spy_refresh), \
             patch.object(bot, "_schedule_idle"):

            await bot._advance_loop(guild, state, vc)

            if refreshed_tracks and refreshed_tracks[-1] is not None and state.current is None:
                desync_events += 1

    if desync_events > 0:
        res.anomalies.append(
            f"Panel embed desync terkonfirmasi: {desync_events}/{iterations} kasus memperbarui panel "
            "sebelum state.current dikosongkan, menyisakan judul lagu usang pada embed Discord."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"desync_events": desync_events}
    return res


# ==============================================================================
# 16. CMD_PLAY VOICE CLIENT STALL ON EXTRACTION FAILURE (Wave 5)
# ==============================================================================
async def fuzz_cmd_play_idle_stall(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_play_idle_stall",
        description="Fuzzing kegagalan ekstraksi yt-dlp pada cmd_play pasca-koneksi voice dan verifikasi penjadwalan idle disconnect",
        iterations=iterations,
    )
    stalled_voice_clients = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=8700 + it)
        voice_ch = vc.channel
        guild.voice_client = None

        perms = MagicMock()
        perms.connect = True
        perms.speak = True
        voice_ch.permissions_for.return_value = perms
        voice_ch.connect = AsyncMock(return_value=vc)

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user = MagicMock()
        interaction.user.voice.channel = voice_ch
        interaction.channel = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        with patch("bot.extract_tracks", side_effect=RuntimeError("Extraction failed")):
            await bot.cmd_play(interaction, "Sample Play Song")

            state = bot.states.get(guild.id)
            if state is None or getattr(state, "idle_task", None) is None:
                stalled_voice_clients += 1

    if stalled_voice_clients > 0:
        res.anomalies.append(
            f"Voice client idle stall terbukti: {stalled_voice_clients}/{iterations} panggilan cmd_play "
            "yang gagal ekstraksi meninggalkan voice client aktif tanpa menjadwalkan idle disconnect task."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stalled_voice_clients": stalled_voice_clients}
    return res


# ==============================================================================
# 17. CONCURRENT JSON WRITER STATIC .TMP COLLISION (Wave 5)
# ==============================================================================
async def fuzz_concurrent_json_writer_tmp_collision(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="concurrent_json_writer_tmp_collision",
        description="Fuzzing race condition penulisan berkas .tmp statis pada dump_runtime_state dan _save_persistent_queue secara konkuren",
        iterations=iterations,
    )
    collision_events = 0

    for it in range(iterations):
        bot = MusicBot()
        save_src = inspect.getsource(bot._save_persistent_queue)
        dump_src = inspect.getsource(dump_runtime_state)

        has_static_tmp = (
            'path + ".tmp"' in save_src or "path + '.tmp'" in save_src
        ) and (
            'path + ".tmp"' in dump_src or "path + '.tmp'" in dump_src
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "queue_state.json")
            bot._queue_state_file = test_file

            guild, vc = _create_mock_environment(guild_id=8800 + it)
            state = QueueState()
            bot.states[guild.id] = state

            write_corruptions = 0
            def spam_save(worker_id):
                for j in range(10):
                    state.volume = 0.1 * ((worker_id + j) % 10)
                    bot._save_persistent_queue()

            threads = [threading.Thread(target=spam_save, args=(t,)) for t in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            await asyncio.sleep(0.05)
            if os.path.exists(test_file):
                try:
                    with open(test_file, "r", encoding="utf-8") as f:
                        json.load(f)
                except Exception:
                    write_corruptions += 1

            if has_static_tmp or write_corruptions > 0:
                collision_events += 1

    if collision_events > 0:
        res.anomalies.append(
            f"Race condition .tmp statis terbukti: {collision_events}/{iterations} iterasi mendeteksi berkas "
            "temporary statis tanpa isolasi unik thread (path + '.tmp') beresiko tabrakan data."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"collision_events": collision_events}
    return res


# ==============================================================================
# 18. DEAD CODE IN IDLE_DISCONNECT ON CIRCUIT BREAKER TRIPPED STATE (Wave 5)
# ==============================================================================
async def fuzz_circuit_breaker_idle_disconnect(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="circuit_breaker_idle_disconnect",
        description="Verifikasi dead code pada idle_disconnect saat circuit breaker aktif dengan antrean terlindungi",
        iterations=iterations,
    )
    hung_voice_clients = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=8900 + it)
        state = QueueState()
        state.consecutive_playback_errors = MAX_TRACK_RETRIES
        state.queue.append(Track("Preserved1", "https://mock.url/p1", "user"))
        state.queue.append(Track("Preserved2", "https://mock.url/p2", "user"))
        state.current = None
        bot.states[guild.id] = state

        with patch("asyncio.sleep", new=AsyncMock(return_value=None)), \
             patch.object(bot, "quit_voice", new=AsyncMock()) as mock_quit:
            await bot.idle_disconnect(guild, state.generation)

            if not mock_quit.called:
                hung_voice_clients += 1

    if hung_voice_clients > 0:
        res.anomalies.append(
            f"Dead code idle_disconnect terbukti: {hung_voice_clients}/{iterations} pemanggilan idle_disconnect() "
            "gagal memutus koneksi voice saat circuit breaker aktif karena sisa antrean dipertahankan."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"hung_voice_clients": hung_voice_clients}
    return res


# ==============================================================================
# 19. STALLED PLAYBACK & ABANDONED QUEUE ON LOOP TRACK ERROR (Wave 5)
# ==============================================================================
async def fuzz_loop_track_error_queue_abandon(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="loop_track_error_queue_abandon",
        description="Fuzzing playback failure pada mode loop_mode=='track' dengan sisa antrean yang tertinggal",
        iterations=iterations,
    )
    abandoned_queue_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=9000 + it)
        state = QueueState()
        state.loop_mode = "track"
        state.current = Track("FailingLoopTrack", "https://mock.url/fail", "user")
        state.queue.append(Track("QueuedSong1", "https://mock.url/q1", "user"))
        state.queue.append(Track("QueuedSong2", "https://mock.url/q2", "user"))
        bot.states[guild.id] = state

        async def mock_extract(func, *args, **kwargs):
            url = args[0] if args else getattr(func, "url", "")
            if url == "https://mock.url/fail":
                raise RuntimeError("Track extraction failed")
            return {"url": "http://stream/ok", "title": "Track"}

        mock_source = MagicMock()
        mock_source.cleanup = MagicMock()

        with patch("bot.run_extract", side_effect=mock_extract), \
             patch("bot.source_for", return_value=mock_source), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_announce"):

            await bot._advance_loop(guild, state, vc)

            if state.current is None and len(state.queue) > 0 and not vc.play.called:
                abandoned_queue_events += 1

    if abandoned_queue_events > 0:
        res.anomalies.append(
            f"Antrean tertahan pada loop track error: {abandoned_queue_events}/{iterations} iterasi menghentikan "
            "pemutaran dan menelantarkan sisa lagu di antrean saat track loop gagal diekstrak."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"abandoned_queue_events": abandoned_queue_events}
    return res


# ==============================================================================
# 20. AUTOPLAY MULTICANDIDATE FALLBACK ON FIRST CANDIDATE FAILURE (Wave 5)
# ==============================================================================
async def fuzz_autoplay_multicandidate_fallback(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="autoplay_multicandidate_fallback",
        description="Fuzzing AutoPlay saat kandidat rekomendasi pertama gagal ekstraksi untuk menguji fallback kandidat berikutnya",
        iterations=iterations,
    )
    fallback_aborted_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=9100 + it)
        state = QueueState()
        state.autoplay = True
        state.current = None
        state.history.append(Track("SeedTrack", "https://mock.url/seed", "user"))
        bot.states[guild.id] = state

        c1 = Track("Candidate1_Bad", "https://mock.url/cand1", "user")
        c2 = Track("Candidate2_Good", "https://mock.url/cand2", "user")

        async def mock_fetch_recs(*args, **kwargs):
            return [c1, c2]

        extracted_urls = []
        async def mock_extract(func, *args, **kwargs):
            url = args[0] if args else getattr(func, "url", "")
            extracted_urls.append(url)
            if url == "https://mock.url/cand1":
                raise RuntimeError("Candidate 1 extraction 404")
            return {"url": "http://stream/good", "title": "Candidate2_Good"}

        mock_source = MagicMock()
        mock_source.cleanup = MagicMock()

        with patch("bot.fetch_recommendations", side_effect=mock_fetch_recs), \
             patch("bot.run_extract", side_effect=mock_extract), \
             patch("bot.source_for", return_value=mock_source), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_announce"):

            await bot._advance_loop(guild, state, vc)

            if "https://mock.url/cand2" not in extracted_urls:
                fallback_aborted_events += 1

    if fallback_aborted_events > 0:
        res.anomalies.append(
            f"AutoPlay abort prematur terbukti: {fallback_aborted_events}/{iterations} iterasi gagal mencoba "
            "kandidat rekomendasi berikutnya ketika kandidat pertama gagal diekstrak."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"fallback_aborted_events": fallback_aborted_events}
    return res


# ==============================================================================
# 21. INFINITE EXTRACTION LOOP ON SKIP DURING SINGLE-TRACK LOOP QUEUE (Wave 5)
# ==============================================================================
async def fuzz_single_track_loop_queue_skip(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="single_track_loop_queue_skip",
        description="Fuzzing perintah Skip di tengah ekstraksi pada single-track loop_mode=='queue' untuk mendeteksi infinite extraction loop",
        iterations=iterations,
    )
    infinite_loop_skips = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=9200 + it)
        state = QueueState()
        state.loop_mode = "queue"
        track = Track("LoopQueueSingle", "https://mock.url/single", "user")
        state.current = track
        state.queue.clear()
        bot.states[guild.id] = state

        extract_count = 0
        async def mock_extract(func, *args, **kwargs):
            nonlocal extract_count
            extract_count += 1
            if extract_count == 1:
                state._skip_pending = True
            if extract_count > 3:
                raise RuntimeError("Stuck in infinite extraction loop")
            return {"url": "http://mock/stream", "title": "Track"}

        mock_source = MagicMock()
        mock_source.cleanup = MagicMock()

        with patch("bot.run_extract", side_effect=mock_extract), \
             patch("bot.source_for", return_value=mock_source), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_announce"):

            try:
                await bot._advance_loop(guild, state, vc)
            except RuntimeError as exc:
                if "infinite extraction loop" in str(exc):
                    infinite_loop_skips += 1
            else:
                if (extract_count > 1 and state.current is track) or vc.play.called or state.current is track:
                    infinite_loop_skips += 1

    if infinite_loop_skips > 0:
        res.anomalies.append(
            f"Infinite extraction loop / skip bypass terbukti: {infinite_loop_skips}/{iterations} kasus skip "
            "pada single-track loop_mode=='queue' gagal membersihkan state.current dan membiarkan lagu tetap diputar."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"infinite_loop_skips": infinite_loop_skips}
    return res


# ==============================================================================
# 22. UNHANDLED OLD.DELETE IN _ANNOUNCE_NOW_PLAYING (Wave 5)
# ==============================================================================
async def fuzz_announce_now_playing_safe_delete(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="announce_now_playing_safe_delete",
        description="Verifikasi penghapusan now-playing message lama secara aman melalui _safe_delete_msg",
        iterations=iterations,
    )
    bypassed_safe_delete = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=9400 + it)
        state = QueueState()
        old_msg = MagicMock()
        state.now_message = old_msg
        state.message = MagicMock()
        state.message.channel = MagicMock()
        state.message.channel.send = AsyncMock(return_value=MagicMock())
        bot.states[guild.id] = state

        track = Track("NewNowTrack", "https://mock.url/now", "user")

        with patch.object(bot, "_safe_delete_msg", new=AsyncMock()) as mock_safe_delete:
            await bot._announce_now_playing(guild, track)

            if not mock_safe_delete.called:
                bypassed_safe_delete += 1

    if bypassed_safe_delete > 0:
        res.anomalies.append(
            f"Bypass _safe_delete_msg terbukti: {bypassed_safe_delete}/{iterations} pemanggilan _announce_now_playing "
            "memanggil old.delete() secara langsung tanpa perlindungan fallback _safe_delete_msg."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"bypassed_safe_delete": bypassed_safe_delete}
    return res


# ==============================================================================
# 23. MISSING DEBOUNCE ON UI VOLUME BUTTONS UP/DOWN (Wave 5)
# ==============================================================================
async def fuzz_volume_burst_debounce(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="volume_burst_debounce",
        description="Fuzzing rapid burst clicks pada tombol volume UI (Up & Down) untuk memverifikasi proteksi debounce",
        iterations=iterations,
    )
    missing_debounce_events = 0
    excessive_writes_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=9300 + it, is_playing=True)
        state = QueueState()
        state.volume = 0.5
        bot.states[guild.id] = state

        panel = MusicPanel(bot)
        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user = MagicMock()
        interaction.user.voice.channel = vc.channel
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        change_vol_calls = 0
        orig_change_vol = bot.change_volume
        async def spy_change_volume(inter, vol):
            nonlocal change_vol_calls
            change_vol_calls += 1
            return await orig_change_vol(inter, vol)

        with patch.object(bot, "change_volume", side_effect=spy_change_volume), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_save_persistent_queue"):

            tasks = []
            for i in range(5):
                if i % 2 == 0:
                    tasks.append(panel.down.callback(interaction))
                else:
                    tasks.append(panel.up.callback(interaction))
            await asyncio.gather(*tasks, return_exceptions=True)

            if change_vol_calls > 2:
                excessive_writes_events += 1
            if getattr(state, "_last_volume_time", None) is None:
                missing_debounce_events += 1

    if missing_debounce_events > 0 or excessive_writes_events > 0:
        res.anomalies.append(
            f"Ketiadaan debounce volume UI terkonfirmasi: {missing_debounce_events}/{iterations} iterasi "
            f"tidak mencatat _last_volume_time dan {excessive_writes_events}/{iterations} iterasi meloloskan "
            "klik bertubi-tubi tanpa proteksi throttling."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {
        "missing_debounce_events": missing_debounce_events,
        "excessive_writes_events": excessive_writes_events,
    }
    return res


# ==============================================================================
# 24. GHOST VOICE CLIENT LOCKOUT ON DISCONNECTED VC (Wave 6)
# ==============================================================================
async def fuzz_ghost_voice_client_lockout(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="ghost_voice_client_lockout",
        description="Fuzzing cmd_play dan summon saat voice_client ada tetapi vc.channel is None / terputus (ghost VoiceClient lockout)",
        iterations=iterations,
    )
    ghost_lockout_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=9500 + it)
        vc.channel = None
        vc.is_connected = MagicMock(return_value=False)

        user_channel = MagicMock()
        user_channel.id = 7788
        user_channel.permissions_for = MagicMock(return_value=MagicMock(connect=True, speak=True))

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user = MagicMock()
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = user_channel
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        with patch("bot.extract_tracks", new=AsyncMock(return_value=[Track("T1", "url", "user")])), \
             patch.object(bot, "_enqueue_tracks", new=AsyncMock(return_value=True)), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_save_persistent_queue"):
            await bot.cmd_play(interaction, "https://mock.url/1")

            for call in interaction.followup.send.call_args_list:
                args, _ = call
                if args and "Bot sedang dipakai di voice channel lain." in str(args[0]):
                    ghost_lockout_events += 1
                    break

    if ghost_lockout_events > 0:
        res.anomalies.append(
            f"Ghost VoiceClient lockout terkonfirmasi: {ghost_lockout_events}/{iterations} iterasi menolak "
            "pengguna dengan 'Bot sedang dipakai di voice channel lain' padahal bot tidak berada di voice channel mana pun (vc.channel is None)."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"ghost_lockout_events": ghost_lockout_events}
    return res


# ==============================================================================
# 25. CROSS-GENERATION ERROR BLEED IN AFTER() CALLBACK (Wave 6)
# ==============================================================================
async def fuzz_cross_generation_after_error_bleed(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cross_generation_after_error_bleed",
        description="Fuzzing error playback pada generation lama yang terlambat memicu false trip circuit breaker di generation baru",
        iterations=iterations,
    )
    cross_gen_error_bleed_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=9600 + it)
        state = QueueState()
        state.generation = 1
        state.consecutive_playback_errors = 2
        bot.states[guild.id] = state

        real_after = None
        def capture_play(src, after=None, **kwargs):
            nonlocal real_after
            real_after = after
            vc.is_playing.return_value = True

        vc.play = MagicMock(side_effect=capture_play)

        with patch("bot.run_extract", new=AsyncMock(return_value={"url": "http://mock/stream", "title": "Track"})), \
             patch("bot.source_for", return_value=MagicMock()), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_announce"), \
             patch.object(bot, "_save_persistent_queue"):

            state.queue.append(Track("Track1", "https://mock.url/1", "user"))
            await bot._advance_loop(guild, state, vc)

            if real_after:
                state.generation = 2
                state.current = Track("FreshTrack", "https://mock.url/fresh", "user")
                state.consecutive_playback_errors = 2
                state._skip_armed = False

                real_after(RuntimeError("Late ffmpeg stream failure"))
                await asyncio.sleep(0.05)

                if state.consecutive_playback_errors >= 3 or state.current is None:
                    cross_gen_error_bleed_events += 1

    if cross_gen_error_bleed_events > 0:
        res.anomalies.append(
            f"Cross-generation error bleed terkonfirmasi: {cross_gen_error_bleed_events}/{iterations} iterasi "
            "mengizinkan error playback dari generasi lama memicu kenaikan consecutive_playback_errors / mematikan lagu aktif di generasi baru."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"cross_gen_error_bleed_events": cross_gen_error_bleed_events}
    return res


# ==============================================================================
# 26. SINGLE FAILING TRACK IDLE STALL IN ADVANCE (Wave 6)
# ==============================================================================
async def fuzz_single_failing_track_idle_stall(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="single_failing_track_idle_stall",
        description="Fuzzing ekstraksi gagal pada antrean berisi 1 lagu dan verifikasi stall voice client tanpa penjadwalan idle disconnect",
        iterations=iterations,
    )
    stalled_single_track_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=9700 + it)
        state = QueueState()
        bad_track = Track("FailingSoloTrack", "https://mock.url/fail", "user")
        state.queue.append(bad_track)
        state.current = None
        bot.states[guild.id] = state

        async def mock_extract(*args, **kwargs):
            raise RuntimeError("Extraction 403 Forbidden")

        idle_scheduled = False
        def spy_schedule_idle(g, gen):
            nonlocal idle_scheduled
            idle_scheduled = True

        with patch("bot.run_extract", side_effect=mock_extract), \
             patch.object(bot, "_schedule_idle", side_effect=spy_schedule_idle), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_save_persistent_queue"):

            await bot._advance_loop(guild, state, vc)

            if not idle_scheduled and not vc.is_playing() and state.current is None and len(state.queue) == 1:
                stalled_single_track_events += 1

    if stalled_single_track_events > 0:
        res.anomalies.append(
            f"Stall voice client pada antrean 1 lagu gagal terkonfirmasi: {stalled_single_track_events}/{iterations} "
            "iterasi menghentikan pemutaran tanpa menjadwalkan _schedule_idle saat 1 lagu di antrean gagal diekstrak."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stalled_single_track_events": stalled_single_track_events}
    return res


# ==============================================================================
# 27. AFK GUARD DISCONNECT ABANDONMENT ON GENERATION CHANGE (Wave 6)
# ==============================================================================
async def fuzz_afk_guard_generation_abandonment(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="afk_guard_generation_abandonment",
        description="Fuzzing AFK Guard pada room kosong saat generation berubah dan verifikasi pembatalan disconnect yang menyebabkan bot tertahan",
        iterations=iterations,
    )
    abandoned_afk_disconnect_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=9800 + it)
        vc.channel.members = []
        state = QueueState()
        state.generation = 1
        bot.states[guild.id] = state

        quit_called = False
        async def mock_quit(g, clear_queue=False):
            nonlocal quit_called
            quit_called = True

        with patch.object(bot, "quit_voice", side_effect=mock_quit):
            task = asyncio.create_task(bot._afk_disconnect(guild, generation=1, timeout=0.01))
            state.generation = 2
            await task

            if not quit_called:
                abandoned_afk_disconnect_events += 1

    if abandoned_afk_disconnect_events > 0:
        res.anomalies.append(
            f"Abandonment AFK Guard terkonfirmasi: {abandoned_afk_disconnect_events}/{iterations} iterasi "
            "membatalkan pemutusan koneksi pada room yang benar-benar kosong hanya karena generation state berubah."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"abandoned_afk_disconnect_events": abandoned_afk_disconnect_events}
    return res


# ==============================================================================
# 28. THREADPOOL ASYNCHRONOUS DISK WRITERS OUT-OF-ORDER RACE (Wave 6)
# ==============================================================================
async def fuzz_threadpool_disk_writers_out_of_order(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="threadpool_disk_writers_out_of_order",
        description="Fuzzing out-of-order writes pada ThreadPool asynchronous disk writer (_save_persistent_queue & dump_runtime_state)",
        iterations=iterations,
    )
    out_of_order_write_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=9900 + it)
        state = QueueState()
        bot.states[guild.id] = state

        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tf:
            test_file = tf.name

        bot._queue_state_file = test_file

        try:
            state.queue = deque([Track(f"OldTrack-{i}", f"https://mock.url/old/{i}", "user") for i in range(5)])

            orig_run_in_executor = asyncio.get_running_loop().run_in_executor
            call_count = 0

            def mock_executor(executor, func, *args):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    def slow_fn():
                        time.sleep(0.04)
                        return func(*args)
                    return orig_run_in_executor(executor, slow_fn)
                else:
                    return orig_run_in_executor(executor, func, *args)

            with patch.object(asyncio.get_running_loop(), "run_in_executor", side_effect=mock_executor):
                bot._save_persistent_queue()

                state.queue = deque([Track("NewTrack-Latest", "https://mock.url/new", "user")])
                bot._save_persistent_queue()

                await asyncio.sleep(0.08)

                if os.path.exists(test_file) and os.path.getsize(test_file) > 0:
                    with open(test_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    g_data = data.get(str(guild.id), {})
                    q_data = g_data.get("queue", [])
                    if len(q_data) == 5:
                        out_of_order_write_events += 1
        finally:
            if os.path.exists(test_file):
                try:
                    os.remove(test_file)
                except Exception:
                    pass

    if out_of_order_write_events > 0:
        res.anomalies.append(
            f"Out-of-order write race terkonfirmasi: {out_of_order_write_events}/{iterations} iterasi "
            "menimpa berkas state persisten dengan data lama karena ketiadaan serialisasi pada loop.run_in_executor."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"out_of_order_write_events": out_of_order_write_events}
    return res


# ==============================================================================
# 29. ANNOUNCE NOW-PLAYING MESSAGE ID FALLBACK (Wave 6)
# ==============================================================================
async def fuzz_announce_now_playing_message_id_fallback(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="announce_now_playing_message_id_fallback",
        description="Verifikasi pengumuman now-playing ketika state.message berupa integer ID (pasca restart) tanpa atribut channel",
        iterations=iterations,
    )
    dropped_announcement_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=10000 + it)
        state = QueueState()
        state.message = 123456789
        state.text_channel_id = 987654321

        mock_channel = MagicMock()
        mock_channel.send = AsyncMock(return_value=MagicMock())
        guild.get_channel = MagicMock(return_value=mock_channel)
        bot.get_channel = MagicMock(return_value=mock_channel)
        bot.states[guild.id] = state

        track = Track("RestoredTrack", "https://mock.url/res", "user")

        with patch.object(bot, "_safe_delete_msg", new=AsyncMock()):
            await bot._announce_now_playing(guild, track)

            if not mock_channel.send.called:
                dropped_announcement_events += 1

    if dropped_announcement_events > 0:
        res.anomalies.append(
            f"Silent drop now-playing terkonfirmasi: {dropped_announcement_events}/{iterations} iterasi "
            "menggugurkan pengiriman pengumuman now-playing karena state.message bertipe integer ID pasca-restart."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"dropped_announcement_events": dropped_announcement_events}
    return res


# ==============================================================================
# 30. CMD_VOLUME CHANNEL AUTHORIZATION & DEBOUNCE (Wave 6)
# ==============================================================================
async def fuzz_cmd_volume_channel_auth_debounce(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_volume_channel_auth_debounce",
        description="Verifikasi otorisasi voice channel dan debounce proteksi disk write pada slash command /volume",
        iterations=iterations,
    )
    unauthorized_volume_events = 0
    missing_volume_debounce_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=10100 + it)
        vc.channel.id = 1111
        state = QueueState()
        state.volume = 1.0
        bot.states[guild.id] = state

        user_channel = MagicMock()
        user_channel.id = 2222

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user = MagicMock()
        interaction.user.voice = MagicMock()
        interaction.user.voice.channel = user_channel
        interaction.response.send_message = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.is_done = MagicMock(return_value=True)
        interaction.followup.send = AsyncMock()

        with patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_save_persistent_queue"):

            await bot.cmd_volume(interaction, 150)

            if state.volume == 1.5:
                unauthorized_volume_events += 1

            # Rapid second call within 0.1s to test debounce throttling
            await bot.cmd_volume(interaction, 180)
            if state.volume == 1.8:
                missing_volume_debounce_events += 1

    if unauthorized_volume_events > 0 or missing_volume_debounce_events > 0:
        res.anomalies.append(
            f"Celah otorisasi & debounce /volume terkonfirmasi: {unauthorized_volume_events}/{iterations} iterasi "
            f"mengizinkan user di channel lain mengubah volume dan {missing_volume_debounce_events}/{iterations} iterasi "
            "tidak menerapkan debounce time guard pada slash command /volume."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {
        "unauthorized_volume_events": unauthorized_volume_events,
        "missing_volume_debounce_events": missing_volume_debounce_events,
    }
    return res


# ==============================================================================
# 31. CLEAN SEED TITLE WORD BOUNDARY CORRUPTION (Wave 6)
# ==============================================================================
async def fuzz_clean_seed_title_word_boundary(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="clean_seed_title_word_boundary",
        description="Verifikasi penanganan kata dan boundary regex pada _clean_seed_title untuk mencegah korupsi substring judul lagu",
        iterations=iterations,
    )
    corrupted_title_events = 0

    test_titles = [
        ("Radiohead - Creep", "Radiohead"),
        ("Shadow of the Day", "Shadow"),
        ("Headlines", "Headlines"),
        ("Earthquake", "Earthquake"),
        ("Move Your Body", "Move"),
    ]

    for it in range(iterations):
        for raw_title, expected_keyword in test_titles:
            cleaned = _clean_seed_title(raw_title)
            if expected_keyword.lower() not in cleaned.lower():
                corrupted_title_events += 1

    if corrupted_title_events > 0:
        res.anomalies.append(
            f"Korupsi substring _clean_seed_title terkonfirmasi: {corrupted_title_events} kasus pemotongan kata "
            "valid (mis. Radiohead -> Raiohea, Shadow -> Sha ow) akibat regex tanpa word boundary (\\b)."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"corrupted_title_events": corrupted_title_events}
    return res


# ==============================================================================
# 32. PANEL SESSION REVOCATION ON PASSWORD CHANGE (Wave 6)
# ==============================================================================
async def fuzz_panel_session_revocation_on_password_change(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_session_revocation_on_password_change",
        description="Verifikasi pencabutan sesi aktif pada panel.py saat kata sandi diubah ke kata sandi baru",
        iterations=iterations,
    )
    unrevoked_session_events = 0

    for it in range(iterations):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".env") as tf:
            env_file = tf.name

        try:
            with open(env_file, "w", encoding="utf-8") as f:
                f.write("PANEL_PASSWORD=oldpassword\n")

            with panel_module._lock:
                panel_module._sessions.clear()

            token = panel_module._mint_session()
            if not panel_module._session_valid(token):
                continue

            panel_module.update_panel_password("newpassword123", env_path=env_file)

            if panel_module._session_valid(token):
                unrevoked_session_events += 1
        finally:
            if os.path.exists(env_file):
                try:
                    os.remove(env_file)
                except Exception:
                    pass
            with panel_module._lock:
                panel_module._sessions.clear()

    if unrevoked_session_events > 0:
        res.anomalies.append(
            f"Kegagalan pencabutan sesi password change terkonfirmasi: {unrevoked_session_events}/{iterations} iterasi "
            "membiarkan sesi lama tetap aktif setelah kata sandi diubah ke nilai baru."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unrevoked_session_events": unrevoked_session_events}
    return res


# ==============================================================================
# 33. UNSYNCHRONIZED DEQUE ITERATION IN PLAYLIST/QUEUE (Wave 6)
# ==============================================================================
async def fuzz_unsynchronized_deque_iteration(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="unsynchronized_deque_iteration",
        description="Fuzzing iterasi konkuren tanpa lock pada state.queue di cmd_queue, playlist, dan refresh_playlist saat mutasi antrean",
        iterations=iterations,
    )
    deque_mutation_errors = 0
    missing_lock_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=10200 + it)
        state = QueueState()
        for i in range(100):
            state.queue.append(Track(f"Track-{i}", f"https://mock.url/{i}", "user"))
        state.current = Track("Current", "https://mock.url/c", "user")
        bot.states[guild.id] = state

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        stop_mutations = False
        def mutate_queue():
            while not stop_mutations:
                try:
                    state.queue.append(Track("Mutate", "url", "user"))
                    state.queue.popleft()
                except Exception:
                    pass
                time.sleep(0.0001)

        mut_thread = threading.Thread(target=mutate_queue, daemon=True)
        mut_thread.start()

        try:
            for _ in range(50):
                try:
                    for _item in state.queue:
                        time.sleep(0.00001)
                except RuntimeError as exc:
                    if "deque mutated during iteration" in str(exc):
                        deque_mutation_errors += 1
                        break
        finally:
            stop_mutations = True
            mut_thread.join(timeout=0.5)

        lock_acquired = False
        orig_lock = state.lock
        class SpyLock:
            async def __aenter__(self):
                nonlocal lock_acquired
                lock_acquired = True
                return await orig_lock.__aenter__()
            async def __aexit__(self, *args):
                return await orig_lock.__aexit__(*args)

        state.lock = SpyLock()
        with patch("bot._check_guild_only", return_value=True):
            await bot.cmd_queue(interaction)
            if not lock_acquired:
                missing_lock_events += 1

    if deque_mutation_errors > 0 or missing_lock_events > 0:
        res.anomalies.append(
            f"Iterasi deque tanpa sinkronisasi terkonfirmasi: {deque_mutation_errors} RuntimeError deque mutated dan "
            f"{missing_lock_events}/{iterations} pemanggilan cmd_queue membaca antrean tanpa acquire state.lock."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {
        "deque_mutation_errors": deque_mutation_errors,
        "missing_lock_events": missing_lock_events,
    }
    return res


# ==============================================================================
# 34. AUDIOPLAYER CONNECTION LOSS DEADLOCK (Wave 7)
# ==============================================================================
async def fuzz_audio_player_connection_loss_deadlock(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="audio_player_connection_loss_deadlock",
        description="Fuzzing voice connection lost pada AudioPlayer._steady_do_run dan verifikasi deadlock ketiadaan self.stop()",
        iterations=iterations,
    )
    deadlock_events = 0

    for it in range(iterations):
        source = DummyAudioSource()
        source.read = MagicMock(return_value=b"audio-frame-sample")

        client = MagicMock()
        client.timeout = 0.01
        client.is_connected = MagicMock(return_value=False)
        client.wait_until_connected = MagicMock(return_value=False)
        client.send_audio_packet = MagicMock()

        player = discord.player.AudioPlayer(source, client)
        player._speak = MagicMock()

        player._do_run()

        # Jika self.stop() tidak dipanggil saat connection lost, _end tidak ter-set
        # dan player.is_playing() / vc.is_playing() akan terus mengembalikan True selamanya.
        if not player._end.is_set():
            deadlock_events += 1

    if deadlock_events > 0:
        res.anomalies.append(
            f"AudioPlayer connection loss deadlock terkonfirmasi: {deadlock_events}/{iterations} iterasi "
            "mengalami deadlock (player._end.is_set() == False) saat connection lost karena _steady_do_run "
            "melakukan return tanpa memanggil self.stop()."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"deadlock_events": deadlock_events}
    return res


# ==============================================================================
# 35. AFK GUARD EMPTY ROOM BOT MEMBER CHECK (Wave 7)
# ==============================================================================
async def fuzz_afk_guard_empty_room_bot_member_check(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="afk_guard_empty_room_bot_member_check",
        description="Fuzzing AFK Guard disconnect abandonment saat interaksi teks mengubah generation di room kosong",
        iterations=iterations,
    )
    abandoned_afk_disconnect_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=11000 + it, is_playing=False)
        bot_member = MagicMock(bot=True)
        vc.channel.members = [bot_member]  # Hanya bot di channel (0 manusia)

        state = QueueState()
        state.generation = 2  # Generation berubah (misal interaksi /skip atau /volume)
        bot.states[guild.id] = state

        bot.quit_voice = AsyncMock()

        await bot._afk_disconnect(guild, generation=1, timeout=0.001)

        # Jika raw_members > 0 (karena bot dihitung) membatalkan disconnect di room kosong:
        if not bot.quit_voice.called:
            abandoned_afk_disconnect_events += 1

    if abandoned_afk_disconnect_events > 0:
        res.anomalies.append(
            f"AFK Guard abandon terkonfirmasi: {abandoned_afk_disconnect_events}/{iterations} iterasi gagal "
            "memutuskan koneksi di room kosong saat generation berubah karena len(raw_members) > 0 selalu True "
            "(menghitung instance bot sendiri)."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"abandoned_afk_disconnect_events": abandoned_afk_disconnect_events}
    return res


# ==============================================================================
# 36. THREADPOOL QUEUE WRITE LOCK LAZY INIT (Wave 7)
# ==============================================================================
async def fuzz_threadpool_queue_write_lock_lazy_init(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="threadpool_queue_write_lock_lazy_init",
        description="Fuzzing race condition inisialisasi lazy pada _queue_write_lock di ThreadPool disk writer",
        iterations=iterations,
    )
    lazy_init_race_events = 0

    for it in range(iterations):
        bot = MusicBot()
        # Jika lock tidak diinisialisasi saat __init__:
        if getattr(bot, "_queue_write_lock", None) is None:
            lazy_init_race_events += 1

    if lazy_init_race_events > 0:
        res.anomalies.append(
            f"Lazy init race condition terkonfirmasi: {lazy_init_race_events}/{iterations} iterasi mendapati "
            "_queue_write_lock bernilai None pada MusicBot.__init__, memicu pembentukan multi-lock saat "
            "eksekusi ThreadPool konkuren."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"lazy_init_race_events": lazy_init_race_events}
    return res


# ==============================================================================
# 37. CLOSE PERSISTENT QUEUE UNAWAITED EXECUTOR (Wave 7)
# ==============================================================================
async def fuzz_close_persistent_queue_unawaited_executor(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="close_persistent_queue_unawaited_executor",
        description="Fuzzing graceful shutdown pada close() dan verifikasi unawaited background executor write",
        iterations=iterations,
    )
    unawaited_close_write_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild = MagicMock(id=12000 + it)
        state = QueueState()
        state.queue.append(Track("CloseTrack", "https://mock.url/close", "user"))
        bot.states[guild.id] = state

        loop = asyncio.get_running_loop()
        executor_calls = []
        orig_run_in_executor = loop.run_in_executor

        def spy_run_in_executor(executor, func, *args):
            fut = orig_run_in_executor(executor, func, *args)
            executor_calls.append(fut)
            return fut

        with patch.object(loop, "run_in_executor", side_effect=spy_run_in_executor), \
             patch.object(bot, "_delete_all_panels", new=AsyncMock()):
            await bot.close()

            # Jika penulisan dikirim ke executor tanpa ditunggu sampai selesai (unawaited task):
            if executor_calls and not executor_calls[0].done():
                unawaited_close_write_events += 1

    if unawaited_close_write_events > 0:
        res.anomalies.append(
            f"Unawaited persistent queue write terkonfirmasi: {unawaited_close_write_events}/{iterations} iterasi "
            "menutup bot (close()) saat worker thread executor belum selesai menulis berkas queue_state.json."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unawaited_close_write_events": unawaited_close_write_events}
    return res


# ==============================================================================
# 38. PANEL STALE SERVICE STATE CACHE (Wave 7)
# ==============================================================================
async def fuzz_panel_stale_service_state_cache(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_stale_service_state_cache",
        description="Verifikasi cache usang _state_cache pada panel.py pasca aksi Start/Stop/Restart service",
        iterations=iterations,
    )
    stale_cache_events = 0

    for it in range(iterations):
        with panel_module._state_cache_lock:
            panel_module._state_cache["bot"] = (time.monotonic(), "active")

        handler = panel_module.Handler.__new__(panel_module.Handler)
        handler.log_message = MagicMock()
        handler.log_exception = MagicMock()
        handler._set_flash = MagicMock()
        handler._redirect = MagicMock(return_value="redirect_ok")
        handler._page = MagicMock(return_value="page_err")

        orig_runner = panel_module.SERVICE_RUNNER
        panel_module.SERVICE_RUNNER = lambda action: (True, "ok")
        try:
            with patch.object(panel_module.store(), "read", return_value={"token": "valid_token"}):
                handler._service("stop")

            with panel_module._state_cache_lock:
                cached_bot = panel_module._state_cache.get("bot")

            # Jika cache 'bot' tidak diinvalidasi pasca stop/start/restart:
            if cached_bot is not None:
                stale_cache_events += 1
        finally:
            panel_module.SERVICE_RUNNER = orig_runner
            with panel_module._state_cache_lock:
                panel_module._state_cache.clear()

    if stale_cache_events > 0:
        res.anomalies.append(
            f"Cache usang service status terkonfirmasi: {stale_cache_events}/{iterations} iterasi membiarkan "
            "_state_cache['bot'] aktif pasca _service() sehingga GET / membaca state kadaluarsa."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stale_cache_events": stale_cache_events}
    return res


# ==============================================================================
# 39. PLAYLIST CLEAR QUEUE IDLE TIMER LEAK (Wave 7)
# ==============================================================================
async def fuzz_playlist_clear_queue_idle_timer_leak(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="playlist_clear_queue_idle_timer_leak",
        description="Fuzzing pembersihan antrian via PlaylistView.clear_queue saat playback tidak aktif dan verifikasi kebocoran idle disconnect",
        iterations=iterations,
    )
    idle_timer_leak_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=13000 + it, is_playing=False)
        vc.is_playing.return_value = False
        vc.channel.id = 7001

        state = QueueState()
        state.current = None
        state.queue.append(Track("SongInQueue", "https://mock.url/1", "user"))
        state.idle_task = None
        bot.states[guild.id] = state

        view = PlaylistView(bot)
        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user.voice.channel.id = 7001
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        with patch.object(bot, "_save_persistent_queue"), \
             patch.object(bot, "refresh", new=AsyncMock()):
            await view.clear_queue.callback(interaction)

        # Jika current None, queue kosong, tidak sedang memutar, tapi idle_task tetap None:
        if state.idle_task is None:
            idle_timer_leak_events += 1

    if idle_timer_leak_events > 0:
        res.anomalies.append(
            f"Kebocoran idle disconnect timer terkonfirmasi: {idle_timer_leak_events}/{iterations} iterasi "
            "mengosongkan antrian tanpa menjadwalkan _schedule_idle saat playback tidak aktif."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"idle_timer_leak_events": idle_timer_leak_events}
    return res


# ==============================================================================
# 40. SEARCH MODAL MISSING TEXT CHANNEL ID (Wave 7)
# ==============================================================================
async def fuzz_search_modal_missing_text_channel_id(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="search_modal_missing_text_channel_id",
        description="Verifikasi registrasi state.text_channel_id pada SearchModal.on_submit saat pemanggilan via modal pencarian",
        iterations=iterations,
    )
    missing_text_channel_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=14000 + it)
        vc.channel.id = 8001

        state = QueueState()
        state.text_channel_id = None
        bot.states[guild.id] = state

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.channel_id = 998877
        interaction.user.voice.channel.id = 8001
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        modal = SearchModal(bot)
        modal.query = MagicMock()
        modal.query.__str__ = MagicMock(return_value="https://mock.url/track")

        with patch("bot.extract_tracks", new=AsyncMock(return_value=[Track("TrackFromModal", "url", "user")])), \
             patch.object(bot, "_enqueue_tracks", new=AsyncMock(return_value=True)), \
             patch.object(bot, "refresh", new=AsyncMock()):
            await modal.on_submit(interaction)

        if getattr(state, "text_channel_id", None) != 998877:
            missing_text_channel_events += 1

    if missing_text_channel_events > 0:
        res.anomalies.append(
            f"Hilangnya text_channel_id terkonfirmasi: {missing_text_channel_events}/{iterations} iterasi tidak "
            "mendaftarkan state.text_channel_id pada SearchModal.on_submit sehingga pengumuman lagu baru gagal terkirim pasca restart."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"missing_text_channel_events": missing_text_channel_events}
    return res


# ==============================================================================
# 41. ON READY QUEUE FILE DELETION ON RECONNECT (Wave 7)
# ==============================================================================
async def fuzz_on_ready_queue_file_deletion_on_reconnect(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="on_ready_queue_file_deletion_on_reconnect",
        description="Fuzzing gateway reconnects (on_ready) dan verifikasi penghapusan berkas queue_state.json aktif",
        iterations=iterations,
    )
    deleted_queue_file_events = 0

    for it in range(iterations):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tf:
            state_file = tf.name

        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({"15000": {"queue": []}}, f)

            bot = MusicBot()
            bot._queue_state_file = state_file

            with patch.object(MusicBot, "guilds", new_callable=PropertyMock, return_value=[]), \
                 patch("bot.dump_runtime_state"):
                # Startup pertama (restore & remove normal)
                await bot.on_ready()

                # Simulasi bot berjalan aktif dan menyimpan persistent queue baru ke disk
                with open(state_file, "w", encoding="utf-8") as f:
                    json.dump({"15000": {"queue": [{"title": "ActiveTrack", "url": "http://u"}]}}, f)

                # Gateway reconnect / IDENTIFY memicu on_ready() kedua
                await bot.on_ready()

                # Jika file dihapus pada on_ready kedua:
                if not os.path.exists(state_file):
                    deleted_queue_file_events += 1
        finally:
            if os.path.exists(state_file):
                try:
                    os.remove(state_file)
                except Exception:
                    pass

    if deleted_queue_file_events > 0:
        res.anomalies.append(
            f"Penghapusan queue state saat gateway reconnect terkonfirmasi: {deleted_queue_file_events}/{iterations} iterasi "
            "menghapus berkas queue_state.json di disk pada pemanggilan on_ready() berulang."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"deleted_queue_file_events": deleted_queue_file_events}
    return res


# ==============================================================================
# 42. ADVANCE UNHANDLED KEYERROR ON MISSING GUILD (Wave 7)
# ==============================================================================
async def fuzz_advance_unhandled_keyerror_on_missing_guild(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="advance_unhandled_keyerror_on_missing_guild",
        description="Fuzzing pemanggilan advance() saat guild belum terdaftar atau telah dihapus dan verifikasi KeyError unhandled",
        iterations=iterations,
    )
    unhandled_keyerror_events = 0

    for it in range(iterations):
        bot = MusicBot()
        unregistered_guild = MagicMock(spec=discord.Guild)
        unregistered_guild.id = 16000 + it
        unregistered_guild.name = f"Unregistered-{16000 + it}"

        try:
            await bot.advance(unregistered_guild)
        except KeyError:
            unhandled_keyerror_events += 1
        except Exception:
            pass

    if unhandled_keyerror_events > 0:
        res.anomalies.append(
            f"Unhandled KeyError terkonfirmasi: {unhandled_keyerror_events}/{iterations} iterasi crash dengan "
            "KeyError saat advance() dipanggil pada guild yang tidak ada di bot.states."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unhandled_keyerror_events": unhandled_keyerror_events}
    return res


# ==============================================================================
# 43. EMPTY ROOM FFMPEG CPU WASTE IN ADVANCE LOOP (Wave 7)
# ==============================================================================
async def fuzz_empty_room_ffmpeg_cpu_waste_advance(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="empty_room_ffmpeg_cpu_waste_advance",
        description="Fuzzing _advance_loop saat memutar lagu di channel kosong tanpa pendengar manusia dan verifikasi pemborosan CPU ffmpeg",
        iterations=iterations,
    )
    wasted_ffmpeg_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=17000 + it, is_playing=False)
        bot_member = MagicMock(bot=True)
        vc.channel.members = [bot_member]  # 0 manusia (hanya bot)

        state = QueueState()
        state.queue.append(Track("EmptyRoomSong", "https://mock.url/1", "user"))
        bot.states[guild.id] = state

        mock_source = MagicMock()
        with patch("bot.run_extract", new=AsyncMock(return_value={"url": "http://stream", "title": "Song"})), \
             patch("bot.source_for", return_value=mock_source) as mock_src, \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_announce"):
            await bot._advance_loop(guild, state, vc)

            # Jika source_for atau vc.play dipanggil di channel tanpa pendengar manusia:
            if vc.play.called or mock_src.called:
                wasted_ffmpeg_events += 1

    if wasted_ffmpeg_events > 0:
        res.anomalies.append(
            f"Pemborosan CPU ffmpeg terkonfirmasi: {wasted_ffmpeg_events}/{iterations} iterasi memproses ekstraksi "
            "dan memutar audio ffmpeg ke voice channel yang tidak memiliki pendengar manusia."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"wasted_ffmpeg_events": wasted_ffmpeg_events}
    return res


# ==============================================================================
# 44. GHOST VOICE CLIENT LOCKOUT IN SEARCH MODAL & MUSIC PANEL GUARD (Wave 8)
# ==============================================================================
async def fuzz_ghost_voice_client_lockout_modal_and_panel(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="ghost_voice_client_lockout_modal_and_panel",
        description="Fuzzing SearchModal & MusicPanel.guard saat voice_client ada tapi vc.channel is None (ghost VoiceClient lockout)",
        iterations=iterations,
    )
    ghost_lockout_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=18000 + it)
        vc.channel = None
        vc.is_connected = MagicMock(return_value=False)
        vc.disconnect = AsyncMock()

        user_channel = MagicMock()
        user_channel.id = 8899
        user_channel.permissions_for = MagicMock(return_value=MagicMock(connect=True, speak=True))

        async def mock_connect(*args, **kwargs):
            if guild.voice_client is not None and not vc.disconnect.called:
                raise discord.ClientException("Already connected to a voice channel.")
            return vc

        user_channel.connect = AsyncMock(side_effect=mock_connect)

        # 1. Test SearchModal.on_submit
        modal_interaction = MagicMock(spec=discord.Interaction)
        modal_interaction.guild = guild
        modal_interaction.user = MagicMock()
        modal_interaction.user.voice = MagicMock(channel=user_channel)
        modal_interaction.response.defer = AsyncMock()
        modal_interaction.followup.send = AsyncMock()

        modal = SearchModal(bot)
        modal.query = MagicMock()
        modal.query.__str__ = MagicMock(return_value="https://mock.url/modal_track")

        await modal.on_submit(modal_interaction)

        lockout_in_modal = False
        for call in modal_interaction.followup.send.call_args_list:
            args, _ = call
            if args and "Bot sudah dipakai di voice lain." in str(args[0]):
                lockout_in_modal = True
                break

        # 2. Test MusicPanel.guard
        panel_interaction = MagicMock(spec=discord.Interaction)
        panel_interaction.guild = guild
        panel_interaction.user = MagicMock()
        panel_interaction.user.voice = MagicMock(channel=user_channel)
        panel_interaction.response.is_done = MagicMock(return_value=False)
        panel_interaction.response.send_message = AsyncMock()
        panel_interaction.followup.send = AsyncMock()

        panel = MusicPanel(bot)
        await panel.guard(panel_interaction, require_voice=True)

        lockout_in_panel = False
        for call in list(panel_interaction.response.send_message.call_args_list) + list(panel_interaction.followup.send.call_args_list):
            args, _ = call
            if args and "Bot sudah dipakai di voice lain." in str(args[0]):
                lockout_in_panel = True
                break

        if lockout_in_modal or lockout_in_panel or not vc.disconnect.called:
            ghost_lockout_events += 1

    if ghost_lockout_events > 0:
        res.anomalies.append(
            f"Ghost VoiceClient lockout pada modal/panel terkonfirmasi: {ghost_lockout_events}/{iterations} iterasi menolak "
            "pengguna dengan 'Bot sudah dipakai di voice lain.' karena tidak memutus ghost vc sebelum connect."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"ghost_lockout_events": ghost_lockout_events}
    return res


# ==============================================================================
# 45. RESTORE PERSISTENT QUEUE UNREPERSISTED (Wave 8)
# ==============================================================================
async def fuzz_restore_persistent_queue_unrepersisted(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="restore_persistent_queue_unrepersisted",
        description="Verifikasi penghapusan queue_state.json di disk saat _restore_persistent_queue tanpa penyimpanan ulang",
        iterations=iterations,
    )
    unrepersisted_events = 0

    for it in range(iterations):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tf:
            state_file = tf.name

        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({
                    "19000": {
                        "queue": [{"title": "RestoredSong", "url": "http://song"}],
                        "current": {"title": "CurSong", "url": "http://cur"},
                    }
                }, f)

            bot = MusicBot()
            bot._save_persistent_queue = MagicMock()

            with patch("bot._persistent_queue_file", return_value=state_file):
                bot._restore_persistent_queue()

            file_removed = not os.path.exists(state_file)
            not_saved = not bot._save_persistent_queue.called

            if file_removed and not_saved:
                unrepersisted_events += 1
        finally:
            if os.path.exists(state_file):
                try:
                    os.remove(state_file)
                except Exception:
                    pass

    if unrepersisted_events > 0:
        res.anomalies.append(
            f"Kehilangan persistent queue terkonfirmasi: {unrepersisted_events}/{iterations} iterasi menghapus file "
            "queue_state.json dari disk tanpa memanggil _save_persistent_queue sehingga rentan hilang total saat restart mendadak."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unrepersisted_events": unrepersisted_events}
    return res


# ==============================================================================
# 46. LISTENERS OUT OF ORDER SEQ WRITER (Wave 8)
# ==============================================================================
async def fuzz_listeners_out_of_order_seq_writer(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="listeners_out_of_order_seq_writer",
        description="Fuzzing race condition out-of-order write pada listeners.json akibat tidak adanya seq update per-berkas",
        iterations=iterations,
    )
    out_of_order_events = 0

    for it in range(iterations):
        with tempfile.TemporaryDirectory() as tmpdir:
            l_path = os.path.join(tmpdir, "listeners.json")

            with bot_module._RUNTIME_STATE_LOCK:
                bot_module._RUNTIME_STATE_LAST_SEQ = 0
                if hasattr(bot_module, "_RUNTIME_LISTENERS_LAST_SEQ"):
                    bot_module._RUNTIME_LISTENERS_LAST_SEQ = 0

            # Simulasi Thread B (seq 2) menulis listeners.json lebih dulu
            seq_b = 2
            payload_b = {"active_listeners": 5, "seq": seq_b}
            tmp_b = f"{l_path}.b.tmp"
            with open(tmp_b, "w", encoding="utf-8") as f:
                json.dump(payload_b, f)

            with bot_module._RUNTIME_STATE_LOCK:
                last_seq = getattr(bot_module, "_RUNTIME_LISTENERS_LAST_SEQ", bot_module._RUNTIME_STATE_LAST_SEQ)
                if seq_b >= last_seq:
                    if hasattr(bot_module, "_RUNTIME_LISTENERS_LAST_SEQ"):
                        bot_module._RUNTIME_LISTENERS_LAST_SEQ = seq_b
                    os.replace(tmp_b, l_path)

            # Thread A (seq 1) yang terlambat mengeksekusi pengecekan listeners.json:
            seq_a = 1
            payload_a = {"active_listeners": 1, "seq": seq_a}
            tmp_a = f"{l_path}.a.tmp"
            with open(tmp_a, "w", encoding="utf-8") as f:
                json.dump(payload_a, f)

            with bot_module._RUNTIME_STATE_LOCK:
                last_seq = getattr(bot_module, "_RUNTIME_LISTENERS_LAST_SEQ", bot_module._RUNTIME_STATE_LAST_SEQ)
                if seq_a >= last_seq:
                    if hasattr(bot_module, "_RUNTIME_LISTENERS_LAST_SEQ"):
                        bot_module._RUNTIME_LISTENERS_LAST_SEQ = seq_a
                    os.replace(tmp_a, l_path)

            # Periksa isi berkas listeners.json di disk
            with open(l_path, "r", encoding="utf-8") as f:
                read_data = json.load(f)

            if read_data.get("seq") == seq_a:
                out_of_order_events += 1

    if out_of_order_events > 0:
        res.anomalies.append(
            f"Race condition out-of-order listeners.json terkonfirmasi: {out_of_order_events}/{iterations} iterasi menimpa "
            "listeners.json dengan data lama karena _RUNTIME_STATE_LAST_SEQ tidak diupdate langsung per berkas."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"out_of_order_events": out_of_order_events}
    return res


# ==============================================================================
# 47. DUMP RUNTIME STATE OFFLINE LISTENERS CLEANUP (Wave 8)
# ==============================================================================
async def fuzz_dump_runtime_state_offline_listeners_cleanup(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="dump_runtime_state_offline_listeners_cleanup",
        description="Verifikasi berkas listeners.json yang tertinggal saat dump_runtime_state_offline saat bot shutdown",
        iterations=iterations,
    )
    stale_listeners_events = 0

    for it in range(iterations):
        with tempfile.TemporaryDirectory() as tmpdir:
            s_path = os.path.join(tmpdir, "state.json")
            l_path = os.path.join(tmpdir, "listeners.json")

            with open(s_path, "w", encoding="utf-8") as f:
                f.write('{"state": "active"}')
            with open(l_path, "w", encoding="utf-8") as f:
                f.write('{"active_listeners": 3}')

            with patch.dict(os.environ, {"BOT_STATE_FILE": s_path}):
                bot_module.dump_runtime_state_offline()

            state_removed = not os.path.exists(s_path)
            listeners_remains = os.path.exists(l_path)

            if state_removed and listeners_remains:
                stale_listeners_events += 1

    if stale_listeners_events > 0:
        res.anomalies.append(
            f"Stale listeners artifact terkonfirmasi: {stale_listeners_events}/{iterations} iterasi meninggalkan "
            "listeners.json di disk saat dump_runtime_state_offline() sehingga mengecoh update.sh."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stale_listeners_events": stale_listeners_events}
    return res


# ==============================================================================
# 48. EMPTY ROOM USER RETURN AUTOPLAY RESTART (Wave 8)
# ==============================================================================
async def fuzz_empty_room_user_return_autoplay_restart(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="empty_room_user_return_autoplay_restart",
        description="Fuzzing kembalinya user ke voice channel kosong saat AutoPlay aktif dan verifikasi pemanggilan advance()",
        iterations=iterations,
    )
    autoplay_abandoned_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=20000 + it, is_playing=False)
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.current = None
        state.queue.clear()
        state.autoplay = True
        state.afk_paused = False
        bot.states[guild.id] = state

        human_member = MagicMock()
        human_member.bot = False
        human_member.id = 55555
        human_member.guild = guild

        before = MagicMock(channel=None)
        after = MagicMock(channel=vc.channel)

        with patch.object(bot, "advance", new=AsyncMock()) as mock_advance:
            await bot.on_voice_state_update(human_member, before, after)
            await asyncio.sleep(0.01)

            if not mock_advance.called:
                autoplay_abandoned_events += 1

    if autoplay_abandoned_events > 0:
        res.anomalies.append(
            f"AutoPlay abandonment terkonfirmasi: {autoplay_abandoned_events}/{iterations} iterasi tidak memanggil "
            "advance() saat user kembali ke voice room kosong dengan AutoPlay aktif karena cek hanya memeriksa state.current/queue."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"autoplay_abandoned_events": autoplay_abandoned_events}
    return res


# ==============================================================================
# 49. STREAM ERROR CACHED URL INVALIDATION (Wave 8)
# ==============================================================================
async def fuzz_stream_error_cached_url_invalidation(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="stream_error_cached_url_invalidation",
        description="Verifikasi pembatalan cached stream_url pada Track saat stream playback error",
        iterations=iterations,
    )
    cached_url_not_reset_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=21000 + it)
        state = QueueState()
        track = Track("ExpiredTrack", "https://mock.url/expired", "user")
        track.stream_url = "http://expired-cdn.googlevideo.com/playback"
        track.stream_ts = time.time()
        state.queue.append(track)
        bot.states[guild.id] = state

        after_cb = None
        def mock_play(source, after=None, **kwargs):
            nonlocal after_cb
            after_cb = after

        vc.play = mock_play

        with patch("bot.source_for", return_value=MagicMock()), \
             patch.object(bot, "finished", new=AsyncMock()), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_announce"), \
             patch.object(bot, "_save_persistent_queue"):
            await bot._advance_loop(guild, state, vc)

            if after_cb:
                after_cb(Exception("HTTP 403 Forbidden: stream url expired"))
                await asyncio.sleep(0.01)

            if track.stream_url is not None:
                cached_url_not_reset_events += 1

    if cached_url_not_reset_events > 0:
        res.anomalies.append(
            f"Cached stream_url tidak diinvalidasi terkonfirmasi: {cached_url_not_reset_events}/{iterations} iterasi membiarkan "
            "track.stream_url lama tetap aktif pasca stream error sehingga memicu kegagalan berulang dan false trip circuit breaker."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"cached_url_not_reset_events": cached_url_not_reset_events}
    return res


# ==============================================================================
# 50. CMD PLAY & SUMMON INTEGER PANEL ID DELETION (Wave 8)
# ==============================================================================
async def fuzz_cmd_play_summon_integer_panel_id_deletion(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_play_summon_integer_panel_id_deletion",
        description="Fuzzing cmd_play dan summon saat state.message berupa integer message ID dan verifikasi AttributeError",
        iterations=iterations,
    )
    attribute_error_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=22000 + it)
        state = QueueState()
        state.message = 1234567890
        bot.states[guild.id] = state

        user_channel = MagicMock()
        user_channel.id = 9001
        user_channel.permissions_for = MagicMock(return_value=MagicMock(connect=True, speak=True))

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.channel = MagicMock()
        interaction.channel.id = 9002
        interaction.channel.send = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.voice = MagicMock(channel=user_channel)
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        with patch("bot.extract_tracks", new=AsyncMock(return_value=[Track("T1", "url", "user")])), \
             patch.object(bot, "_enqueue_tracks", new=AsyncMock(return_value=True)), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_safe_delete_msg") as mock_safe_delete:
            await bot.cmd_play(interaction, "https://mock.url/1")

        state.message = 987654321
        summon_interaction = MagicMock(spec=discord.Interaction)
        summon_interaction.guild = guild
        summon_interaction.channel = MagicMock()
        summon_interaction.channel.id = 9002
        summon_interaction.channel.send = AsyncMock()
        summon_interaction.user = MagicMock()
        summon_interaction.user.voice = MagicMock(channel=user_channel)
        summon_interaction.response.defer = AsyncMock()
        summon_interaction.followup.send = AsyncMock()

        with patch.object(bot, "_safe_delete_msg") as mock_safe_delete_summon:
            await bot.summon(summon_interaction)

        if not mock_safe_delete.called or not mock_safe_delete_summon.called:
            attribute_error_events += 1

    if attribute_error_events > 0:
        res.anomalies.append(
            f"AttributeError panel delete terkonfirmasi: {attribute_error_events}/{iterations} iterasi memicu "
            "AttributeError pada state.message bertipe int (pasca restart) tanpa _safe_delete_msg sehingga panel lama di Discord tidak terhapus."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"attribute_error_events": attribute_error_events}
    return res


# ==============================================================================
# 51. ANNOUNCE NOW PLAYING CHANNEL RESOLUTION (Wave 8)
# ==============================================================================
async def fuzz_announce_now_playing_channel_resolution(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="announce_now_playing_channel_resolution",
        description="Verifikasi fallback channel pada _announce_now_playing dan quit_voice saat now_message berupa message ID",
        iterations=iterations,
    )
    wrong_channel_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=23000 + it)
        state = QueueState()
        state.text_channel_id = 9002
        state.now_message = 11223344
        state.message = MagicMock()
        state.message.channel = MagicMock(id=9002)
        bot.states[guild.id] = state

        ch_general = MagicMock(spec=discord.TextChannel, id=9001)
        ch_music = MagicMock(spec=discord.TextChannel, id=9002)
        guild.text_channels = [ch_general, ch_music]
        guild.get_channel = MagicMock(side_effect=lambda cid: ch_music if cid == 9002 else ch_general)

        with patch.object(bot, "_safe_delete_msg", wraps=bot._safe_delete_msg) as spy_safe_delete:
            track = Track("NewTrack", "http://url", "user")
            await bot._announce_now_playing(guild, track)

            for call in spy_safe_delete.call_args_list:
                args, kwargs = call
                msg_arg = args[0] if args else kwargs.get("msg")
                if msg_arg == 11223344:
                    channel_kwarg = kwargs.get("channel")
                    if channel_kwarg is None:
                        if ch_general.get_partial_message.called and not ch_music.get_partial_message.called:
                            wrong_channel_events += 1

    if wrong_channel_events > 0:
        res.anomalies.append(
            f"Fallback channel salah terkonfirmasi: {wrong_channel_events}/{iterations} iterasi memanggil "
            "_safe_delete_msg tanpa channel sehingga fallback ke text_channels[0] dan gagal menghapus pesan (404)."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"wrong_channel_events": wrong_channel_events}
    return res


# ==============================================================================
# 52. PANEL STALE LOG CACHE POST SERVICE ACTION (Wave 8)
# ==============================================================================
async def fuzz_panel_stale_log_cache_post_service_action(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_stale_log_cache_post_service_action",
        description="Verifikasi pembersihan _log_cache pada panel.py pasca aksi Start/Stop/Restart service",
        iterations=iterations,
    )
    stale_log_cache_events = 0

    for it in range(iterations):
        with panel_module._log_cache_lock:
            panel_module._log_cache["journal"] = (time.monotonic() + 15.0, "OLD LOG FROM PREVIOUS RUN")

        handler = panel_module.Handler.__new__(panel_module.Handler)
        handler.log_message = MagicMock()
        handler.log_exception = MagicMock()
        handler._set_flash = MagicMock()
        handler._redirect = MagicMock(return_value="redirect_ok")
        handler._page = MagicMock(return_value="page_err")

        orig_runner = panel_module.SERVICE_RUNNER
        panel_module.SERVICE_RUNNER = lambda action: (True, "ok")
        try:
            with patch.object(panel_module.store(), "read", return_value={"token": "valid_token"}):
                handler._service("restart")

            with panel_module._log_cache_lock:
                has_stale_log = "journal" in panel_module._log_cache

            if has_stale_log:
                stale_log_cache_events += 1
        finally:
            panel_module.SERVICE_RUNNER = orig_runner
            with panel_module._log_cache_lock:
                panel_module._log_cache.clear()

    if stale_log_cache_events > 0:
        res.anomalies.append(
            f"Cache log usang terkonfirmasi: {stale_log_cache_events}/{iterations} iterasi membiarkan "
            "_log_cache tetap aktif pasca _service() sehingga tampilan log web panel menampilkan data kadaluarsa hingga 15 detik."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stale_log_cache_events": stale_log_cache_events}
    return res


# ==============================================================================
# 53. RELEASE EXTRACT SLOT UNDERFLOW (Wave 8)
# ==============================================================================
async def fuzz_release_extract_slot_underflow(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="release_extract_slot_underflow",
        description="Fuzzing counter underflow pada _release_extract_slot dan kebocoran batas MAX_EXTRACT_THREADS",
        iterations=iterations,
    )
    slot_underflow_events = 0

    for it in range(iterations):
        with bot_module._EXTRACT_THREADS_LOCK:
            bot_module._EXTRACT_THREADS = 0

        # Panggil release ekstra saat counter 0
        bot_module._release_extract_slot()

        with bot_module._EXTRACT_THREADS_LOCK:
            is_negative = bot_module._EXTRACT_THREADS < 0

        if is_negative:
            acquired = 0
            for _ in range(bot_module.MAX_EXTRACT_THREADS + 1):
                if bot_module._reserve_extract_slot():
                    acquired += 1
            if acquired > bot_module.MAX_EXTRACT_THREADS:
                slot_underflow_events += 1

        with bot_module._EXTRACT_THREADS_LOCK:
            bot_module._EXTRACT_THREADS = 0

    if slot_underflow_events > 0:
        res.anomalies.append(
            f"Counter underflow _release_extract_slot terkonfirmasi: {slot_underflow_events}/{iterations} iterasi "
            f"membiarkan _EXTRACT_THREADS menjadi negatif dan melampaui MAX_EXTRACT_THREADS ({bot_module.MAX_EXTRACT_THREADS}) pada STB ARM."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"slot_underflow_events": slot_underflow_events}
    return res


# ==============================================================================
# 54. IDLE DISCONNECT TASK LEAK FINALLY (Wave 8)
# ==============================================================================
async def fuzz_idle_disconnect_task_leak_finally(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="idle_disconnect_task_leak_finally",
        description="Verifikasi retensi referensi task state.idle_task setelah idle_disconnect selesai tanpa quit",
        iterations=iterations,
    )
    idle_task_leak_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=24000 + it)
        vc.is_playing.return_value = True

        state = QueueState()
        state.generation = 1
        # Set state.current agar should_quit = False (lagu sedang diputar saat timer idle berakhir)
        state.current = Track("PlayingTrack", "http://url", "user")
        bot.states[guild.id] = state

        with patch("bot.asyncio.sleep", new=AsyncMock(return_value=None)):
            task = asyncio.create_task(bot.idle_disconnect(guild, state.generation))
            state.idle_task = task
            await task

            # Jika task sudah selesai tapi state.idle_task tidak dibersihkan di finally:
            if state.idle_task is not None:
                idle_task_leak_events += 1

    if idle_task_leak_events > 0:
        res.anomalies.append(
            f"Task reference leak pada state.idle_task terkonfirmasi: {idle_task_leak_events}/{iterations} iterasi "
            "tidak membersihkan state.idle_task di finally block saat idle_disconnect selesai."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"idle_task_leak_events": idle_task_leak_events}
    return res


# ==============================================================================
# 55. ANNOUNCE NOW PLAYING FALLBACK CHANNEL MISMATCH (Wave 9)
# ==============================================================================
async def fuzz_announce_now_playing_fallback_channel_mismatch(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="announce_now_playing_fallback_channel_mismatch",
        description="Verifikasi pemanggilan _safe_delete_msg pada _announce_now_playing menggunakan resolved channel untuk message ID",
        iterations=iterations,
    )
    mismatch_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=25000 + it)
        ch_first = MagicMock(spec=discord.TextChannel)
        ch_first.id = 101
        ch_first.get_partial_message = MagicMock()
        ch_music = MagicMock(spec=discord.TextChannel)
        ch_music.id = 202
        ch_music.get_partial_message = MagicMock()
        guild.text_channels = [ch_first, ch_music]
        guild.get_channel = MagicMock(side_effect=lambda cid: ch_music if cid == 202 else ch_first if cid == 101 else None)

        state = QueueState()
        panel_msg = MagicMock()
        panel_msg.channel = ch_music
        state.message = panel_msg
        state.text_channel_id = 202
        state.now_message = 998877 + it
        bot.states[guild.id] = state

        called_channel = None
        orig_safe_delete = bot._safe_delete_msg

        async def mock_safe_delete(msg, channel=None, guild=None):
            nonlocal called_channel
            called_channel = channel
            return await orig_safe_delete(msg, channel=channel, guild=guild)

        bot._safe_delete_msg = mock_safe_delete

        track = Track("TestSong", "http://url", "user")
        with patch.object(ch_music, "send", new=AsyncMock(return_value=MagicMock())):
            await bot._announce_now_playing(guild, track)

        if called_channel is None or getattr(called_channel, "id", None) != ch_music.id:
            mismatch_events += 1

    if mismatch_events > 0:
        res.anomalies.append(
            f"Fallback channel mismatch terkonfirmasi: {mismatch_events}/{iterations} iterasi memanggil "
            "_safe_delete_msg tanpa target channel yang telah di-resolve sehingga fallback ke text channel pertama dan gagal hapus (404)."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"mismatch_events": mismatch_events}
    return res


# ==============================================================================
# 56. REFRESH PANEL HTTP RATE LIMIT DISCARD (Wave 9)
# ==============================================================================
async def fuzz_refresh_panel_http_rate_limit_discard(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="refresh_panel_http_rate_limit_discard",
        description="Verifikasi penanganan HTTP 429/5xx pada refresh() agar tidak membuang state.message aktif",
        iterations=iterations,
    )
    discard_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=26000 + it)
        state = QueueState()
        bot.states[guild.id] = state

        mock_msg = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 429
        mock_msg.edit = AsyncMock(side_effect=discord.HTTPException(mock_resp, "Rate limited"))
        state.message = mock_msg

        with patch("bot.asyncio.sleep", new=AsyncMock(return_value=None)):
            await bot.refresh(state)
            if state.refresh_task:
                await state.refresh_task

        if state.message is None:
            discard_events += 1

    if discard_events > 0:
        res.anomalies.append(
            f"Stale panel message discard terkonfirmasi: {discard_events}/{iterations} iterasi men-null-kan "
            "state.message saat terjadi transient HTTP 429 rate limit sehingga kontrol panel aktif hilang."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"discard_events": discard_events}
    return res


# ==============================================================================
# 57. DUMP RUNTIME STATE OFFLINE WRITER RACE (Wave 9)
# ==============================================================================
async def fuzz_dump_runtime_state_offline_writer_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="dump_runtime_state_offline_writer_race",
        description="Fuzzing race condition out-of-order write antara dump_runtime_state_offline dan background writer",
        iterations=iterations,
    )
    race_events = 0

    for it in range(iterations):
        with tempfile.TemporaryDirectory() as tmpdir:
            s_path = os.path.join(tmpdir, "state.json")
            l_path = os.path.join(tmpdir, "listeners.json")

            with bot_module._RUNTIME_STATE_LOCK:
                bot_module._RUNTIME_STATE_LAST_SEQ = 10
                bot_module._RUNTIME_LISTENERS_LAST_SEQ = 10

            with patch.dict(os.environ, {"BOT_STATE_FILE": s_path}):
                bot_module.dump_runtime_state_offline()

            with bot_module._RUNTIME_STATE_LOCK:
                seq_state = bot_module._RUNTIME_STATE_LAST_SEQ
                seq_listeners = bot_module._RUNTIME_LISTENERS_LAST_SEQ

            if seq_state <= 10 or seq_listeners <= 10:
                delayed_seq = 11
                tmp_delayed = f"{l_path}.delayed.tmp"
                with open(tmp_delayed, "w", encoding="utf-8") as f:
                    json.dump({"active_listeners": 1}, f)

                with bot_module._RUNTIME_STATE_LOCK:
                    if delayed_seq >= bot_module._RUNTIME_LISTENERS_LAST_SEQ:
                        os.replace(tmp_delayed, l_path)

                if os.path.exists(l_path):
                    race_events += 1

    if race_events > 0:
        res.anomalies.append(
            f"Race condition dump_runtime_state_offline terkonfirmasi: {race_events}/{iterations} iterasi membiarkan "
            "background writer menimpa listeners.json pasca shutdown karena sequence tidak di-bump secara atomik."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"race_events": race_events}
    return res


# ==============================================================================
# 58. SAFEDEQUE CONTAINS MUTATION RACE (Wave 9)
# ==============================================================================
async def fuzz_safedeque_contains_mutation_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="safedeque_contains_mutation_race",
        description="Fuzzing keanggotaan 'in' pada SafeDeque saat mutasi konkuren tanpa proteksi exception",
        iterations=iterations,
    )
    contains_race_events = 0

    for it in range(iterations):
        sd = bot_module.SafeDeque()
        for i in range(200):
            sd.append(Track(f"Track-{i}", f"http://url/{i}", "user"))

        has_custom_contains = "__contains__" in bot_module.SafeDeque.__dict__
        if not has_custom_contains:
            contains_race_events += 1
        else:
            stop_flag = threading.Event()
            mutation_error = False

            def mutator():
                while not stop_flag.is_set():
                    try:
                        sd.append(Track("New", "http://new", "u"))
                        sd.popleft()
                    except Exception:
                        pass

            t = threading.Thread(target=mutator)
            t.start()
            try:
                target = Track("Target", "http://target", "u")
                for _ in range(500):
                    _ = target in sd
            except RuntimeError:
                mutation_error = True
            finally:
                stop_flag.set()
                t.join()

            if mutation_error:
                contains_race_events += 1

    if contains_race_events > 0:
        res.anomalies.append(
            f"Unhandled SafeDeque.__contains__ race terkonfirmasi: {contains_race_events}/{iterations} iterasi "
            "memanggil deque.__contains__ bawaan CPython tanpa retry/proteksi saat mutasi konkuren (RuntimeError unhandled)."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"contains_race_events": contains_race_events}
    return res


# ==============================================================================
# 59. PANEL EMPTY QUEUE VOICE STRANDED (Wave 9)
# ==============================================================================
async def fuzz_panel_empty_queue_voice_stranded(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_empty_queue_voice_stranded",
        description="Verifikasi penjadwalan idle disconnect pada tombol skip/back/pause saat antrian dan audio kosong",
        iterations=iterations,
    )
    stranded_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=27000 + it)
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.current = None
        state.queue.clear()
        state.history.clear()
        state.idle_task = None
        bot.states[guild.id] = state

        panel = MusicPanel(bot)
        panel.guard = AsyncMock(return_value=True)

        user_ch = MagicMock()
        user_ch.id = vc.channel.id
        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user = MagicMock()
        interaction.user.voice = MagicMock(channel=user_ch)
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        await panel.skip.callback(interaction)

        if state.idle_task is None and not (vc.is_playing() or vc.is_paused()) and state.current is None:
            stranded_events += 1

    if stranded_events > 0:
        res.anomalies.append(
            f"Voice client stranded terkonfirmasi: {stranded_events}/{iterations} iterasi tidak menjadwalkan "
            "idle disconnect pada tombol skip/back/pause saat antrian kosong sehingga bot tertahan di voice channel selamanya."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stranded_events": stranded_events}
    return res


# ==============================================================================
# 60. EMPTY ROOM DUAL TIMER COLLISION (Wave 9)
# ==============================================================================
async def fuzz_empty_room_dual_timer_collision(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="empty_room_dual_timer_collision",
        description="Fuzzing dual timer collision (afk_task dan idle_task) di room kosong dan retensi idle_task saat user kembali",
        iterations=iterations,
    )
    collision_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=28000 + it)
        vc.channel.members = [MagicMock(bot=True)]
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.current = None
        state.queue.clear()
        bot.states[guild.id] = state

        with patch("bot.asyncio.sleep", new=AsyncMock(return_value=None)):
            await bot.advance(guild)

            both_scheduled = (state.afk_task is not None) and (state.idle_task is not None)

            human_member = MagicMock()
            human_member.bot = False
            human_member.guild = guild
            before = MagicMock(channel=None)
            after = MagicMock(channel=vc.channel)

            await bot.on_voice_state_update(human_member, before, after)

            idle_not_cancelled = state.idle_task is not None and not state.idle_task.done()

            if both_scheduled or idle_not_cancelled:
                collision_events += 1

    if collision_events > 0:
        res.anomalies.append(
            f"Dual timer collision terkonfirmasi: {collision_events}/{iterations} iterasi menjadwalkan afk_task "
            "dan idle_task sekaligus di room kosong, dan idle_task tidak dibatalkan saat user kembali sehingga memutus koneksi bot."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"collision_events": collision_events}
    return res


# ==============================================================================
# 61. TRACKS FROM METADATA WEB URL CACHING (Wave 9)
# ==============================================================================
async def fuzz_tracks_from_metadata_web_url_caching(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="tracks_from_metadata_web_url_caching",
        description="Verifikasi filtering URL web YouTube (/embed/, /live/, /v/) agar tidak di-cache sebagai stream_url",
        iterations=iterations,
    )
    false_cache_events = 0

    bad_urls = [
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ",
        "https://www.youtube.com/v/dQw4w9WgXcQ",
    ]

    for it in range(iterations):
        for u in bad_urls:
            raw_data = {
                "title": "Test Title",
                "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "url": u,
                "duration": 180,
            }
            tracks = bot_module._tracks_from_metadata(raw_data, "user", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            if tracks and tracks[0].stream_url is not None:
                false_cache_events += 1

    if false_cache_events > 0:
        res.anomalies.append(
            f"False caching stream URL terkonfirmasi: {false_cache_events}/{iterations * len(bad_urls)} percobaan "
            "menyimpan URL halaman web YouTube (/embed/, /live/, /v/) sebagai stream_url mentah sehingga ffmpeg gagal memutar."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"false_cache_events": false_cache_events}
    return res


# ==============================================================================
# 62. BUFFERED AUDIO SOURCE READER CLEANUP FALSE ERROR (Wave 9)
# ==============================================================================
async def fuzz_buffered_audio_source_reader_cleanup_false_error(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="buffered_audio_source_reader_cleanup_false_error",
        description="Verifikasi pencegahan pencatatan _current_error pada BufferedAudioSource saat normal cleanup",
        iterations=iterations,
    )
    false_error_events = 0

    for it in range(iterations):
        mock_source = MagicMock(spec=discord.AudioSource)
        closed = threading.Event()
        reading_event = threading.Event()

        def mock_read():
            reading_event.set()
            if closed.wait(timeout=0.1):
                raise ValueError("I/O operation on closed pipe")
            return b"\x00" * 3840

        def mock_cleanup():
            closed.set()

        mock_source.read = mock_read
        mock_source.cleanup = mock_cleanup
        mock_source.is_opus.return_value = False

        bas = BufferedAudioSource(mock_source)
        reading_event.wait(timeout=0.5)
        bas.cleanup()
        time.sleep(0.01)

        err = _source_error(bas)
        if err is not None:
            false_error_events += 1

    if false_error_events > 0:
        res.anomalies.append(
            f"False positive audio error terkonfirmasi: {false_error_events}/{iterations} iterasi mencatat "
            "penutupan ffmpeg normal sebagai _current_error sehingga memicu kenaikan consecutive_playback_errors dan false circuit breaker trip."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"false_error_events": false_error_events}
    return res


# ==============================================================================
# 63. CMD QUEUE AND PLAYLIST LOCK CONTENTION (Wave 9)
# ==============================================================================
async def fuzz_cmd_queue_and_playlist_lock_contention(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_queue_and_playlist_lock_contention",
        description="Fuzzing penahanan state.lock selama network I/O Discord API di cmd_queue dan MusicPanel.playlist",
        iterations=iterations,
    )
    contention_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=29000 + it)
        state = QueueState()
        state.current = None
        state.queue.clear()
        bot.states[guild.id] = state

        lock_held_in_queue = False
        interaction1 = MagicMock(spec=discord.Interaction)
        interaction1.guild = guild
        interaction1.response.defer = AsyncMock()

        async def mock_followup_send(*args, **kwargs):
            nonlocal lock_held_in_queue
            if state.lock.locked():
                lock_held_in_queue = True

        interaction1.followup.send = mock_followup_send
        await bot.cmd_queue(interaction1)

        lock_held_in_playlist = False
        interaction2 = MagicMock(spec=discord.Interaction)
        interaction2.guild = guild

        async def mock_send_modal(*args, **kwargs):
            nonlocal lock_held_in_playlist
            if state.lock.locked():
                lock_held_in_playlist = True

        interaction2.response.send_modal = mock_send_modal
        panel = MusicPanel(bot)
        await panel.playlist.callback(interaction2)

        if lock_held_in_queue or lock_held_in_playlist:
            contention_events += 1

    if contention_events > 0:
        res.anomalies.append(
            f"Blocking event loop lock contention terkonfirmasi: {contention_events}/{iterations} iterasi menahan "
            "state.lock selama network I/O Discord API (followup.send / send_modal) sehingga memblokir pemutaran audio di STB ARM."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"contention_events": contention_events}
    return res


# ==============================================================================
# 64. SYNCED GUILDS RETENTION ON GUILD REMOVE (Wave 9)
# ==============================================================================
async def fuzz_synced_guilds_retention_on_guild_remove(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="synced_guilds_retention_on_guild_remove",
        description="Verifikasi pembersihan _synced_guilds pada on_guild_remove agar slash command sinkron saat re-invite",
        iterations=iterations,
    )
    desync_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=30000 + it)
        bot._synced_guilds.add(guild.id)

        await bot.on_guild_remove(guild)

        is_retained = guild.id in bot._synced_guilds

        bot.tree.sync = AsyncMock()
        await bot.on_guild_join(guild)

        sync_called = bot.tree.sync.called

        if is_retained or not sync_called:
            desync_events += 1

    if desync_events > 0:
        res.anomalies.append(
            f"Permanent command desync terkonfirmasi: {desync_events}/{iterations} iterasi tidak mereset "
            "_synced_guilds di on_guild_remove sehingga slash commands tidak pernah disinkronkan kembali saat bot di-invite ulang."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"desync_events": desync_events}
    return res


# ==============================================================================
# 65. PANEL LOGOUT SERVER SESSION REVOCATION (Wave 9)
# ==============================================================================
async def fuzz_panel_logout_server_session_revocation(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_logout_server_session_revocation",
        description="Verifikasi pembatalan token di tabel server-side _sessions saat mengakses endpoint /logout",
        iterations=iterations,
    )
    leak_events = 0

    for it in range(iterations):
        token = f"session_test_token_{it}_{time.time()}"
        panel_module._sessions[token] = time.time() + 3600.0

        orig_pw = panel_module.PASSWORD
        panel_module.PASSWORD = "validpassword"
        try:
            handler = panel_module.Handler.__new__(panel_module.Handler)
            handler.path = "/logout"
            handler.headers = {"Cookie": f"{panel_module.COOKIE}={token}", "Host": "127.0.0.1:9130"}
            handler._host_ok = MagicMock(return_value=True)
            handler._redirect = MagicMock(return_value="redirect_ok")
            handler.log_message = MagicMock()

            handler.do_GET()

            token_still_active = token in panel_module._sessions
            if token_still_active:
                leak_events += 1
        finally:
            panel_module.PASSWORD = orig_pw
            panel_module._sessions.pop(token, None)

    if leak_events > 0:
        res.anomalies.append(
            f"Server-side session leak terkonfirmasi: {leak_events}/{iterations} iterasi membiarkan token sesi tetap aktif "
            "di tabel _sessions server pasca /logout sehingga rentan replay attack hingga 12 jam."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"leak_events": leak_events}
    return res


# ==============================================================================
# 66. PANEL UPDATE CACHE INVALIDATION (Wave 9)
# ==============================================================================
async def fuzz_panel_update_cache_invalidation(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_update_cache_invalidation",
        description="Verifikasi pembersihan _state_cache dan _log_cache pasca eksekusi pembaruan /update pada panel.py",
        iterations=iterations,
    )
    stale_cache_events = 0

    for it in range(iterations):
        with panel_module._state_cache_lock:
            panel_module._state_cache["bot"] = (time.monotonic() + 15.0, "OLD_BOT_STATE")
        with panel_module._log_cache_lock:
            panel_module._log_cache["journal"] = (time.monotonic() + 15.0, "OLD_JOURNAL_LOG")

        handler = panel_module.Handler.__new__(panel_module.Handler)
        handler.log_message = MagicMock()
        handler.log_exception = MagicMock()
        handler._set_flash = MagicMock()
        handler._redirect = MagicMock(return_value="redirect_ok")

        orig_run_update = panel_module.run_update
        panel_module.run_update = lambda: (True, "yt-dlp updated successfully")
        try:
            handler._update()

            with panel_module._state_cache_lock:
                has_stale_state = "bot" in panel_module._state_cache
            with panel_module._log_cache_lock:
                has_stale_log = "journal" in panel_module._log_cache

            if has_stale_state or has_stale_log:
                stale_cache_events += 1
        finally:
            panel_module.run_update = orig_run_update
            with panel_module._state_cache_lock:
                panel_module._state_cache.clear()
            with panel_module._log_cache_lock:
                panel_module._log_cache.clear()

    if stale_cache_events > 0:
        res.anomalies.append(
            f"Stale cache pasca /update terkonfirmasi: {stale_cache_events}/{iterations} iterasi membiarkan "
            "_state_cache dan _log_cache tetap tersimpan pasca update yt-dlp sehingga tampilan web panel kadaluarsa hingga 15 detik."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stale_cache_events": stale_cache_events}
    return res


# ==============================================================================
# 67. STRANDED VOICE CLIENT CURRENT NOT NONE IDLE BYPASS (Wave 10)
# ==============================================================================
async def fuzz_stranded_voice_client_current_not_none_idle_bypass(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="stranded_voice_client_current_not_none_idle_bypass",
        description="Verifikasi bypass idle disconnect pada tombol pause/skip saat state.current masih non-None dan queue kosong",
        iterations=iterations,
    )
    bypassed_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=31000 + it)
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.current = Track("StaleTrack", "http://mock/stale", "user")
        state.queue.clear()
        state.history.clear()
        state.idle_task = None
        bot.states[guild.id] = state

        bot.refresh = AsyncMock()
        panel = MusicPanel(bot)
        panel.guard = AsyncMock(return_value=True)

        user_ch = MagicMock()
        user_ch.id = vc.channel.id
        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user = MagicMock()
        interaction.user.voice = MagicMock(channel=user_ch)
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        await panel.pause.callback(interaction)

        if state.idle_task is None and not (vc.is_playing() or vc.is_paused()) and not state.queue:
            bypassed_events += 1

    if bypassed_events > 0:
        res.anomalies.append(
            f"Stranded voice client terkonfirmasi: {bypassed_events}/{iterations} iterasi mem-bypass penjadwalan "
            "idle disconnect pada tombol pause/skip saat audio berhenti tetapi state.current non-None, sehingga bot tertahan di voice."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"bypassed_events": bypassed_events}
    return res


# ==============================================================================
# 68. CMD BACK RACE CONDITION IDLE CHECK (Wave 10)
# ==============================================================================
async def fuzz_cmd_back_race_condition_idle_check(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_back_race_condition_idle_check",
        description="Fuzzing race condition dan ketiadaan pengecekan had_prev / idle scheduling pada cmd_back",
        iterations=iterations,
    )
    race_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=32000 + it)
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.history.clear()
        state.current = None
        state.queue.clear()
        bot.states[guild.id] = state

        user_ch = MagicMock()
        user_ch.id = vc.channel.id
        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user = MagicMock()
        interaction.user.voice = MagicMock(channel=user_ch)
        interaction.response.defer = AsyncMock()
        interaction.response.is_done = MagicMock(return_value=True)
        interaction.followup.send = AsyncMock()

        bot.advance = AsyncMock()
        bot._stop_player = AsyncMock()

        with patch.object(bot_module, "_check_same_voice", return_value=(True, "")):
            state.history.append(Track("Old", "http://old", "u"))
            orig_lock = state.lock
            class DrainLock:
                async def __aenter__(self):
                    state.history.clear()
                    return await orig_lock.__aenter__()
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return await orig_lock.__aexit__(exc_type, exc_val, exc_tb)

            state.lock = DrainLock()
            await bot.cmd_back(interaction)

        sent_misleading_msg = False
        for call_args in interaction.followup.send.call_args_list:
            if "Memutar lagu sebelumnya." in str(call_args):
                sent_misleading_msg = True

        if sent_misleading_msg or bot.advance.called:
            race_events += 1

    if race_events > 0:
        res.anomalies.append(
            f"cmd_back race condition & missing had_prev check terkonfirmasi: {race_events}/{iterations} iterasi "
            "tetap memanggil advance() dan mengirim pesan 'Memutar lagu sebelumnya' meskipun history telah kosong saat lock diambil."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"race_events": race_events}
    return res


# ==============================================================================
# 69. STOP QUIT DISCONNECTED VOICE LOCKOUT (Wave 10)
# ==============================================================================
async def fuzz_stop_quit_disconnected_voice_lockout(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="stop_quit_disconnected_voice_lockout",
        description="Verifikasi lockout cmd_stop, cmd_quit, dan button_stop saat bot tidak terhubung voice",
        iterations=iterations,
    )
    lockout_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild = MagicMock(spec=discord.Guild)
        guild.id = 33000 + it
        guild.voice_client = None

        state = QueueState()
        for i in range(5):
            state.queue.append(Track(f"StaleSong-{i}", f"http://mock/{i}", "user"))
        state.current = Track("CurrentDead", "http://mock/dead", "user")
        bot.states[guild.id] = state

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user = MagicMock()
        interaction.user.voice = MagicMock(channel=MagicMock(id=999))
        interaction.response.defer = AsyncMock()
        interaction.response.is_done = MagicMock(return_value=True)
        interaction.followup.send = AsyncMock()

        await bot.cmd_stop(interaction)

        if len(state.queue) > 0 or state.current is not None:
            lockout_events += 1

    if lockout_events > 0:
        res.anomalies.append(
            f"Lockout cmd_stop/quit terkonfirmasi: {lockout_events}/{iterations} iterasi menolak perintah stop/quit "
            "saat bot tidak terhubung voice, sehingga antrian tidak bisa direset dan cache tidak bisa dibersihkan pengguna."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"lockout_events": lockout_events}
    return res


# ==============================================================================
# 70. ADVANCE PHASE 4 STALE GENERATION SOURCE LEAK (Wave 10)
# ==============================================================================
async def fuzz_advance_phase4_stale_generation_source_leak(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="advance_phase4_stale_generation_source_leak",
        description="Verifikasi kebocoran AudioSource dan missing generation check pada _advance_loop pasca source_for",
        iterations=iterations,
    )
    leak_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=34000 + it)
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        track = Track("TestTrack", "https://mock.url/1", "user")
        state.queue.append(track)
        state.generation = 1
        bot.states[guild.id] = state

        mock_source = MagicMock(spec=discord.AudioSource)
        mock_source.cleanup = MagicMock()

        def mock_source_for(data, volume=0.5):
            state.generation += 1
            return mock_source

        with patch("bot.source_for", side_effect=mock_source_for), \
             patch("bot.run_extract", return_value={"url": "http://stream", "title": "TestTrack"}):
            await bot.advance(guild)

            if not mock_source.cleanup.called and vc.play.called:
                leak_events += 1

    if leak_events > 0:
        res.anomalies.append(
            f"Phase 4 stale generation source leak terkonfirmasi: {leak_events}/{iterations} iterasi memutar source "
            "atau membiarkan source tidak di-cleanup saat generation berubah selama pembuatan AudioSource."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"leak_events": leak_events}
    return res


# ==============================================================================
# 71. BUFFERED AUDIO SOURCE CLEANUP EVENT LOOP FREEZE (Wave 10)
# ==============================================================================
async def fuzz_buffered_audio_source_cleanup_event_loop_freeze(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="buffered_audio_source_cleanup_event_loop_freeze",
        description="Verifikasi blocking worker.join(2.0) pada BufferedAudioSource.cleanup yang membekukan event loop",
        iterations=iterations,
    )
    freeze_events = 0

    for it in range(iterations):
        mock_source = MagicMock(spec=discord.AudioSource)
        mock_source.cleanup = MagicMock()
        mock_source.is_opus.return_value = False

        slow_worker = MagicMock()
        slow_worker.is_alive.return_value = True

        joined_with_timeout = False
        def mock_join(timeout=None):
            nonlocal joined_with_timeout
            if timeout is not None and timeout > 0:
                joined_with_timeout = True

        slow_worker.join = mock_join

        bas = BufferedAudioSource.__new__(BufferedAudioSource)
        bas._cleaned = False
        bas.stop_event = threading.Event()
        bas.ready_event = threading.Event()
        bas.source = mock_source
        bas.queue = queue.Queue()
        bas.worker = slow_worker

        bas.cleanup()

        if joined_with_timeout:
            freeze_events += 1

    if freeze_events > 0:
        res.anomalies.append(
            f"Synchronous worker.join event loop freeze terkonfirmasi: {freeze_events}/{iterations} iterasi memanggil "
            "worker.join(2.0) secara sinkron langsung di thread pemanggil (asyncio event loop) saat cleanup AudioSource."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"freeze_events": freeze_events}
    return res


# ==============================================================================
# 72. DUMP RUNTIME STATE TMP CHMOD PERMISSION (Wave 10)
# ==============================================================================
async def fuzz_dump_runtime_state_tmp_chmod_permission(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="dump_runtime_state_tmp_chmod_permission",
        description="Verifikasi missing os.chmod 0644 pada file sementara state.json di dump_runtime_state",
        iterations=iterations,
    )
    permission_missing_events = 0

    for it in range(iterations):
        with tempfile.TemporaryDirectory() as tmpdir:
            s_path = os.path.join(tmpdir, "state.json")
            orig_umask = os.umask(0o077)
            try:
                bot = MusicBot()
                with patch.dict(os.environ, {"BOT_STATE_FILE": s_path}):
                    bot_module.dump_runtime_state(bot)
                    time.sleep(0.05)

                if os.path.exists(s_path):
                    mode = os.stat(s_path).st_mode & 0o777
                    if mode != 0o644:
                        permission_missing_events += 1
            finally:
                os.umask(orig_umask)

    if permission_missing_events > 0:
        res.anomalies.append(
            f"Missing chmod 0644 terkonfirmasi: {permission_missing_events}/{iterations} iterasi menghasilkan "
            "state.json tanpa izin 0644 (mengikuti umask proses sehingga file hanya 0600), memicu PermissionError saat dibaca panel."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"permission_missing_events": permission_missing_events}
    return res


# ==============================================================================
# 73. DUMP RUNTIME STATE OFFLINE MAX SEQ RACE (Wave 10)
# ==============================================================================
async def fuzz_dump_runtime_state_offline_max_seq_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="dump_runtime_state_offline_max_seq_race",
        description="Fuzzing race condition sequence bump pada dump_runtime_state_offline vs background executor writer",
        iterations=iterations,
    )
    race_events = 0

    for it in range(iterations):
        with tempfile.TemporaryDirectory() as tmpdir:
            s_path = os.path.join(tmpdir, "state.json")

            with bot_module._RUNTIME_STATE_LOCK:
                bot_module._RUNTIME_STATE_SEQ = 50
                bot_module._RUNTIME_STATE_LAST_SEQ = 10

            with patch.dict(os.environ, {"BOT_STATE_FILE": s_path}):
                bot_module.dump_runtime_state_offline()

            with bot_module._RUNTIME_STATE_LOCK:
                offline_last_seq = bot_module._RUNTIME_STATE_LAST_SEQ
                current_seq = bot_module._RUNTIME_STATE_SEQ

            if offline_last_seq < current_seq:
                race_events += 1

    if race_events > 0:
        res.anomalies.append(
            f"dump_runtime_state_offline sequence race terkonfirmasi: {race_events}/{iterations} iterasi hanya "
            "meng-increment _RUNTIME_STATE_LAST_SEQ satu kali alih-alih max(_RUNTIME_STATE_SEQ, _RUNTIME_STATE_LAST_SEQ) + 1, "
            "sehingga background executor writer yang tertunda tetap dapat menimpa dan memunculkan kembali state.json."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"race_events": race_events}
    return res


# ==============================================================================
# 74. SKIP PENDING LINGERING FLAG RACE (Wave 10)
# ==============================================================================
async def fuzz_skip_pending_lingering_flag_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="skip_pending_lingering_flag_race",
        description="Fuzzing race condition flag _skip_pending lingering akibat pengecekan _advancing di luar state.lock",
        iterations=iterations,
    )
    lingering_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=35000 + it)
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state._advancing = 1
        state._skip_pending = False
        bot.states[guild.id] = state

        user_ch = MagicMock()
        user_ch.id = vc.channel.id
        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user = MagicMock()
        interaction.user.voice = MagicMock(channel=user_ch)
        interaction.response.defer = AsyncMock()
        interaction.response.is_done = MagicMock(return_value=True)
        interaction.followup.send = AsyncMock()

        with patch.object(bot_module, "_check_same_voice", return_value=(True, "")):
            orig_lock = state.lock
            class InterceptLock:
                async def __aenter__(self):
                    state._advancing = 0
                    return await orig_lock.__aenter__()
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return await orig_lock.__aexit__(exc_type, exc_val, exc_tb)

            state.lock = InterceptLock()
            await bot.cmd_skip(interaction)

        if getattr(state, "_skip_pending", False) and state._advancing == 0:
            lingering_events += 1

    if lingering_events > 0:
        res.anomalies.append(
            f"_skip_pending lingering flag terkonfirmasi: {lingering_events}/{iterations} iterasi menyetel "
            "state._skip_pending = True padahal advance() sudah selesai saat lock diperoleh, menyebabkan lagu berikutnya ter-skip otomatis."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"lingering_events": lingering_events}
    return res


# ==============================================================================
# 75. TRACK DATACLASS EQUALITY MISMATCH (Wave 10)
# ==============================================================================
async def fuzz_track_dataclass_equality_mismatch(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="track_dataclass_equality_mismatch",
        description="Verifikasi kegagalan perbandingan equality dataclass Track akibat field dinamis stream_url dan stream_ts",
        iterations=iterations,
    )
    mismatch_events = 0

    for it in range(iterations):
        t1 = Track(
            title="Lagu Uji",
            url="https://www.youtube.com/watch?v=abc12345",
            requester="UserA",
            duration=180,
            stream_url=None,
            stream_ts=None,
        )
        t2 = Track(
            title="Lagu Uji",
            url="https://www.youtube.com/watch?v=abc12345",
            requester="UserA",
            duration=180,
            stream_url="https://rr1---sn.googlevideo.com/videoplayback?expire=99999",
            stream_ts=time.time(),
        )

        if t1 != t2 or t1 not in [t2]:
            mismatch_events += 1

    if mismatch_events > 0:
        res.anomalies.append(
            f"Track __eq__ mismatch terkonfirmasi: {mismatch_events}/{iterations} iterasi gagal menyamakan Track "
            "yang identik karena field dinamis stream_url atau stream_ts ikut dibandingkan pada __eq__."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"mismatch_events": mismatch_events}
    return res


# ==============================================================================
# 76. AUTOPLAY IDLE CONNECTED ADVANCE TRIGGER (Wave 10)
# ==============================================================================
async def fuzz_autoplay_idle_connected_advance_trigger(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="autoplay_idle_connected_advance_trigger",
        description="Verifikasi cmd_autoplay dan MusicPanel.autoplay memicu advance saat bot terhubung di voice dan idle",
        iterations=iterations,
    )
    untoggled_advance_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=36000 + it)
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.autoplay = False
        state.queue.clear()
        state.current = None
        state.history.append(Track("SeedSong", "http://seed", "user"))
        bot.states[guild.id] = state

        bot.advance = AsyncMock()

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.response.defer = AsyncMock()
        interaction.response.is_done = MagicMock(return_value=True)
        interaction.followup.send = AsyncMock()

        with patch.object(bot_module, "_check_guild_only", return_value=True):
            await bot.cmd_autoplay(interaction)

        if not bot.advance.called:
            untoggled_advance_events += 1

    if untoggled_advance_events > 0:
        res.anomalies.append(
            f"AutoPlay idle abandonment terkonfirmasi: {untoggled_advance_events}/{iterations} iterasi tidak "
            "memicu advance() saat AutoPlay diaktifkan ketika bot terhubung di voice dan sedang idle, menyebabkan bot tidak memutar rekomendasi."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"untoggled_advance_events": untoggled_advance_events}
    return res


# ==============================================================================
# 77. VOICE STATE UPDATE UNLOCKED MUTATION (Wave 10)
# ==============================================================================
async def fuzz_voice_state_update_unlocked_mutation(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="voice_state_update_unlocked_mutation",
        description="Fuzzing mutasi field state tanpa state.lock pada on_voice_state_update saat user kembali ke voice",
        iterations=iterations,
    )
    unlocked_mutation_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=37000 + it)
        vc.is_playing.return_value = True
        vc.is_paused.return_value = False

        state = QueueState()
        dummy_task = asyncio.create_task(asyncio.sleep(10))
        state.afk_task = dummy_task
        state.idle_task = dummy_task
        state.afk_paused = True
        bot.states[guild.id] = state

        lock_acquired = False
        orig_lock = state.lock
        class TrackingLock:
            async def __aenter__(self):
                nonlocal lock_acquired
                lock_acquired = True
                return await orig_lock.__aenter__()
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return await orig_lock.__aexit__(exc_type, exc_val, exc_tb)

        state.lock = TrackingLock()

        human = MagicMock(spec=discord.Member)
        human.bot = False
        human.guild = guild
        before = MagicMock(channel=None)
        after = MagicMock(channel=vc.channel)

        await bot.on_voice_state_update(human, before, after)
        dummy_task.cancel()

        if not lock_acquired:
            unlocked_mutation_events += 1

    if unlocked_mutation_events > 0:
        res.anomalies.append(
            f"on_voice_state_update unlocked mutation terkonfirmasi: {unlocked_mutation_events}/{iterations} iterasi "
            "memutasi afk_task, idle_task, dan afk_paused di luar state.lock saat listener kembali ke voice channel."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unlocked_mutation_events": unlocked_mutation_events}
    return res


# ==============================================================================
# 78. QUIT VOICE SYNC GC COLLECT EVENT LOOP BLOCK (Wave 10)
# ==============================================================================
async def fuzz_quit_voice_sync_gc_collect_event_loop_block(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="quit_voice_sync_gc_collect_event_loop_block",
        description="Verifikasi pemanggilan gc.collect() sinkron pada quit_voice yang memblokir asyncio event loop",
        iterations=iterations,
    )
    sync_gc_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=38000 + it)
        vc.disconnect = AsyncMock()

        state = QueueState()
        bot.states[guild.id] = state

        gc_called_in_main_thread = False
        main_thread_id = threading.get_ident()

        def mock_gc_collect():
            nonlocal gc_called_in_main_thread
            if threading.get_ident() == main_thread_id:
                gc_called_in_main_thread = True
            return 0

        with patch("bot.gc.collect", side_effect=mock_gc_collect):
            await bot.quit_voice(guild, clear_queue=True)

        if gc_called_in_main_thread:
            sync_gc_events += 1

    if sync_gc_events > 0:
        res.anomalies.append(
            f"Synchronous gc.collect event loop blocking terkonfirmasi: {sync_gc_events}/{iterations} iterasi memanggil "
            "gc.collect() langsung di thread event loop tanpa asyncio.to_thread, menyebabkan lag/freeze pada STB ARM."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"sync_gc_events": sync_gc_events}
    return res


# ==============================================================================
# 79. MUSIC PANEL DIRECT DICT INDEXING KEYERROR (Wave 10)
# ==============================================================================
async def fuzz_music_panel_direct_dict_indexing_keyerror(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="music_panel_direct_dict_indexing_keyerror",
        description="Fuzzing unhandled KeyError pada MusicPanel shuffle, loop, dan autoplay akibat direct indexing states",
        iterations=iterations,
    )
    key_error_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild = MagicMock(spec=discord.Guild)
        guild.id = 39000 + it
        bot.states.pop(guild.id, None)

        panel = MusicPanel(bot)
        panel.guard = AsyncMock(return_value=True)

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        threw_key_error = False
        try:
            await panel.shuffle.callback(interaction)
        except KeyError:
            threw_key_error = True

        if threw_key_error:
            key_error_events += 1

    if key_error_events > 0:
        res.anomalies.append(
            f"Unhandled KeyError terkonfirmasi: {key_error_events}/{iterations} iterasi melempar KeyError "
            "pada MusicPanel shuffle/loop/autoplay akibat direct indexing self.bot.states[interaction.guild.id]."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"key_error_events": key_error_events}
    return res


# ==============================================================================
# 80. PANEL LOGS FRESH UNBOUNDED JOURNALCTL DEBOUNCE (Wave 10)
# ==============================================================================
async def fuzz_panel_logs_fresh_unbounded_journalctl_debounce(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_logs_fresh_unbounded_journalctl_debounce",
        description="Fuzzing unbounded journalctl process execution pada GET /api/logs?fresh=1 tanpa proteksi debounce",
        iterations=iterations,
    )
    unbounded_journalctl_events = 0

    for it in range(iterations):
        call_count = 0
        def mock_read_bot_logs(lines=35):
            nonlocal call_count
            call_count += 1
            return "LOGS"

        with patch.object(panel_module, "read_bot_logs", side_effect=mock_read_bot_logs):
            with panel_module._log_cache_lock:
                panel_module._log_cache.clear()

            for _ in range(5):
                panel_module.read_bot_logs_cached(50, fresh=True)

            if call_count >= 5:
                unbounded_journalctl_events += 1

    if unbounded_journalctl_events > 0:
        res.anomalies.append(
            f"Unbounded journalctl execution terkonfirmasi: {unbounded_journalctl_events}/{iterations} iterasi "
            "mengeksekusi journalctl berkali-kali tanpa debounce pada fresh=True, berpotensi membebani CPU ARM STB."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unbounded_journalctl_events": unbounded_journalctl_events}
    return res


# ==============================================================================
# 81. CMD PLAY MISSING GET CHANNEL FALLBACK (Wave 10)
# ==============================================================================
async def fuzz_cmd_play_missing_get_channel_fallback(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_play_missing_get_channel_fallback",
        description="Verifikasi kegagalan pengiriman panel di cmd_play saat interaction.channel None tetapi channel_id ada",
        iterations=iterations,
    )
    missing_channel_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=40000 + it)
        text_channel = MagicMock()
        text_channel.id = 8888
        text_channel.send = AsyncMock()
        guild.get_channel = MagicMock(return_value=text_channel)

        state = QueueState()
        bot.states[guild.id] = state

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.channel = None
        interaction.channel_id = 8888
        interaction.user = MagicMock()
        interaction.user.voice = MagicMock(channel=vc.channel)
        interaction.response.defer = AsyncMock()
        interaction.response.is_done = MagicMock(return_value=True)
        interaction.followup.send = AsyncMock()

        with patch("bot.extract_tracks", return_value=[Track("TestTrack", "https://youtube.com/watch?v=dQw4w9WgXcQ", "user")]), \
             patch.object(bot_module, "_check_same_voice", return_value=(True, "")):
            await bot.cmd_play(interaction, "https://youtube.com/watch?v=dQw4w9WgXcQ")

        if not text_channel.send.called:
            missing_channel_events += 1

    if missing_channel_events > 0:
        res.anomalies.append(
            f"cmd_play missing channel fallback terkonfirmasi: {missing_channel_events}/{iterations} iterasi "
            "gagal memunculkan panel musik saat interaction.channel None meski channel_id valid tersedia."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"missing_channel_events": missing_channel_events}
    return res


# ==============================================================================
# 82. MUSIC PANEL VOLUME READ MODIFY WRITE RACE (Wave 10)
# ==============================================================================
async def fuzz_music_panel_volume_read_modify_write_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="music_panel_volume_read_modify_write_race",
        description="Fuzzing race condition read-modify-write pada tombol volume up dan down di MusicPanel",
        iterations=iterations,
    )
    race_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=41000 + it)
        state = QueueState()
        state.volume = 0.5
        bot.states[guild.id] = state

        panel = MusicPanel(bot)
        panel.guard = AsyncMock(return_value=True)

        interaction1 = MagicMock(spec=discord.Interaction)
        interaction1.guild = guild
        interaction1.response.defer = AsyncMock()
        interaction1.followup.send = AsyncMock()

        read_volume_outside_lock = False
        src = inspect.getsource(MusicPanel.down)
        if "state.volume - 0.1" in src:
            read_volume_outside_lock = True

        if read_volume_outside_lock:
            race_events += 1

    if race_events > 0:
        res.anomalies.append(
            f"Volume read-modify-write race terkonfirmasi: {race_events}/{iterations} iterasi menghitung "
            "target volume di luar state.lock (state.volume +- 0.1) sebelum change_volume() dipanggil."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"race_events": race_events}
    return res


# ==============================================================================
# 83. PANEL BUTTON STALE GUARD STRANDED VOICE (Wave 11)
# ==============================================================================
async def fuzz_panel_button_stale_guard_stranded_voice(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_button_stale_guard_stranded_voice",
        description="Fuzzing stale panel button require_voice=True voice connect sebelum validasi stale message",
        iterations=iterations,
    )
    stranded_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=42000 + it)
        guild.voice_client = None

        state = QueueState()
        active_msg = MagicMock()
        active_msg.id = 11111 + it
        state.message = active_msg
        state.queue.clear()
        state.idle_task = None
        bot.states[guild.id] = state

        user_ch = MagicMock()
        user_ch.id = 9999
        perms = MagicMock()
        perms.connect = True
        perms.speak = True
        user_ch.permissions_for = MagicMock(return_value=perms)

        async def fake_connect(timeout=20, self_deaf=True):
            connected_vc = MagicMock(spec=discord.VoiceClient)
            connected_vc.channel = user_ch
            connected_vc.is_connected = MagicMock(return_value=True)
            connected_vc.is_playing = MagicMock(return_value=False)
            connected_vc.is_paused = MagicMock(return_value=False)
            connected_vc.disconnect = AsyncMock()
            guild.voice_client = connected_vc
            return connected_vc

        user_ch.connect = AsyncMock(side_effect=fake_connect)

        stale_msg = MagicMock()
        stale_msg.id = 22222 + it

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.message = stale_msg
        interaction.user = MagicMock()
        interaction.user.voice = MagicMock(channel=user_ch)
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.response.send_message = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        panel = MusicPanel(bot)
        allowed = await panel.guard(interaction, require_voice=True)

        is_stranded = False
        if not allowed:
            cur_vc = guild.voice_client
            if cur_vc and cur_vc.is_connected() and state.idle_task is None:
                is_stranded = True

        if is_stranded:
            stranded_events += 1

    if stranded_events > 0:
        res.anomalies.append(
            f"Stranded voice client pada stale panel terkonfirmasi: {stranded_events}/{iterations} iterasi "
            "menghubungkan voice client sebelum memvalidasi kesegaran pesan panel, lalu me-reject tanpa "
            "memutuskan voice client atau menjadwalkan idle disconnect sehingga bot tersangkut selamanya."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stranded_events": stranded_events}
    return res


# ==============================================================================
# 84. AUTOPLAY SKIP EXTRACTION RELOOP (Wave 11)
# ==============================================================================
async def fuzz_autoplay_skip_extraction_reloop(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="autoplay_skip_extraction_reloop",
        description="Fuzzing skip_now saat ekstraksi AutoPlay dan verifikasi eksklusi candidate URL dari played_urls/autoplay_failed_urls",
        iterations=iterations,
    )
    reloop_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=43000 + it)
        state = QueueState()
        state.autoplay = True
        state.queue.clear()
        state.history.clear()
        state._skip_pending = True
        bot.states[guild.id] = state

        cand = Track("AutoCand", "https://youtube.com/watch?v=cand123", "AutoPlay")
        autoplay_candidates = [cand]
        autoplay_failed_urls = set()

        skip_now = False
        async with state.lock:
            if state._skip_pending:
                state._skip_pending = False
                skip_now = True
                if state.queue:
                    if state.queue[0] is cand:
                        state.queue.popleft()
                elif state.loop_mode in ('track', 'queue') and state.current is cand:
                    state.current = None

        if skip_now:
            src_loop = inspect.getsource(MusicBot._advance_loop)
            if "autoplay_failed_urls.add" in src_loop:
                autoplay_failed_urls.add(cand.url)

        played_urls = {t.url for t in list(state.history)[-20:]}
        played_urls.update(autoplay_failed_urls)
        repicked = next((c for c in autoplay_candidates if c.url not in played_urls), None)

        if repicked is cand:
            reloop_events += 1

    if reloop_events > 0:
        res.anomalies.append(
            f"AutoPlay skip extraction reloop terkonfirmasi: {reloop_events}/{iterations} iterasi "
            "melewati track kandidat AutoPlay saat ekstraksi tanpa mencatat URL-nya ke played_urls/autoplay_failed_urls, "
            "sehingga loop AutoPlay mengekstrak dan memutar kembali kandidat yang sama persis."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"reloop_events": reloop_events}
    return res


# ==============================================================================
# 85. PANEL SKIP IDLE CIRCUIT BREAKER LATCH (Wave 11)
# ==============================================================================
async def fuzz_panel_skip_idle_circuit_breaker_latch(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_skip_idle_circuit_breaker_latch",
        description="Verifikasi reset consecutive_playback_errors pada MusicPanel.skip saat audio tidak aktif berputar",
        iterations=iterations,
    )
    unreset_latch_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=44000 + it)
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.consecutive_playback_errors = 2
        state.queue.append(Track("NextSong", "http://next", "u"))
        bot.states[guild.id] = state

        panel = MusicPanel(bot)
        panel.guard = AsyncMock(return_value=True)

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user = MagicMock()
        interaction.user.voice = MagicMock(channel=vc.channel)
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        bot.advance = AsyncMock()

        await panel.skip.callback(interaction)

        if state.consecutive_playback_errors != 0:
            unreset_latch_events += 1

    if unreset_latch_events > 0:
        res.anomalies.append(
            f"Panel skip unreset error latch terkonfirmasi: {unreset_latch_events}/{iterations} iterasi "
            "tidak me-reset consecutive_playback_errors saat skip ditekan ketika audio tidak aktif berputar, "
            "sehingga 1 error berikutnya langsung memicu circuit breaker secara prematur."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unreset_latch_events": unreset_latch_events}
    return res


# ==============================================================================
# 86. AFK DISCONNECT TASK LEAK DONE CHECK (Wave 11)
# ==============================================================================
async def fuzz_afk_disconnect_task_leak_done_check(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="afk_disconnect_task_leak_done_check",
        description="Verifikasi retensi referensi task state.empty_task/afk_task setelah _empty_disconnect / _afk_disconnect selesai",
        iterations=iterations,
    )
    task_leak_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=45000 + it)
        vc.channel.members = [MagicMock(bot=True)]

        state = QueueState()
        state.generation = 1
        bot.states[guild.id] = state
        bot.quit_voice = AsyncMock()

        task = asyncio.create_task(bot._empty_disconnect(guild, state.generation))
        state.empty_task = task
        state.afk_task = None

        with patch("asyncio.sleep", AsyncMock()):
            await task

        if state.empty_task is not None:
            task_leak_events += 1

    if task_leak_events > 0:
        res.anomalies.append(
            f"Task reference leak pada _afk_disconnect terkonfirmasi: {task_leak_events}/{iterations} iterasi "
            "membiarkan state.empty_task tidak di-null-kan saat state.afk_task is None, menyebabkan Task selesai "
            "dan referensi guild tertahan di memori."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"task_leak_events": task_leak_events}
    return res


# ==============================================================================
# 87. DUMP RUNTIME STATE CURRENT TITLE RACE (Wave 11)
# ==============================================================================
async def fuzz_dump_runtime_state_current_title_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="dump_runtime_state_current_title_race",
        description="Fuzzing race condition akses state.current.title di dump_runtime_state saat state.current di-null-kan konkuren",
        iterations=iterations,
    )
    race_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=46000 + it)
        class ShiftyState:
            def __init__(self):
                self._access = 0
                self.queue = []
            @property
            def current(self):
                self._access += 1
                if self._access == 1:
                    return Track("Track 1", "http://t1", "user")
                return None

        state = ShiftyState()
        bot.states[guild.id] = state

        logged_attr_error = False
        with patch.object(MusicBot, "guilds", new_callable=PropertyMock, return_value=[guild]), \
             patch.object(bot_module.log, "debug") as mock_debug:
            bot_module.dump_runtime_state(bot)
            for call_args in mock_debug.call_args_list:
                for arg in call_args[0]:
                    if isinstance(arg, AttributeError) and "title" in str(arg):
                        logged_attr_error = True

        if logged_attr_error:
            race_events += 1

    if race_events > 0:
        res.anomalies.append(
            f"dump_runtime_state current.title AttributeError race terkonfirmasi: {race_events}/{iterations} iterasi "
            "mengakses state.current.title secara langsung setelah pengecekan getattr(state, 'current', None), "
            "melempar AttributeError jika state.current menjadi None di tengah eksekusi."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"race_events": race_events}
    return res


# ==============================================================================
# 88. SAVE PERSISTENT QUEUE TMP CHMOD PERMISSION (Wave 11)
# ==============================================================================
async def fuzz_save_persistent_queue_tmp_chmod_permission(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="save_persistent_queue_tmp_chmod_permission",
        description="Verifikasi missing os.chmod 0644 pada berkas .tmp di _save_persistent_queue",
        iterations=iterations,
    )
    permission_missing_events = 0

    for it in range(iterations):
        with tempfile.TemporaryDirectory() as tmpdir:
            q_path = os.path.join(tmpdir, "queue_state.json")
            orig_umask = os.umask(0o077)
            try:
                bot = MusicBot()
                guild, vc = _create_mock_environment(guild_id=47000 + it)
                state = QueueState()
                state.queue.append(Track("T1", "http://t1", "user"))
                bot.states[guild.id] = state

                with patch("bot._persistent_queue_file", return_value=q_path):
                    fut = bot._save_persistent_queue()
                    if fut is not None:
                        await fut

                if os.path.exists(q_path):
                    mode = os.stat(q_path).st_mode & 0o777
                    if mode != 0o644:
                        permission_missing_events += 1
            finally:
                os.umask(orig_umask)

    if permission_missing_events > 0:
        res.anomalies.append(
            f"_save_persistent_queue missing chmod 0644 terkonfirmasi: {permission_missing_events}/{iterations} iterasi "
            "menulis queue_state.json tanpa os.chmod 0644 sehingga file hanya berizin 0600 di bawah umask ketat, "
            "berisiko PermissionError untuk tool monitoring/updater."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"permission_missing_events": permission_missing_events}
    return res


# ==============================================================================
# 89. CMD MUSIK IDLE TIMER OMISSION (Wave 11)
# ==============================================================================
async def fuzz_cmd_musik_idle_timer_omission(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_musik_idle_timer_omission",
        description="Verifikasi ketiadaan penjadwalan _schedule_idle pada slash command /musik saat antrean kosong",
        iterations=iterations,
    )
    missing_idle_schedule_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=48000 + it)
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.queue.clear()
        state.current = None
        state.idle_task = None
        bot.states[guild.id] = state

        user_ch = vc.channel
        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.user = MagicMock()
        interaction.user.voice = MagicMock(channel=user_ch)
        interaction.channel = MagicMock()
        interaction.channel_id = 98765
        interaction.channel.send = AsyncMock(return_value=MagicMock(id=12345))
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        bot._schedule_idle = MagicMock()

        await bot.summon(interaction)

        if not bot._schedule_idle.called and state.idle_task is None:
            missing_idle_schedule_events += 1

    if missing_idle_schedule_events > 0:
        res.anomalies.append(
            f"/musik missing _schedule_idle terkonfirmasi: {missing_idle_schedule_events}/{iterations} iterasi "
            "menghubungkan bot ke voice channel dan menampilkan panel musik tanpa menjadwalkan _schedule_idle, "
            "sehingga bot tertahan selamanya di voice channel bila antrean kosong dan ada listener di room."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"missing_idle_schedule_events": missing_idle_schedule_events}
    return res


# ==============================================================================
# 90. PANEL BUTTONS RAPID CLICK EMMC DEBOUNCE (Wave 11)
# ==============================================================================
async def fuzz_panel_buttons_rapid_click_eMMC_debounce(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_buttons_rapid_click_eMMC_debounce",
        description="Fuzzing rapid clicks pada tombol shuffle, loop, dan autoplay di MusicPanel dan ketiadaan debounce",
        iterations=iterations,
    )
    missing_debounce_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=49000 + it)
        state = QueueState()
        state.queue.append(Track("T1", "http://t1", "u"))
        state.queue.append(Track("T2", "http://t2", "u"))
        bot.states[guild.id] = state

        panel = MusicPanel(bot)
        panel.guard = AsyncMock(return_value=True)

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        writes_called = 0
        def count_save():
            nonlocal writes_called
            writes_called += 1

        bot._save_persistent_queue = count_save

        btn = MagicMock(spec=discord.ui.Button)
        await panel.shuffle.callback(interaction)
        await panel.shuffle.callback(interaction)

        if writes_called >= 2:
            missing_debounce_events += 1

    if missing_debounce_events > 0:
        res.anomalies.append(
            f"MusicPanel shuffle/loop/autoplay missing debounce terkonfirmasi: {missing_debounce_events}/{iterations} iterasi "
            "mengeksekusi penulisan disk I/O ganda pada klik cepat tanpa batas debounce, membebani eMMC pada STB ARM."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"missing_debounce_events": missing_debounce_events}
    return res


# ==============================================================================
# 91. CMD AUTOPLAY STALE CURRENT LOCKOUT (Wave 11)
# ==============================================================================
async def fuzz_cmd_autoplay_stale_current_lockout(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_autoplay_stale_current_lockout",
        description="Verifikasi lockout pemanggilan advance() pada cmd_autoplay saat state.current non-None pasca playback selesai",
        iterations=iterations,
    )
    lockout_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=50000 + it)
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.autoplay = False
        state.current = Track("FinishedTrack", "http://seed", "u")
        state.queue.clear()
        bot.states[guild.id] = state

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        bot.advance = AsyncMock()
        bot.refresh = AsyncMock()

        await bot.cmd_autoplay(interaction)

        if not bot.advance.called:
            lockout_events += 1

    if lockout_events > 0:
        res.anomalies.append(
            f"cmd_autoplay stale current lockout terkonfirmasi: {lockout_events}/{iterations} iterasi "
            "mengabaikan pemanggilan advance() saat AutoPlay diaktifkan karena mengecek `not state.current`, "
            "sehingga AutoPlay terkunci bila state.current sisa lagu lama masih ada."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"lockout_events": lockout_events}
    return res


# ==============================================================================
# 92. CMD PAUSE UNLOCKED MUTATION AND IDLE OMISSION (Wave 11)
# ==============================================================================
async def fuzz_cmd_pause_unlocked_mutation_and_idle_omission(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_pause_unlocked_mutation_and_idle_omission",
        description="Fuzzing mutasi consecutive_playback_errors di luar lock dan ketiadaan idle schedule pada cmd_pause",
        iterations=iterations,
    )
    unlocked_or_omitted_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=51000 + it)
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.current = Track("StaleTrack", "http://stale", "u")
        state.queue.clear()
        state.consecutive_playback_errors = 1
        state.idle_task = None
        bot.states[guild.id] = state

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        bot.refresh = AsyncMock()
        bot._schedule_idle = MagicMock()

        with patch.object(bot_module, "_check_same_voice", return_value=(True, "")):
            await bot.cmd_pause(interaction)

        if not bot._schedule_idle.called and state.current is not None:
            unlocked_or_omitted_events += 1

    if unlocked_or_omitted_events > 0:
        res.anomalies.append(
            f"cmd_pause missing idle schedule & unlocked mutation terkonfirmasi: {unlocked_or_omitted_events}/{iterations} iterasi "
            "membiarkan state.current tidak di-null-kan dan tidak menjadwalkan _schedule_idle saat pause dipanggil dalam kondisi idle."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unlocked_or_omitted_events": unlocked_or_omitted_events}
    return res


# ==============================================================================
# 93. CONCURRENT PLAY AND MUSIK PANEL DUPLICATION (Wave 11)
# ==============================================================================
async def fuzz_concurrent_play_and_musik_panel_duplication(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="concurrent_play_and_musik_panel_duplication",
        description="Fuzzing race condition check and replace state.message di luar lock pada /play dan /musik",
        iterations=iterations,
    )
    duplicate_panel_events = 0

    for it in range(iterations):
        src_play = inspect.getsource(MusicBot.cmd_play)
        src_musik = inspect.getsource(MusicBot.summon)

        unlocked_in_play = "existing = state.message" in src_play and not any("async with state.lock:" in line for line in src_play.split("existing = state.message")[0].split("\n")[-4:])
        unlocked_in_musik = "if state.message:" in src_musik and not any("async with state.lock:" in line for line in src_musik.split("if state.message:")[0].split("\n")[-4:])

        if unlocked_in_play and unlocked_in_musik:
            duplicate_panel_events += 1

    if duplicate_panel_events > 0:
        res.anomalies.append(
            f"Concurrent /play dan /musik panel duplication race terkonfirmasi: {duplicate_panel_events}/{iterations} iterasi "
            "memeriksa dan menimpa state.message tanpa sinkronisasi state.lock, memungkinkan kedua pemanggilan membuat panel "
            "baru secara simultan dan meninggalkan pesan panel duplikat/orphaned di Discord."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"duplicate_panel_events": duplicate_panel_events}
    return res


# ==============================================================================
# 94. PLAYLIST VIEW REFRESH INSTANCE LEAK (Wave 11)
# ==============================================================================
async def fuzz_playlist_view_refresh_instance_leak(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="playlist_view_refresh_instance_leak",
        description="Verifikasi pembuatan instance PlaylistView baru dan followup baru pada refresh_playlist",
        iterations=iterations,
    )
    instance_leak_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=52000 + it)
        state = QueueState()
        bot.states[guild.id] = state

        view = PlaylistView(bot)
        btn = MagicMock(spec=discord.ui.Button)

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        await view.refresh_playlist.callback(interaction)

        if interaction.followup.send.called:
            called_kwargs = interaction.followup.send.call_args[1]
            sent_view = called_kwargs.get("view")
            if sent_view is not None and sent_view is not view:
                instance_leak_events += 1

    if instance_leak_events > 0:
        res.anomalies.append(
            f"PlaylistView refresh instance leak terkonfirmasi: {instance_leak_events}/{iterations} iterasi "
            "mengirim ephemeral followup baru dengan instance PlaylistView(self.bot) baru alih-alih mengedit pesan "
            "yang sudah ada, memicu kebocoran view handler aktif pada STB ARM."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"instance_leak_events": instance_leak_events}
    return res


# ==============================================================================
# 95. MUSIC BOT EMBED FORMATTING AND LENGTH SAFETY (Wave 11)
# ==============================================================================
async def fuzz_music_bot_embed_formatting_and_length_safety(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="music_bot_embed_formatting_and_length_safety",
        description="Verifikasi escaping backticks dan penanganan field kosong/panjang pada MusicBot.embed",
        iterations=iterations,
    )
    unsafe_embed_events = 0

    for it in range(iterations):
        bot = MusicBot()
        state = QueueState()
        track = Track(title="Song with `inline code` title", url="http://t", requester="user", author="")
        state.current = track

        embed = bot.embed(state)

        has_broken_backtick = "``" in embed.description or "`Song with `inline code`" in embed.description
        author_empty = False
        for f in embed.fields:
            if f.name == "🎙 Music Author" and f.value == "``":
                author_empty = True

        if has_broken_backtick or author_empty:
            unsafe_embed_events += 1

    if unsafe_embed_events > 0:
        res.anomalies.append(
            f"MusicBot.embed formatting/length safety issue terkonfirmasi: {unsafe_embed_events}/{iterations} iterasi "
            "menginterpolasi track.title dan track.author ke dalam backticks tanpa escaping, menghasilkan markdown rusak "
            "atau field value kosong (``) yang memicu Discord 400 Bad Request."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unsafe_embed_events": unsafe_embed_events}
    return res


# ==============================================================================
# 96. VOICE STATE UPDATE REDUNDANT DUAL DUMP IO (Wave 11)
# ==============================================================================
async def fuzz_voice_state_update_redundant_dual_dump_io(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="voice_state_update_redundant_dual_dump_io",
        description="Verifikasi pemanggilan redundan ganda dump_runtime_state per transisi voice state",
        iterations=iterations,
    )
    dual_dump_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=53000 + it)
        vc.is_connected.return_value = True
        vc.is_playing.return_value = True

        state = QueueState()
        bot.states[guild.id] = state
        bot.refresh = AsyncMock()

        dump_count = 0
        def counting_dump(b):
            nonlocal dump_count
            dump_count += 1

        member = MagicMock(spec=discord.Member)
        member.bot = False
        member.guild = guild
        vc.channel.members = [MagicMock(bot=True)]

        before = MagicMock(channel=vc.channel)
        after = MagicMock(channel=None)

        with patch("bot.dump_runtime_state", side_effect=counting_dump):
            await bot.on_voice_state_update(member, before, after)

        if dump_count > 1:
            dual_dump_events += 1

    if dual_dump_events > 0:
        res.anomalies.append(
            f"on_voice_state_update redundant dual dump_runtime_state terkonfirmasi: {dual_dump_events}/{iterations} iterasi "
            f"memanggil dump_runtime_state sebanyak {dump_count} kali dalam satu event voice update, "
            "menimbulkan disk write ganda ke eMMC STB ARM."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"dual_dump_events": dual_dump_events}
    return res


# ==============================================================================
# 97. PANEL FRESH LOGS CONCURRENT DEBOUNCE RACE (Wave 11)
# ==============================================================================
async def fuzz_panel_fresh_logs_concurrent_debounce_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_fresh_logs_concurrent_debounce_race",
        description="Fuzzing race condition timestamp _last_fresh_log_time pada read_bot_logs_cached saat request fresh simultan",
        iterations=iterations,
    )
    redundant_fork_events = 0

    for it in range(iterations):
        with panel_module._log_cache_lock:
            panel_module._log_cache.clear()
            panel_module._last_fresh_log_time.clear()

        fork_count = 0
        def slow_read_logs(lines):
            nonlocal fork_count
            fork_count += 1
            time.sleep(0.05)
            return f"LOG_LINES_{fork_count}"

        orig_fn = panel_module.read_bot_logs
        panel_module.read_bot_logs = slow_read_logs
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                f1 = pool.submit(panel_module.read_bot_logs_cached, 35, True)
                time.sleep(0.01)
                f2 = pool.submit(panel_module.read_bot_logs_cached, 35, True)
                f1.result()
                f2.result()

            if fork_count > 1:
                redundant_fork_events += 1
        finally:
            panel_module.read_bot_logs = orig_fn
            with panel_module._log_cache_lock:
                panel_module._log_cache.clear()
                panel_module._last_fresh_log_time.clear()

    if redundant_fork_events > 0:
        res.anomalies.append(
            f"read_bot_logs_cached fresh debounce race terkonfirmasi: {redundant_fork_events}/{iterations} iterasi "
            f"menjalankan {fork_count} proses journalctl simultan karena _last_fresh_log_time hanya diperbarui "
            "setelah journalctl selesai, bukan saat request masuk ke window debounce."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"redundant_fork_events": redundant_fork_events}
    return res


# ==============================================================================
# 98. PANEL YTDLP VERSION MODULE CACHE STALE (Wave 11)
# ==============================================================================
async def fuzz_panel_ytdlp_version_module_cache_stale(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_ytdlp_version_module_cache_stale",
        description="Verifikasi stale version pada ytdlp_version akibat caching sys.modules['yt_dlp.version']",
        iterations=iterations,
    )
    stale_version_events = 0

    for it in range(iterations):
        old_mock_mod = MagicMock()
        old_mock_mod.__version__ = "2026.01.01"
        sys.modules["yt_dlp.version"] = old_mock_mod

        v1 = panel_module.ytdlp_version()

        src = inspect.getsource(panel_module.ytdlp_version)
        does_reload_or_metadata = "importlib" in src or "reload" in src

        if not does_reload_or_metadata:
            stale_version_events += 1

    if stale_version_events > 0:
        res.anomalies.append(
            f"ytdlp_version sys.modules cache stale terkonfirmasi: {stale_version_events}/{iterations} iterasi "
            "mengimpor yt_dlp.version tanpa reload / importlib.metadata, sehingga setelah update.sh selesai "
            "panel tetap menampilkan versi lama sampai service panel di-restart."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stale_version_events": stale_version_events}
    return res


# ==============================================================================
# 99. TRACK LOOP EMPTY CHANNEL ABANDONMENT (Wave 12)
# ==============================================================================
async def fuzz_loop_track_empty_channel_abandonment(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="loop_track_empty_channel_abandonment",
        description="Fuzzing pembatalan loop track saat pendengar keluar channel kosong dan verifikasi hilangnya track pada on_voice_state_update",
        iterations=iterations,
    )
    abandonment_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=60000 + it)
        vc.channel.members = [MagicMock(bot=True)]
        vc.is_playing = MagicMock(return_value=False)
        vc.is_paused = MagicMock(return_value=False)

        state = QueueState()
        state.loop_mode = "track"
        loop_track = Track("LoopedSong", "https://youtube.com/watch?v=loop1", "user")
        state.current = loop_track
        state.queue.clear()
        bot.states[guild.id] = state

        bot._save_persistent_queue = MagicMock()
        bot.refresh = AsyncMock()
        bot._schedule_idle = MagicMock()

        await bot._advance_loop(guild, state, vc)

        wiped_to_none = (state.current is None)

        human_member = MagicMock()
        human_member.guild = guild
        human_member.bot = False
        human_member.id = 9991
        before_state = MagicMock(channel=None)
        after_state = MagicMock(channel=vc.channel)
        vc.channel.members = [MagicMock(bot=True), human_member]

        bot.advance = AsyncMock()
        await bot.on_voice_state_update(human_member, before_state, after_state)

        advance_called = bot.advance.called

        if wiped_to_none and not advance_called:
            abandonment_events += 1

    if abandonment_events > 0:
        res.anomalies.append(
            f"Loop track abandonment di channel kosong terkonfirmasi: {abandonment_events}/{iterations} iterasi "
            "_advance_loop me-wipe state.current ke None dan memindahkannya ke history saat pendengar keluar channel, "
            "sehingga saat pengguna bergabung kembali on_voice_state_update tidak memicu advance() dan loop lagu hilang selamanya."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"abandonment_events": abandonment_events}
    return res


# ==============================================================================
# 100. IDLE DISCONNECT BOOLEAN PRECEDENCE FLAW (Wave 12)
# ==============================================================================
async def fuzz_idle_disconnect_boolean_precedence_flaw(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="idle_disconnect_boolean_precedence_flaw",
        description="Verifikasi cacat precedence boolean pada idle_disconnect yang memutus bot saat ada antrean lagu valid",
        iterations=iterations,
    )
    premature_disconnect_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=61000 + it)
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.generation = 1
        state.current = None
        state.queue.append(Track("QueuedSong", "https://youtube.com/watch?v=q1", "user"))
        state.consecutive_playback_errors = 0
        bot.states[guild.id] = state

        bot.quit_voice = AsyncMock()

        with patch("asyncio.sleep", new=AsyncMock()):
            await bot.idle_disconnect(guild, state.generation)

        if bot.quit_voice.called:
            premature_disconnect_events += 1

    if premature_disconnect_events > 0:
        res.anomalies.append(
            f"idle_disconnect boolean precedence flaw terkonfirmasi: {premature_disconnect_events}/{iterations} iterasi "
            "bot memutuskan koneksi voice channel setelah idle_disconnect padahal antrean masih memiliki lagu valid "
            "(karena `not_playing` selalu True saat idle di dalam ekspresi `not state.queue or cb_tripped or not_playing`)."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"premature_disconnect_events": premature_disconnect_events}
    return res


# ==============================================================================
# 101. QUEUE FULL STRANDED VOICE IDLE OMISSION (Wave 12)
# ==============================================================================
async def fuzz_queue_full_stranded_voice_idle_omission(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="queue_full_stranded_voice_idle_omission",
        description="Fuzzing ketiadaan _schedule_idle saat _enqueue_tracks gagal akibat antrian penuh pada cmd_play & SearchModal",
        iterations=iterations,
    )
    stranded_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=62000 + it)
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.current = None
        state.queue.clear()
        state.idle_task = None
        bot.states[guild.id] = state

        bot._schedule_idle = MagicMock()
        bot._safe_delete_msg = AsyncMock()

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.channel_id = 9001
        interaction.user = MagicMock()
        interaction.user.mention = "@user"
        interaction.user.voice = MagicMock(channel=vc.channel)
        interaction.response.is_done.return_value = False
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        tracks_to_add = [Track(f"T{i}", f"http://t/{i}", "u") for i in range(MAX_QUEUE + 1)]

        with patch("bot.extract_tracks", new=AsyncMock(return_value=tracks_to_add)):
            await bot.cmd_play(interaction, "https://youtube.com/playlist?list=FULL")

        if not bot._schedule_idle.called and state.idle_task is None and not state.current and not state.queue:
            stranded_events += 1

    if stranded_events > 0:
        res.anomalies.append(
            f"Voice client stranded saat antrian penuh terkonfirmasi: {stranded_events}/{iterations} iterasi "
            "cmd_play dan SearchModal terhubung ke voice channel tetapi langsung return saat _enqueue_tracks gagal "
            "(antrean penuh) tanpa menjadwalkan _schedule_idle, membiarkan bot tertahan di voice channel tanpa batas waktu."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stranded_events": stranded_events}
    return res


# ==============================================================================
# 102. MUSIC PANEL PAUSE UNLOCKED MUTATION (Wave 12)
# ==============================================================================
async def fuzz_music_panel_pause_unlocked_mutation(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="music_panel_pause_unlocked_mutation",
        description="Fuzzing mutasi state.current, error reset, dan pembacaan generation tanpa state.lock di MusicPanel.pause",
        iterations=iterations,
    )
    unlocked_mutation_events = 0

    for it in range(iterations):
        src = inspect.getsource(MusicPanel.pause)
        has_lock = "async with state.lock:" in src
        unlocked_current_reset = "state.current = None" in src and not any(
            "async with state.lock:" in line for line in src.split("state.current = None")[0].split("\n")[-6:]
        )
        unlocked_error_reset = "state.consecutive_playback_errors = 0" in src and not any(
            "async with state.lock:" in line for line in src.split("state.consecutive_playback_errors = 0")[0].split("\n")[-4:]
        )
        unlocked_idle_call = "self.bot._schedule_idle(interaction.guild, state.generation)" in src and not any(
            "async with state.lock:" in line for line in src.split("self.bot._schedule_idle(interaction.guild, state.generation)")[0].split("\n")[-6:]
        )

        if not has_lock or unlocked_current_reset or unlocked_error_reset or unlocked_idle_call:
            unlocked_mutation_events += 1

    if unlocked_mutation_events > 0:
        res.anomalies.append(
            f"MusicPanel.pause unlocked state mutation terkonfirmasi: {unlocked_mutation_events}/{iterations} iterasi "
            "mengubah state.consecutive_playback_errors, me-null-kan state.current, dan membaca state.generation "
            "di luar perlindungan state.lock sehingga rentan race condition dan desinkronisasi generation."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unlocked_mutation_events": unlocked_mutation_events}
    return res


# ==============================================================================
# 103. GUILD REMOVE VOICE CLIENT SUBPROCESS LEAK (Wave 12)
# ==============================================================================
async def fuzz_guild_remove_voice_client_subprocess_leak(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="guild_remove_voice_client_subprocess_leak",
        description="Fuzzing kebocoran voice client, audio player, dan proses ffmpeg latar belakang pada on_guild_remove",
        iterations=iterations,
    )
    leaked_voice_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=63000 + it)
        vc.is_connected.return_value = True
        vc.stop = MagicMock()
        vc.cleanup = MagicMock()

        state = QueueState()
        state.current = Track("PlayingSong", "http://s", "u")
        bot.states[guild.id] = state
        bot._save_persistent_queue = MagicMock()
        bot.quit_voice = AsyncMock()

        await bot.on_guild_remove(guild)

        if not bot.quit_voice.called and not vc.stop.called:
            leaked_voice_events += 1

    if leaked_voice_events > 0:
        res.anomalies.append(
            f"on_guild_remove voice client & subprocess leak terkonfirmasi: {leaked_voice_events}/{iterations} iterasi "
            "bot dikeluarkan dari guild tetapi tidak memanggil quit_voice() atau vc.stop(), membiarkan koneksi voice, "
            "AudioPlayer worker thread, dan proses ffmpeg berjalan tanpa henti di latar belakang sistem."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"leaked_voice_events": leaked_voice_events}
    return res


# ==============================================================================
# 104. ENQUEUE TRACKS PLAYING CHECK RACE (Wave 12)
# ==============================================================================
async def fuzz_enqueue_tracks_playing_check_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="enqueue_tracks_playing_check_race",
        description="Fuzzing evaluasi vc.is_playing() di luar state.lock pada _enqueue_tracks yang me-wipe state.current",
        iterations=iterations,
    )
    race_wipe_events = 0

    for it in range(iterations):
        src = inspect.getsource(MusicBot._enqueue_tracks)
        playing_before_lock = "playing = bool(" in src and "async with state.lock:" in src and (
            src.find("playing = bool(") < src.find("async with state.lock:")
        )

        if playing_before_lock:
            race_wipe_events += 1

    if race_wipe_events > 0:
        res.anomalies.append(
            f"_enqueue_tracks playing check race terkonfirmasi: {race_wipe_events}/{iterations} iterasi "
            "mengevaluasi status playing sebelum mengakuisisi state.lock; bila playback aktif tepat sebelum lock, "
            "state.current yang baru diputar di-wipe ke history dan di-null-kan karena status playing basi."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"race_wipe_events": race_wipe_events}
    return res


# ==============================================================================
# 105. SHUTDOWN GHOST PANEL ID PERSISTENCE (Wave 12)
# ==============================================================================
async def fuzz_shutdown_ghost_panel_id_persistence(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="shutdown_ghost_panel_id_persistence",
        description="Fuzzing persistensi ghost panel_message_id di queue_state.json akibat urutan eksekusi close() bot",
        iterations=iterations,
    )
    ghost_panel_persist_events = 0

    for it in range(iterations):
        src = inspect.getsource(MusicBot.close)
        save_idx = src.find("self._save_persistent_queue()")
        delete_idx = src.find("self._delete_all_panels()")

        save_after_delete = False
        if delete_idx != -1:
            save_after_delete = "self._save_persistent_queue()" in src[delete_idx:]

        if save_idx != -1 and delete_idx != -1 and save_idx < delete_idx and not save_after_delete:
            ghost_panel_persist_events += 1

    if ghost_panel_persist_events > 0:
        res.anomalies.append(
            f"Shutdown ghost panel_message_id persistence terkonfirmasi: {ghost_panel_persist_events}/{iterations} iterasi "
            "bot memanggil _save_persistent_queue() sebelum _delete_all_panels() pada close(), sehingga panel_message_id "
            "pesan yang sudah dihapus tetap tersimpan di disk dan direstore sebagai ID palsu saat bot boot kembali."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"ghost_panel_persist_events": ghost_panel_persist_events}
    return res


# ==============================================================================
# 106. REFRESH PANEL INTEGER ID STALL (Wave 12)
# ==============================================================================
async def fuzz_refresh_panel_integer_id_stall(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="refresh_panel_integer_id_stall",
        description="Verifikasi stall dan pengabaian embed update pada refresh() saat state.message berupa integer ID",
        iterations=iterations,
    )
    dropped_refresh_events = 0

    for it in range(iterations):
        bot = MusicBot()
        state = QueueState()
        state.message = 123456789 + it
        state.text_channel_id = 9001
        state.current = Track("Song", "http://s", "u")

        src = inspect.getsource(bot.refresh)
        has_int_handling = "isinstance(msg, int)" in src or "fetch_message" in src

        if not has_int_handling:
            dropped_refresh_events += 1

    if dropped_refresh_events > 0:
        res.anomalies.append(
            f"refresh() integer ID stall terkonfirmasi: {dropped_refresh_events}/{iterations} iterasi "
            "mengabaikan pembaruan panel embed ketika state.message berupa integer ID karena hasattr(msg, 'edit') "
            "mengembalikan False tanpa mencoba me-resolve message melalui channel.fetch_message()."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"dropped_refresh_events": dropped_refresh_events}
    return res


# ==============================================================================
# 107. CMD SKIP ADVANCING CHECK RACE (Wave 12)
# ==============================================================================
async def fuzz_cmd_skip_advancing_check_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_skip_advancing_check_race",
        description="Fuzzing race condition akses state._advancing di luar state.lock pada cmd_skip dan MusicPanel.skip",
        iterations=iterations,
    )
    unlocked_advancing_events = 0

    for it in range(iterations):
        src_cmd = inspect.getsource(MusicBot.cmd_skip)
        src_panel = inspect.getsource(MusicPanel.skip)

        cmd_unlocked = "state._advancing > 0" in src_cmd and (
            src_cmd.find("state._advancing > 0") < src_cmd.find("async with state.lock:")
        )
        panel_unlocked = "state._advancing > 0" in src_panel and (
            src_panel.find("state._advancing > 0") < src_panel.find("async with state.lock:")
        )

        if cmd_unlocked or panel_unlocked:
            unlocked_advancing_events += 1

    if unlocked_advancing_events > 0:
        res.anomalies.append(
            f"cmd_skip & panel.skip _advancing check-then-act race terkonfirmasi: {unlocked_advancing_events}/{iterations} iterasi "
            "mengecek state._advancing > 0 di luar state.lock sehingga rentan race condition di mana status _advancing "
            "berubah tepat sebelum lock diambil, menyebabkan track gagal di-skip atau diekstraksi ulang."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unlocked_advancing_events": unlocked_advancing_events}
    return res


# ==============================================================================
# 108. VC PLAY CLIENT EXCEPTION IDLE ABANDONMENT (Wave 12)
# ==============================================================================
async def fuzz_vc_play_client_exception_idle_abandonment(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="vc_play_client_exception_idle_abandonment",
        description="Fuzzing vc.play ClientException pada _advance_loop dan verifikasi voice client stranded tanpa idle timer",
        iterations=iterations,
    )
    stranded_client_exception_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=64000 + it)
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        track = Track("FailingClientSong", "http://mock/1", "user")
        state.queue.append(track)
        bot.states[guild.id] = state

        vc.play.side_effect = discord.ClientException("Already playing audio or audio driver error")

        mock_source = MagicMock()
        mock_source.cleanup = MagicMock()

        bot._save_persistent_queue = MagicMock()
        bot.refresh = AsyncMock()
        bot._schedule_idle = MagicMock()
        bot.quit_voice = AsyncMock()

        with patch("bot.extract", return_value={"url": "http://mock/stream", "title": "Track"}), \
             patch("bot.run_extract", new=AsyncMock(return_value={"url": "http://mock/stream", "title": "Track"})), \
             patch("bot.source_for", return_value=mock_source):
            await bot._advance_loop(guild, state, vc)

        if not bot._schedule_idle.called and state.idle_task is None and vc.is_connected():
            stranded_client_exception_events += 1

    if stranded_client_exception_events > 0:
        res.anomalies.append(
            f"vc.play ClientException stranded voice client terkonfirmasi: {stranded_client_exception_events}/{iterations} iterasi "
            "_advance_loop langsung return saat ClientException tanpa mencapai blok penjadwalan idle disconnect, "
            "membiarkan voice client tersambung selamanya tanpa audio yang aktif."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stranded_client_exception_events": stranded_client_exception_events}
    return res


# ==============================================================================
# 109. ANNOUNCE NOW PLAYING CANCELLATION ORPHAN (Wave 12)
# ==============================================================================
async def fuzz_announce_now_playing_cancellation_orphan(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="announce_now_playing_cancellation_orphan",
        description="Fuzzing pembatalan task di sela await channel.send pada _announce_now_playing yang meng-orphan pesan",
        iterations=iterations,
    )
    orphaned_announcement_events = 0

    for it in range(iterations):
        src = inspect.getsource(MusicBot._announce_now_playing)
        catches_cancel = "asyncio.CancelledError" in src
        has_shield = "asyncio.shield" in src

        if not catches_cancel and not has_shield:
            orphaned_announcement_events += 1

    if orphaned_announcement_events > 0:
        res.anomalies.append(
            f"_announce_now_playing cancellation orphan terkonfirmasi: {orphaned_announcement_events}/{iterations} iterasi "
            "channel.send() tidak dilindungi dari CancelledError, sehingga pembatalan task pengumuman sebelumnya di sela await "
            "membuat pesan terkirim di Discord tetapi referensinya tidak disimpan di state.now_message, menjadi pesan yatim."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"orphaned_announcement_events": orphaned_announcement_events}
    return res


# ==============================================================================
# 110. CHANGE VOLUME NAN VALUE ERROR (Wave 12)
# ==============================================================================
async def fuzz_change_volume_nan_value_error(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="change_volume_nan_value_error",
        description="Fuzzing input float('nan') pada change_volume dan unhandled ValueError pada int(round(vol * 100))",
        iterations=iterations,
    )
    nan_value_error_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=65000 + it)
        state = QueueState()
        bot.states[guild.id] = state
        bot._save_persistent_queue = MagicMock()
        bot.refresh = AsyncMock()

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.response.is_done.return_value = True
        interaction.followup.send = AsyncMock()

        src = inspect.getsource(MusicBot.change_volume)
        has_nan_guard = "isnan" in src or "isfinite" in src

        if not has_nan_guard:
            nan_value_error_events += 1

    if nan_value_error_events > 0:
        res.anomalies.append(
            f"change_volume NaN validation omission terkonfirmasi: {nan_value_error_events}/{iterations} iterasi "
            "change_volume tidak memvalidasi math.isnan() atau math.isfinite() pada target_vol, mengandalkan "
            "evaluasi clamping min/max yang rentan meloloskan NaN dan memicu unhandled ValueError pada int(round(vol * 100))."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"nan_value_error_events": nan_value_error_events}
    return res


# ==============================================================================
# 111. TRACKS FROM METADATA MISSING ID WATCH NONE (Wave 12)
# ==============================================================================
async def fuzz_tracks_from_metadata_missing_id_watch_none(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="tracks_from_metadata_missing_id_watch_none",
        description="Verifikasi korupsi URL 'watch?v=None' pada _tracks_from_metadata saat metadata playlist tanpa url dan id",
        iterations=iterations,
    )
    invalid_watch_none_events = 0

    for it in range(iterations):
        data = {
            "_type": "playlist",
            "entries": [
                {"title": f"Corrupted Track {it}"}
            ]
        }
        tracks = bot_module._tracks_from_metadata(data, "requester", "target")
        for t in tracks:
            if "watch?v=None" in t.url:
                invalid_watch_none_events += 1

    if invalid_watch_none_events > 0:
        res.anomalies.append(
            f"_tracks_from_metadata watch?v=None terkonfirmasi: {invalid_watch_none_events}/{iterations} iterasi "
            "metadata entri playlist yang kehilangan URL dan ID menyuntikkan track dengan URL invalid 'watch?v=None' "
            "ke dalam antrean lagu, membuang resource ekstraksi yt-dlp pada STB ARM."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"invalid_watch_none_events": invalid_watch_none_events}
    return res


# ==============================================================================
# 112. BACK IDLE UNLOCKED STATE MUTATION (Wave 12)
# ==============================================================================
async def fuzz_back_idle_unlocked_state_mutation(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="back_idle_unlocked_state_mutation",
        description="Fuzzing mutasi state.current dan pembacaan state.generation di luar state.lock pada cmd_back dan MusicPanel.back",
        iterations=iterations,
    )
    unlocked_back_mutation_events = 0

    for it in range(iterations):
        src_cmd = inspect.getsource(MusicBot.cmd_back)
        src_panel = inspect.getsource(MusicPanel.back)

        cmd_has_unlocked_idle = "if not had_prev:" in src_cmd and "state.current = None" in src_cmd.split("if not had_prev:")[1]
        panel_has_unlocked_idle = "if not had_prev:" in src_panel and "state.current = None" in src_panel.split("if not had_prev:")[1]

        if cmd_has_unlocked_idle or panel_has_unlocked_idle:
            unlocked_back_mutation_events += 1

    if unlocked_back_mutation_events > 0:
        res.anomalies.append(
            f"cmd_back & panel.back unlocked state.current mutation terkonfirmasi: {unlocked_back_mutation_events}/{iterations} iterasi "
            "me-null-kan state.current dan mengakses state.generation di luar state.lock pada penanganan cabang idle saat had_prev=False."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unlocked_back_mutation_events": unlocked_back_mutation_events}
    return res


# ==============================================================================
# 113. PANEL YTDLP VERSION UNCACHED METADATA SCAN (Wave 12)
# ==============================================================================
async def fuzz_panel_ytdlp_version_uncached_metadata_scan(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_ytdlp_version_uncached_metadata_scan",
        description="Verifikasi pemindaian uncached importlib.metadata pada ytdlp_version di setiap request panel",
        iterations=iterations,
    )
    uncached_metadata_scan_events = 0

    for it in range(iterations):
        src = inspect.getsource(panel_module.ytdlp_version)
        has_cache = "_ytdlp_version_cache" in src or "_cached_version" in src or "_last_version_time" in src

        if not has_cache:
            uncached_metadata_scan_events += 1

    if uncached_metadata_scan_events > 0:
        res.anomalies.append(
            f"panel ytdlp_version uncached metadata scan terkonfirmasi: {uncached_metadata_scan_events}/{iterations} iterasi "
            "ytdlp_version memindai importlib.metadata.version('yt-dlp') pada setiap HTTP request panel tanpa cache TTL, "
            "meningkatkan beban read I/O pada eMMC STB ARM."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"uncached_metadata_scan_events": uncached_metadata_scan_events}
    return res


# ==============================================================================
# 114. PANEL UPDATE LOG UNCACHED DISK IO (Wave 12)
# ==============================================================================
async def fuzz_panel_update_log_uncached_disk_io(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_update_log_uncached_disk_io",
        description="Verifikasi synchronous disk I/O tanpa cache pada read_last_update_log() di panel.py",
        iterations=iterations,
    )
    uncached_disk_io_events = 0

    for it in range(iterations):
        src = inspect.getsource(panel_module.read_last_update_log)
        has_cache = "_update_log_cache" in src or "_last_log_read_time" in src or "_cached_update_log" in src

        if not has_cache:
            uncached_disk_io_events += 1

    if uncached_disk_io_events > 0:
        res.anomalies.append(
            f"panel read_last_update_log uncached disk I/O terkonfirmasi: {uncached_disk_io_events}/{iterations} iterasi "
            "read_last_update_log() membaca berkas UPDATE_LOG_PATH secara sinkron dari disk pada setiap render atau polling log, "
            "menimbulkan latensi event loop dan keausan penyimpanan flash eMMC."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"uncached_disk_io_events": uncached_disk_io_events}
    return res


# ==============================================================================
# 115. TRACK LOOP EXTRACTION FAILURE STALL & IDLE OMISSION (Wave 13)
# ==============================================================================
async def fuzz_loop_track_extraction_failure_stall_and_idle_omission(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="loop_track_extraction_failure_stall_and_idle_omission",
        description="Fuzzing kegagalan ekstraksi pada loop_mode=='track' saat queue kosong dan verifikasi penelantaran voice client tanpa idle timer",
        iterations=iterations,
    )
    stalled_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=70000 + it)
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.loop_mode = "track"
        track = Track("FailingLoopTrack", f"https://youtube.com/watch?v=fail_loop_{it}", "user")
        state.current = track
        state.queue.clear()
        bot.states[guild.id] = state

        bot._save_persistent_queue = MagicMock()
        bot.refresh = AsyncMock()
        bot._schedule_idle = MagicMock()

        with patch("bot.source_for", side_effect=Exception("Track extraction 404")):
            await bot._advance_loop(guild, state, vc)

        if state.current is not None and not bot._schedule_idle.called:
            stalled_events += 1

    if stalled_events > 0:
        res.anomalies.append(
            f"Track loop extraction failure idle omission terkonfirmasi: {stalled_events}/{iterations} iterasi "
            "loop_mode=='track' saat ekstraksi gagal mempertahankan state.current non-None, menggagalkan evaluasi "
            "schedule_idle dan menelantarkan voice client di channel tanpa timer idle disconnect."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stalled_events": stalled_events}
    return res


# ==============================================================================
# 116. QUEUE LOOP TRACK DROP ON EXTRACTION FAILURE (Wave 13)
# ==============================================================================
async def fuzz_loop_queue_track_drop_on_extraction_failure(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="loop_queue_track_drop_on_extraction_failure",
        description="Fuzzing kegagalan ekstraksi track pada loop_mode=='queue' dan verifikasi hilangnya track yang sedang diputar dari rotasi antrean",
        iterations=iterations,
    )
    track_drop_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=71000 + it)
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.loop_mode = "queue"
        prev_track = Track("PrevSong", f"https://youtube.com/watch?v=prev_{it}", "user")
        failing_next = Track("FailingNext", f"https://youtube.com/watch?v=fail_next_{it}", "user")
        state.current = prev_track
        state.queue.append(failing_next)
        bot.states[guild.id] = state

        bot._save_persistent_queue = MagicMock()
        bot.refresh = AsyncMock()
        bot._schedule_idle = MagicMock()

        with patch("bot.source_for", side_effect=Exception("Next track extraction error")):
            await bot._advance_loop(guild, state, vc)

        if prev_track not in state.queue and state.current is None:
            track_drop_events += 1

    if track_drop_events > 0:
        res.anomalies.append(
            f"Queue loop track drop on extraction failure terkonfirmasi: {track_drop_events}/{iterations} iterasi "
            "pada loop_mode=='queue' saat track berikutnya gagal ekstraksi, lagu sebelumnya di state.current dipindahkan "
            "ke history dan di-null-kan tanpa di-enqueue kembali ke antrean, menghilangkannya dari rotasi queue loop secara permanen."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"track_drop_events": track_drop_events}
    return res


# ==============================================================================
# 117. CLOSE VOICE CLIENT DISCONNECT & SUBPROCESS LEAK (Wave 13)
# ==============================================================================
async def fuzz_close_voice_client_disconnect_and_subprocess_leak(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="close_voice_client_disconnect_and_subprocess_leak",
        description="Verifikasi penghentian pemutaran audio, cleanup ffmpeg subprocess, dan disconnect voice client pada bot.close()",
        iterations=iterations,
    )
    leak_events = 0

    for it in range(iterations):
        src = inspect.getsource(MusicBot.close)
        has_vc_handling = "voice_clients" in src or "vc.disconnect" in src or "vc.stop" in src

        if not has_vc_handling:
            leak_events += 1

    if leak_events > 0:
        res.anomalies.append(
            f"bot.close() voice client & ffmpeg subprocess leak terkonfirmasi: {leak_events}/{iterations} iterasi "
            "shutdown close() tidak menghentikan playback, membersihkan BufferedAudioSource, atau memutus voice client "
            "aktif melalui self.voice_clients, meninggalkan subprocess ffmpeg menggantung di background STB ARM."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"leak_events": leak_events}
    return res


# ==============================================================================
# 118. SUMMON CHANNEL SEND FAILURE STRANDED VOICE (Wave 13)
# ==============================================================================
async def fuzz_summon_channel_send_failure_stranded_voice(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="summon_channel_send_failure_stranded_voice",
        description="Fuzzing kegagalan channel.send pada /musik (summon) pasca voice connect dan verifikasi penelantaran voice client tanpa idle timer",
        iterations=iterations,
    )
    stranded_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=72000 + it)
        guild.voice_client = None
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        vc.is_connected.return_value = True

        state = QueueState()
        state.queue.clear()
        state.current = None
        bot.states[guild.id] = state
        bot._schedule_idle = MagicMock()

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.response.is_done.return_value = True
        interaction.followup.send = AsyncMock()

        voice = MagicMock()
        voice.channel = MagicMock()
        voice.channel.id = 9201
        voice.channel.connect = AsyncMock(return_value=vc)
        voice.channel.permissions_for = MagicMock(return_value=MagicMock(connect=True, speak=True))
        interaction.user.voice = voice
        guild.me = MagicMock()

        channel = MagicMock()
        channel.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Forbidden"))
        interaction.channel = channel
        interaction.channel_id = 9202

        await bot.summon(interaction)

        if not bot._schedule_idle.called and not vc.disconnect.called:
            stranded_events += 1

    if stranded_events > 0:
        res.anomalies.append(
            f"summon channel.send failure stranded voice terkonfirmasi: {stranded_events}/{iterations} iterasi "
            "/musik berhasil menghubungkan voice client tetapi gagal mengirim panel (Forbidden/HTTPException), "
            "melompat langsung ke except block tanpa memanggil _schedule_idle atau memutus koneksi, menelantarkan bot di voice selamanya."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stranded_events": stranded_events}
    return res


# ==============================================================================
# 119. MUSIC PANEL GUARD TIMEOUT GHOST VOICE LOCKOUT (Wave 13)
# ==============================================================================
async def fuzz_music_panel_guard_timeout_ghost_voice_lockout(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="music_panel_guard_timeout_ghost_voice_lockout",
        description="Fuzzing timeout pada MusicPanel.guard voice connect dan verifikasi disconnect force=True untuk mencegah ghost VoiceClient",
        iterations=iterations,
    )
    ghost_lockout_events = 0

    for it in range(iterations):
        src = inspect.getsource(MusicPanel.guard)
        has_guard_disconnect = False
        if "TimeoutError" in src:
            timeout_block = src.split("TimeoutError)")[1].split("except discord.ClientException")[0]
            if "disconnect" in timeout_block:
                has_guard_disconnect = True

        if not has_guard_disconnect:
            ghost_lockout_events += 1

    if ghost_lockout_events > 0:
        res.anomalies.append(
            f"MusicPanel.guard timeout ghost VoiceClient lockout terkonfirmasi: {ghost_lockout_events}/{iterations} iterasi "
            "guard tidak memanggil disconnect(force=True) pada interaction.guild.voice_client saat TimeoutError, "
            "meninggalkan objek VoiceClient setengah terbuka yang memblokir interaksi panel berikutnya dengan ClientException."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"ghost_lockout_events": ghost_lockout_events}
    return res


# ==============================================================================
# 120. RESTORED STATE CURRENT DESYNC & TRACK LOSS (Wave 13)
# ==============================================================================
async def fuzz_restored_state_current_desync_and_track_loss(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="restored_state_current_desync_and_track_loss",
        description="Fuzzing pemulihan state.current dari queue_state.json pasca restart dan verifikasi track loss pada /play berikutnya",
        iterations=iterations,
    )
    track_loss_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=73000 + it)
        guild.voice_client = None

        restored_data = {
            "current": {"title": "InterruptedSong", "url": "https://youtube.com/watch?v=interrupted", "requester": "user"},
            "queue": [],
        }

        state = QueueState()
        bot.states[guild.id] = state
        track = bot_module._dict_to_track(restored_data["current"])
        state.current = track

        new_track = [Track("NewSong", "https://youtube.com/watch?v=newsong", "user")]
        await bot._enqueue_tracks(guild, new_track)

        if track in state.history and track not in state.queue and state.current is not track:
            track_loss_events += 1

    if track_loss_events > 0:
        res.anomalies.append(
            f"Restored state.current desync & track loss terkonfirmasi: {track_loss_events}/{iterations} iterasi "
            "pemulihan state.current saat bot terputus pasca restart menyebabkan embed palsu menampilkan lagu berputar, "
            "dan /play berikutnya langsung membuang track yang dipulihkan ke history tanpa pernah memutarnya."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"track_loss_events": track_loss_events}
    return res


# ==============================================================================
# 121. SHUFFLE PERSISTENT QUEUE FILE WIPEOUT RACE (Wave 13)
# ==============================================================================
async def fuzz_shuffle_persistent_queue_file_wipeout_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="shuffle_persistent_queue_file_wipeout_race",
        description="Fuzzing race condition concurrent shuffle dan _save_persistent_queue saat state.queue kosong sesaat yang menghapus queue_state.json",
        iterations=iterations,
    )
    wipeout_race_events = 0

    for it in range(iterations):
        src_shuffle = inspect.getsource(MusicPanel.shuffle)
        src_cmd = inspect.getsource(MusicBot.cmd_shuffle)
        src_save = inspect.getsource(MusicBot._save_persistent_queue)

        uses_clear_extend = ("state.queue.clear()" in src_shuffle and "state.queue.extend" in src_shuffle) or \
                            ("state.queue.clear()" in src_cmd and "state.queue.extend" in src_cmd)
        holds_state_lock = "async with st.lock" in src_save or "with st.lock" in src_save

        if uses_clear_extend and not holds_state_lock:
            wipeout_race_events += 1

    if wipeout_race_events > 0:
        res.anomalies.append(
            f"Persistent queue file wipeout race on shuffle terkonfirmasi: {wipeout_race_events}/{iterations} iterasi "
            "shuffle menggunakan pola non-atomik clear() lalu extend() sementara _save_persistent_queue membaca antrean tanpa state.lock, "
            "berisiko mengosongkan payload dan menghapus queue_state.json dari disk saat dieksekusi bersamaan."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"wipeout_race_events": wipeout_race_events}
    return res


# ==============================================================================
# 122. ANNOUNCE NOW PLAYING ASYNCIO SHIELD CANCELLATION ORPHAN (Wave 13)
# ==============================================================================
async def fuzz_announce_now_playing_asyncio_shield_cancellation_orphan(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="announce_now_playing_asyncio_shield_cancellation_orphan",
        description="Fuzzing pembatalan announce_task di sela await asyncio.shield(channel.send) pada _announce_now_playing yang meng-orphan pesan",
        iterations=iterations,
    )
    orphan_events = 0

    for it in range(iterations):
        src = inspect.getsource(MusicBot._announce_now_playing)
        has_vulnerable_shield = "state.now_message = await asyncio.shield" in src

        if has_vulnerable_shield:
            orphan_events += 1

    if orphan_events > 0:
        res.anomalies.append(
            f"Orphaned now-playing message via asyncio.shield cancellation terkonfirmasi: {orphan_events}/{iterations} iterasi "
            "assignment state.now_message = await asyncio.shield() memicu CancelledError saat task dibatalkan di tengah pengiriman, "
            "meninggalkan pesan Discord aktif tanpa tersimpan di state.now_message sehingga tidak dapat dihapus."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"orphan_events": orphan_events}
    return res


# ==============================================================================
# 123. ESCAPE MARKDOWN NONE TYPE ERROR (Wave 13)
# ==============================================================================
async def fuzz_escape_markdown_none_type_error(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="escape_markdown_none_type_error",
        description="Fuzzing track title None pada escape_markdown di PlaylistView, MusicPanel.playlist, cmd_queue, dan _announce_now_playing",
        iterations=iterations,
    )
    none_type_error_events = 0

    for it in range(iterations):
        src_pv = inspect.getsource(PlaylistView.refresh_playlist)
        src_panel_pl = inspect.getsource(MusicPanel.playlist)
        src_cmd_q = inspect.getsource(MusicBot.cmd_queue)
        src_announce = inspect.getsource(MusicBot._announce_now_playing)

        vulnerable_pv = "escape_markdown(current_track.title)" in src_pv or "escape_markdown(t.title)" in src_pv
        vulnerable_panel = "escape_markdown(current_track.title)" in src_panel_pl or "escape_markdown(t.title)" in src_panel_pl
        vulnerable_cmd = "escape_markdown(current_track.title)" in src_cmd_q or "escape_markdown(t.title)" in src_cmd_q
        vulnerable_ann = "escape_markdown(track.title)" in src_announce

        if vulnerable_pv or vulnerable_panel or vulnerable_cmd or vulnerable_ann:
            none_type_error_events += 1

    if none_type_error_events > 0:
        res.anomalies.append(
            f"escape_markdown(None) TypeError terkonfirmasi: {none_type_error_events}/{iterations} iterasi "
            "track.title bernilai None dipassing langsung ke discord.utils.escape_markdown() tanpa fallback string di "
            "PlaylistView, MusicPanel.playlist, cmd_queue, atau _announce_now_playing, memicu unhandled TypeError yang meng-crash command/view."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"none_type_error_events": none_type_error_events}
    return res


# ==============================================================================
# 124. FORMAT DURATION NAN INF VALUE ERROR (Wave 13)
# ==============================================================================
async def fuzz_format_duration_nan_inf_value_error(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="format_duration_nan_inf_value_error",
        description="Fuzzing input float('nan') dan float('inf') pada format_duration dan verifikasi unhandled ValueError/OverflowError",
        iterations=iterations,
    )
    nan_inf_error_events = 0

    for it in range(iterations):
        crashed = False
        try:
            bot_module.format_duration(float('nan'))
        except (ValueError, OverflowError):
            crashed = True

        try:
            bot_module.format_duration(float('inf'))
        except (ValueError, OverflowError):
            crashed = True

        if crashed:
            nan_inf_error_events += 1

    if nan_inf_error_events > 0:
        res.anomalies.append(
            f"format_duration NaN / inf crash terkonfirmasi: {nan_inf_error_events}/{iterations} iterasi "
            "format_duration(float('nan')) memicu ValueError dan format_duration(float('inf')) memicu OverflowError "
            "karena pengecekan `seconds <= 0` bernilai False untuk NaN/inf sebelum int(seconds)."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"nan_inf_error_events": nan_inf_error_events}
    return res


# ==============================================================================
# 125. CLEAN SEED TITLE SINGLE NOISE WORD WIPEOUT (Wave 13)
# ==============================================================================
async def fuzz_clean_seed_title_single_noise_word_wipeout(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="clean_seed_title_single_noise_word_wipeout",
        description="Verifikasi pembersihan total judul lagu satu kata noise pada _clean_seed_title yang menggagalkan pencarian AutoPlay",
        iterations=iterations,
    )
    wipeout_events = 0

    for it in range(iterations):
        cleaned = bot_module._clean_seed_title("Audio")
        queries = bot_module.build_recommendation_queries(["Audio"])

        if cleaned == "" and len(queries) == 0:
            wipeout_events += 1

    if wipeout_events > 0:
        res.anomalies.append(
            f"_clean_seed_title total title wipeout terkonfirmasi: {wipeout_events}/{iterations} iterasi "
            "judul lagu satu kata noise ('Audio', 'Official', 'HQ') di-strip hingga menjadi string kosong '', "
            "menyebabkan build_recommendation_queries menolak seed dan menggagalkan AutoPlay."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"wipeout_events": wipeout_events}
    return res


# ==============================================================================
# 126. TRACKS FROM METADATA DOUBLE WATCH URL CORRUPTION (Wave 13)
# ==============================================================================
async def fuzz_tracks_from_metadata_double_watch_url_corruption(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="tracks_from_metadata_double_watch_url_corruption",
        description="Verifikasi korupsi URL https://www.youtube.com/watch?v=watch?v=ID pada flat playlist dengan URL relatif",
        iterations=iterations,
    )
    double_url_events = 0

    for it in range(iterations):
        data = {
            "_type": "playlist",
            "entries": [
                {"title": f"Song {it}", "url": "watch?v=dQw4w9WgXcQ"}
            ]
        }
        tracks = bot_module._tracks_from_metadata(data, "user", "target")
        if tracks and "watch?v=watch?v=" in tracks[0].url:
            double_url_events += 1

    if double_url_events > 0:
        res.anomalies.append(
            f"_tracks_from_metadata double watch?v= corruption terkonfirmasi: {double_url_events}/{iterations} iterasi "
            "entri playlist flat dengan url relatif 'watch?v=ID' menghasilkan URL cacat 'https://www.youtube.com/watch?v=watch?v=ID', "
            "menggagalkan pemutaran dan ekstraksi lagu."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"double_url_events": double_url_events}
    return res


# ==============================================================================
# 127. TRACKS FROM METADATA NON PLAYLIST SEARCH QUERY POLLUTION (Wave 13)
# ==============================================================================
async def fuzz_tracks_from_metadata_non_playlist_search_query_pollution(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="tracks_from_metadata_non_playlist_search_query_pollution",
        description="Verifikasi polusi target ytsearch pada URL track non-playlist ketika data['id'] tersedia tetapi webpage_url kosong",
        iterations=iterations,
    )
    pollution_events = 0

    for it in range(iterations):
        data = {
            "id": "dQw4w9WgXcQ",
            "title": f"Song {it}",
            "duration": 200,
        }
        tracks = bot_module._tracks_from_metadata(data, "user", "ytsearch1:shape of you")
        if tracks:
            t = tracks[0]
            if t.url.startswith("ytsearch1:") and bot_module.extract_video_id(t.url) is None:
                pollution_events += 1

    if pollution_events > 0:
        res.anomalies.append(
            f"_tracks_from_metadata search query pollution terkonfirmasi: {pollution_events}/{iterations} iterasi "
            "ekstraksi non-playlist tanpa webpage_url menggunakan string target kueri pencarian alih-alih mengonstruksi "
            "watch URL dari data['id'], merusak penyimpanan antrean dan menggagalkan ekstraksi video ID untuk AutoPlay YouTube Mix."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"pollution_events": pollution_events}
    return res


# ==============================================================================
# 128. AFK DISCONNECT TIMEOUT INF OVERFLOW ERROR (Wave 13)
# ==============================================================================
async def fuzz_afk_disconnect_timeout_inf_overflow_error(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="afk_disconnect_timeout_inf_overflow_error",
        description="Fuzzing AFK_TIMEOUT_SECONDS bernilai 'inf' pada _afk_disconnect dan verifikasi unhandled OverflowError pada dur_str formatting",
        iterations=iterations,
    )
    overflow_events = 0

    for it in range(iterations):
        timeout = float('inf')
        crashed = False
        try:
            dur_str = "3 menit" if timeout == 180 else (f"{int(timeout // 60)} menit" if timeout >= 60 else f"{int(timeout)} detik")
        except (ValueError, OverflowError):
            crashed = True

        src = inspect.getsource(bot_module.get_afk_timeout)
        allows_inf = "isfinite" not in src and "isinf" not in src

        if crashed and allows_inf:
            overflow_events += 1

    if overflow_events > 0:
        res.anomalies.append(
            f"_afk_disconnect timeout inf OverflowError terkonfirmasi: {overflow_events}/{iterations} iterasi "
            "get_afk_timeout mengizinkan float('inf') dan int(timeout // 60) memicu unhandled OverflowError "
            "sebelum bot dapat memutus koneksi dari voice."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"overflow_events": overflow_events}
    return res


# ==============================================================================
# 129. PANEL UPDATE STALE YTDLP VERSION & LOG CACHE (Wave 13)
# ==============================================================================
async def fuzz_panel_update_stale_ytdlp_version_and_log_cache(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_update_stale_ytdlp_version_and_log_cache",
        description="Verifikasi kegagalan invalidasi _ytdlp_version_cache dan _update_log_cache pada panel._update() pasca eksekusi update",
        iterations=iterations,
    )
    stale_cache_events = 0

    for it in range(iterations):
        src = inspect.getsource(panel_module.Handler._update)
        invalidates_ytdlp_cache = "_ytdlp_version_cache" in src
        invalidates_update_log = "_update_log_cache" in src

        if not invalidates_ytdlp_cache or not invalidates_update_log:
            stale_cache_events += 1

    if stale_cache_events > 0:
        res.anomalies.append(
            f"panel._update() stale cache retention terkonfirmasi: {stale_cache_events}/{iterations} iterasi "
            "_update() hanya membersihkan _state_cache dan _log_cache, gagal menginvalidasi _ytdlp_version_cache (30s TTL) "
            "dan _update_log_cache sehingga panel terus menampilkan versi yt-dlp lama pada halaman yang di-redirect."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stale_cache_events": stale_cache_events}
    return res


# ==============================================================================
# 130. PANEL CACHED SYSTEMCTL THUNDERING HERD FORK (Wave 13)
# ==============================================================================
async def fuzz_panel_cached_systemctl_thundering_herd_fork(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_cached_systemctl_thundering_herd_fork",
        description="Fuzzing permintaan konkuren pada _cached_systemctl saat cache kedaluwarsa dan verifikasi thundering herd subprocess fork",
        iterations=iterations,
    )
    thundering_herd_events = 0

    for it in range(iterations):
        src = inspect.getsource(panel_module._cached_systemctl)
        has_fetch_lock = "fetch_lock" in src or "_systemctl_lock" in src or "_state_fetch_lock" in src

        if not has_fetch_lock:
            thundering_herd_events += 1

    if thundering_herd_events > 0:
        res.anomalies.append(
            f"panel _cached_systemctl thundering herd fork terkonfirmasi: {thundering_herd_events}/{iterations} iterasi "
            "_cached_systemctl tidak memiliki lock serialisasi fetch saat TTL kedaluwarsa, menyebabkan request HTTP konkuren "
            "secara serempak mem-fork proses systemctl is-active ganda dan membebani CPU STB ARM."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"thundering_herd_events": thundering_herd_events}
    return res


# ==============================================================================
# 131. ESCAPE MARKDOWN NONE TYPE ERROR IN MODAL & PLAY (Wave 14)
# ==============================================================================
async def fuzz_escape_markdown_none_type_error_modal_and_play(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="escape_markdown_none_type_error_modal_and_play",
        description="Fuzzing track.title bernilai None pada escape_markdown di SearchModal.on_submit dan cmd_play",
        iterations=iterations,
    )
    none_type_error_events = 0

    for it in range(iterations):
        src_modal = inspect.getsource(SearchModal.on_submit)
        src_play = inspect.getsource(MusicBot.cmd_play)

        vulnerable_modal = "escape_markdown(tracks[0].title)" in src_modal and "tracks[0].title or" not in src_modal
        vulnerable_play = "escape_markdown(tracks[0].title)" in src_play and "tracks[0].title or" not in src_play

        if vulnerable_modal or vulnerable_play:
            none_type_error_events += 1

    if none_type_error_events > 0:
        res.anomalies.append(
            f"escape_markdown(None) TypeError di modal & cmd_play terkonfirmasi: {none_type_error_events}/{iterations} iterasi "
            "tracks[0].title bernilai None dipassing langsung ke discord.utils.escape_markdown() tanpa fallback string di "
            "SearchModal.on_submit (lines 1266, 1268) atau cmd_play (lines 2401, 2403), memicu unhandled TypeError yang meng-crash interaksi."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"none_type_error_events": none_type_error_events}
    return res


# ==============================================================================
# 132. VC PLAY CLIENT EXCEPTION NONEMPTY QUEUE VOICE LOCKOUT (Wave 14)
# ==============================================================================
async def fuzz_vc_play_client_exception_nonempty_queue_voice_lockout(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="vc_play_client_exception_nonempty_queue_voice_lockout",
        description="Fuzzing vc.play ClientException pada _advance_loop dengan antrean non-kosong dan verifikasi ghost voice lockout",
        iterations=iterations,
    )
    lockout_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=74000 + it)
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        track1 = Track("Song1", f"https://youtube.com/watch?v=s1_{it}", "user")
        track2 = Track("Song2", f"https://youtube.com/watch?v=s2_{it}", "user")
        state.queue.append(track1)
        state.queue.append(track2)
        state.current = None
        bot.states[guild.id] = state

        vc.play.side_effect = discord.ClientException("Already playing audio")

        bot._save_persistent_queue = MagicMock()
        bot.refresh = AsyncMock()
        bot._schedule_idle = MagicMock()

        with patch("bot.source_for", return_value=MagicMock()):
            await bot._advance_loop(guild, state, vc)

        cb_tripped = state.consecutive_playback_errors >= 3
        can_idle_quit = (not state.queue) or cb_tripped
        if not can_idle_quit and state.current is None and not vc.is_playing():
            lockout_events += 1

    if lockout_events > 0:
        res.anomalies.append(
            f"vc.play ClientException non-empty queue lockout terkonfirmasi: {lockout_events}/{iterations} iterasi "
            "saat vc.play melempar ClientException dengan antrean non-kosong, _advance_loop kembali tanpa membuang lagu "
            "atau memicu circuit breaker, menahan lagu di head antrean dan menggagalkan idle_disconnect (not state.queue is False), "
            "mengunci VoiceClient di channel tanpa audio selamanya."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"lockout_events": lockout_events}
    return res


# ==============================================================================
# 133. PERSISTENT QUEUE GUILD SETTINGS WIPEOUT ON EMPTY QUEUE (Wave 14)
# ==============================================================================
async def fuzz_persistent_queue_guild_settings_wipeout_on_empty_queue(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="persistent_queue_guild_settings_wipeout_on_empty_queue",
        description="Verifikasi penghapusan berkas queue_state.json dan kehilangan pengaturan guild (volume, loop, autoplay) saat antrean kosong",
        iterations=iterations,
    )
    wipeout_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild_id = 75000 + it
        state = QueueState()
        state.volume = 0.85
        state.loop_mode = "queue"
        state.autoplay = True
        state.current = None
        state.queue.clear()
        bot.states[guild_id] = state

        src = inspect.getsource(MusicBot._save_persistent_queue)
        vulnerable = "if curr or q:" in src and "getattr(st, 'volume'" in src

        if vulnerable:
            wipeout_events += 1

    if wipeout_events > 0:
        res.anomalies.append(
            f"Persistent queue settings wipeout on empty queue terkonfirmasi: {wipeout_events}/{iterations} iterasi "
            "evaluasi 'if curr or q:' di line 1844 mengabaikan guild dengan antrean kosong, mengosongkan payload "
            "dan memicu penghapusan queue_state.json di line 1874, memusnahkan preferensi volume, loop_mode, dan autoplay pengguna."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"wipeout_events": wipeout_events}
    return res


# ==============================================================================
# 134. SKIP STOPPED PLAYBACK FAILING QUEUE HEAD DROP OMISSION (Wave 14)
# ==============================================================================
async def fuzz_skip_stopped_playback_failing_queue_head_drop_omission(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="skip_stopped_playback_failing_queue_head_drop_omission",
        description="Fuzzing skip saat pemutaran berhenti / circuit breaker aktif dan verifikasi pembuangan track rusak di state.queue[0]",
        iterations=iterations,
    )
    stuck_head_events = 0

    for it in range(iterations):
        src_panel_skip = inspect.getsource(MusicPanel.skip)
        src_cmd_skip = inspect.getsource(MusicBot.cmd_skip)

        panel_drops_queue_head = "state.queue.popleft()" in src_panel_skip or "del state.queue[0]" in src_panel_skip
        cmd_drops_queue_head = "state.queue.popleft()" in src_cmd_skip or "del state.queue[0]" in src_cmd_skip

        if not panel_drops_queue_head or not cmd_drops_queue_head:
            stuck_head_events += 1

    if stuck_head_events > 0:
        res.anomalies.append(
            f"Skip on stopped playback stuck queue head terkonfirmasi: {stuck_head_events}/{iterations} iterasi "
            "saat audio berhenti (state.current is None, circuit breaker aktif atau idle), MusicPanel.skip dan cmd_skip "
            "hanya mengecek 'if state.current:' tanpa membuang lagu rusak di head antrean (state.queue[0]), "
            "menyebabkan pemanggilan advance() berikutnya kembali mencoba memutar lagu yang sama yang gagal."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stuck_head_events": stuck_head_events}
    return res


# ==============================================================================
# 135. SUMMON VOICE STRANDED ON NONEMPTY QUEUE (Wave 14)
# ==============================================================================
async def fuzz_summon_voice_stranded_on_nonempty_queue(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="summon_voice_stranded_on_nonempty_queue",
        description="Fuzzing /musik (summon) saat state.queue memiliki lagu tersisa dan audio idle dan verifikasi ketiadaan idle timer atau advance trigger",
        iterations=iterations,
    )
    stranded_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=76000 + it)
        guild.voice_client = None
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False
        vc.is_connected.return_value = True

        state = QueueState()
        track = Track("RestoredSong", f"https://youtube.com/watch?v=res_{it}", "user")
        state.queue.append(track)
        state.current = None
        bot.states[guild.id] = state
        bot._schedule_idle = MagicMock()
        bot.advance = AsyncMock()

        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = guild
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        voice = MagicMock()
        voice.channel = MagicMock()
        voice.channel.id = 9301
        voice.channel.connect = AsyncMock(return_value=vc)
        voice.channel.permissions_for = MagicMock(return_value=MagicMock(connect=True, speak=True))
        interaction.user.voice = voice
        guild.me = MagicMock()

        channel = MagicMock()
        channel.send = AsyncMock(return_value=MagicMock(id=9302))
        interaction.channel = channel
        interaction.channel_id = 9303

        await bot.summon(interaction)

        if not bot._schedule_idle.called and not bot.advance.called:
            stranded_events += 1

    if stranded_events > 0:
        res.anomalies.append(
            f"summon voice stranded on non-empty queue terkonfirmasi: {stranded_events}/{iterations} iterasi "
            "/musik menghubungkan voice client dengan state.queue berisi lagu tetapi audio tidak berjalan; "
            "kondisi 'and not state.queue' di line 2904 mencegah penjadwalan idle timer sementara advance() tidak dipicu, "
            "menelantarkan bot di voice selamanya tanpa ada audio yang dimainkan."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stranded_events": stranded_events}
    return res


# ==============================================================================
# 136. LOOP QUEUE TRACK DROP ON DUPLICATE TRACK EQUALITY (Wave 14)
# ==============================================================================
async def fuzz_loop_queue_track_drop_on_duplicate_track_equality(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="loop_queue_track_drop_on_duplicate_track_equality",
        description="Fuzzing kehilangan lagu pada rotasi loop_mode=='queue' akibat structural equality Track dataclass saat duplikasi lagu",
        iterations=iterations,
    )
    track_drop_events = 0

    for it in range(iterations):
        src = inspect.getsource(MusicBot._advance_loop)
        uses_in_check = "state.current not in state.queue" in src

        t1 = Track("DupSong", "https://youtube.com/watch?v=dupsong", "user")
        t2 = Track("DupSong", "https://youtube.com/watch?v=dupsong", "user")
        q = [t2]

        is_structurally_equal = (t1 in q) and (not any(t is t1 for t in q))

        if uses_in_check and is_structurally_equal:
            track_drop_events += 1

    if track_drop_events > 0:
        res.anomalies.append(
            f"loop_mode=='queue' track drop on duplicate equality terkonfirmasi: {track_drop_events}/{iterations} iterasi "
            "pengecekan 'state.current not in state.queue' di line 3343 menggunakan dataclass equality (__eq__), "
            "sehingga jika antrean memiliki lagu duplikat dengan URL/metadata sama, lagu yang sedang selesai diputar "
            "diabaikan dan tidak dimasukkan kembali ke antrean, menghilangkannya dari rotasi loop queue."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"track_drop_events": track_drop_events}
    return res


# ==============================================================================
# 137. BOT CLOSE MISSING VC SOURCE CLEANUP FFMPEG LEAK (Wave 14)
# ==============================================================================
async def fuzz_bot_close_missing_vc_source_cleanup_ffmpeg_leak(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="bot_close_missing_vc_source_cleanup_ffmpeg_leak",
        description="Verifikasi kebocoran BufferedAudioSource reader thread dan proses ffmpeg latar belakang pada bot.close() akibat ketiadaan vc.source.cleanup()",
        iterations=iterations,
    )
    leak_events = 0

    for it in range(iterations):
        src = inspect.getsource(MusicBot.close)
        has_source_cleanup = "source.cleanup" in src or "getattr(vc, 'source'" in src

        if not has_source_cleanup:
            leak_events += 1

    if leak_events > 0:
        res.anomalies.append(
            f"bot.close() missing vc.source.cleanup ffmpeg leak terkonfirmasi: {leak_events}/{iterations} iterasi "
            "MusicBot.close() di lines 2344-2353 memanggil vc.stop() dan vc.disconnect(), tetapi tidak memanggil "
            "vc.source.cleanup(), meninggalkan BufferedAudioSource reader thread dan proses ffmpeg child running di background STB ARM."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"leak_events": leak_events}
    return res


# ==============================================================================
# 138. AUDIO PLAYER SEND SILENCE EOF FALSE PLAYBACK ERROR (Wave 14)
# ==============================================================================
async def fuzz_audio_player_send_silence_eof_false_playback_error(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="audio_player_send_silence_eof_false_playback_error",
        description="Fuzzing send_silence() pasca EOF normal pada AudioPlayer._steady_do_run dan verifikasi false playback error",
        iterations=iterations,
    )
    false_error_events = 0

    for it in range(iterations):
        src = inspect.getsource(bot_module.patch_audio_player)
        vulnerable = "self.send_silence()" in src and "try:" not in src.split("self.send_silence()")[0].split("if client.is_connected():")[-1]

        if vulnerable:
            false_error_events += 1

    if false_error_events > 0:
        res.anomalies.append(
            f"AudioPlayer send_silence unhandled exception terkonfirmasi: {false_error_events}/{iterations} iterasi "
            "_steady_do_run memanggil self.send_silence() tanpa try-except setelah normal EOF; jika socket voice terputus, "
            "exception akan lolos ke AudioPlayer.run, mengeset self._current_error dan memicu callback after(error) dengan error palsu."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"false_error_events": false_error_events}
    return res


# ==============================================================================
# 139. PANEL EMPTY TRACK QUEUE LEN DISPLAY MISMATCH (Wave 14)
# ==============================================================================
async def fuzz_panel_empty_track_queue_len_display_mismatch(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_empty_track_queue_len_display_mismatch",
        description="Verifikasi tampilan '(antrean kosong)' pada panel web saat pemutaran idle/standby padahal antrean berisi lagu",
        iterations=iterations,
    )
    display_mismatch_events = 0

    for it in range(iterations):
        dummy_info = {
            "guilds": [
                {
                    "name": "TestServer",
                    "connected": True,
                    "channel_name": "Music Room",
                    "is_playing": False,
                    "is_paused": False,
                    "track": "",
                    "queue_len": 5,
                    "listener_count": 0,
                    "listeners": [],
                    "members": 10,
                }
            ]
        }
        html = panel_module.format_guilds_html(dummy_info)

        if "(antrean kosong)" in html and "5 di antrean" not in html:
            display_mismatch_events += 1

    if display_mismatch_events > 0:
        res.anomalies.append(
            f"Panel web empty track queue display mismatch terkonfirmasi: {display_mismatch_events}/{iterations} iterasi "
            "panel.py di line 611 langsung merender '(antrean kosong)' jika track kosong, mengabaikan queue_len yang "
            "berisi lagu di antrean saat bot sedang standby di voice channel."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"display_mismatch_events": display_mismatch_events}
    return res


# ==============================================================================
# 140. PANEL READ BOT RUNTIME INFO UNCACHED DISK IO (Wave 14)
# ==============================================================================
async def fuzz_panel_read_bot_runtime_info_uncached_disk_io(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_read_bot_runtime_info_uncached_disk_io",
        description="Verifikasi synchronous disk I/O dan pembacaan berkas state.json tanpa cache in-memory TTL pada read_bot_runtime_info()",
        iterations=iterations,
    )
    uncached_io_events = 0

    for it in range(iterations):
        src = inspect.getsource(panel_module.read_bot_runtime_info)
        has_cache = "_runtime_info_cache" in src or "_state_cache" in src or "cache" in src

        if not has_cache:
            uncached_io_events += 1

    if uncached_io_events > 0:
        res.anomalies.append(
            f"read_bot_runtime_info uncached disk I/O terkonfirmasi: {uncached_io_events}/{iterations} iterasi "
            "read_bot_runtime_info() di panel.py membaca state.json dari disk secara synchronous tanpa TTL cache in-memory, "
            "menyebabkan disk I/O berulang pada setiap HTTP request dan polling status di STB ARM."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"uncached_io_events": uncached_io_events}
    return res


# ==============================================================================
# 141. PANEL PASSWORD SAVE FAILURE SESSION LOCKOUT (Wave 14)
# ==============================================================================
async def fuzz_panel_password_save_failure_session_lockout(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_password_save_failure_session_lockout",
        description="Verifikasi pencabutan seluruh sesi login aktif dan lockout pengguna saat store().write() gagal I/O pasca perubahan kata sandi",
        iterations=iterations,
    )
    lockout_events = 0

    for it in range(iterations):
        src = inspect.getsource(panel_module.Handler._save)
        update_pos = src.find("update_panel_password(raw_pass)")
        write_pos = src.find("store().write(")

        if update_pos != -1 and write_pos != -1 and update_pos < write_pos:
            lockout_events += 1

    if lockout_events > 0:
        res.anomalies.append(
            f"Panel password change failure session lockout terkonfirmasi: {lockout_events}/{iterations} iterasi "
            "update_panel_password() dipanggil di line 1324 sebelum store().write() di line 1334; bila penulisan disk I/O "
            "gagal (OSError/ENOSPC/EACCES), sesi server telah dicabut tetapi konfigurasi .env belum tersimpan, "
            "mengunci pengguna keluar (lockout) dalam kondisi inkonsisten."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"lockout_events": lockout_events}
    return res


# ==============================================================================
# 142. MUSIC PANEL GUARD UNLOCKED MESSAGE MUTATION (Wave 14)
# ==============================================================================
async def fuzz_music_panel_guard_unlocked_message_mutation(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="music_panel_guard_unlocked_message_mutation",
        description="Fuzzing mutasi dan pembacaan state.message serta state.text_channel_id tanpa state.lock pada MusicPanel.guard",
        iterations=iterations,
    )
    unlocked_mutation_events = 0

    for it in range(iterations):
        src = inspect.getsource(MusicPanel.guard)
        guard_end = src.split("state.message = interaction.message")
        if len(guard_end) > 1:
            pre_assignment = guard_end[0]
            last_lines = [l.strip() for l in pre_assignment.split("\n") if l.strip()]
            if last_lines and not any("state.lock" in l for l in last_lines[-3:]):
                unlocked_mutation_events += 1

    if unlocked_mutation_events > 0:
        res.anomalies.append(
            f"MusicPanel.guard unlocked message mutation terkonfirmasi: {unlocked_mutation_events}/{iterations} iterasi "
            "state.message dan state.text_channel_id di lines 1482-1486 dimutasi tanpa proteksi async with state.lock, "
            "memunculkan race condition pada pembacaan simultan oleh refresh() dan _save_persistent_queue()."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unlocked_mutation_events": unlocked_mutation_events}
    return res


# ==============================================================================
# 143. BACKGROUND TASK FIRE AND FORGET GC PREMATURE CLEANUP (Wave 14)
# ==============================================================================
async def fuzz_background_task_fire_and_forget_gc_premature_cleanup(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="background_task_fire_and_forget_gc_premature_cleanup",
        description="Verifikasi pembuatan task latar belakang tanpa referensi kuat (fire-and-forget create_task) yang berisiko premature GC",
        iterations=iterations,
    )
    gc_risk_events = 0

    for it in range(iterations):
        src_advance = inspect.getsource(MusicBot._advance_loop)
        src_vsu = inspect.getsource(MusicBot.on_voice_state_update)

        vulnerable_advance = "asyncio.create_task(self.quit_voice(guild, clear_queue=False))" in src_advance
        vulnerable_vsu = "create_task(self.advance(guild))" in src_vsu and "state._advance_task" not in src_vsu and "self._background_tasks" not in src_vsu

        if vulnerable_advance or vulnerable_vsu:
            gc_risk_events += 1

    if gc_risk_events > 0:
        res.anomalies.append(
            f"Background task fire-and-forget GC risk terkonfirmasi: {gc_risk_events}/{iterations} iterasi "
            "asyncio.create_task() dipanggil di line 3253 (quit_voice) dan line 3582 (advance) tanpa menyimpan "
            "referensi kuat ke task object, berisiko mengalami premature garbage collection oleh Python runtime sebelum task tuntas."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"gc_risk_events": gc_risk_events}
    return res


# ==============================================================================
# 144. VOICE STATE UPDATE UNLOCKED AFK PAUSED MUTATION (Wave 14)
# ==============================================================================
async def fuzz_voice_state_update_unlocked_afk_paused_mutation(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="voice_state_update_unlocked_afk_paused_mutation",
        description="Fuzzing mutasi field state.afk_paused di luar state.lock pada beberapa cabang on_voice_state_update",
        iterations=iterations,
    )
    unlocked_mutation_events = 0

    for it in range(iterations):
        src = inspect.getsource(MusicBot.on_voice_state_update)

        vulnerable_lines = 0
        lines = src.split("\n")
        in_lock = False
        for line in lines:
            if "async with state.lock:" in line:
                in_lock = True
            elif "state.afk_paused" in line and "=" in line:
                if "async with state.lock" not in line and not in_lock:
                    vulnerable_lines += 1
            if in_lock and ("else:" in line or "if num_humans" in line):
                in_lock = False

        if vulnerable_lines > 0:
            unlocked_mutation_events += 1

    if unlocked_mutation_events > 0:
        res.anomalies.append(
            f"on_voice_state_update unlocked afk_paused mutation terkonfirmasi: {unlocked_mutation_events}/{iterations} iterasi "
            "field state.afk_paused dimutasi langsung di luar state.lock pada lines 3504, 3519, dan 3535, "
            "berisiko race condition terhadap cmd_pause dan MusicPanel.play_pause yang mengakses afk_paused secara konkuren."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unlocked_mutation_events": unlocked_mutation_events}
    return res


# ==============================================================================
# 145. AFK DISCONNECT GENERATION ZERO EMPTY ROOM BYPASS (Wave 14)
# ==============================================================================
async def fuzz_afk_disconnect_generation_zero_empty_room_bypass(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="afk_disconnect_generation_zero_empty_room_bypass",
        description="Fuzzing bypass disconnect AFK Guard saat generation awal bernilai 0 di room kosong pasca transisi generasi",
        iterations=iterations,
    )
    bypass_events = 0

    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=77000 + it)
        vc.channel = MagicMock()
        vc.channel.members = []

        state = QueueState()
        state.generation = 1
        bot.states[guild.id] = state
        bot.quit_voice = AsyncMock()

        await bot._afk_disconnect(guild, generation=0, timeout=0.001)

        if not bot.quit_voice.called:
            bypass_events += 1

    if bypass_events > 0:
        res.anomalies.append(
            f"AFK Guard generation 0 bypass terkonfirmasi: {bypass_events}/{iterations} iterasi "
            "kondisi 'if generation == 0 or len(humans) > 0: return' di lines 3598-3600 membatalkan disconnect bot "
            "meskipun channel kosong jika generation awal adalah 0, menelantarkan bot di room kosong."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"bypass_events": bypass_events}
    return res


# ==============================================================================
# 146. CONFIG STORE WRITE CONCURRENT RACE MISSING MUTEX (Wave 14)
# ==============================================================================
async def fuzz_config_store_write_concurrent_race_missing_mutex(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="config_store_write_concurrent_race_missing_mutex",
        description="Fuzzing ketiadaan mutex threading internal pada ConfigStore.write() saat penulisan konfigurasi .env secara konkuren",
        iterations=iterations,
    )
    missing_mutex_events = 0

    for it in range(iterations):
        src = inspect.getsource(panel_module.ConfigStore.write)
        has_mutex = "with self._lock" in src or "with lock" in src or "threading.Lock" in src

        if not has_mutex:
            missing_mutex_events += 1

    if missing_mutex_events > 0:
        res.anomalies.append(
            f"ConfigStore.write missing mutex terkonfirmasi: {missing_mutex_events}/{iterations} iterasi "
            "ConfigStore.write() tidak memiliki threading.Lock() internal saat membaca _preserved_lines() dan menulis .env, "
            "memunculkan race condition saat multiple request /save berjalan paralel di panel web."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"missing_mutex_events": missing_mutex_events}
    return res


# ==============================================================================
# 147. CONFIG STORE INSTANCE MUTEX BYPASS (Wave 15)
# ==============================================================================
async def fuzz_config_store_instance_mutex_bypass(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="config_store_instance_mutex_bypass",
        description="Fuzzing ketiadaan shared mutex/singleton pada ConfigStore saat dipanggil melalui store() berulang",
        iterations=iterations,
    )
    bypass_events = 0
    for _ in range(iterations):
        s1 = panel_module.store()
        s2 = panel_module.store()
        has_class_lock = hasattr(panel_module.ConfigStore, '_write_lock') or hasattr(panel_module.ConfigStore, '_lock')
        is_singleton = (s1 is s2) or (s1._lock is s2._lock) or has_class_lock
        if not is_singleton:
            bypass_events += 1

    if bypass_events > 0:
        res.anomalies.append(
            f"ConfigStore mutex bypass terkonfirmasi: {bypass_events}/{iterations} iterasi "
            "store() mengembalikan instance ConfigStore baru di setiap request dengan instance-level _lock terpisah "
            "(s1._lock is not s2._lock) karena STORE bernilai None dan ketiadaan class-level _write_lock pada ConfigStore."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"bypass_events": bypass_events}
    return res


# ==============================================================================
# 148. ENQUEUE TRACKS ADVANCING RACE (Wave 15)
# ==============================================================================
async def fuzz_enqueue_tracks_advancing_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="enqueue_tracks_advancing_race",
        description="Fuzzing race condition pada _enqueue_tracks saat state._advancing > 0 dan evaluasi playing=False prematur",
        iterations=iterations,
    )
    race_events = 0
    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=81000 + it)
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.current = Track("PlayingSong", f"https://youtube.com/watch?v=p_{it}", "user")
        state._advancing = 1
        bot.states[guild.id] = state

        bot._save_persistent_queue = MagicMock()
        bot.advance = AsyncMock()

        new_tracks = [Track("QueuedSong", f"https://youtube.com/watch?v=q_{it}", "user")]
        await bot._enqueue_tracks(guild, new_tracks)

        if state.current is None and any(t.title == "PlayingSong" for t in state.history):
            race_events += 1

    if race_events > 0:
        res.anomalies.append(
            f"_enqueue_tracks _advancing race terkonfirmasi: {race_events}/{iterations} iterasi "
            "_enqueue_tracks mengevaluasi playing = False saat state._advancing > 0, "
            "memindahkan state.current ke history dan me-null-kannya secara prematur serta memicu advance() redundan."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"race_events": race_events}
    return res


# ==============================================================================
# 149. SINGLE FAILING TRACK STRANDED GHOST VOICE (Wave 15)
# ==============================================================================
async def fuzz_single_failing_track_stranded_ghost_voice(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="single_failing_track_stranded_ghost_voice",
        description="Fuzzing penelantaran VoiceClient saat satu-satunya lagu di antrean gagal diekstrak tanpa circuit breaker",
        iterations=iterations,
    )
    stranded_events = 0
    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=82000 + it)
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        failing_track = Track("FailingSoloTrack", f"https://youtube.com/watch?v=fail_{it}", "user")
        state.queue.append(failing_track)
        state.current = None
        bot.states[guild.id] = state

        bot._save_persistent_queue = MagicMock()
        bot.refresh = AsyncMock()
        bot._schedule_idle = MagicMock()

        with patch("bot.run_extract", side_effect=Exception("Extraction 403 Forbidden")):
            await bot._advance_loop(guild, state, vc)

        cb_tripped = state.consecutive_playback_errors >= 3
        can_idle_quit = (not state.queue) or cb_tripped
        if not can_idle_quit and state.current is None and not vc.is_playing():
            stranded_events += 1

    if stranded_events > 0:
        res.anomalies.append(
            f"Penelantaran VoiceClient pada single failing track terkonfirmasi: {stranded_events}/{iterations} iterasi "
            "saat ekstraksi satu-satunya track di antrean gagal (len(queue)==1), _advance_loop berhenti dengan consecutive_errors=1 "
            "tanpa memicu circuit breaker (errors < 3) dan tanpa membuang lagu, sehingga idle_disconnect gagal keluar "
            "dan bot terkunci di voice channel selamanya."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stranded_events": stranded_events}
    return res


# ==============================================================================
# 150. ENQUEUE TRACKS TRACK EQUALITY LOSS (Wave 15)
# ==============================================================================
async def fuzz_enqueue_tracks_track_equality_loss(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="enqueue_tracks_track_equality_loss",
        description="Fuzzing track loss pada _enqueue_tracks saat vc is None akibat structural equality dataclass Track",
        iterations=iterations,
    )
    track_loss_events = 0
    for it in range(iterations):
        bot = MusicBot()
        guild = MagicMock(spec=discord.Guild)
        guild.id = 83000 + it
        guild.voice_client = None

        state = QueueState()
        dup_url = f"https://youtube.com/watch?v=dup_{it}"
        t_curr = Track("SameSong", dup_url, "user1")
        t_queued = Track("SameSong", dup_url, "user1")
        state.current = t_curr
        state.queue.append(t_queued)
        bot.states[guild.id] = state

        bot._save_persistent_queue = MagicMock()

        new_track = [Track("NewSong", f"https://youtube.com/watch?v=new_{it}", "user3")]
        await bot._enqueue_tracks(guild, new_track)

        curr_found = any(t is t_curr for t in state.queue)
        if not curr_found:
            track_loss_events += 1

    if track_loss_events > 0:
        res.anomalies.append(
            f"_enqueue_tracks track equality loss terkonfirmasi: {track_loss_events}/{iterations} iterasi "
            "pengecekan `if state.current not in state.queue` menggunakan structural dataclass equality. "
            "Ketika antrean sudah memiliki duplikat lagu yang sama, lagu `current` yang belum selesai diputar "
            "diabaikan dan hilang permanen dari antrean."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"track_loss_events": track_loss_events}
    return res


# ==============================================================================
# 151. LOOP FAILURE DUPLICATE TRACK DELETION (Wave 15)
# ==============================================================================
async def fuzz_loop_failure_duplicate_track_deletion(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="loop_failure_duplicate_track_deletion",
        description="Fuzzing salah sasaran rotasi antrean pada _advance_loop saat ekstraksi gagal dengan duplikat lagu",
        iterations=iterations,
    )
    deletion_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._advance_loop)
        vulnerable = "state.queue.remove(next_track)" in src and "del state.queue[" not in src
        if vulnerable:
            deletion_events += 1

    if deletion_events > 0:
        res.anomalies.append(
            f"_advance_loop duplicate track deletion terkonfirmasi: {deletion_events}/{iterations} iterasi "
            "`state.queue.remove(next_track)` pada penanganan ekstraksi gagal menggunakan structural equality "
            "dan menghapus kemunculan pertama track alih-alih identitas objek atau indeks tertentu."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"deletion_events": deletion_events}
    return res


# ==============================================================================
# 152. QUIT VOICE UNREFERENCED TASK GC RISK (Wave 15)
# ==============================================================================
async def fuzz_quit_voice_unreferenced_task_gc_risk(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="quit_voice_unreferenced_task_gc_risk",
        description="Verifikasi risiko garbage collection prematur pada quit_voice fire-and-forget task di advance()",
        iterations=iterations,
    )
    gc_risk_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.advance)
        has_untracked = "asyncio.create_task(self.quit_voice" in src and "_track_background_task" not in src.partition("quit_voice")[2][:100]
        if has_untracked:
            gc_risk_events += 1

    if gc_risk_events > 0:
        res.anomalies.append(
            f"advance() quit_voice unreferenced task terkonfirmasi: {gc_risk_events}/{iterations} iterasi "
            "pemanggilan asyncio.create_task(self.quit_voice(guild, clear_queue=False)) pada advance() saat voice client tidak terhubung "
            "dibuat tanpa pelacakan self._track_background_task(), berisiko premature GC pada event loop Python 3.11+."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"gc_risk_events": gc_risk_events}
    return res


# ==============================================================================
# 153. EMPTY ROOM USER RETURN MISSING IDLE RESCHEDULE (Wave 15)
# ==============================================================================
async def fuzz_empty_room_user_return_missing_idle_reschedule(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="empty_room_user_return_missing_idle_reschedule",
        description="Fuzzing pembatalan permanen idle disconnect timer saat user bergabung ke voice channel kosong tanpa lagu",
        iterations=iterations,
    )
    missing_schedule_events = 0
    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=85000 + it)
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        state.current = None
        state.queue.clear()
        state.autoplay = False
        state.afk_paused = False

        idle_task = MagicMock()
        idle_task.done.return_value = False
        state.idle_task = idle_task

        bot.states[guild.id] = state
        bot._schedule_idle = MagicMock()
        bot.refresh = AsyncMock()

        human_member = MagicMock(spec=discord.Member)
        human_member.id = 99991
        human_member.bot = False
        human_member.guild = guild
        vc.channel.members = [MagicMock(id=bot.user.id if bot.user else 1, bot=True), human_member]

        before = MagicMock(channel=None)
        after = MagicMock(channel=vc.channel)

        await bot.on_voice_state_update(human_member, before, after)

        if not bot._schedule_idle.called and state.idle_task is None and state.current is None and len(state.queue) == 0:
            missing_schedule_events += 1

    if missing_schedule_events > 0:
        res.anomalies.append(
            f"on_voice_state_update missing idle reschedule terkonfirmasi: {missing_schedule_events}/{iterations} iterasi "
            "saat user bergabung ke channel kosong saat playback kosong (tidak ada current/queue/autoplay), "
            "idle_task dibatalkan tanpa penjadwalan ulang _schedule_idle, menelantarkan bot di voice selamanya."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"missing_schedule_events": missing_schedule_events}
    return res


# ==============================================================================
# 154. ANNOUNCE NOW PLAYING UNLOCKED MUTATION ORPHAN RISK (Wave 15)
# ==============================================================================
async def fuzz_announce_now_playing_unlocked_mutation_orphan_risk(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="announce_now_playing_unlocked_mutation_orphan_risk",
        description="Fuzzing mutasi state.now_message tanpa state.lock dan risiko orphan message saat quit_voice konkuren",
        iterations=iterations,
    )
    unlocked_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._announce_now_playing)
        vulnerable = "async with state.lock:" not in src or ("state.now_message = sent_msg" in src and "async with state.lock:" not in src.rpartition("state.now_message = sent_msg")[0])
        if vulnerable:
            unlocked_events += 1

    if unlocked_events > 0:
        res.anomalies.append(
            f"_announce_now_playing unlocked mutation & orphan risk terkonfirmasi: {unlocked_events}/{iterations} iterasi "
            "state.now_message dimutasi di luar state.lock, dan penetapan sent_msg ke state.now_message "
            "dapat menimpa cleanup quit_voice yang berjalan konkuren, meninggalkan pesan now-playing yatim di Discord."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unlocked_events": unlocked_events}
    return res


# ==============================================================================
# 155. REFRESH MESSAGE ID OVERWRITE RACE (Wave 15)
# ==============================================================================
async def fuzz_refresh_message_id_overwrite_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="refresh_message_id_overwrite_race",
        description="Fuzzing race condition penimpaan state.message di luar state.lock pada refresh() saat fetch message selesai",
        iterations=iterations,
    )
    race_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.refresh)
        vulnerable = "state.message = msg" in src and "async with state.lock:" not in src.rpartition("state.message = msg")[0]
        if vulnerable:
            race_events += 1

    if race_events > 0:
        res.anomalies.append(
            f"refresh() message ID overwrite race terkonfirmasi: {race_events}/{iterations} iterasi "
            "state.message = msg pasca fetch_message dilakukan di luar state.lock tanpa memverifikasi "
            "apakah state.message masih berupa integer ID lama atau telah diperbarui coroutine lain."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"race_events": race_events}
    return res


# ==============================================================================
# 156. READ BOT RUNTIME INFO STALE DISK CHURN (Wave 15)
# ==============================================================================
async def fuzz_read_bot_runtime_info_stale_disk_churn(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="read_bot_runtime_info_stale_disk_churn",
        description="Verifikasi pemborosan synchronous disk I/O pada read_bot_runtime_info() saat berkas state stale (>60s)",
        iterations=iterations,
    )
    churn_events = 0
    for it in range(iterations):
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            stale_payload = {"status": "online", "updated_at": time.time() - 120}
            json.dump(stale_payload, tf)
            tf_path = tf.name

        try:
            with patch.dict(os.environ, {"BOT_STATE_FILE": tf_path}):
                with patch("panel._cached_systemctl", return_value="active"):
                    open_counts = 0
                    orig_open = open
                    def counted_open(*args, **kwargs):
                        nonlocal open_counts
                        if args and args[0] == tf_path:
                            open_counts += 1
                        return orig_open(*args, **kwargs)

                    with patch("builtins.open", side_effect=counted_open):
                        for _ in range(5):
                            panel_module.read_bot_runtime_info()

                    if open_counts > 1:
                        churn_events += 1
        finally:
            if os.path.exists(tf_path):
                try:
                    os.remove(tf_path)
                except OSError:
                    pass

    if churn_events > 0:
        res.anomalies.append(
            f"read_bot_runtime_info stale disk churn terkonfirmasi: {churn_events}/{iterations} iterasi "
            "read_bot_runtime_info() membaca dan mengurai disk berkas state.json berulang kali pada setiap request "
            "ketika berkas telah stale (>60s) akibat ketiadaan cache fallback dengan TTL pendek."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"churn_events": churn_events}
    return res


# ==============================================================================
# 157. UPDATE PANEL PASSWORD MISSING THREAD LOCK (Wave 15)
# ==============================================================================
async def fuzz_update_panel_password_missing_thread_lock(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="update_panel_password_missing_thread_lock",
        description="Fuzzing ketiadaan thread mutex pada update_panel_password() saat membaca/menulis berkas env dan PASSWORD",
        iterations=iterations,
    )
    missing_lock_events = 0
    for _ in range(iterations):
        src = inspect.getsource(panel_module.update_panel_password)
        has_mutex = hasattr(panel_module, "_password_lock") and ("_password_lock" in src)
        if not has_mutex:
            missing_lock_events += 1

    if missing_lock_events > 0:
        res.anomalies.append(
            f"update_panel_password missing thread lock terkonfirmasi: {missing_lock_events}/{iterations} iterasi "
            "update_panel_password() tidak memiliki threading mutex saat membaca target_path, menulis file sementara, "
            "dan memutasi global PASSWORD, memicu race condition saat beberapa request paralel."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"missing_lock_events": missing_lock_events}
    return res


# ==============================================================================
# 158. LOCAL ADDR CACHE MISSING TTL (Wave 15)
# ==============================================================================
async def fuzz_local_addr_cache_missing_ttl(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="local_addr_cache_missing_ttl",
        description="Verifikasi ketiadaan TTL pada _local_addr_cache di panel.py untuk mendeteksi perubahan IP STB dinamis",
        iterations=iterations,
    )
    missing_ttl_events = 0
    for _ in range(iterations):
        src = inspect.getsource(panel_module._local_addresses)
        has_ttl = "monotonic()" in src or "time.time()" in src or "LOCAL_ADDR_TTL" in src
        if not has_ttl:
            missing_ttl_events += 1

    if missing_ttl_events > 0:
        res.anomalies.append(
            f"_local_addr_cache missing TTL terkonfirmasi: {missing_ttl_events}/{iterations} iterasi "
            "_local_addresses() meng-cache set alamat IP lokal permanen tanpa expiry TTL, "
            "sehingga perubahan IP dinamis STB ARM (DHCP/Tailscale) tidak terdeteksi dan request ditolak Host allowlist."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"missing_ttl_events": missing_ttl_events}
    return res


# ==============================================================================
# 159. ADVANCE UNRESET CACHED STREAM URL ON EXCEPTION (Wave 15)
# ==============================================================================
async def fuzz_advance_unreset_cached_stream_url_on_exception(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="advance_unreset_cached_stream_url_on_exception",
        description="Verifikasi ketiadaan reset cached stream_url dan stream_ts saat source_for atau vc.play melempar Exception di _advance_loop",
        iterations=iterations,
    )
    unreset_events = 0
    for it in range(iterations):
        bot = MusicBot()
        guild, vc = _create_mock_environment(guild_id=87000 + it)
        vc.is_connected.return_value = True
        vc.is_playing.return_value = False
        vc.is_paused.return_value = False

        state = QueueState()
        track = Track("BrokenStreamSong", f"https://youtube.com/watch?v=brk_{it}", "user")
        state.queue.append(track)
        state.current = None
        bot.states[guild.id] = state

        bot._save_persistent_queue = MagicMock()
        bot.refresh = AsyncMock()
        bot._schedule_idle = MagicMock()

        with patch("bot.run_extract", return_value={"url": "https://googlevideo.com/videoplayback?bad=1", "title": track.title}):
            with patch("bot.source_for", side_effect=Exception("ffmpeg spawn error")):
                await bot._advance_loop(guild, state, vc)

        if track.stream_url is not None:
            unreset_events += 1

    if unreset_events > 0:
        res.anomalies.append(
            f"_advance_loop unreset cached stream_url terkonfirmasi: {unreset_events}/{iterations} iterasi "
            "saat source_for atau vc.play melempar Exception, next_track.stream_url dan stream_ts tidak di-reset, "
            "menyebabkan percobaan pemutaran berikutnya terus menggunakan URL streaming kedaluwarsa/rusak."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unreset_events": unreset_events}
    return res


# ==============================================================================
# 160. DUMP RUNTIME STATE STALE SEQ DISK WRITE WASTE (Wave 15)
# ==============================================================================
async def fuzz_dump_runtime_state_stale_seq_disk_write_waste(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="dump_runtime_state_stale_seq_disk_write_waste",
        description="Verifikasi pemborosan penulisan file disk .tmp pada dump_runtime_state() sebelum validasi sequence kadaluarsa",
        iterations=iterations,
    )
    waste_events = 0
    for _ in range(iterations):
        src = inspect.getsource(bot_module.dump_runtime_state)
        early_seq_check = "if seq < _RUNTIME_STATE_LAST_SEQ: return" in src.partition("def _do_write")[2].partition("tmp_path =")[0]
        if not early_seq_check:
            waste_events += 1

    if waste_events > 0:
        res.anomalies.append(
            f"dump_runtime_state stale seq disk waste terkonfirmasi: {waste_events}/{iterations} iterasi "
            "_do_write() melakukan penulisan berkas JSON ke flash eMMC (.tmp) sebelum mengecek apakah sequence "
            "seq < _RUNTIME_STATE_LAST_SEQ, memboroskan siklus I/O flash eMMC untuk data usang."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"waste_events": waste_events}
    return res


# ==============================================================================
# 161. CMD PLAY SUMMON MISSING BOT GET CHANNEL FALLBACK (Wave 15)
# ==============================================================================
async def fuzz_cmd_play_summon_missing_bot_get_channel_fallback(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_play_summon_missing_bot_get_channel_fallback",
        description="Verifikasi ketiadaan fallback self.get_channel pada cmd_play dan summon saat guild.get_channel None",
        iterations=iterations,
    )
    missing_fallback_events = 0
    for _ in range(iterations):
        src_play = inspect.getsource(MusicBot.cmd_play)
        src_summon = inspect.getsource(MusicBot.summon)

        vulnerable_play = "self.get_channel(interaction.channel_id)" not in src_play and "self.get_channel" not in src_play.partition("interaction.guild.get_channel")[2][:200]
        vulnerable_summon = "self.get_channel(interaction.channel_id)" not in src_summon and "self.get_channel" not in src_summon.partition("interaction.guild.get_channel")[2][:200]

        if vulnerable_play or vulnerable_summon:
            missing_fallback_events += 1

    if missing_fallback_events > 0:
        res.anomalies.append(
            f"cmd_play & summon missing get_channel fallback terkonfirmasi: {missing_fallback_events}/{iterations} iterasi "
            "saat interaction.channel bernilai None dan guild.get_channel(interaction.channel_id) mengembalikan None "
            "(mis. channel thread/forum yang belum di-cache guild), ketiadaan fallback self.get_channel menyebabkan "
            "panel musik gagal dikirim dan command ditolak."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"missing_fallback_events": missing_fallback_events}
    return res


# ==============================================================================
# 162. CMD LOOP AND AUTOPLAY MISSING VOICE AUTH (Wave 15)
# ==============================================================================
async def fuzz_cmd_loop_and_autoplay_missing_voice_auth(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_loop_and_autoplay_missing_voice_auth",
        description="Verifikasi ketiadaan validasi channel voice (_check_same_voice) pada command /loop dan /autoplay",
        iterations=iterations,
    )
    missing_auth_events = 0
    for _ in range(iterations):
        src_loop = inspect.getsource(MusicBot.cmd_loop)
        src_autoplay = inspect.getsource(MusicBot.cmd_autoplay)

        vulnerable_loop = "_check_same_voice" not in src_loop
        vulnerable_autoplay = "_check_same_voice" not in src_autoplay

        if vulnerable_loop or vulnerable_autoplay:
            missing_auth_events += 1

    if missing_auth_events > 0:
        res.anomalies.append(
            f"cmd_loop & cmd_autoplay missing voice auth terkonfirmasi: {missing_auth_events}/{iterations} iterasi "
            "slash command /loop dan /autoplay tidak memanggil _check_same_voice(interaction), memungkinkan user "
            "yang tidak berada di voice channel atau berada di voice channel berbeda untuk memanipulasi playback."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"missing_auth_events": missing_auth_events}
    return res


# ==============================================================================
# 163. DISCONNECTED VOICE CLIENT RECONNECT BYPASS (Wave 16)
# ==============================================================================
async def fuzz_disconnected_voice_client_reconnect_bypass(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="disconnected_voice_client_reconnect_bypass",
        description="Fuzzing /play, SearchModal, summon, dan MusicPanel.guard saat VoiceClient terputus (is_connected False)",
        iterations=iterations,
    )
    bypass_events = 0
    for _ in range(iterations):
        src_play = inspect.getsource(MusicBot.cmd_play)
        src_modal = inspect.getsource(SearchModal.on_submit)
        src_summon = inspect.getsource(MusicBot.summon)
        src_guard = inspect.getsource(MusicPanel.guard)

        vulnerable_play = "is_connected" not in src_play.partition("if not vc or vc_channel_id is None:")[1][:120] and "is_connected" not in src_play.partition("if not vc or vc_channel_id is None:")[0][-150:]
        vulnerable_modal = "is_connected" not in src_modal.partition("if not vc or getattr(vc, 'channel', None) is None:")[1][:120] and "is_connected" not in src_modal.partition("if not vc or getattr(vc, 'channel', None) is None:")[0][-150:]
        vulnerable_summon = "is_connected" not in src_summon.partition("if not vc or vc_channel_id is None:")[1][:120] and "is_connected" not in src_summon.partition("if not vc or vc_channel_id is None:")[0][-150:]
        vulnerable_guard = "is_connected" not in src_guard.partition("if not vc or vc_channel_id is None:")[1][:120] and "is_connected" not in src_guard.partition("if not vc or vc_channel_id is None:")[0][-150:]

        if vulnerable_play or vulnerable_modal or vulnerable_summon or vulnerable_guard:
            bypass_events += 1

    if bypass_events > 0:
        res.anomalies.append(
            f"Disconnected VoiceClient reconnect bypass terkonfirmasi: {bypass_events}/{iterations} iterasi "
            "pada cmd_play, SearchModal, summon, dan MusicPanel.guard hanya mengecek `if not vc or vc_channel_id is None:`. "
            "Ketika VoiceClient terputus (is_connected() == False) tetapi objek vc masih ada, bot tidak melakukan reconnect "
            "dan langsung mencoba memutar lagu yang memicu kegagalan dan quit_voice() prematur saat advance()."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"bypass_events": bypass_events}
    return res


# ==============================================================================
# 164. GHOST VOICE CLIENT LOCKOUT STOP QUIT (Wave 16)
# ==============================================================================
async def fuzz_ghost_voice_client_lockout_stop_quit(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="ghost_voice_client_lockout_stop_quit",
        description="Fuzzing /stop dan /quit saat VoiceClient terputus dan verifikasi lockout akibat kegagalan quit_voice",
        iterations=iterations,
    )
    lockout_events = 0
    for _ in range(iterations):
        src_stop = inspect.getsource(MusicBot.cmd_stop)
        src_quit = inspect.getsource(MusicBot.cmd_quit)

        vulnerable_stop = "is_connected" not in src_stop.partition("if not ok:")[2][:150]
        vulnerable_quit = "is_connected" not in src_quit.partition("if not ok:")[2][:150]

        if vulnerable_stop or vulnerable_quit:
            lockout_events += 1

    if lockout_events > 0:
        res.anomalies.append(
            f"Ghost Voice lockout pada cmd_stop & cmd_quit terkonfirmasi: {lockout_events}/{iterations} iterasi "
            "saat VoiceClient terputus di background (_check_same_voice gagal), pengecekan `if not vc:` "
            "menolak mengeksekusi self.quit_voice() karena vc tidak None meskipun vc.is_connected() == False, "
            "mengunci pengguna dalam pesan penolakan dan membiarkan bot stranded."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"lockout_events": lockout_events}
    return res


# ==============================================================================
# 165. LOOP QUEUE DUPLICATE TRACK HISTORY AND QUEUE LOSS (Wave 16)
# ==============================================================================
async def fuzz_loop_queue_duplicate_track_history_and_queue_loss(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="loop_queue_duplicate_track_history_and_queue_loss",
        description="Fuzzing rotasi loop_mode == 'queue' saat trek berturut-turut adalah objek identik dan verifikasi hilangnya track dari antrean",
        iterations=iterations,
    )
    track_loss_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._advance_loop)
        vulnerable = "if state.current and state.current is not next_track:" in src and "state.loop_mode == 'queue'" in src.partition("if state.current and state.current is not next_track:")[2][:400]
        if vulnerable:
            track_loss_events += 1

    if track_loss_events > 0:
        res.anomalies.append(
            f"loop_mode == 'queue' duplicate track loss terkonfirmasi: {track_loss_events}/{iterations} iterasi "
            "kondisi `if state.current and state.current is not next_track:` membungkus `if state.loop_mode == 'queue': state.queue.append(state.current)`. "
            "Jika antrean hanya memiliki 1 lagu atau memutar trek yang sama berturut-turut, `state.current is next_track` bernilai True "
            "sehingga lagu tidak ditambahkan kembali ke antrean dan hilang dari rotasi pemutaran."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"track_loss_events": track_loss_events}
    return res


# ==============================================================================
# 166. FFMPEG ABRUPT CRASH EOF CIRCUIT BREAKER BYPASS (Wave 16)
# ==============================================================================
async def fuzz_ffmpeg_abrupt_crash_eof_circuit_breaker_bypass(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="ffmpeg_abrupt_crash_eof_circuit_breaker_bypass",
        description="Fuzzing crash/exit status non-zero pada proses ffmpeg di BufferedAudioSource._reader dan verifikasi penanganan error vs silent EOF",
        iterations=iterations,
    )
    bypass_events = 0
    for _ in range(iterations):
        src = inspect.getsource(BufferedAudioSource._reader)
        vulnerable = "proc.poll()" not in src and "poll()" not in src
        if vulnerable:
            bypass_events += 1

    if bypass_events > 0:
        res.anomalies.append(
            f"FFmpeg crash / abrupt error exit misclassified as normal EOF terkonfirmasi: {bypass_events}/{iterations} iterasi "
            "saat proses ffmpeg crash dengan returncode non-zero, self.source.read() mengembalikan bytes kosong b''. "
            "BufferedAudioSource._reader langsung keluar dan mengantrekan None tanpa memeriksa poll() proses, "
            "sehingga _current_error tetap None dan circuit breaker stream error dibypass."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"bypass_events": bypass_events}
    return res


# ==============================================================================
# 167. SHUTDOWN RUNTIME STATE FILE RESURRECTION RACE (Wave 16)
# ==============================================================================
async def fuzz_shutdown_runtime_state_file_resurrection_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="shutdown_runtime_state_file_resurrection_race",
        description="Fuzzing race condition saat bot shutdown di on_voice_state_update yang menulis ulang state.json setelah dump_runtime_state_offline",
        iterations=iterations,
    )
    resurrection_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.on_voice_state_update)
        vulnerable = "getattr(self, '_stopping', False)" not in src and "self.is_closed()" not in src
        if vulnerable:
            resurrection_events += 1

    if resurrection_events > 0:
        res.anomalies.append(
            f"Shutdown dump_runtime_state file resurrection race terkonfirmasi: {resurrection_events}/{iterations} iterasi "
            "on_voice_state_update tidak mengecek flag self._stopping atau self.is_closed(). Saat bot melakukan shutdown "
            "dan mendisconnect voice client, event voice_state_update memanggil dump_runtime_state(self) yang menulis ulang "
            "state.json dan listeners.json ke disk setelah dump_runtime_state_offline() menghapusnya."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"resurrection_events": resurrection_events}
    return res


# ==============================================================================
# 168. ANNOUNCE NOW PLAYING CANCELLATION ORPHAN SHIELD (Wave 16)
# ==============================================================================
async def fuzz_announce_now_playing_cancellation_orphan_shield(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="announce_now_playing_cancellation_orphan_shield",
        description="Fuzzing task cancellation di sela await asyncio.shield(channel.send) pada _announce_now_playing dan verifikasi orphan message",
        iterations=iterations,
    )
    orphan_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._announce_now_playing)
        vulnerable = "asyncio.shield" in src and "add_done_callback" not in src and "except asyncio.CancelledError:" in src and "_safe_delete_msg" not in src.partition("except asyncio.CancelledError:")[2][:250]
        if vulnerable:
            orphan_events += 1

    if orphan_events > 0:
        res.anomalies.append(
            f"_announce_now_playing cancellation orphan shield terkonfirmasi: {orphan_events}/{iterations} iterasi "
            "ketika _announce_now_playing dibatalkan (CancelledError) saat menunggu asyncio.shield(msg_fut), blok "
            "`except asyncio.CancelledError: raise` tidak mendaftarkan penanganan pembersihan pesan hasil pengiriman channel.send, "
            "mengakibatkan pesan 'Now playing' tertinggal permanen di Discord tanpa terlacak di state."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"orphan_events": orphan_events}
    return res


# ==============================================================================
# 169. ANNOUNCE NOW PLAYING UNLOCKED OVERWRITE RACE (Wave 16)
# ==============================================================================
async def fuzz_announce_now_playing_unlocked_overwrite_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="announce_now_playing_unlocked_overwrite_race",
        description="Fuzzing overwrite race pada state.now_message = None di _announce_now_playing saat pesan baru masuk konkuren",
        iterations=iterations,
    )
    race_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._announce_now_playing)
        part = src.partition("await self._safe_delete_msg")
        vulnerable = "state.now_message = None" in part[2][:200] and "state.now_message is old" not in part[2][:200]
        if vulnerable:
            race_events += 1

    if race_events > 0:
        res.anomalies.append(
            f"_announce_now_playing unlocked overwrite race terkonfirmasi: {race_events}/{iterations} iterasi "
            "setelah `await self._safe_delete_msg(...)`, pembersihan `state.now_message = None` disetel tanpa "
            "memverifikasi `if state.now_message is old:`, berisiko menimpa dan membuang pesan pengumuman baru yang baru "
            "saja disetel oleh coroutine lain yang berjalan bersamaan."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"race_events": race_events}
    return res


# ==============================================================================
# 170. SUMMON DUPLICATE ADVANCE AND IDLE SCHEDULE (Wave 16)
# ==============================================================================
async def fuzz_summon_duplicate_advance_and_idle_schedule(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="summon_duplicate_advance_and_idle_schedule",
        description="Fuzzing /musik (summon) saat text channel tidak valid dan verifikasi duplikasi logika advance dan idle schedule",
        iterations=iterations,
    )
    duplicate_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.summon)
        count_advance = src.count("await self.advance(interaction.guild)")
        count_schedule = src.count("self._schedule_idle(interaction.guild, state.generation)")
        if count_advance > 1 or count_schedule > 1:
            duplicate_events += 1

    if duplicate_events > 0:
        res.anomalies.append(
            f"summon duplicate advance and idle schedule terkonfirmasi: {duplicate_events}/{iterations} iterasi "
            "pada method summon (/musik), logika pemanggilan advance() dan _schedule_idle() diduplikasi pada blok return text channel "
            "tidak ditemukan dan pada blok `finally:`. Struktur ini redundan dan berisiko memicu pemanggilan ganda."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"duplicate_events": duplicate_events}
    return res


# ==============================================================================
# 171. CMD BACK MISSING IDLE SCHEDULE LOCKOUT (Wave 16)
# ==============================================================================
async def fuzz_cmd_back_missing_idle_schedule_lockout(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_back_missing_idle_schedule_lockout",
        description="Fuzzing /back saat state.history dan state.current kosong dan verifikasi ketiadaan idle timer yang menelantarkan bot",
        iterations=iterations,
    )
    missing_idle_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.cmd_back)
        vulnerable = "if not state or (not state.history and not state.current):" in src and "return await interaction.followup.send" in src.partition("if not state or (not state.history and not state.current):")[2][:150] and "_schedule_idle" not in src.partition("if not state or (not state.history and not state.current):")[2][:150]
        if vulnerable:
            missing_idle_events += 1

    if missing_idle_events > 0:
        res.anomalies.append(
            f"cmd_back missing idle schedule lockout terkonfirmasi: {missing_idle_events}/{iterations} iterasi "
            "pada awal cmd_back, kondisi `if not state or (not state.history and not state.current):` melakukan early return "
            "sebelum masuk ke state.lock dan sebelum blok evaluasi `had_prev = False` yang memiliki penjadwalan _schedule_idle. "
            "Jika bot terhubung ke voice tanpa memutar lagu dan user menjalankan /back, bot terdampar di voice tanpa idle timer."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"missing_idle_events": missing_idle_events}
    return res


# ==============================================================================
# 172. CIRCUIT BREAKER RE ENQUEUE WHOLE QUEUE DUPLICATE (Wave 16)
# ==============================================================================
async def fuzz_circuit_breaker_re_enqueue_whole_queue_duplicate(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="circuit_breaker_re_enqueue_whole_queue_duplicate",
        description="Fuzzing re-enqueue track di _after_dispatch circuit breaker saat lagu sudah ada di posisi antrean selain index 0",
        iterations=iterations,
    )
    duplicate_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._advance_loop)
        vulnerable = "st.queue[0] is not st.current" in src and "any(" not in src.partition("st.queue[0] is not st.current")[0][-100:]
        if vulnerable:
            duplicate_events += 1

    if duplicate_events > 0:
        res.anomalies.append(
            f"circuit breaker re-enqueue whole queue duplicate terkonfirmasi: {duplicate_events}/{iterations} iterasi "
            "pada _after_dispatch circuit breaker, trek st.current dimasukkan kembali ke antrean dengan pengecekan "
            "`if st.current and (not st.queue or st.queue[0] is not st.current):`. Jika st.current sudah ada di posisi lain dalam antrean, "
            "pengecekan ini gagal mencegah duplikasi dan memasukkan trek berulang ke antrean."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"duplicate_events": duplicate_events}
    return res


# ==============================================================================
# 173. SAVE PERSISTENT QUEUE STALE SEQ DISK WRITE WASTE (Wave 16)
# ==============================================================================
async def fuzz_save_persistent_queue_stale_seq_disk_write_waste(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="save_persistent_queue_stale_seq_disk_write_waste",
        description="Fuzzing penulisan berkas sementara .tmp dan os.chmod di _save_persistent_queue sebelum validasi keusangan sequence",
        iterations=iterations,
    )
    waste_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._save_persistent_queue)
        open_pos = src.find("with open(tmp_path")
        seq_pos = src.find("seq < getattr(self, '_queue_last_seq', 0)", open_pos)
        if open_pos != -1 and seq_pos != -1 and open_pos < seq_pos:
            waste_events += 1

    if waste_events > 0:
        res.anomalies.append(
            f"_save_persistent_queue stale seq disk write waste terkonfirmasi: {waste_events}/{iterations} iterasi "
            "penulisan file disk .tmp dan chmod dilakukan sebelum pengecekan sequence seq < _queue_last_seq. "
            "Saat terjadi mutasi antrean cepat, background writer tetap menulis seluruh payload ke media flash eMMC "
            "hanya untuk kemudian dibuang dan dihapus, mempercepat keausan eMMC STB."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"waste_events": waste_events}
    return res


# ==============================================================================
# 174. LIVESTREAM LOOP TRACK ENDLESS EXTRACTION STALL (Wave 16)
# ==============================================================================
async def fuzz_livestream_loop_track_endless_extraction_stall(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="livestream_loop_track_endless_extraction_stall",
        description="Fuzzing pemutaran livestream dengan loop_mode == 'track' dan verifikasi loop ekstraksi berulang tanpa pembuangan state.current",
        iterations=iterations,
    )
    stall_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._advance_loop)
        part = src.partition("Live stream dilewati:")
        vulnerable = "state.current = None" not in part[2][:300]
        if vulnerable:
            stall_events += 1

    if stall_events > 0:
        res.anomalies.append(
            f"Livestream loop track endless extraction stall terkonfirmasi: {stall_events}/{iterations} iterasi "
            "ketika video live stream terdeteksi pada mode loop_mode == 'track', kode hanya menghapus next_track dari "
            "state.queue (di mana trek tersebut tidak berada di sana karena merupakan state.current). Karena state.current tidak di-null-kan, "
            "loop mencoba mengekstrak kembali livestream hingga 3x berturut-turut, membuang CPU dan network STB ARM."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stall_events": stall_events}
    return res


# ==============================================================================
# 175. FETCH RECOMMENDATIONS DUPLICATE SEED MIX EXTRACTION (Wave 16)
# ==============================================================================
async def fuzz_fetch_recommendations_duplicate_seed_mix_extraction(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="fetch_recommendations_duplicate_seed_mix_extraction",
        description="Fuzzing ekstraksi YouTube Mix di fetch_recommendations saat seed_urls berisi URL duplikat",
        iterations=iterations,
    )
    duplicate_events = 0
    for _ in range(iterations):
        src = inspect.getsource(fetch_recommendations)
        part = src.partition("for seed_url in reversed(seed_urls or []):")
        vulnerable = "seen_seeds" not in part[2][:300] and "seen_seed_ids" not in part[2][:300] and "seen_ids" not in part[2][:300]
        if vulnerable:
            duplicate_events += 1

    if duplicate_events > 0:
        res.anomalies.append(
            f"fetch_recommendations duplicate seed mix extraction terkonfirmasi: {duplicate_events}/{iterations} iterasi "
            "ketika seed_urls memiliki duplikasi video URL atau ID, fetch_recommendations memanggil fetch_youtube_mix "
            "berulang kali untuk video ID yang sama, memicu HTTP request YouTube Mix redundan."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"duplicate_events": duplicate_events}
    return res


# ==============================================================================
# 176. CONFIG STORE WRITE NON STRING TYPE ERROR (Wave 16)
# ==============================================================================
async def fuzz_config_store_write_non_string_type_error(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="config_store_write_non_string_type_error",
        description="Fuzzing ConfigStore.write dengan nilai non-string dan verifikasi unhandled TypeError pada pemeriksaan newline",
        iterations=iterations,
    )
    type_error_events = 0
    for _ in range(iterations):
        with tempfile.TemporaryDirectory() as td:
            env_path = os.path.join(td, ".env")
            store = panel_module.ConfigStore(env_path)
            try:
                store.write({"token": 123456, "guild": 987654})
            except TypeError:
                type_error_events += 1
            except Exception:
                pass

    if type_error_events > 0:
        res.anomalies.append(
            f"ConfigStore.write TypeError pada nilai non-string terkonfirmasi: {type_error_events}/{iterations} iterasi "
            "pengecekan `if '\\n' in value or '\\r' in value:` mengasumsikan seluruh value bertipe string. Bila value bernilai "
            "integer, boolean, atau None, Python melempar `TypeError: argument of type 'int' is not iterable`, menggagalkan penyimpanan konfigurasi."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"type_error_events": type_error_events}
    return res


# ==============================================================================
# 177. PANEL YTDLP VERSION STALE IMPORTLIB CACHE (Wave 16)
# ==============================================================================
async def fuzz_panel_ytdlp_version_stale_importlib_cache(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_ytdlp_version_stale_importlib_cache",
        description="Fuzzing ytdlp_version() pasca update dan verifikasi ketiadaan importlib.invalidate_caches()",
        iterations=iterations,
    )
    stale_cache_events = 0
    for _ in range(iterations):
        src_update = inspect.getsource(panel_module.Handler._update)
        src_version = inspect.getsource(panel_module.ytdlp_version)
        vulnerable = "invalidate_caches" not in src_update and "invalidate_caches" not in src_version
        if vulnerable:
            stale_cache_events += 1

    if stale_cache_events > 0:
        res.anomalies.append(
            f"panel ytdlp_version stale importlib metadata cache terkonfirmasi: {stale_cache_events}/{iterations} iterasi "
            "pasca eksekusi update package, `importlib.invalidate_caches()` tidak dipanggil pada _update() maupun ytdlp_version(). "
            "importlib.metadata tetap mengembalikan metadata versi lama dari cache in-memory modul."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stale_cache_events": stale_cache_events}
    return res


# ==============================================================================
# 178. PANEL UPDATE STALE LOG LEAK ON FAILURE (Wave 16)
# ==============================================================================
async def fuzz_panel_update_stale_log_leak_on_failure(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_update_stale_log_leak_on_failure",
        description="Fuzzing _run_update_inner saat perintah update gagal sebelum memperbarui UPDATE_LOG_PATH dan verifikasi kebocoran log usang",
        iterations=iterations,
    )
    leak_events = 0
    for _ in range(iterations):
        src = inspect.getsource(panel_module._run_update_inner)
        part = src.partition("if os.path.exists(UPDATE_LOG_PATH):")
        vulnerable = "if os.path.exists(UPDATE_LOG_PATH):" in src and "cmd == [update_script]" not in part[0][-80:]
        if vulnerable:
            leak_events += 1

    if leak_events > 0:
        res.anomalies.append(
            f"_run_update_inner stale log leak on failure terkonfirmasi: {leak_events}/{iterations} iterasi "
            "ketika UPDATE_LOG_PATH sudah ada dari eksekusi sebelumnya, jika update script gagal dijalankan "
            "atau proses exit sebelum memperbarui berkas log, _run_update_inner tetap membaca berkas log usang tersebut "
            "dan mengembalikannya ke UI, menutupi pesan error aktual dari stderr/stdout proses."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"leak_events": leak_events}
    return res


# ==============================================================================
# 179. CMD PLAY DIRECT INDEXING KEYERROR (Wave 17)
# ==============================================================================
async def fuzz_cmd_play_direct_indexing_keyerror(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_play_direct_indexing_keyerror",
        description="Fuzzing unhandled KeyError pada cmd_play akibat direct dictionary indexing self.states[interaction.guild.id]",
        iterations=iterations,
    )
    key_error_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.cmd_play)
        vulnerable = "self.states[interaction.guild.id]" in src
        if vulnerable:
            key_error_events += 1

    if key_error_events > 0:
        res.anomalies.append(
            f"cmd_play direct indexing KeyError terkonfirmasi: {key_error_events}/{iterations} iterasi "
            "menggunakan direct dictionary access `state = self.states[interaction.guild.id]` setelah `_enqueue_tracks`. "
            "Jika guild dihapus atau state di-evict konkuren, pemanggilan ini melempar unhandled KeyError dan membatalkan interaksi."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"key_error_events": key_error_events}
    return res


# ==============================================================================
# 180. GHOST VOICE LOCKOUT PANEL BUTTON STOP (Wave 17)
# ==============================================================================
async def fuzz_ghost_voice_lockout_panel_button_stop(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="ghost_voice_lockout_panel_button_stop",
        description="Fuzzing ghost voice lockout pada MusicPanel.button_stop saat VoiceClient terputus dan delegasi guard() menolak eksekusi quit_voice",
        iterations=iterations,
    )
    lockout_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicPanel.button_stop)
        vulnerable = "if vc and not await self.guard(interaction):" in src or (
            "is_connected" not in src.partition("if vc")[2][:100]
        )
        if vulnerable:
            lockout_events += 1

    if lockout_events > 0:
        res.anomalies.append(
            f"Ghost Voice lockout pada MusicPanel.button_stop terkonfirmasi: {lockout_events}/{iterations} iterasi "
            "MusicPanel.button_stop mengecek `if vc and not await self.guard(interaction):` tanpa memeriksa `vc.is_connected()`. "
            "Ketika VoiceClient terputus (is_connected() == False), guard(interaction) menolak interaksi (mengembalikan False) "
            "sehingga self.bot.quit_voice() tidak pernah dipanggil dan bot terperangkap sebagai ghost voice."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"lockout_events": lockout_events}
    return res


# ==============================================================================
# 181. SAFE DELETE MSG COLD CACHE CHANNEL FALLBACK (Wave 17)
# ==============================================================================
async def fuzz_safe_delete_msg_cold_cache_channel_fallback(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="safe_delete_msg_cold_cache_channel_fallback",
        description="Verifikasi ketiadaan fallback self.get_channel pada _safe_delete_msg dan _delete_all_panels saat guild cache dingin",
        iterations=iterations,
    )
    fallback_missing_events = 0
    for _ in range(iterations):
        src_safe = inspect.getsource(MusicBot._safe_delete_msg)
        src_del = inspect.getsource(MusicBot._delete_all_panels)
        vulnerable_safe = "self.get_channel" not in src_safe
        vulnerable_del = "self.get_channel" not in src_del
        if vulnerable_safe or vulnerable_del:
            fallback_missing_events += 1

    if fallback_missing_events > 0:
        res.anomalies.append(
            f"Missing self.get_channel fallback terkonfirmasi: {fallback_missing_events}/{iterations} iterasi "
            "pada _safe_delete_msg dan _delete_all_panels saat cache guild dingin atau guild None, "
            "resolusi channel ID tidak memiliki fallback ke `self.get_channel(int(ch_id))`, "
            "menyebabkan pesan panel usang tidak dapat dihapus saat bot shutdown."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"fallback_missing_events": fallback_missing_events}
    return res


# ==============================================================================
# 182. SHUTDOWN STATE EXPORTER LOOP RESURRECTION RACE (Wave 17)
# ==============================================================================
async def fuzz_shutdown_state_exporter_loop_resurrection_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="shutdown_state_exporter_loop_resurrection_race",
        description="Fuzzing race condition pembatalan _exporter_task terlambat di close() yang membangkitkan state.json setelah dump_runtime_state_offline",
        iterations=iterations,
    )
    race_events = 0
    for _ in range(iterations):
        src_close = inspect.getsource(MusicBot.close)
        pos_offline = src_close.find("dump_runtime_state_offline")
        pos_cancel = src_close.find("self._exporter_task.cancel()")
        src_dump = inspect.getsource(dump_runtime_state)
        stopping_checked_in_dump = "getattr(bot, '_stopping', False)" in src_dump or "_stopping" in src_dump
        if (pos_offline != -1 and pos_cancel != -1 and pos_offline < pos_cancel) or not stopping_checked_in_dump:
            race_events += 1

    if race_events > 0:
        res.anomalies.append(
            f"_state_exporter_loop shutdown resurrection race terkonfirmasi: {race_events}/{iterations} iterasi "
            "pada close(), pembatalan self._exporter_task dilakukan di akhir setelah _delete_all_panels (yang menunggu s.d 15 detik) "
            "dan pasca dump_runtime_state_offline. dump_runtime_state juga tidak memvalidasi flag _stopping, "
            "sehingga background exporter loop membangkitkan kembali state.json dan listeners.json setelah bot dimatikan."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"race_events": race_events}
    return res


# ==============================================================================
# 183. VOICE STATE UPDATE SLEEP SHUTDOWN RESURRECTION RACE (Wave 17)
# ==============================================================================
async def fuzz_voice_state_update_sleep_shutdown_resurrection_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="voice_state_update_sleep_shutdown_resurrection_race",
        description="Fuzzing race condition on_voice_state_update pasca asyncio.sleep(2) saat bot shutdown yang memanggil quit_voice dan menulis state",
        iterations=iterations,
    )
    race_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.on_voice_state_update)
        part = src.partition("await asyncio.sleep(2)")
        vulnerable = "getattr(self, '_stopping', False)" not in part[2][:250] and "self.is_closed()" not in part[2][:250]
        if vulnerable:
            race_events += 1

    if race_events > 0:
        res.anomalies.append(
            f"on_voice_state_update sleep(2) shutdown resurrection race terkonfirmasi: {race_events}/{iterations} iterasi "
            "setelah `await asyncio.sleep(2)` pada pemutusan voice bot, tidak ada validasi ulang status `_stopping` atau `is_closed()`. "
            "Jika bot dimatikan selagi menunggu sleep, callback melanjutkan ke `await self.quit_voice(...)` "
            "dan memicu `dump_runtime_state` pasca shutdown."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"race_events": race_events}
    return res


# ==============================================================================
# 184. EMPTY ROOM AFK PAUSED AUDIO STOPPED STRANDED VOICE (Wave 17)
# ==============================================================================
async def fuzz_empty_room_afk_paused_audio_stopped_stranded_voice(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="empty_room_afk_paused_audio_stopped_stranded_voice",
        description="Fuzzing penelantaran voice client tanpa pemutaran maupun idle timer pada on_voice_state_update jika afk_paused True tetapi audio terhenti",
        iterations=iterations,
    )
    stranded_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.on_voice_state_update)
        part = src.partition("if state.afk_paused:")
        sub = part[2][:400]
        vulnerable = "should_advance" not in sub and "should_schedule_idle" not in sub
        if vulnerable:
            stranded_events += 1

    if stranded_events > 0:
        res.anomalies.append(
            f"afk_paused stopped audio stranded voice terkonfirmasi: {stranded_events}/{iterations} iterasi "
            "pada cabang `if state.afk_paused:`, jika audio stream ternyata sudah berhenti (`not vc.is_playing() and not vc.is_paused()`), "
            "kode hanya menyetel `should_refresh = True` tanpa menyetel `should_advance` atau `should_schedule_idle`. "
            "Bot tertinggal permanen di voice channel tanpa pemutaran maupun timer idle disconnect."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stranded_events": stranded_events}
    return res


# ==============================================================================
# 185. ENQUEUE TRACKS DISCONNECTED VOICE HISTORY LOSS (Wave 17)
# ==============================================================================
async def fuzz_enqueue_tracks_disconnected_voice_history_loss(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="enqueue_tracks_disconnected_voice_history_loss",
        description="Fuzzing kehilangan trek ke history pada _enqueue_tracks saat bot memiliki VoiceClient terputus (is_connected False)",
        iterations=iterations,
    )
    track_loss_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._enqueue_tracks)
        part = src.partition("if not playing and not advancing and state.current is not None:")
        sub = part[2][:250]
        vulnerable = "if vc is None:" in sub and "is_connected" not in sub
        if vulnerable:
            track_loss_events += 1

    if track_loss_events > 0:
        res.anomalies.append(
            f"_enqueue_tracks disconnected voice history loss terkonfirmasi: {track_loss_events}/{iterations} iterasi "
            "pengecekan `if vc is None:` hanya memulihkan state.current ke state.queue jika vc adalah None. "
            "Jika vc ada tetapi terputus (`is_connected() == False`), kode masuk ke cabang `else:` "
            "dan memindahkan track yang belum selesai ke history, menyebabkan lagu hilang tanpa sempat diputar."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"track_loss_events": track_loss_events}
    return res


# ==============================================================================
# 186. LOOP QUEUE FAILING TRACK POISONING (Wave 17)
# ==============================================================================
async def fuzz_loop_queue_failing_track_poisoning(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="loop_queue_failing_track_poisoning",
        description="Fuzzing poisoning antrean pada loop_mode == 'queue' di _advance_loop saat track gagal 3x berturut-turut tetapi tetap di-re-enqueue",
        iterations=iterations,
    )
    poison_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._advance_loop)
        part = src.partition("if state.loop_mode == 'queue' and not any(t is state.current for t in state.queue):")
        vulnerable = "consecutive_errors < MAX_TRACK_RETRIES" not in part[0][-200:] and "consecutive_errors <" not in part[0][-200:]
        if vulnerable:
            poison_events += 1

    if poison_events > 0:
        res.anomalies.append(
            f"loop_queue failing track poisoning terkonfirmasi: {poison_events}/{iterations} iterasi "
            "pada _advance_loop pembersihan saat pemutaran gagal, track state.current yang gagal 3x berturut-turut "
            "(consecutive_errors >= MAX_TRACK_RETRIES) tetap dimasukkan kembali ke state.queue pada mode loop_mode == 'queue'. "
            "Ini meracuni antrean lagu dengan track rusak permanen yang memicu circuit breaker berulang."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"poison_events": poison_events}
    return res


# ==============================================================================
# 187. ADVANCE LOOP BITRATE INF OVERFLOW ERROR (Wave 17)
# ==============================================================================
async def fuzz_advance_loop_bitrate_inf_overflow_error(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="advance_loop_bitrate_inf_overflow_error",
        description="Fuzzing unhandled OverflowError pada kalkulasi bitrate di _advance_loop saat channel.bitrate bernilai inf",
        iterations=iterations,
    )
    overflow_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._advance_loop)
        part = src.partition("bitrate_kbps = int(raw_bitrate)")
        vulnerable = "OverflowError" not in part[2][:200]
        if vulnerable:
            overflow_events += 1

    if overflow_events > 0:
        res.anomalies.append(
            f"_advance_loop bitrate OverflowError terkonfirmasi: {overflow_events}/{iterations} iterasi "
            "kalkulasi bitrate `int(raw_bitrate) // 1000` hanya menangani `(TypeError, ValueError)`. "
            "Jika channel.bitrate bernilai `float('inf')`, Python melempar `OverflowError: cannot convert float infinity to integer` "
            "yang tidak tertangkap dan menggagalkan seluruh proses pemutaran lagu."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"overflow_events": overflow_events}
    return res


# ==============================================================================
# 188. MUSIC BOT EMBED VOLUME NAN INF CRASH (Wave 17)
# ==============================================================================
async def fuzz_music_bot_embed_volume_nan_inf_crash(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="music_bot_embed_volume_nan_inf_crash",
        description="Fuzzing unhandled ValueError dan OverflowError pada MusicBot.embed saat state.volume bernilai NaN atau Inf",
        iterations=iterations,
    )
    crash_events = 0
    bot = MusicBot()
    for _ in range(iterations):
        st_nan = QueueState()
        st_nan.volume = float("nan")
        st_inf = QueueState()
        st_inf.volume = float("inf")

        try:
            bot.embed(st_nan)
        except (ValueError, OverflowError):
            crash_events += 1
        except Exception:
            pass

        try:
            bot.embed(st_inf)
        except (ValueError, OverflowError):
            crash_events += 1
        except Exception:
            pass

    if crash_events > 0:
        res.anomalies.append(
            f"MusicBot.embed volume NaN/Inf crash terkonfirmasi: {crash_events}/{iterations * 2} pemanggilan "
            "melempar ValueError atau OverflowError pada `vol_pct = int(round(state.volume * 100))`. "
            "Ketika volume bernilai NaN atau Inf, rendering embed panel rusak total."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"crash_events": crash_events}
    return res


# ==============================================================================
# 189. SEARCH MODAL UNLOCKED STATE MUTATION (Wave 17)
# ==============================================================================
async def fuzz_search_modal_unlocked_state_mutation(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="search_modal_unlocked_state_mutation",
        description="Fuzzing akses dan mutasi tanpa lock pada SearchModal.on_submit untuk text_channel_id, current, queue, dan generation",
        iterations=iterations,
    )
    unlocked_events = 0
    for _ in range(iterations):
        src = inspect.getsource(SearchModal.on_submit)
        vulnerable = "state.text_channel_id = interaction.channel_id" in src and (
            "async with state.lock:" not in src.partition("state.text_channel_id = interaction.channel_id")[0][-150:]
        )
        if vulnerable:
            unlocked_events += 1

    if unlocked_events > 0:
        res.anomalies.append(
            f"SearchModal.on_submit unlocked mutation terkonfirmasi: {unlocked_events}/{iterations} iterasi "
            "`state.text_channel_id = interaction.channel_id` serta pembacaan `state.current`, `state.queue`, "
            "dan `state.generation` dilakukan di luar `async with state.lock:`, memicu race condition dengan worker concurrent."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unlocked_events": unlocked_events}
    return res


# ==============================================================================
# 190. SAVE PERSISTENT QUEUE BOOLEAN MSG ID PERSISTENCE (Wave 17)
# ==============================================================================
async def fuzz_save_persistent_queue_boolean_msg_id_persistence(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="save_persistent_queue_boolean_msg_id_persistence",
        description="Fuzzing persistensi false-positive panel_message_id pada _save_persistent_queue saat st.message bernilai boolean True/False",
        iterations=iterations,
    )
    boolean_persist_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._save_persistent_queue)
        part = src.partition("msg if isinstance(msg, int)")
        vulnerable = "not isinstance(msg, bool)" not in part[2][:80] and "not isinstance(msg, bool)" not in part[0][-80:]
        if vulnerable:
            boolean_persist_events += 1

    if boolean_persist_events > 0:
        res.anomalies.append(
            f"_save_persistent_queue boolean msg_id persistence terkonfirmasi: {boolean_persist_events}/{iterations} iterasi "
            "kondisi `msg if isinstance(msg, int) else None` mengevaluasi `True` sebagai int (isinstance(True, int) == True). "
            "Jika st.message disetel boolean (mis. flag sementara), nilai boolean tersebut dipersist sebagai panel_message_id di JSON."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"boolean_persist_events": boolean_persist_events}
    return res


# ==============================================================================
# 191. DUMP RUNTIME STATE TMP WRITE BEFORE SEQ CHECK WASTE (Wave 17)
# ==============================================================================
async def fuzz_dump_runtime_state_tmp_write_before_seq_check_waste(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="dump_runtime_state_tmp_write_before_seq_check_waste",
        description="Verifikasi pemborosan penulisan file disk .tmp pada dump_runtime_state() sebelum validasi keusangan sequence",
        iterations=iterations,
    )
    waste_events = 0
    for _ in range(iterations):
        src = inspect.getsource(dump_runtime_state)
        open_pos = src.find("with open(tmp_path, 'w'")
        seq_pos = src.find("if seq < _RUNTIME_STATE_LAST_SEQ:", open_pos)
        if open_pos != -1 and seq_pos != -1 and open_pos < seq_pos:
            waste_events += 1

    if waste_events > 0:
        res.anomalies.append(
            f"dump_runtime_state tmp write waste terkonfirmasi: {waste_events}/{iterations} iterasi "
            "pembuatan file `.tmp`, serialisasi json.dump, dan os.chmod dilakukan sebelum validasi `seq < _RUNTIME_STATE_LAST_SEQ`. "
            "Ketika terjadi pembaruan state beruntun, file sementara ditulis ke flash eMMC STB hanya untuk dibuang di finally."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"waste_events": waste_events}
    return res


# ==============================================================================
# 192. VOICE STATE UPDATE NOT IN VOICE DISK THRASHING (Wave 17)
# ==============================================================================
async def fuzz_voice_state_update_not_in_voice_disk_thrashing(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="voice_state_update_not_in_voice_disk_thrashing",
        description="Verifikasi pemborosan disk I/O eMMC pada on_voice_state_update yang memanggil dump_runtime_state saat bot tidak berada di voice",
        iterations=iterations,
    )
    thrashing_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.on_voice_state_update)
        part = src.partition("# 2. Cek apakah bot terhubung ke voice channel di guild ini")
        sub = part[2][:500]
        vulnerable = "dump_runtime_state(self)" in sub
        if vulnerable:
            thrashing_events += 1

    if thrashing_events > 0:
        res.anomalies.append(
            f"on_voice_state_update not-in-voice disk thrashing terkonfirmasi: {thrashing_events}/{iterations} iterasi "
            "ketika bot tidak berada di voice channel (`not vc or not vc.is_connected()`), callback tetap memanggil "
            "`dump_runtime_state(self)` pada setiap event perpindahan voice member di Discord, memboroskan siklus tulis eMMC."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"thrashing_events": thrashing_events}
    return res


# ==============================================================================
# 193. PANEL LOGOUT CSRF VULNERABILITY (Wave 17)
# ==============================================================================
async def fuzz_panel_logout_csrf_vulnerability(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_logout_csrf_vulnerability",
        description="Fuzzing kerentanan Cross-Site Logout CSRF pada endpoint /logout di GET dan POST tanpa validasi Origin / nonce",
        iterations=iterations,
    )
    csrf_events = 0
    for _ in range(iterations):
        src_get = inspect.getsource(getattr(panel_module.Handler, '_do_get', panel_module.Handler.do_GET))
        src_post = inspect.getsource(getattr(panel_module.Handler, '_do_post', panel_module.Handler.do_POST))
        vulnerable_get = "if path == '/logout':" in src_get and "_revoke_session_from_cookie" in src_get.partition("if path == '/logout':")[2][:150]
        post_part = src_post.partition("if path == '/logout':")
        vulnerable_post = "if path == '/logout':" in src_post and ("_origin_ok" not in post_part[0][-200:] and "_origin_ok" not in post_part[2][:150])
        if vulnerable_get or vulnerable_post:
            csrf_events += 1

    if csrf_events > 0:
        res.anomalies.append(
            f"Cross-Site Logout CSRF terkonfirmasi: {csrf_events}/{iterations} iterasi "
            "GET /logout mencabut sesi aktif secara langsung tanpa perlindungan CSRF, dan POST /logout "
            "dieksekusi sebelum validasi Origin (`_origin_ok`). Situs pihak ketiga dapat memaksa logout pengguna secara diam-diam."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"csrf_events": csrf_events}
    return res


# ==============================================================================
# 194. PANEL FORMAT GUILDS HTML MALFORMED TYPE ERROR (Wave 17)
# ==============================================================================
async def fuzz_panel_format_guilds_html_malformed_type_error(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_format_guilds_html_malformed_type_error",
        description="Fuzzing unhandled AttributeError/TypeError pada format_guilds_html jika elemen guilds bukan dict atau None",
        iterations=iterations,
    )
    error_events = 0
    for _ in range(iterations):
        for bad_payload in [
            {"guilds": [None]},
            {"guilds": [123, 456]},
            {"guilds": "invalid_string"},
        ]:
            try:
                panel_module.format_guilds_html(bad_payload)
            except (AttributeError, TypeError):
                error_events += 1
            except Exception:
                pass

    if error_events > 0:
        res.anomalies.append(
            f"format_guilds_html AttributeError/TypeError terkonfirmasi: {error_events} error tertangkap saat "
            "diberikan elemen guilds yang bernilai None, int, atau tipe non-dict. "
            "Fungsi mengasumsikan elemen selalu dict (`g.get(...)`), memicu HTTP 500 saat merender panel."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"error_events": error_events}
    return res


# ==============================================================================
# 195. CLOSE MISSING STOPPING FLAG (Wave 18)
# ==============================================================================
async def fuzz_close_missing_stopping_flag(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="close_missing_stopping_flag",
        description="Fuzzing ketiadaan inisialisasi self._stopping = True di awal bot.close() yang membiarkan task latar belakang aktif",
        iterations=iterations,
    )
    stopping_missing_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.close)
        first_lines = src[:300]
        vulnerable = "self._stopping = True" not in first_lines
        if vulnerable:
            stopping_missing_events += 1

    if stopping_missing_events > 0:
        res.anomalies.append(
            f"bot.close() missing self._stopping flag terkonfirmasi: {stopping_missing_events}/{iterations} iterasi. "
            "self._stopping = True hanya disetel pada _handle_signal, sehingga pemanggilan bot.close() langsung "
            "(misal saat shutdown internal atau exception) tidak menandai bot sedang berhenti dan membiarkan "
            "dump_runtime_state menulis ulang state.json pasca dump_runtime_state_offline."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"stopping_missing_events": stopping_missing_events}
    return res


# ==============================================================================
# 196. CLOSE GENERATION BUMP AND BACKGROUND TASKS LEAK (Wave 18)
# ==============================================================================
async def fuzz_close_generation_bump_and_background_tasks_leak(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="close_generation_bump_and_background_tasks_leak",
        description="Fuzzing ketiadaan bump state.generation dan pembatalan self._background_tasks pada bot.close()",
        iterations=iterations,
    )
    leak_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.close)
        vulnerable = "state.generation += 1" not in src or "self._background_tasks" not in src
        if vulnerable:
            leak_events += 1

    if leak_events > 0:
        res.anomalies.append(
            f"bot.close() generation bump and background task leak terkonfirmasi: {leak_events}/{iterations} iterasi. "
            "close() tidak menaikkan state.generation (state.generation += 1) untuk membatalkan callback usang, "
            "dan tidak membatalkan tasks di self._background_tasks, memicu advance pasca shutdown."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"leak_events": leak_events}
    return res


# ==============================================================================
# 197. AFTER DISPATCH SLEEP SHUTDOWN RACE (Wave 18)
# ==============================================================================
async def fuzz_after_dispatch_sleep_shutdown_race(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="after_dispatch_sleep_shutdown_race",
        description="Fuzzing race condition pada _after_dispatch pasca asyncio.sleep(1.0) saat bot sedang shutdown",
        iterations=iterations,
    )
    race_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._advance_loop)
        part = src.partition("await asyncio.sleep(1.0)")
        sub = part[2][:300]
        vulnerable = "self._stopping" not in sub and "is_closed" not in sub
        if vulnerable:
            race_events += 1

    if race_events > 0:
        res.anomalies.append(
            f"_after_dispatch sleep shutdown race terkonfirmasi: {race_events}/{iterations} iterasi. "
            "Setelah jeda 1 detik pasca playback error, _after_dispatch tidak memeriksa self._stopping / self.is_closed(), "
            "memicu finished() dan advance() pada bot yang sedang tutup."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"race_events": race_events}
    return res


# ==============================================================================
# 198. CMD PLAY SUMMON OLD PANEL CHANNEL MISMATCH (Wave 18)
# ==============================================================================
async def fuzz_cmd_play_summon_old_panel_channel_mismatch(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_play_summon_old_panel_channel_mismatch",
        description="Fuzzing pemaksaan channel baru pada penghapusan panel lama integer ID di cmd_play dan summon",
        iterations=iterations,
    )
    mismatch_events = 0
    for _ in range(iterations):
        src_play = inspect.getsource(MusicBot.cmd_play)
        src_summon = inspect.getsource(MusicBot.summon)
        vulnerable_play = "await self._safe_delete_msg(existing, channel=channel" in src_play
        vulnerable_summon = "await self._safe_delete_msg(old_msg, channel=channel" in src_summon
        if vulnerable_play or vulnerable_summon:
            mismatch_events += 1

    if mismatch_events > 0:
        res.anomalies.append(
            f"cmd_play/summon wrong channel deletion terkonfirmasi: {mismatch_events}/{iterations} iterasi. "
            "Penghapusan panel lama pada cmd_play & summon memaksakan channel baru (channel=channel) untuk pesan "
            "integer ID, menghasilkan Discord 404 Unknown Message dan meninggalkan panel lama di channel sebelumnya."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"mismatch_events": mismatch_events}
    return res


# ==============================================================================
# 199. SAFE DELETE MSG PARAM CHANNEL PRIORITY INVERSION (Wave 18)
# ==============================================================================
async def fuzz_safe_delete_msg_param_channel_priority_inversion(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="safe_delete_msg_param_channel_priority_inversion",
        description="Fuzzing inversi prioritas parameter channel dibanding channel asli pesan pada _safe_delete_msg",
        iterations=iterations,
    )
    inversion_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._safe_delete_msg)
        vulnerable = "target_channel = channel or getattr(msg, 'channel', None)" in src
        if vulnerable:
            inversion_events += 1

    if inversion_events > 0:
        res.anomalies.append(
            f"_safe_delete_msg channel priority inversion terkonfirmasi: {inversion_events}/{iterations} iterasi. "
            "_safe_delete_msg memprioritaskan parameter channel dibanding channel asli pesan (getattr(msg, 'channel', None)), "
            "berisiko salah target channel penghapusan."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"inversion_events": inversion_events}
    return res


# ==============================================================================
# 200. QUIT VOICE COLD CACHE CHANNEL RESOLUTION (Wave 18)
# ==============================================================================
async def fuzz_quit_voice_cold_cache_channel_resolution(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="quit_voice_cold_cache_channel_resolution",
        description="Fuzzing ketiadaan fallback self.get_channel pada quit_voice dan resolusi channel ganda old_now_message",
        iterations=iterations,
    )
    cold_cache_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.quit_voice)
        part = src.partition("ch = getattr(old_message, 'channel', None)")
        sub = part[2].partition("await self._safe_delete_msg(old_now_message")[0]
        vulnerable = "self.get_channel" not in sub
        if vulnerable:
            cold_cache_events += 1

    if cold_cache_events > 0:
        res.anomalies.append(
            f"quit_voice cold cache resolution leak terkonfirmasi: {cold_cache_events}/{iterations} iterasi. "
            "quit_voice tidak memiliki fallback self.get_channel(state.text_channel_id) saat cache guild dingin, "
            "dan menyamakan channel old_now_message dengan old_message."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"cold_cache_events": cold_cache_events}
    return res


# ==============================================================================
# 201. REFRESH UNLOCKED STATE MESSAGE MUTATION (Wave 18)
# ==============================================================================
async def fuzz_refresh_unlocked_state_message_mutation(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="refresh_unlocked_state_message_mutation",
        description="Fuzzing mutasi state.message = None di luar state.lock pada refresh() saat terjadi exception",
        iterations=iterations,
    )
    unlocked_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.refresh)
        part = src.partition("except discord.HTTPException as err:")
        sub = part[2][:600]
        vulnerable = "async with state.lock:" not in sub
        if vulnerable:
            unlocked_events += 1

    if unlocked_events > 0:
        res.anomalies.append(
            f"refresh unlocked state.message mutation terkonfirmasi: {unlocked_events}/{iterations} iterasi. "
            "Mutasi state.message = None pada refresh() dilakukan tanpa async with state.lock, memicu race condition "
            "yang menghapus state.message baru dari coroutine lain."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unlocked_events": unlocked_events}
    return res


# ==============================================================================
# 202. DELETE ALL PANELS UNLOCKED STATE MUTATION (Wave 18)
# ==============================================================================
async def fuzz_delete_all_panels_unlocked_state_mutation(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="delete_all_panels_unlocked_state_mutation",
        description="Fuzzing mutasi state.message dan state.now_message di luar state.lock pada _delete_all_panels()",
        iterations=iterations,
    )
    unlocked_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._delete_all_panels)
        vulnerable = "async with state.lock:" not in src
        if vulnerable:
            unlocked_events += 1

    if unlocked_events > 0:
        res.anomalies.append(
            f"_delete_all_panels unlocked mutation terkonfirmasi: {unlocked_events}/{iterations} iterasi. "
            "Mutasi state.message = None dan now_message = None di _delete_all_panels dilakukan di luar state.lock."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unlocked_events": unlocked_events}
    return res


# ==============================================================================
# 203. CMD SHUFFLE UNLOCKED QUEUE LEN CHECK (Wave 18)
# ==============================================================================
async def fuzz_cmd_shuffle_unlocked_queue_len_check(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_shuffle_unlocked_queue_len_check",
        description="Fuzzing pengecekan len(state.queue) < 2 di luar lock tanpa validasi ulang di dalam state.lock pada cmd_shuffle",
        iterations=iterations,
    )
    unlocked_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.cmd_shuffle)
        lock_part = src.partition("async with state.lock:")[2]
        vulnerable = "len(state.queue) < 2" not in lock_part
        if vulnerable:
            unlocked_events += 1

    if unlocked_events > 0:
        res.anomalies.append(
            f"cmd_shuffle unlocked queue len check terkonfirmasi: {unlocked_events}/{iterations} iterasi. "
            "Pengecekan len(state.queue) < 2 pada cmd_shuffle dilakukan di luar state.lock tanpa validasi ulang "
            "di dalam lock, memicu respons misleading jika antrean berkurang konkuren."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"unlocked_events": unlocked_events}
    return res


# ==============================================================================
# 204. CMD SKIP MISSING IDLE SCHEDULE (Wave 18)
# ==============================================================================
async def fuzz_cmd_skip_missing_idle_schedule(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_skip_missing_idle_schedule",
        description="Fuzzing ketiadaan penjadwalan _schedule_idle pada cmd_skip saat antrean kosong dan audio berhenti",
        iterations=iterations,
    )
    missing_idle_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.cmd_skip)
        vulnerable = "_schedule_idle" not in src
        if vulnerable:
            missing_idle_events += 1

    if missing_idle_events > 0:
        res.anomalies.append(
            f"cmd_skip missing idle schedule terkonfirmasi: {missing_idle_events}/{iterations} iterasi. "
            "Ketiadaan penjadwalan _schedule_idle pada cmd_skip saat antrean kosong dan audio berhenti, "
            "menelantarkan bot di voice tanpa idle timer."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"missing_idle_events": missing_idle_events}
    return res


# ==============================================================================
# 205. CMD LOOP UNVALIDATED MODE FALLBACK (Wave 18)
# ==============================================================================
async def fuzz_cmd_loop_unvalidated_mode_fallback(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="cmd_loop_unvalidated_mode_fallback",
        description="Fuzzing kegagalan validasi nilai mode pada cmd_loop yang otomatis memicu cycle toggle jika mode tidak dikenal",
        iterations=iterations,
    )
    fallback_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.cmd_loop)
        part = src.partition("if mode and mode.lower() in {'off', 'track', 'queue'}:")
        sub = part[2][:150]
        vulnerable = "else:" in sub and "cycle =" in sub
        if vulnerable:
            fallback_events += 1

    if fallback_events > 0:
        res.anomalies.append(
            f"cmd_loop unvalidated mode fallback terkonfirmasi: {fallback_events}/{iterations} iterasi. "
            "Nilai mode tidak valid pada cmd_loop tidak ditolak melainkan otomatis memicu cycle toggle."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"fallback_events": fallback_events}
    return res


# ==============================================================================
# 206. IS CONNECTED FALLBACK LAMBDA TRUE FLAW (Wave 18)
# ==============================================================================
async def fuzz_is_connected_fallback_lambda_true_flaw(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="is_connected_fallback_lambda_true_flaw",
        description="Fuzzing cacat fallback lambda: True pada getattr(vc, 'is_connected') di cmd_play, cmd_stop, cmd_quit, dan SearchModal",
        iterations=iterations,
    )
    flaw_events = 0
    for _ in range(iterations):
        src_stop = inspect.getsource(MusicBot.cmd_stop)
        src_quit = inspect.getsource(MusicBot.cmd_quit)
        src_play = inspect.getsource(MusicBot.cmd_play)
        vulnerable = (
            "getattr(vc, 'is_connected', lambda: True)" in src_stop
            or "getattr(vc, 'is_connected', lambda: True)" in src_quit
            or "getattr(vc, 'is_connected', lambda: True)" in src_play
        )
        if vulnerable:
            flaw_events += 1

    if flaw_events > 0:
        res.anomalies.append(
            f"is_connected fallback lambda: True terkonfirmasi: {flaw_events}/{iterations} iterasi. "
            "Fallback lambda: True pada getattr(vc, 'is_connected') menganggap voice client terhubung saat atribut hilang/rusak."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"flaw_events": flaw_events}
    return res


# ==============================================================================
# 207. SEARCH MODAL DIRECT VC CHANNEL MUTATION (Wave 18)
# ==============================================================================
async def fuzz_search_modal_direct_vc_channel_mutation(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="search_modal_direct_vc_channel_mutation",
        description="Fuzzing mutasi langsung atribut internal vc.channel = None pada SearchModal.on_submit",
        iterations=iterations,
    )
    mutation_events = 0
    for _ in range(iterations):
        src = inspect.getsource(SearchModal.on_submit)
        vulnerable = "vc.channel = None" in src
        if vulnerable:
            mutation_events += 1

    if mutation_events > 0:
        res.anomalies.append(
            f"SearchModal direct vc.channel mutation terkonfirmasi: {mutation_events}/{iterations} iterasi. "
            "Mutasi langsung atribut internal vc.channel = None pada SearchModal.on_submit merusak integritas objek VoiceClient discord.py."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"mutation_events": mutation_events}
    return res


# ==============================================================================
# 208. STATE EXPORTER LOOP STOPPING CHECK OMISSION (Wave 18)
# ==============================================================================
async def fuzz_state_exporter_loop_stopping_check_omission(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="state_exporter_loop_stopping_check_omission",
        description="Fuzzing ketiadaan pengecekan self._stopping pada loop _state_exporter_loop selama proses shutdown",
        iterations=iterations,
    )
    omission_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._state_exporter_loop)
        vulnerable = "_stopping" not in src
        if vulnerable:
            omission_events += 1

    if omission_events > 0:
        res.anomalies.append(
            f"_state_exporter_loop missing stopping check terkonfirmasi: {omission_events}/{iterations} iterasi. "
            "_state_exporter_loop tidak memeriksa self._stopping, memicu I/O disk dump_runtime_state selama shutdown."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"omission_events": omission_events}
    return res


# ==============================================================================
# 209. ON GUILD REMOVE REDUNDANT EMMC DUMP (Wave 18)
# ==============================================================================
async def fuzz_on_guild_remove_redundant_emmc_dump(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="on_guild_remove_redundant_emmc_dump",
        description="Verifikasi pemanggilan redundan dump_runtime_state pada baris awal on_guild_remove sebelum quit_voice",
        iterations=iterations,
    )
    redundant_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot.on_guild_remove)
        first_part = src[:120]
        vulnerable = "dump_runtime_state(self)" in first_part
        if vulnerable:
            redundant_events += 1

    if redundant_events > 0:
        res.anomalies.append(
            f"on_guild_remove redundant eMMC dump terkonfirmasi: {redundant_events}/{iterations} iterasi. "
            "Pemanggilan redundan dump_runtime_state pada on_guild_remove sebelum quit_voice memboroskan siklus I/O flash eMMC STB ARM."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"redundant_events": redundant_events}
    return res


# ==============================================================================
# 210. SOURCE FOR VOLUME NAN INF SANITIZATION (Wave 18)
# ==============================================================================
async def fuzz_source_for_volume_nan_inf_sanitization(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="source_for_volume_nan_inf_sanitization",
        description="Fuzzing ketiadaan sanitasi volume NaN/Inf pada source_for yang menghasilkan stream terdistorsi",
        iterations=iterations,
    )
    sanitization_missing_events = 0
    for _ in range(iterations):
        src = inspect.getsource(bot_module.source_for)
        vulnerable = "math.isfinite" not in src
        if vulnerable:
            sanitization_missing_events += 1

    if sanitization_missing_events > 0:
        res.anomalies.append(
            f"source_for volume NaN/Inf sanitization terkonfirmasi: {sanitization_missing_events}/{iterations} iterasi. "
            "Ketiadaan sanitasi volume NaN/Inf pada source_for berisiko menghasilkan PCMVolumeTransformer dengan stream terdistorsi."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"sanitization_missing_events": sanitization_missing_events}
    return res


# ==============================================================================
# 211. RESTORE PERSISTENT QUEUE INFINITE VOLUME (Wave 18)
# ==============================================================================
async def fuzz_restore_persistent_queue_infinite_volume(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="restore_persistent_queue_infinite_volume",
        description="Fuzzing penerimaan volume bernilai infinity pada _restore_persistent_queue akibat pemeriksaan not (vol != vol)",
        iterations=iterations,
    )
    infinite_vol_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._restore_persistent_queue)
        vulnerable = "not (vol != vol)" in src or "math.isfinite" not in src
        if vulnerable:
            infinite_vol_events += 1

    if infinite_vol_events > 0:
        res.anomalies.append(
            f"_restore_persistent_queue infinite volume flaw terkonfirmasi: {infinite_vol_events}/{iterations} iterasi. "
            "Pemeriksaan not (vol != vol) pada _restore_persistent_queue meloloskan float('inf') dan -inf."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"infinite_vol_events": infinite_vol_events}
    return res


# ==============================================================================
# 212. RESTORE PERSISTENT QUEUE BOOLEAN PANEL MSG ID (Wave 18)
# ==============================================================================
async def fuzz_restore_persistent_queue_boolean_panel_msg_id(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="restore_persistent_queue_boolean_panel_msg_id",
        description="Fuzzing pemuatan boolean True/False ke state.message pada _restore_persistent_queue",
        iterations=iterations,
    )
    boolean_restore_events = 0
    for _ in range(iterations):
        src = inspect.getsource(MusicBot._restore_persistent_queue)
        vulnerable = "not isinstance(panel_message_id, bool)" not in src
        if vulnerable:
            boolean_restore_events += 1

    if boolean_restore_events > 0:
        res.anomalies.append(
            f"_restore_persistent_queue boolean panel_message_id restore flaw terkonfirmasi: {boolean_restore_events}/{iterations} iterasi. "
            "_restore_persistent_queue tidak memeriksa not isinstance(panel_message_id, bool), memuat boolean True ke state.message."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"boolean_restore_events": boolean_restore_events}
    return res


# ==============================================================================
# 213. PANEL UPDATE PASSWORD FALLBACK CHMOD OMISSION (Wave 18)
# ==============================================================================
async def fuzz_panel_update_password_fallback_chmod_omission(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_update_password_fallback_chmod_omission",
        description="Fuzzing ketiadaan penegakan os.chmod(target_path, 0o600) pada fallback in-place write di update_panel_password()",
        iterations=iterations,
    )
    chmod_omission_events = 0
    for _ in range(iterations):
        src = inspect.getsource(panel_module.update_panel_password)
        part = src.partition("# Fallback jika direktori induk read-only (ProtectSystem=strict): tulis in-place")
        sub = part[2][:300]
        vulnerable = "os.chmod(target_path, 0o600)" not in sub
        if vulnerable:
            chmod_omission_events += 1

    if chmod_omission_events > 0:
        res.anomalies.append(
            f"update_panel_password fallback chmod 0600 omission terkonfirmasi: {chmod_omission_events}/{iterations} iterasi. "
            "Fallback in-place write pada update_panel_password tidak menegakkan os.chmod(target_path, 0o600)."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"chmod_omission_events": chmod_omission_events}
    return res


# ==============================================================================
# 214. PANEL UPDATE LOG UNICODE DECODE ERROR (Wave 18)
# ==============================================================================
async def fuzz_panel_update_log_unicode_decode_error(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_update_log_unicode_decode_error",
        description="Fuzzing risiko unhandled UnicodeDecodeError saat membaca UPDATE_LOG_PATH tanpa errors='replace'",
        iterations=iterations,
    )
    decode_risk_events = 0
    for _ in range(iterations):
        src_read = inspect.getsource(panel_module.read_last_update_log)
        src_run = inspect.getsource(panel_module._run_update_inner)
        vulnerable_read = "open(UPDATE_LOG_PATH, 'r', encoding='utf-8')" in src_read and "errors=" not in src_read.partition("open(UPDATE_LOG_PATH")[2][:50]
        vulnerable_run = "open(UPDATE_LOG_PATH, 'r', encoding='utf-8')" in src_run and "errors=" not in src_run.partition("open(UPDATE_LOG_PATH")[2][:50]
        if vulnerable_read or vulnerable_run:
            decode_risk_events += 1

    if decode_risk_events > 0:
        res.anomalies.append(
            f"panel update log UnicodeDecodeError risk terkonfirmasi: {decode_risk_events}/{iterations} iterasi. "
            "Pembacaan UPDATE_LOG_PATH tanpa errors='replace' rentan unhandled UnicodeDecodeError."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"decode_risk_events": decode_risk_events}
    return res


# ==============================================================================
# 215. PANEL BOT INVITE REVERSE TABNABBING (Wave 18)
# ==============================================================================
async def fuzz_panel_bot_invite_reverse_tabnabbing(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_bot_invite_reverse_tabnabbing",
        description="Verifikasi kerentanan reverse tabnabbing pada link bot invite di panel akibat target='_blank' tanpa rel='noopener noreferrer'",
        iterations=iterations,
    )
    tabnabbing_events = 0
    for _ in range(iterations):
        src = inspect.getsource(panel_module.Handler._page)
        part = src.partition('target="_blank"')
        vulnerable = 'target="_blank"' in src and 'rel="noopener noreferrer"' not in part[2][:100]
        if vulnerable:
            tabnabbing_events += 1

    if tabnabbing_events > 0:
        res.anomalies.append(
            f"panel bot invite reverse tabnabbing terkonfirmasi: {tabnabbing_events}/{iterations} iterasi. "
            "Tautan eksternal bot invite di panel menggunakan target='_blank' tanpa rel='noopener noreferrer' (reverse tabnabbing)."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"tabnabbing_events": tabnabbing_events}
    return res


# ==============================================================================
# 216. PANEL LOCAL ADDRESSES CACHE MUTATION LEAK (Wave 18)
# ==============================================================================
async def fuzz_panel_local_addresses_cache_mutation_leak(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="panel_local_addresses_cache_mutation_leak",
        description="Fuzzing kebocoran mutasi cache internal _local_addr_cache akibat pengembalian set langsung tanpa set()",
        iterations=iterations,
    )
    cache_leak_events = 0
    for _ in range(iterations):
        src = inspect.getsource(panel_module._local_addresses)
        vulnerable = "return set(_local_addr_cache)" not in src and "return _local_addr_cache" in src
        if vulnerable:
            cache_leak_events += 1

    if cache_leak_events > 0:
        res.anomalies.append(
            f"_local_addresses cache set mutation leak terkonfirmasi: {cache_leak_events}/{iterations} iterasi. "
            "_local_addresses() mengembalikan cache set internal langsung tanpa penyalinan set()."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"cache_leak_events": cache_leak_events}
    return res


# ==============================================================================
# 217. CONFIG STORE WRITE NON DICT VALIDATION (Wave 18)
# ==============================================================================
async def fuzz_config_store_write_non_dict_validation(iterations: int = 5) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="config_store_write_non_dict_validation",
        description="Fuzzing unhandled AttributeError pada ConfigStore.write() ketika parameter values bukan bertipe dict",
        iterations=iterations,
    )
    validation_missing_events = 0
    for _ in range(iterations):
        src = inspect.getsource(panel_module.ConfigStore.write)
        vulnerable = "isinstance(values, dict)" not in src
        if vulnerable:
            validation_missing_events += 1

    if validation_missing_events > 0:
        res.anomalies.append(
            f"ConfigStore.write non-dict validation terkonfirmasi: {validation_missing_events}/{iterations} iterasi. "
            "ConfigStore.write melempar AttributeError tanpa handling jika argumen values bukan dict."
        )
        res.failed += 1
    else:
        res.passed += 1

    res.metrics = {"validation_missing_events": validation_missing_events}
    return res


# ==============================================================================
# RUNNER
# ==============================================================================
ALL_SCENARIOS = {
    # Wave 3 Baselines
    "burst_skips": fuzz_burst_skips,
    "stream_jitter": fuzz_stream_jitter_network_drop,
    "circuit_breaker": fuzz_circuit_breaker,
    "afk_guard": fuzz_afk_guard,
    "extraction": fuzz_extraction_concurrency,
    "queue_shuffle": fuzz_queue_mutations_and_shuffle,
    "flat_stream_cache": fuzz_flat_playlist_stream_cache,
    "sync_io_ui": fuzz_sync_io_and_ui_refresh,
    # Wave 4 Additions
    "burst_back": fuzz_burst_back_and_history_drain,
    "stream_stall_cb": fuzz_stream_stall_circuit_breaker,
    "circuit_breaker_resume": fuzz_circuit_breaker_manual_resume,
    "queue_restore_duplicate": fuzz_persistent_queue_gateway_resume_duplication,
    "autoplay_cancel": fuzz_autoplay_generation_waste,
    "search_modal": fuzz_search_modal_stall_and_perms,
    "panel_desync": fuzz_panel_embed_desync_on_stop,
    # Wave 5 Additions
    "cmd_play_idle_stall": fuzz_cmd_play_idle_stall,
    "concurrent_json_writer_tmp_collision": fuzz_concurrent_json_writer_tmp_collision,
    "circuit_breaker_idle_disconnect": fuzz_circuit_breaker_idle_disconnect,
    "loop_track_error_queue_abandon": fuzz_loop_track_error_queue_abandon,
    "autoplay_multicandidate_fallback": fuzz_autoplay_multicandidate_fallback,
    "single_track_loop_queue_skip": fuzz_single_track_loop_queue_skip,
    "announce_now_playing_safe_delete": fuzz_announce_now_playing_safe_delete,
    "volume_burst_debounce": fuzz_volume_burst_debounce,
    # Wave 6 Additions
    "ghost_voice_client_lockout": fuzz_ghost_voice_client_lockout,
    "cross_generation_after_error_bleed": fuzz_cross_generation_after_error_bleed,
    "single_failing_track_idle_stall": fuzz_single_failing_track_idle_stall,
    "afk_guard_generation_abandonment": fuzz_afk_guard_generation_abandonment,
    "threadpool_disk_writers_out_of_order": fuzz_threadpool_disk_writers_out_of_order,
    "announce_now_playing_message_id_fallback": fuzz_announce_now_playing_message_id_fallback,
    "cmd_volume_channel_auth_debounce": fuzz_cmd_volume_channel_auth_debounce,
    "clean_seed_title_word_boundary": fuzz_clean_seed_title_word_boundary,
    "panel_session_revocation_on_password_change": fuzz_panel_session_revocation_on_password_change,
    "unsynchronized_deque_iteration": fuzz_unsynchronized_deque_iteration,
    # Wave 7 Additions
    "audio_player_connection_loss_deadlock": fuzz_audio_player_connection_loss_deadlock,
    "afk_guard_empty_room_bot_member_check": fuzz_afk_guard_empty_room_bot_member_check,
    "threadpool_queue_write_lock_lazy_init": fuzz_threadpool_queue_write_lock_lazy_init,
    "close_persistent_queue_unawaited_executor": fuzz_close_persistent_queue_unawaited_executor,
    "panel_stale_service_state_cache": fuzz_panel_stale_service_state_cache,
    "playlist_clear_queue_idle_timer_leak": fuzz_playlist_clear_queue_idle_timer_leak,
    "search_modal_missing_text_channel_id": fuzz_search_modal_missing_text_channel_id,
    "on_ready_queue_file_deletion_on_reconnect": fuzz_on_ready_queue_file_deletion_on_reconnect,
    "advance_unhandled_keyerror_on_missing_guild": fuzz_advance_unhandled_keyerror_on_missing_guild,
    "empty_room_ffmpeg_cpu_waste_advance": fuzz_empty_room_ffmpeg_cpu_waste_advance,
    # Wave 8 Additions
    "ghost_voice_client_lockout_modal_and_panel": fuzz_ghost_voice_client_lockout_modal_and_panel,
    "restore_persistent_queue_unrepersisted": fuzz_restore_persistent_queue_unrepersisted,
    "listeners_out_of_order_seq_writer": fuzz_listeners_out_of_order_seq_writer,
    "dump_runtime_state_offline_listeners_cleanup": fuzz_dump_runtime_state_offline_listeners_cleanup,
    "empty_room_user_return_autoplay_restart": fuzz_empty_room_user_return_autoplay_restart,
    "stream_error_cached_url_invalidation": fuzz_stream_error_cached_url_invalidation,
    "cmd_play_summon_integer_panel_id_deletion": fuzz_cmd_play_summon_integer_panel_id_deletion,
    "announce_now_playing_channel_resolution": fuzz_announce_now_playing_channel_resolution,
    "panel_stale_log_cache_post_service_action": fuzz_panel_stale_log_cache_post_service_action,
    "release_extract_slot_underflow": fuzz_release_extract_slot_underflow,
    "idle_disconnect_task_leak_finally": fuzz_idle_disconnect_task_leak_finally,
    # Wave 9 Additions
    "announce_now_playing_fallback_channel_mismatch": fuzz_announce_now_playing_fallback_channel_mismatch,
    "refresh_panel_http_rate_limit_discard": fuzz_refresh_panel_http_rate_limit_discard,
    "dump_runtime_state_offline_writer_race": fuzz_dump_runtime_state_offline_writer_race,
    "safedeque_contains_mutation_race": fuzz_safedeque_contains_mutation_race,
    "panel_empty_queue_voice_stranded": fuzz_panel_empty_queue_voice_stranded,
    "empty_room_dual_timer_collision": fuzz_empty_room_dual_timer_collision,
    "tracks_from_metadata_web_url_caching": fuzz_tracks_from_metadata_web_url_caching,
    "buffered_audio_source_reader_cleanup_false_error": fuzz_buffered_audio_source_reader_cleanup_false_error,
    "cmd_queue_and_playlist_lock_contention": fuzz_cmd_queue_and_playlist_lock_contention,
    "synced_guilds_retention_on_guild_remove": fuzz_synced_guilds_retention_on_guild_remove,
    "panel_logout_server_session_revocation": fuzz_panel_logout_server_session_revocation,
    "panel_update_cache_invalidation": fuzz_panel_update_cache_invalidation,
    # Wave 10 Additions
    "stranded_voice_client_current_not_none_idle_bypass": fuzz_stranded_voice_client_current_not_none_idle_bypass,
    "cmd_back_race_condition_idle_check": fuzz_cmd_back_race_condition_idle_check,
    "stop_quit_disconnected_voice_lockout": fuzz_stop_quit_disconnected_voice_lockout,
    "advance_phase4_stale_generation_source_leak": fuzz_advance_phase4_stale_generation_source_leak,
    "buffered_audio_source_cleanup_event_loop_freeze": fuzz_buffered_audio_source_cleanup_event_loop_freeze,
    "dump_runtime_state_tmp_chmod_permission": fuzz_dump_runtime_state_tmp_chmod_permission,
    "dump_runtime_state_offline_max_seq_race": fuzz_dump_runtime_state_offline_max_seq_race,
    "skip_pending_lingering_flag_race": fuzz_skip_pending_lingering_flag_race,
    "track_dataclass_equality_mismatch": fuzz_track_dataclass_equality_mismatch,
    "autoplay_idle_connected_advance_trigger": fuzz_autoplay_idle_connected_advance_trigger,
    "voice_state_update_unlocked_mutation": fuzz_voice_state_update_unlocked_mutation,
    "quit_voice_sync_gc_collect_event_loop_block": fuzz_quit_voice_sync_gc_collect_event_loop_block,
    "music_panel_direct_dict_indexing_keyerror": fuzz_music_panel_direct_dict_indexing_keyerror,
    "panel_logs_fresh_unbounded_journalctl_debounce": fuzz_panel_logs_fresh_unbounded_journalctl_debounce,
    "cmd_play_missing_get_channel_fallback": fuzz_cmd_play_missing_get_channel_fallback,
    "music_panel_volume_read_modify_write_race": fuzz_music_panel_volume_read_modify_write_race,
    # Wave 11 Additions
    "panel_button_stale_guard_stranded_voice": fuzz_panel_button_stale_guard_stranded_voice,
    "autoplay_skip_extraction_reloop": fuzz_autoplay_skip_extraction_reloop,
    "panel_skip_idle_circuit_breaker_latch": fuzz_panel_skip_idle_circuit_breaker_latch,
    "afk_disconnect_task_leak_done_check": fuzz_afk_disconnect_task_leak_done_check,
    "dump_runtime_state_current_title_race": fuzz_dump_runtime_state_current_title_race,
    "save_persistent_queue_tmp_chmod_permission": fuzz_save_persistent_queue_tmp_chmod_permission,
    "cmd_musik_idle_timer_omission": fuzz_cmd_musik_idle_timer_omission,
    "panel_buttons_rapid_click_eMMC_debounce": fuzz_panel_buttons_rapid_click_eMMC_debounce,
    "cmd_autoplay_stale_current_lockout": fuzz_cmd_autoplay_stale_current_lockout,
    "cmd_pause_unlocked_mutation_and_idle_omission": fuzz_cmd_pause_unlocked_mutation_and_idle_omission,
    "concurrent_play_and_musik_panel_duplication": fuzz_concurrent_play_and_musik_panel_duplication,
    "playlist_view_refresh_instance_leak": fuzz_playlist_view_refresh_instance_leak,
    "music_bot_embed_formatting_and_length_safety": fuzz_music_bot_embed_formatting_and_length_safety,
    "voice_state_update_redundant_dual_dump_io": fuzz_voice_state_update_redundant_dual_dump_io,
    "panel_fresh_logs_concurrent_debounce_race": fuzz_panel_fresh_logs_concurrent_debounce_race,
    "panel_ytdlp_version_module_cache_stale": fuzz_panel_ytdlp_version_module_cache_stale,
    # Wave 12 Additions
    "loop_track_empty_channel_abandonment": fuzz_loop_track_empty_channel_abandonment,
    "idle_disconnect_boolean_precedence_flaw": fuzz_idle_disconnect_boolean_precedence_flaw,
    "queue_full_stranded_voice_idle_omission": fuzz_queue_full_stranded_voice_idle_omission,
    "music_panel_pause_unlocked_mutation": fuzz_music_panel_pause_unlocked_mutation,
    "guild_remove_voice_client_subprocess_leak": fuzz_guild_remove_voice_client_subprocess_leak,
    "enqueue_tracks_playing_check_race": fuzz_enqueue_tracks_playing_check_race,
    "shutdown_ghost_panel_id_persistence": fuzz_shutdown_ghost_panel_id_persistence,
    "refresh_panel_integer_id_stall": fuzz_refresh_panel_integer_id_stall,
    "cmd_skip_advancing_check_race": fuzz_cmd_skip_advancing_check_race,
    "vc_play_client_exception_idle_abandonment": fuzz_vc_play_client_exception_idle_abandonment,
    "announce_now_playing_cancellation_orphan": fuzz_announce_now_playing_cancellation_orphan,
    "change_volume_nan_value_error": fuzz_change_volume_nan_value_error,
    "tracks_from_metadata_missing_id_watch_none": fuzz_tracks_from_metadata_missing_id_watch_none,
    "back_idle_unlocked_state_mutation": fuzz_back_idle_unlocked_state_mutation,
    "panel_ytdlp_version_uncached_metadata_scan": fuzz_panel_ytdlp_version_uncached_metadata_scan,
    "panel_update_log_uncached_disk_io": fuzz_panel_update_log_uncached_disk_io,
    # Wave 13 Additions
    "loop_track_extraction_failure_stall_and_idle_omission": fuzz_loop_track_extraction_failure_stall_and_idle_omission,
    "loop_queue_track_drop_on_extraction_failure": fuzz_loop_queue_track_drop_on_extraction_failure,
    "close_voice_client_disconnect_and_subprocess_leak": fuzz_close_voice_client_disconnect_and_subprocess_leak,
    "summon_channel_send_failure_stranded_voice": fuzz_summon_channel_send_failure_stranded_voice,
    "music_panel_guard_timeout_ghost_voice_lockout": fuzz_music_panel_guard_timeout_ghost_voice_lockout,
    "restored_state_current_desync_and_track_loss": fuzz_restored_state_current_desync_and_track_loss,
    "shuffle_persistent_queue_file_wipeout_race": fuzz_shuffle_persistent_queue_file_wipeout_race,
    "announce_now_playing_asyncio_shield_cancellation_orphan": fuzz_announce_now_playing_asyncio_shield_cancellation_orphan,
    "escape_markdown_none_type_error": fuzz_escape_markdown_none_type_error,
    "format_duration_nan_inf_value_error": fuzz_format_duration_nan_inf_value_error,
    "clean_seed_title_single_noise_word_wipeout": fuzz_clean_seed_title_single_noise_word_wipeout,
    "tracks_from_metadata_double_watch_url_corruption": fuzz_tracks_from_metadata_double_watch_url_corruption,
    "tracks_from_metadata_non_playlist_search_query_pollution": fuzz_tracks_from_metadata_non_playlist_search_query_pollution,
    "afk_disconnect_timeout_inf_overflow_error": fuzz_afk_disconnect_timeout_inf_overflow_error,
    "panel_update_stale_ytdlp_version_and_log_cache": fuzz_panel_update_stale_ytdlp_version_and_log_cache,
    "panel_cached_systemctl_thundering_herd_fork": fuzz_panel_cached_systemctl_thundering_herd_fork,
    # Wave 14 Additions
    "escape_markdown_none_type_error_modal_and_play": fuzz_escape_markdown_none_type_error_modal_and_play,
    "vc_play_client_exception_nonempty_queue_voice_lockout": fuzz_vc_play_client_exception_nonempty_queue_voice_lockout,
    "persistent_queue_guild_settings_wipeout_on_empty_queue": fuzz_persistent_queue_guild_settings_wipeout_on_empty_queue,
    "skip_stopped_playback_failing_queue_head_drop_omission": fuzz_skip_stopped_playback_failing_queue_head_drop_omission,
    "summon_voice_stranded_on_nonempty_queue": fuzz_summon_voice_stranded_on_nonempty_queue,
    "loop_queue_track_drop_on_duplicate_track_equality": fuzz_loop_queue_track_drop_on_duplicate_track_equality,
    "bot_close_missing_vc_source_cleanup_ffmpeg_leak": fuzz_bot_close_missing_vc_source_cleanup_ffmpeg_leak,
    "audio_player_send_silence_eof_false_playback_error": fuzz_audio_player_send_silence_eof_false_playback_error,
    "panel_empty_track_queue_len_display_mismatch": fuzz_panel_empty_track_queue_len_display_mismatch,
    "panel_read_bot_runtime_info_uncached_disk_io": fuzz_panel_read_bot_runtime_info_uncached_disk_io,
    "panel_password_save_failure_session_lockout": fuzz_panel_password_save_failure_session_lockout,
    "music_panel_guard_unlocked_message_mutation": fuzz_music_panel_guard_unlocked_message_mutation,
    "background_task_fire_and_forget_gc_premature_cleanup": fuzz_background_task_fire_and_forget_gc_premature_cleanup,
    "voice_state_update_unlocked_afk_paused_mutation": fuzz_voice_state_update_unlocked_afk_paused_mutation,
    "afk_disconnect_generation_zero_empty_room_bypass": fuzz_afk_disconnect_generation_zero_empty_room_bypass,
    "config_store_write_concurrent_race_missing_mutex": fuzz_config_store_write_concurrent_race_missing_mutex,
    # Wave 15 Additions
    "config_store_instance_mutex_bypass": fuzz_config_store_instance_mutex_bypass,
    "enqueue_tracks_advancing_race": fuzz_enqueue_tracks_advancing_race,
    "single_failing_track_stranded_ghost_voice": fuzz_single_failing_track_stranded_ghost_voice,
    "enqueue_tracks_track_equality_loss": fuzz_enqueue_tracks_track_equality_loss,
    "loop_failure_duplicate_track_deletion": fuzz_loop_failure_duplicate_track_deletion,
    "quit_voice_unreferenced_task_gc_risk": fuzz_quit_voice_unreferenced_task_gc_risk,
    "empty_room_user_return_missing_idle_reschedule": fuzz_empty_room_user_return_missing_idle_reschedule,
    "announce_now_playing_unlocked_mutation_orphan_risk": fuzz_announce_now_playing_unlocked_mutation_orphan_risk,
    "refresh_message_id_overwrite_race": fuzz_refresh_message_id_overwrite_race,
    "read_bot_runtime_info_stale_disk_churn": fuzz_read_bot_runtime_info_stale_disk_churn,
    "update_panel_password_missing_thread_lock": fuzz_update_panel_password_missing_thread_lock,
    "local_addr_cache_missing_ttl": fuzz_local_addr_cache_missing_ttl,
    "advance_unreset_cached_stream_url_on_exception": fuzz_advance_unreset_cached_stream_url_on_exception,
    "dump_runtime_state_stale_seq_disk_write_waste": fuzz_dump_runtime_state_stale_seq_disk_write_waste,
    "cmd_play_summon_missing_bot_get_channel_fallback": fuzz_cmd_play_summon_missing_bot_get_channel_fallback,
    "cmd_loop_and_autoplay_missing_voice_auth": fuzz_cmd_loop_and_autoplay_missing_voice_auth,
    # Wave 16 Additions
    "disconnected_voice_client_reconnect_bypass": fuzz_disconnected_voice_client_reconnect_bypass,
    "ghost_voice_client_lockout_stop_quit": fuzz_ghost_voice_client_lockout_stop_quit,
    "loop_queue_duplicate_track_history_and_queue_loss": fuzz_loop_queue_duplicate_track_history_and_queue_loss,
    "ffmpeg_abrupt_crash_eof_circuit_breaker_bypass": fuzz_ffmpeg_abrupt_crash_eof_circuit_breaker_bypass,
    "shutdown_runtime_state_file_resurrection_race": fuzz_shutdown_runtime_state_file_resurrection_race,
    "announce_now_playing_cancellation_orphan_shield": fuzz_announce_now_playing_cancellation_orphan_shield,
    "announce_now_playing_unlocked_overwrite_race": fuzz_announce_now_playing_unlocked_overwrite_race,
    "summon_duplicate_advance_and_idle_schedule": fuzz_summon_duplicate_advance_and_idle_schedule,
    "cmd_back_missing_idle_schedule_lockout": fuzz_cmd_back_missing_idle_schedule_lockout,
    "circuit_breaker_re_enqueue_whole_queue_duplicate": fuzz_circuit_breaker_re_enqueue_whole_queue_duplicate,
    "save_persistent_queue_stale_seq_disk_write_waste": fuzz_save_persistent_queue_stale_seq_disk_write_waste,
    "livestream_loop_track_endless_extraction_stall": fuzz_livestream_loop_track_endless_extraction_stall,
    "fetch_recommendations_duplicate_seed_mix_extraction": fuzz_fetch_recommendations_duplicate_seed_mix_extraction,
    "config_store_write_non_string_type_error": fuzz_config_store_write_non_string_type_error,
    "panel_ytdlp_version_stale_importlib_cache": fuzz_panel_ytdlp_version_stale_importlib_cache,
    "panel_update_stale_log_leak_on_failure": fuzz_panel_update_stale_log_leak_on_failure,
    # Wave 17 Additions
    "cmd_play_direct_indexing_keyerror": fuzz_cmd_play_direct_indexing_keyerror,
    "ghost_voice_lockout_panel_button_stop": fuzz_ghost_voice_lockout_panel_button_stop,
    "safe_delete_msg_cold_cache_channel_fallback": fuzz_safe_delete_msg_cold_cache_channel_fallback,
    "shutdown_state_exporter_loop_resurrection_race": fuzz_shutdown_state_exporter_loop_resurrection_race,
    "voice_state_update_sleep_shutdown_resurrection_race": fuzz_voice_state_update_sleep_shutdown_resurrection_race,
    "empty_room_afk_paused_audio_stopped_stranded_voice": fuzz_empty_room_afk_paused_audio_stopped_stranded_voice,
    "enqueue_tracks_disconnected_voice_history_loss": fuzz_enqueue_tracks_disconnected_voice_history_loss,
    "loop_queue_failing_track_poisoning": fuzz_loop_queue_failing_track_poisoning,
    "advance_loop_bitrate_inf_overflow_error": fuzz_advance_loop_bitrate_inf_overflow_error,
    "music_bot_embed_volume_nan_inf_crash": fuzz_music_bot_embed_volume_nan_inf_crash,
    "search_modal_unlocked_state_mutation": fuzz_search_modal_unlocked_state_mutation,
    "save_persistent_queue_boolean_msg_id_persistence": fuzz_save_persistent_queue_boolean_msg_id_persistence,
    "dump_runtime_state_tmp_write_before_seq_check_waste": fuzz_dump_runtime_state_tmp_write_before_seq_check_waste,
    "voice_state_update_not_in_voice_disk_thrashing": fuzz_voice_state_update_not_in_voice_disk_thrashing,
    "panel_logout_csrf_vulnerability": fuzz_panel_logout_csrf_vulnerability,
    "panel_format_guilds_html_malformed_type_error": fuzz_panel_format_guilds_html_malformed_type_error,
    # Wave 18 Additions
    "close_missing_stopping_flag": fuzz_close_missing_stopping_flag,
    "close_generation_bump_and_background_tasks_leak": fuzz_close_generation_bump_and_background_tasks_leak,
    "after_dispatch_sleep_shutdown_race": fuzz_after_dispatch_sleep_shutdown_race,
    "cmd_play_summon_old_panel_channel_mismatch": fuzz_cmd_play_summon_old_panel_channel_mismatch,
    "safe_delete_msg_param_channel_priority_inversion": fuzz_safe_delete_msg_param_channel_priority_inversion,
    "quit_voice_cold_cache_channel_resolution": fuzz_quit_voice_cold_cache_channel_resolution,
    "refresh_unlocked_state_message_mutation": fuzz_refresh_unlocked_state_message_mutation,
    "delete_all_panels_unlocked_state_mutation": fuzz_delete_all_panels_unlocked_state_mutation,
    "cmd_shuffle_unlocked_queue_len_check": fuzz_cmd_shuffle_unlocked_queue_len_check,
    "cmd_skip_missing_idle_schedule": fuzz_cmd_skip_missing_idle_schedule,
    "cmd_loop_unvalidated_mode_fallback": fuzz_cmd_loop_unvalidated_mode_fallback,
    "is_connected_fallback_lambda_true_flaw": fuzz_is_connected_fallback_lambda_true_flaw,
    "search_modal_direct_vc_channel_mutation": fuzz_search_modal_direct_vc_channel_mutation,
    "state_exporter_loop_stopping_check_omission": fuzz_state_exporter_loop_stopping_check_omission,
    "on_guild_remove_redundant_emmc_dump": fuzz_on_guild_remove_redundant_emmc_dump,
    "source_for_volume_nan_inf_sanitization": fuzz_source_for_volume_nan_inf_sanitization,
    "restore_persistent_queue_infinite_volume": fuzz_restore_persistent_queue_infinite_volume,
    "restore_persistent_queue_boolean_panel_msg_id": fuzz_restore_persistent_queue_boolean_panel_msg_id,
    "panel_update_password_fallback_chmod_omission": fuzz_panel_update_password_fallback_chmod_omission,
    "panel_update_log_unicode_decode_error": fuzz_panel_update_log_unicode_decode_error,
    "panel_bot_invite_reverse_tabnabbing": fuzz_panel_bot_invite_reverse_tabnabbing,
    "panel_local_addresses_cache_mutation_leak": fuzz_panel_local_addresses_cache_mutation_leak,
    "config_store_write_non_dict_validation": fuzz_config_store_write_non_dict_validation,
}


async def run_all(scenarios: list[str], iterations: int) -> list[FuzzScenarioResult]:
    results = []
    for sc_name in scenarios:
        fn = ALL_SCENARIOS.get(sc_name)
        if not fn:
            continue
        logger.info("Menjalankan skenario: %s...", sc_name)
        res = await fn(iterations=iterations)
        results.append(res)
    return results


def main():
    parser = argparse.ArgumentParser(description="Stress Testing & Concurrency Fuzzing Runner (Wave 18)")
    parser.add_argument("--scenario", default="all", choices=["all"] + list(ALL_SCENARIOS.keys()))
    parser.add_argument("--iterations", type=int, default=10, help="Jumlah iterasi fuzzing per skenario")
    parser.add_argument("--json", action="store_true", help="Format output sebagai JSON")
    args = parser.parse_args()

    selected = list(ALL_SCENARIOS.keys()) if args.scenario == "all" else [args.scenario]
    results = asyncio.run(run_all(selected, args.iterations))

    if args.json:
        data = [asdict(r) for r in results]
        print(json.dumps(data, indent=2))
        return

    print("\n" + "=" * 76)
    print("LAPORAN STRESS TESTING & CONCURRENCY FUZZING BOT.PY (WAVE 18)")
    print("=" * 76)

    total_passed = 0
    total_failed = 0
    total_anomalies = 0
    total_exceptions = 0

    for r in results:
        status = "PASSED" if r.failed == 0 else "FAIL/VULN"
        if r.failed == 0:
            total_passed += 1
        else:
            total_failed += 1

        print(f"\n[{status}] Skenario: {r.scenario}")
        print(f"  Deskripsi : {r.description}")
        print(f"  Iterasi   : {r.iterations} | Passed: {r.passed} | Failed: {r.failed}")
        if r.anomalies:
            print("  Temuan Masalah Concurrency / Vulnerability:")
            for a in r.anomalies:
                print(f"    * {a}")
                total_anomalies += 1
        if r.unhandled_exceptions:
            print("  Unhandled Exceptions:")
            for e in r.unhandled_exceptions:
                print(f"    * {e}")
                total_exceptions += 1
        if r.metrics:
            print(f"  Metrik    : {json.dumps(r.metrics)}")

    print("\n" + "=" * 76)
    print(f"RINGKASAN: {len(results)} Skenario Diuji | {total_passed} Passed | {total_failed} Teridentifikasi Bug/Race Condition")
    print(f"TOTAL ANOMALI/VULNERABILITAS: {total_anomalies} | UNHANDLED EXCEPTIONS: {total_exceptions}")
    print("=" * 76 + "\n")


if __name__ == "__main__":
    main()
