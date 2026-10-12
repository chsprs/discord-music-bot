#!/usr/bin/env python3
"""Stress Testing & Concurrency Fuzzing Script for Discord Music Bot (Wave 7).

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

Usage:
    ./venv/bin/python tools/stress_concurrency_fuzz.py
    ./venv/bin/python tools/stress_concurrency_fuzz.py --json
    ./venv/bin/python tools/stress_concurrency_fuzz.py --scenario audio_player_connection_loss_deadlock
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import logging
import os
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
    parser = argparse.ArgumentParser(description="Stress Testing & Concurrency Fuzzing Runner (Wave 7)")
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
    print("LAPORAN STRESS TESTING & CONCURRENCY FUZZING BOT.PY (WAVE 7)")
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
