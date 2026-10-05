# KAN-4 — Dokumentasi: README + `.env.example`

**Assignee:** worker-C · **Prio:** P2 · **Depends:** — · **File:** `/opt/discord-music-bot/README.md`, `/opt/discord-music-bot/.env.example` (**HANYA dua file ini**)

> ⚠️ **JANGAN sentuh `bot.py`** — worker-A memegang file itu. Teks `/help` sudah diubah lead.

## Tujuan
Dokumentasikan AutoPlay berbasis **YouTube Mix** dan variabel `MIX_RESULT_LIMIT`.

## Perubahan wajib

### 1. `README.md`
- Baris fitur AutoPlay (sekitar baris 48) → jelaskan sumber **YouTube Mix (`list=RD`, algoritma radio resmi YouTube)**, dengan **fallback pencarian teks**, dan **anti-ulang** lagu yang pernah diputar.
- Tabel tombol AutoPlay (sekitar baris 90) → sebut "berbasis YouTube Mix".
- Tabel env var (bila ada) → tambahkan `MIX_RESULT_LIMIT` (default `15`).
- **JANGAN** ubah badge jumlah tes / "Ran N tests" — itu tanggung jawab lead (KAN-6).

### 2. `.env.example`
- Tambahkan blok komentar + contoh:
  ```
  # Jumlah lagu yang diambil dari YouTube Mix tiap rekomendasi (1-50, default 15).
  # Makin besar makin banyak pilihan tapi ekstraksi makin lambat.
  #MIX_RESULT_LIMIT=15
  ```
- Ikuti gaya file yang ada (komentar `#`, tanpa spasi di sekitar `=`).

### 3. `bot.py` — HANYA teks help
- Baris `'`/autoplay` — rekomendasi otomatis ...'` di `cmd_help` → sebut "YouTube Mix".
- **JANGAN** sentuh logika `advance()` / helper mix. Bila worker-A belum selesai, cukup ubah teks help; jangan tambahkan kode.

## Acceptance Criteria
- [ ] README menyebut YouTube Mix + fallback + anti-ulang.
- [ ] `.env.example` memuat `MIX_RESULT_LIMIT` dengan komentar.
- [ ] `/help` menyebut YouTube Mix.
- [ ] Tidak ada perubahan kode fungsional di `bot.py`.

## Verifikasi
```bash
cd /opt/discord-music-bot
grep -n "Mix\|MIX_RESULT_LIMIT" README.md .env.example bot.py
```

## Larangan
- JANGAN ubah badge tes / angka "Ran N tests".
- JANGAN ubah `tests/`. JANGAN commit.
