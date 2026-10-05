# KAN-2 — Core: helper YouTube Mix di `bot.py`

**Assignee:** worker-A · **Prio:** P0 · **Depends:** KAN-1 (selesai) · **File:** `/opt/discord-music-bot/bot.py` (HANYA file ini)

## Tujuan
Tambahkan helper untuk mengekstrak **YouTube Mix (radio `list=RD`)** dari sebuah videoId, lalu mengembalikan daftar `Track`.

## Interface BEKU (jangan diubah — worker-B menulis tes terhadap ini)

```python
# Konstanta modul (dekat METADATA_OPTIONS)
MIX_RESULT_LIMIT = int(os.environ.get('MIX_RESULT_LIMIT', '15'))

def extract_video_id(url: str | None) -> str | None:
    """Ambil videoId YouTube (11 char) dari URL. None bila tidak bisa.
    Dukung: /watch?v=ID, youtu.be/ID, /embed/ID, /shorts/ID, /live/ID, music.youtube.com.
    Abaikan parameter list= / start_radio=."""

def build_mix_url(video_id: str) -> str:
    """https://www.youtube.com/watch?v={video_id}&list=RD{video_id}&start_radio=1"""

async def fetch_youtube_mix(video_id: str, exclude_urls: set[str] | None = None,
                            requester: str = 'AutoPlay',
                            limit: int | None = None) -> list[Track]:
    """Ambil lagu dari YouTube Mix untuk videoId.
    - limit default = MIX_RESULT_LIMIT (playlistend).
    - WAJIB playlistend=limit (tanpa ini ekstraksi ~20s).
    - Pakai _with_cookies(...) + js_runtimes.
    - Buang track yang url-nya ada di exclude_urls.
    - Buang livestream/dead entry (lewat _tracks_from_metadata / filter yang ada).
    - Kembalikan list[Track]; KOSONG bila gagal (JANGAN raise ke pemanggil)."""
```

## Langkah implementasi
1. Tambah `MIX_RESULT_LIMIT` setelah `METADATA_OPTIONS`/`STREAM_OPTIONS`.
2. Tambah `MIX_OPTIONS` = salinan `METADATA_OPTIONS` + `{'playlistend': ...}` (tanpa `noplaylist`).
   - `extract_flat` HARUS `'in_playlist'` (sudah ada di `METADATA_OPTIONS`).
3. Implement `extract_video_id` pakai `urllib.parse` (`urlparse`, `parse_qs`) + regex untuk `youtu.be/`, `/shorts/`, `/embed/`. **Jangan** import library baru.
4. Implement `build_mix_url` (1 baris f-string).
5. Implement `fetch_youtube_mix`:
   - Bangun URL via `build_mix_url`.
   - `async with EXTRACT_SEM: data = await asyncio.wait_for(asyncio.to_thread(_fetch_metadata_mix, url), timeout=60)` — atau panggil `_fetch_metadata` dengan opsi mix. **Sederhana:** buat `_fetch_mix_metadata(url, limit)` kecil yang memakai `yt_dlp.YoutubeDL(_with_cookies(MIX_OPTIONS_MENIT(limit)))`.
   - Tangkap `Exception` → `log.warning` → `return []`.
   - Parse lewat `_tracks_from_metadata(data, requester, url)` (fungsi ini SUDAH ada, dipakai `extract_tracks`). Tangkap `ValueError` → `return []`.
   - Filter `exclude_urls`.
6. Pastikan `MIX_OPTIONS` dihitung ulang bila `limit` berbeda (buat dict per-panggilan, jangan mutasi global).

## Bukti teknis (KAN-1) yang WAJIB dipatuhi
- Bentuk URL: `watch?v=<id>&list=RD<id>&start_radio=1` (bentuk `playlist?list=RD` GAGAL).
- `playlistend=15` → ~1.5s. Tanpa `playlistend` → ~20s (dilarang).
- ID invalid → `yt_dlp.utils.DownloadError` → harus ditelan jadi `return []`.

## Acceptance Criteria
- [ ] `extract_video_id('https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ&start_radio=1') == 'dQw4w9WgXcQ'`
- [ ] `extract_video_id('https://youtu.be/dQw4w9WgXcQ') == 'dQw4w9WgXcQ'`
- [ ] `extract_video_id('bukan url') is None`
- [ ] `build_mix_url('abc') == 'https://www.youtube.com/watch?v=abc&list=RDabc&start_radio=1'`
- [ ] `fetch_youtube_mix` mengembalikan `[]` (bukan raise) saat `_fetch_mix_metadata` melempar error.
- [ ] `fetch_youtube_mix` membuang URL di `exclude_urls`.
- [ ] Tidak ada import pihak ketiga baru.

## Verifikasi (jalankan sendiri sebelum lapor)
```bash
cd /opt/discord-music-bot
PYTHONPATH="" PYTHONHOME="" ./venv/bin/python -c "
from bot import extract_video_id, build_mix_url, MIX_RESULT_LIMIT
assert extract_video_id('https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ')=='dQw4w9WgXcQ'
assert extract_video_id('https://youtu.be/dQw4w9WgXcQ')=='dQw4w9WgXcQ'
assert extract_video_id('bukan url') is None
print('OK', MIX_RESULT_LIMIT, build_mix_url('abc'))
"
```

## Larangan
- JANGAN mengubah `advance()` (itu KAN-3).
- JANGAN mengubah `tests/` (itu worker-B).
- JANGAN commit / push — lead yang melakukan (KAN-7).
