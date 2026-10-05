# 🤝 BRIEFING WORKER — Aturan Umum (WAJIB DIBACA SEBELUM KERJA)

Kamu adalah worker pada epic **"Upgrade AutoPlay ke YouTube Mix"** di repo `/opt/discord-music-bot`.
Kerjakan **HANYA kartu yang diberikan**, dan **HANYA file yang tertera di kartu**.

## Aturan emas
1. **Satu kartu = satu scope.** Jangan "sekalian memperbaiki" hal lain.
2. **Hormati kepemilikan file:**
   - `bot.py` → **worker-A** (KAN-2, KAN-3) + worker-C (hanya teks help KAN-4)
   - `tests/test_bot.py` → **worker-B** (KAN-5)
   - `README.md` / `.env.example` → **worker-C** (KAN-4)
   - Jangan ada dua worker menulis file yang sama.
3. **JANGAN commit, JANGAN push, JANGAN restart service.** Lead yang melakukannya (KAN-7).
4. **Interface beku.** Tanda tangan fungsi di kartu adalah kontrak; jangan diubah tanpa izin lead.
5. **Jalankan perintah verifikasi di kartu** dan tempel outputnya saat lapor.
6. Kalau interface yang kamu butuhkan belum ada → **berhenti dan lapor**, jangan bikin stub.

## Lingkungan
- Python venv: `./venv/bin/python`
- Selalu jalankan dengan `PYTHONPATH="" PYTHONHOME=""` (mencegah kontaminasi env).
- Tes: `PYTHONPATH="" PYTHONHOME="" ./venv/bin/python -m unittest discover -s tests -p "test_*.py"`
- yt-dlp versi: `2026.08.19`

## Fakta teknis terverifikasi (JANGAN diragukan, sudah diuji di box)
- ✅ `https://www.youtube.com/watch?v=<id>&list=RD<id>&start_radio=1` → radio asli YouTube.
- ❌ `https://www.youtube.com/playlist?list=RD<id>` → error "playlist type is unviewable".
- ⏱️ Tanpa `playlistend` → ~20s. Dengan `playlistend=15` → ~1.5s. **Wajib pakai `playlistend`.**
- 🚫 VideoId invalid → `yt_dlp.utils.DownloadError` → tangkap dan kembalikan `[]`.

## Format laporan balik ke lead
```
KARTU: KAN-X
STATUS: selesai | terblokir
FILE DIUBAH: <daftar>
BUKTI: <tempel output perintah verifikasi>
CATATAN: <hambatan / keputusan>
```
