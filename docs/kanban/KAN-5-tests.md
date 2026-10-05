# KAN-5 — Tes: YouTube Mix (unit + integrasi)

**Assignee:** worker-B · **Prio:** P1 · **Depends:** interface KAN-2/KAN-3 **beku** · **File:** `/opt/discord-music-bot/tests/test_bot.py` (HANYA file ini)

## Tujuan
Tambah tes untuk helper Mix dan integrasi AutoPlay, **tanpa** memanggil jaringan (mock `yt_dlp.YoutubeDL`).

## Interface yang diuji (BEKU dari KAN-2/KAN-3)
```python
from bot import (extract_video_id, build_mix_url, fetch_youtube_mix,
                 MIX_RESULT_LIMIT, fetch_recommendations)
```

## Tes wajib (tambahkan ke class `AutoplayRecommendationTests` atau class baru `YouTubeMixTests`)

1. **`test_extract_video_id_variants`**
   - `watch?v=ID`, `youtu.be/ID`, `/shorts/ID`, `/embed/ID`, `music.youtube.com/watch?v=ID`
   - `'bukan url'` → `None`, `''` → `None`, `None` → `None`
2. **`test_build_mix_url_format`**
   - `build_mix_url('abc') == 'https://www.youtube.com/watch?v=abc&list=RDabc&start_radio=1'`
3. **`test_fetch_youtube_mix_parses_entries`**
   - Mock `bot.yt_dlp.YoutubeDL` → `extract_info` mengembalikan `{'entries': [...]}` (judul+url+id).
   - Pastikan `playlistend` dipakai (assert `YoutubeDL` dipanggil dengan opsi berisi `playlistend` = `MIX_RESULT_LIMIT` atau limit yang diminta). **Gunakan pola mock yang sama dengan `test_extract_tracks_playlist_skips_none_and_caps`.**
4. **`test_fetch_youtube_mix_returns_empty_on_error`**
   - `extract_info.side_effect = bot_module.yt_dlp.utils.DownloadError('boom')`
   - Hasil harus `[]` (TIDAK raise).
5. **`test_fetch_youtube_mix_filters_exclude_urls`**
   - Satu entri URL-nya ada di `exclude_urls` → tersaring.
6. **`test_fetch_recommendations_prefers_mix_when_seed_urls`**
   - `seed_urls=['https://youtube.com/watch?v=abc']`, patch `bot.fetch_youtube_mix` (AsyncMock) mengembalikan 1 track → hasil = track itu, dan `bot._fetch_metadata`/pencarian teks **tidak** dipanggil.
7. **`test_fetch_recommendations_falls_back_to_text_when_mix_empty`**
   - `fetch_youtube_mix` → `[]`, patch `bot._fetch_metadata` → hasil teks tetap keluar.

## Aturan penulisan
- Ikuti gaya file: `unittest.TestCase`, `MagicMock`, `AsyncMock`, `patch`.
- Jalankan tiap tes baru secara terisolasi dulu.
- **JANGAN** memodifikasi tes lama.
- **JANGAN** menyentuh `bot.py`. Bila interface belum ada saat mulai → **berhenti & lapor** ke lead (jangan bikin stub di `bot.py`).

## Verifikasi
```bash
cd /opt/discord-music-bot
PYTHONPATH="" PYTHONHOME="" ./venv/bin/python -m unittest tests.test_bot.YouTubeMixTests tests.test_bot.AutoplayRecommendationTests -v
```

## Acceptance Criteria
- [ ] ≥ 7 tes baru, semuanya lulus.
- [ ] Tidak ada tes yang menyentuh jaringan nyata.
- [ ] Tes lama tetap lulus.

## Larangan
- JANGAN ubah `bot.py` / `README.md`. JANGAN commit.
