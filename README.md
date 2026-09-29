# Discord Music Bot

Bot Discord ringan: `/musik` sekali untuk masuk voice dan mengirim panel. Setelah itu gunakan tombol **Cari / Tambah**, **Jeda / Lanjut**, **Lewati**, **Antrian**, **Stop**. Pencarian lewat modal; pencarian judul memakai YouTube, URL `music.youtube.com` juga didukung.

## Status

Kode dan uji lokal siap. **Belum login ke Discord; belum ada token, guild ID, atau pengujian voice end-to-end.** Service belum dipasang/diaktifkan. Penggunaan RAM/CPU nyata belum diukur; klaim `<100 MB` dan `<3%` dari percakapan sebelumnya bukan hasil pengukuran.

## Syarat

- Python 3.11, `ffmpeg`, Node.js >=22, libopus, dan `requirements.txt` dalam venv.
- Discord Developer Portal: buat aplikasi/bot, undang dengan scope `bot` + `applications.commands`; izinkan `View Channel`, `Send Messages`, `Embed Links`, `Connect`, `Speak`. Privileged Message Content intent **tidak diperlukan**.
- Simpan token **lokal**, jangan tempel di Telegram atau Git. Buat `/opt/discord-music-bot/.env` mode `0600` dengan `DISCORD_TOKEN=...` dan opsional `DISCORD_GUILD_ID=...` (ID server uji). Admin harus mengisi langsung di mesin melalui input rahasia, bukan lewat chat.
- Unit contoh ada di `discord-music.service`; pasang dan aktifkan hanya sesudah izin layanan eksplisit. `DynamicUser=yes`, runtime cache di `/run/discord-music`, kode read-only. Logging ke journal.

## Panel web (LAN)

`panel.py` — panel lokal stdlib-only di `http://192.168.1.100:9130`.

- Login wajib (password dari `PANEL_PASSWORD`). Sesi memakai HMAC, bukan password mentah.
- Menampilkan status service bot, menyimpan `DISCORD_TOKEN` dan `DISCORD_GUILD_ID` ke `.env` mode `0600`. Token **tidak pernah** ditampilkan kembali.
- Tombol **Nyalakan / Mulai ulang / Matikan** memanggil `systemctl` untuk `discord-music.service`.
- CSRF: POST tanpa `Origin` yang cocok ditolak; metode selain GET/HEAD/POST dibalas `405`.

Jalankan manual (uji):

```bash
PANEL_PASSWORD='pilih-sandi-kuat' PANEL_PORT=9130 \
  /opt/discord-music-bot/venv/bin/python /opt/discord-music-bot/panel.py
```

Sebagai service: simpan sandi di `/opt/discord-music-panel.env` (`PANEL_PASSWORD=...`, mode `600`), lalu pasang `discord-music-panel.service`. **Belum dipasang/diaktifkan.**

> Peringatan: HTTP di LAN tidak mengenkripsi sandi/token saat dikirim dari browser. Pakai hanya di jaringan rumah tepercaya; jangan buka port ini ke internet.

## Verifikasi sebelum aktivasi

```bash
PYTHONPATH=/opt/discord-music-bot /opt/discord-music-bot/venv/bin/python -m unittest discover -s /opt/discord-music-bot/tests -v
systemd-analyze verify /opt/discord-music-bot/discord-music.service
```

## Batasan

- Antrian ada di RAM; restart bot menghapus antrian. Tombol panel lama tetap merespons karena persistent view; panel dipulihkan saat ditekan.
- URL CDN diambil ulang tepat saat lagu diputar agar tautan tidak kedaluwarsa di antrian.
- Preferensi Opus WebM; kalau tidak tersedia, FFmpeg transcode ke Opus. Kualitas dibatasi sumber YouTube, Discord, dan setelan voice channel; **bukan** lossless atau jaminan bebas iklan/akses permanen. YouTube dapat mengubah extractor/menolak stream.
- Satu sesi voice per server. Auto-keluar sesudah 3 menit tanpa lagu, atau setelah 15 detik tanpa pendengar. Tidak mendukung volume/seek/playlist persisten.
