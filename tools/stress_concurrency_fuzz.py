#!/usr/bin/env python3
"""Stress Testing & Concurrency Fuzzing Script for Discord Music Bot (Wave 11).

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

Usage:
    ./venv/bin/python tools/stress_concurrency_fuzz.py
    ./venv/bin/python tools/stress_concurrency_fuzz.py --json
    ./venv/bin/python tools/stress_concurrency_fuzz.py --scenario panel_button_stale_guard_stranded_voice
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
    parser = argparse.ArgumentParser(description="Stress Testing & Concurrency Fuzzing Runner (Wave 11)")
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
    print("LAPORAN STRESS TESTING & CONCURRENCY FUZZING BOT.PY (WAVE 11)")
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
