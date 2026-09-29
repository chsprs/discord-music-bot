# Discord Music Bot (Lightweight & Ad-Free)

Bot musik Discord ultra-ringan (<50MB RAM) yang dirancang khusus untuk Linux SBC/STB ARM64 (Armbian) maupun VPS x86. Mengalirkan direct audio stream Opus dari YouTube / YouTube Music langsung ke voice socket Discord tanpa encoding video yang membebani CPU, serta dilengkapi web panel konfigurasi LAN mandiri (tanpa framework, Python stdlib).

---

## Fitur Utama

- **Hemat Memori & CPU:** Konsumsi RAM stabil ~46 MB pada arsitektur ARM64 / STB.
- **Bebas Iklan (Ad-Free):** Memutar direct stream audio dari CDN Google (`googlevideo.com`), bebas dari pre-roll dan mid-roll ads.
- **Dukungan Playlist Cepat:**
  - Mendukung link YouTube & YouTube Music playlist (`list=...`).
  - Metadata diekstrak secara instan (<2 detik) hingga 100 lagu.
  - Video private/dihapus otomatis dilewati tanpa crash (`ignoreerrors`).
  - Audio stream diekstrak secara *lazy* (hanya saat giliran lagu dimulai) agar URL CDN tidak kedaluwarsa dan menghemat bandwidth.
- **Dukungan Slash Commands Lengkap:**
  - `/musik` — Menampilkan panel interaktif (tombol kontrol UI).
  - `/play <lagu>` — Memutar lagu atau playlist langsung dari judul / URL.
  - `/skip` — Melewati lagu yang sedang diputar.
  - `/stop` — Menghentikan pemutaran dan mengeluarkan bot dari voice channel.
  - `/antrian` — Menampilkan daftar antrian lagu.
  - `/pause` — Menjeda atau melanjutkan pemutaran.
- **Web Control Panel Mandiri:**
  - Dijalankan via `panel.py` pada port `9130` (stdlib HTTP, CSRF-protected).
  - Memungkinkan input Bot Token dan Server ID langsung dari browser tanpa membuka terminal.
  - Mengontrol service (`start` / `restart` / `stop`) via tombol web.
- **Auto-Sync & Auto-Start:**
  - Sinkronisasi otomatis ke seluruh server Discord yang terhubung dan auto-sync saat bot diundang ke server baru (`on_guild_join`).
  - Service systemd terintegrasi untuk otomatis aktif saat STB / server boot.

---

## Instalasi Cepat (One-Line / Ready to Use)

Jalankan perintah berikut di terminal Linux STB / VPS kamu:

```bash
git clone https://github.com/chsprs/discord-music-bot.git /opt/discord-music-bot
cd /opt/discord-music-bot
sudo ./install.sh
```

Skrip installer otomatis:
1. Memeriksa dan menginstal dependensi OS (`python3`, `ffmpeg`, `nodejs`, dll.).
2. Menyiapkan Python virtual environment dan dependensi `pip`.
3. Memasang unit systemd `discord-music.service` dan `discord-music-panel.service`.
4. Mengaktifkan auto-start saat server boot.
5. Menjalankan unit test mandiri (37/37 passing).
6. Menyalakan Web Control Panel di port `9130`.

---

## Langkah Penggunaan

1. Buka browser di perangkat yang satu jaringan LAN:
   ```
   http://<IP_SERVER_STB>:9130
   ```
2. Masukkan **Bot Token** dan **Guild ID** (Server ID Discord).
3. Klik **Simpan konfigurasi**, lalu klik **Nyalakan bot**.
4. Masuk ke Voice Channel di Discord, lalu ketik `/musik` atau `/play <judul/url>`.

---

## Konfigurasi Discord Developer Portal

Saat membuat bot di [Discord Developer Portal](https://discord.com/developers/applications):

1. **OAuth2 / Installation:**
   - **Installation Contexts**: Centang **Guild Install**.
   - **Scopes**: Centang `bot` dan `applications.commands`.
   - **Permissions**: Centang:
     - `View Channels`
     - `Send Messages`
     - `Embed Links`
     - `Attach Files`
     - `Read Message History`
     - `Connect`
     - `Speak`
2. **Privileged Gateway Intents:**
   - Tidak memerlukan *Message Content Intent* karena bot 100% menggunakan Slash Commands dan Button Interaction.
3. **Link Undangan Bot:**
   ```
   https://discord.com/oauth2/authorize?client_id=<YOUR_CLIENT_ID>&scope=bot+applications.commands&permissions=2150714368
   ```

---

## Struktur Berkas

```
/opt/discord-music-bot/
├── bot.py                      # Core bot Discord (audio pipeline, queue, commands)
├── panel.py                    # Web Control Panel LAN (stdlib HTTP)
├── requirements.txt            # Dependensi Python
├── install.sh                  # Skrip instalasi otomatis
├── discord-music.service       # Service systemd bot musik
├── discord-music-panel.service # Service systemd panel web
├── .env.example                # Templat konfigurasi
├── .gitignore
├── README.md
└── tests/
    ├── test_bot.py             # Unit test core bot & commands (mocked API)
    └── test_panel.py           # Unit test web panel & CSRF
```

---

## Pengujian Mandiri

Jalankan seluruh rangkaian tes:

```bash
cd /opt/discord-music-bot
PYTHONPATH=. ./venv/bin/python -m unittest discover -s tests -v
```

---

## Lisensi

MIT License. Dibuat untuk performa andal dan konsumsi daya rendah di lingkungan homelab STB Armbian.
