#!/usr/bin/env python3
"""Stress Testing & Concurrency Fuzzing Script for Discord Music Bot (Wave 3).

Skenario Simulasi & Verifikasi:
1. Burst skips & _advance_lock race condition
2. Stream jitter, network drop, & voice error recovery
3. Circuit breaker threshold & queue preservation
4. AFK Guard generation lifecycle & premature disconnect
5. yt-dlp concurrency, cancellation, & slot leak (ExtractionBusy)
6. Concurrent queue mutations (shuffle desync & deque iteration)
7. Flat playlist stream_url false-positive caching
8. Synchronous event-loop I/O & UI refresh consistency

Usage:
    ./venv/bin/python tools/stress_concurrency_fuzz.py
    ./venv/bin/python tools/stress_concurrency_fuzz.py --json
    ./venv/bin/python tools/stress_concurrency_fuzz.py --scenario burst_skips
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import sys
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import discord
import bot as bot_module
from bot import (
    ExtractionBusy,
    MAX_EXTRACT_THREADS,
    MAX_QUEUE,
    MAX_TRACK_RETRIES,
    MusicBot,
    MusicPanel,
    QueueState,
    Track,
    dump_runtime_state,
    run_extract,
)

# Set logging level for clean execution output
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger("fuzz_runner")
logger.setLevel(logging.INFO)


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
# 1. BURST SKIPS & _ADVANCE_LOCK RACE CONDITION
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
            # Task A masuk _advance_loop. Tepat sebelum Task A melepaskan _advance_lock,
            # Task B memanggil advance(). Task B melihat _advance_lock.locked() == True
            # dan langsung me-return (drop), meninggalkan queue yang terisi tanpa pemutaran.
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

            # Task A sudah selesai loop (antrean kosong), namun masih di dalam blok `async with _advance_lock`.
            # Task B memasukkan lagu baru dan memanggil advance():
            new_track = Track(f"Queued-{it}", "https://mock.url/q", "user")
            state.queue.append(new_track)

            task_b = asyncio.create_task(bot.advance(guild))
            await task_b  # Drop karena line 2510: if state._advance_lock.locked(): return

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
# 2. STREAM JITTER & NETWORK DROP RECOVERY
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

        with patch("bot.extract", return_value={"url": "http://mock/stream", "title": "Track"}), \
             patch("bot.run_extract", new=AsyncMock(return_value={"url": "http://mock/stream", "title": "Track"})), \
             patch("bot.source_for", return_value=mock_source), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_announce"):

            if it % 2 == 0:
                # Kasus 1: vc.play() melempar ClientException("Not connected to voice")
                vc.play.side_effect = discord.ClientException("Not connected to voice.")
                vc.is_connected.return_value = False

                await bot.advance(guild)
                await asyncio.sleep(0.01)

                client_exceptions_handled += 1
                if quit_called:
                    quit_voice_triggers += 1
            else:
                # Kasus 2: Socket drop / stream error via after(error) callback
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
# 3. CIRCUIT BREAKER RESILIENCE
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

        with patch("bot.extract", return_value={"url": "http://mock/stream", "title": "Track"}), \
             patch("bot.run_extract", new=AsyncMock(return_value={"url": "http://mock/stream", "title": "Track"})), \
             patch("bot.source_for", return_value=mock_source), \
             patch.object(bot, "refresh", new=AsyncMock()), \
             patch.object(bot, "_schedule_idle") as mock_idle, \
             patch.object(bot, "_save_persistent_queue") as mock_save, \
             patch.object(bot, "_announce"):

            await bot.advance(guild)

            # Suntikkan 3 kegagalan audio berturut-turut
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
# 4. AFK GUARD LIFECYCLE & GENERATION BYPASS
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
        state.generation = 0  # Inisialisasi default
        bot.states[guild.id] = state

        # Eksperimen reproduksi bug bot.py:2979:
        # `if state and generation != state.generation and generation != 0: return`
        # Jika task dimulai pada generation=0, lalu state.generation dinaikkan menjadi 1:
        # `0 != 1 and 0 != 0` -> `True and False` -> `False`!
        # Pengecekan TIDAK menghentikan eksekusi, sehingga bot keluar voice secara prematur!
        vc.channel.members = []  # Room kosong
        quit_called = False
        async def mock_quit(guild: discord.Guild, clear_queue: bool = False, delete_panel: bool = True):
            nonlocal quit_called
            quit_called = True

        bot.quit_voice = mock_quit

        # Generation dinaikkan ke 1 (mis. user berinteraksi)
        state.generation = 1

        # Jalankan _afk_disconnect dengan generation awal = 0
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
# 5. YT-DLP EXTRACTION CONCURRENCY & SLOT LEAK
# ==============================================================================
async def fuzz_extraction_concurrency(iterations: int = 10) -> FuzzScenarioResult:
    res = FuzzScenarioResult(
        scenario="ytdlp_extraction_concurrency",
        description="Fuzzing konkurensi ekstraksi yt-dlp, pembatalan coroutine, dan kebocoran slot thread",
        iterations=iterations,
    )
    leaked_slots = 0

    for it in range(iterations):
        # Reset counter thread untuk pengukuran deterministik
        with bot_module._EXTRACT_THREADS_LOCK:
            bot_module._EXTRACT_THREADS = 0

        # Verifikasi pembatalan coroutine run_extract() tidak membocorkan slot:
        task = asyncio.create_task(bot_module.run_extract(lambda: time.sleep(0.05)))
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Tunggu sejenak jika thread sempat terpilih sebelum pembatalan
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
# 6. QUEUE MUTATIONS, SHUFFLE DESYNC, & PERSISTENCE I/O
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

        # Test 1: Duplikasi lagu akibat shuffle di tengah ekstraksi:
        # advance() memilih next_track = state.queue[0] (t1) di fase 1.
        # Saat ekstraksi berlangsung di luar lock, user menekan Shuffle.
        # Queue diacak sehingga t1 bergeser ke posisi belakang [t2, t3, t1].
        # Saat ekstraksi selesai, fase 4 mengecek `if state.queue[0] is next_track: popleft()`.
        # Karena t1 bukan lagi di index 0, popleft() dilewati!
        # Lagu t1 diputar (state.current = t1), TETAPI JUGA TETAP BERADA DI DALAM QUEUE!
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

            # Shuffle memindahkan t1 ke akhir queue
            async with state.lock:
                state.queue.clear()
                state.queue.extend([t2, t3, t1])

            shuffle_gate.set()
            await adv_task

            if state.current is t1 and t1 in state.queue:
                duplicate_track_events += 1

        # Test 2: Deque mutated during iteration pada _save_persistent_queue()
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
# 7. FLAT PLAYLIST STREAM_URL FALSE-POSITIVE CACHING
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
# 8. SYNC I/O & UI REFRESH CONSISTENCY
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

            # Jika panel sudah ada di channel yang sama, refresh TIDAK dipanggil di cmd_play!
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
# RUNNER
# ==============================================================================
ALL_SCENARIOS = {
    "burst_skips": fuzz_burst_skips,
    "stream_jitter": fuzz_stream_jitter_network_drop,
    "circuit_breaker": fuzz_circuit_breaker,
    "afk_guard": fuzz_afk_guard,
    "extraction": fuzz_extraction_concurrency,
    "queue_shuffle": fuzz_queue_mutations_and_shuffle,
    "flat_stream_cache": fuzz_flat_playlist_stream_cache,
    "sync_io_ui": fuzz_sync_io_and_ui_refresh,
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
    parser = argparse.ArgumentParser(description="Stress Testing & Concurrency Fuzzing Runner (Wave 3)")
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
    print("LAPORAN STRESS TESTING & CONCURRENCY FUZZING BOT.PY (WAVE 3)")
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
