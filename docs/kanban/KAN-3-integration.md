# KAN-3 — Integrasi AutoPlay ke YouTube Mix di `advance()`

**Assignee:** worker-A · **Prio:** P0 · **Depends:** KAN-2 · **File:** `/opt/discord-music-bot/bot.py` (HANYA file ini)

## Tujuan
Saat antrian/playlist habis dan AutoPlay aktif, utamakan **YouTube Mix** (radio) berbasis lagu yang sedang diputar / riwayat; bila gagal → fallback ke pencarian teks lama.

## Interface BEKU
`fetch_recommendations` ditambah parameter opsional (WAJIB backward-compatible):

```python
async def fetch_recommendations(history_titles: list[str], exclude_urls: set[str],
                                requester: str = 'AutoPlay',
                                seed_urls: list[str] | None = None) -> list[Track]:
```

**Perilaku baru `fetch_recommendations`:**
1. **Jika `seed_urls` diisi:** iterasi `seed_urls` (terbaru dulu) → `extract_video_id` → `fetch_youtube_mix(vid, exclude_urls, requester)`. Kembalikan kandidat pertama yang **non-kosong**. (Radio nyata = paling relevan.)
2. **Fallback:** bila `seed_urls` kosong / semua mix kosong → jalankan logika lama (kueri `ytsearch5: ...` dari `build_recommendation_queries`).
3. Tetap dedup & filter `exclude_urls`.

## Langkah implementasi di `advance()` (fase 2 AutoPlay)
Ganti blok fase 2 agar:
```python
async with state.lock:
    seed_titles = [t.title for t in list(state.history)[-5:]]
    seed_urls   = [t.url   for t in list(state.history)[-5:]]
    if state.current:
        seed_titles.append(state.current.title)
        seed_urls.append(state.current.url)
    played_urls = {t.url for t in list(state.history)[-20:]}
    if state.current:
        played_urls.add(state.current.url)
candidates = await fetch_recommendations(seed_titles, played_urls, seed_urls=seed_urls)
next_track = next((c for c in candidates if c.url not in played_urls), None)
if next_track is None:
    log.info('AutoPlay: tidak ada rekomendasi baru, pemutaran berhenti.')
    break
log.info('AutoPlay (Mix) memilih: %s', next_track.title)
```
- **Pertahankan** struktur `try/except`, lock-safety (resolve di luar `state.lock`), dan `break` yang sudah ada.
- **Jangan** menyentuh fase 1 / 3 / 4.

## Acceptance Criteria
- [ ] `advance()` mengirim `seed_urls` berisi URL lagu aktif + riwayat terakhir.
- [ ] Bila `fetch_youtube_mix` mengembalikan kandidat baru → diputar (bukan lagu yang sudah diputar).
- [ ] Bila semua kandidat sudah pernah diputar → `break` (bot berhenti rapi, tidak mengulang).
- [ ] Bila mix gagal total → fallback teks masih jalan (tidak ada regresi tes lama).
- [ ] Tidak ada deadlock: `fetch_recommendations` dipanggil **di luar** `state.lock`.

## Verifikasi
```bash
cd /opt/discord-music-bot
PYTHONPATH="" PYTHONHOME="" ./venv/bin/python -m unittest tests.test_bot.AutoplayRecommendationTests -v
```
Semua tes lama AutoplayRecommendationTests HARUS tetap lulus.

## Larangan
- JANGAN ubah tanda tangan `fetch_youtube_mix` / `extract_video_id` (KAN-2 beku).
- JANGAN ubah `tests/`. JANGAN commit.
