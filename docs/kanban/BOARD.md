# 📋 KANBAN BOARD — Upgrade AutoPlay ke YouTube Mix (Radio RD)

**Epic:** Ganti algoritma rekomendasi AutoPlay dari *text-search heuristic* menjadi **YouTube Mix (`list=RD`)** — algoritma radio resmi YouTube, dengan fallback ke pencarian teks.
**Repo:** `/opt/discord-music-bot` · **Branch:** `feat-autoplay-ytmusic-mix` → merge ke `main` + `tes` · **Status: ✅ SELESAI**

---

## Kolom

| Backlog | Ready | In Progress | Review | Done |
|---|---|---|---|---|
| — | — | — | — | KAN-1 … KAN-7 ✅ |

---

## Kartu

| ID | Judul | Assignee | Prio | Depends | Kolom |
|---|---|---|---|---|---|
| **KAN-1** | Discovery & de-risk: verifikasi ekstraksi YouTube Mix | lead | P0 | — | ✅ Done |
| **KAN-2** | Core: helper `extract_video_id` / `build_mix_url` / `fetch_youtube_mix` | **worker-A** | P0 | KAN-1 | ✅ Done |
| **KAN-3** | Integrasi: `advance()` AutoPlay pakai Mix + fallback teks | **worker-A** | P0 | KAN-2 | ✅ Done |
| **KAN-4** | Docs: README + `.env.example` | **worker-C** | P2 | — | ✅ Done |
| **KAN-5** | Tests: unit + integrasi YouTube Mix (13 tes) | **worker-B** | P1 | interface beku | ✅ Done |
| **KAN-6** | Verifikasi: full suite (237/237) + smoke test radio nyata | lead | P0 | KAN-2..5 | ✅ Done |
| **KAN-7** | Deploy: commit → push `main`+`tes` → restart service | lead | P0 | KAN-6 | ✅ Done |

> **Catatan WIP:** KAN-2 & KAN-3 satu penulis (`worker-A`, file `bot.py`). KAN-5 (`worker-B`) menulis `tests/test_bot.py`. KAN-4 (`worker-C`) menulis `README.md` + `.env.example`. **Tidak ada dua worker yang menulis file yang sama.**

---

## Hasil Discovery (KAN-1) — bukti nyata di box

```
watch?v=kJQP7kiw5Fk&list=RDkJQP7kiw5Fk   → OK, 410 entri (~20s)   → playlistend=15 = ~1.5s
watch?v=...&list=RD...&start_radio=1      → OK, radio asli (Despacito → Bailando → Danza Kuduro)
playlist?list=RDkJQP7kiw5Fk               → ERROR "playlist type is unviewable"  ❌ JANGAN DIPAKAI
watch?v=zzzzzzzzzzz&list=RDzzzzzzzzzzz    → DownloadError "video is unavailable" → fallback aman
```

**Kesimpulan:** pakai bentuk `watch?v=<id>&list=RD<id>&start_radio=1`, wajib `playlistend` untuk hemat waktu.

### Smoke test (KAN-6) — jalur jaringan nyata
- Seed Despacito → **14 track / 2.5s**, hasil algoritmik asli (Ed Sheeran, Chainsmokers, Clean Bandit, Shawn Mendes); seed tersaring (anti-ulang) ✅
- Fallback: seed bukan URL YouTube → 5 track via pencarian teks ✅
- Backward-compat: `seed_urls` kosong → jalur teks lama tetap jalan ✅

---

## Definition of Done (Epic) — semua ✅
- [x] AutoPlay mengutamakan YouTube Mix; bila gagal → fallback pencarian teks (perilaku lama).
- [x] Tidak mengulang lagu yang sudah diputar (filter URL).
- [x] Full test suite hijau: **237/237**.
- [x] Smoke test radio nyata sukses di box.
- [x] README + `.env.example` + `/help` diperbarui.
- [x] Merge ke `main` + `tes`, service `discord-music.service` restart & online.
