# 🎵 Discord Music Bot (Lightweight, Ad-Free & Studio Quality)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-v2.7-5865F2?logo=discord&logoColor=white)](https://discordpy.readthedocs.io/)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-pinned-red)](https://github.com/yt-dlp/yt-dlp)
[![Tests](https://img.shields.io/badge/Tests-544%2F544%20Passing-brightgreen)](https://github.com/chsprs/discord-music-bot)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux%20ARM64%20%7C%20x86__64-orange)](https://armbian.com)
[![RAM Usage](https://img.shields.io/badge/RAM-%3C50MB-success)](#performa--arsitektur)

Bot musik Discord ultra-ringan, hemat sumber daya (<50MB RAM), dan bebas iklan yang dirancang khusus untuk homelab Linux SBC/STB ARM64 (Armbian, Raspberry Pi) maupun VPS x86. Mengalirkan direct audio stream Opus dari YouTube & YouTube Music langsung ke voice socket Discord dengan kualitas audio tinggi, kontrol panel interaktif modern, dan web panel manajemen LAN tanpa ketergantungan framework berat.

---

## 📸 Tampilan Antarmuka

### 🎧 Discord Player (Interactive Music Panel)
Tampilan panel interaktif modern di voice/text channel Discord dengan 10 tombol kontrol realtime, indikator bitrate/codec, dan informasi metadata lagu.

![Discord Player UI](assets/screenshots/discord-player-ui.png)

### 🖥️ Web Control Panel Mandiri (Port 9130)
Dashboard web lokal ringan untuk pemantauan runtime, kontrol service, konfigurasi token/server, dan log pembaruan otomatis tanpa perlu akses SSH terminal.

| Desktop Dashboard | Mobile Responsive |
| :---: | :---: |
| ![Web Dashboard Desktop](assets/screenshots/web-panel-dashboard.png) | ![Web Dashboard Mobile](assets/screenshots/web-panel-mobile.png) |

---

## ✨ Fitur Utama

- **Hemat Memori & CPU:** Konsumsi RAM stabil ~46 MB pada arsitektur STB ARM64 (Amlogic S905X / H96 Max / HG680P) tanpa beban video rendering. Bot hanya berlangganan event gateway yang dipakai (`guilds`, `voice_states`, `dm_messages`) dan tidak menyimpan cache pesan, jadi obrolan ramai di server tidak membebani CPU/RAM STB.
- **Bebas Iklan (Ad-Free):** Memutar direct stream audio dari CDN Google (`googlevideo.com`), bebas dari gangguan pre-roll dan mid-roll iklan.
- **Kualitas Audio Studio (Studio Quality):**
  - Profil enkoder Opus full-band (`-application audio`) dengan kualitas kompresi algoritma maksimal (`-compression_level 10`).
  - Penyesuaian bitrate dinamis otomatis mengikuti kapasitas bitrate voice channel Discord server (hingga 96–128 kbps).
  - Variable Bitrate (`-vbr on`) menjaga dinamika bass, treble, dan vokal tetap jernih tanpa clipping.
- **Pengaturan Volume Realtime:**
  - Slider/step volume via tombol `Down` (-10%) dan `Up` (+10%) hingga 200%.
  - Menggunakan `PCMVolumeTransformer` terintegrasi libopus C-native sehingga volume berubah seketika tanpa jeda pemuatan ulang lagu.
- **Dukungan Playlist & Pencarian Kilat:**
  - Mendukung tautan video tunggal maupun playlist YouTube / YouTube Music (`list=...`).
  - Ekstraksi metadata instan (<2 detik) hingga 100 lagu per playlist.
  - Video private / dihapus otomatis dilewati tanpa menghentikan pemutaran (`ignoreerrors`).
  - **Tanpa jeda antar lagu:** stream lagu berikutnya (antrean, loop, atau kandidat AutoPlay) disiapkan di latar belakang ±60 detik sebelum lagu yang sedang diputar habis, sehingga lagu berikutnya langsung mulai tanpa menunggu ekstraksi (±2–4 detik di server x86, lebih lama di STB). Kesegaran URL CDN dicek dari parameter `expire` milik YouTube, jadi URL yang masih berlaku tidak diekstraksi ulang.
- **Fitur Cerdas (AutoPlay, Loop, Shuffle & History):**
  - **AutoPlay (YouTube Mix):** Saat antrian/playlist habis, bot mengambil rekomendasi langsung dari **YouTube Mix** — algoritma radio resmi YouTube (`watch?v=<id>&list=RD<id>&start_radio=1`) yang di-seed dari lagu yang baru diputar, sehingga hasilnya mengikuti "radio" asli YouTube, bukan sekadar pencarian kata kunci. Bila ekstraksi Mix gagal (video tak tersedia / radio tidak dapat dibuka), bot otomatis **fallback ke pencarian teks** berbasis riwayat lagu sebelumnya. Semua kandidat disaring terhadap lagu yang pernah diputar (**anti-ulang**) agar tidak mengulang lagu yang sama; bila tidak ada kandidat baru, pemutaran berhenti dengan rapi. Jumlah lagu yang ditarik per rekomendasi diatur lewat `MIX_RESULT_LIMIT` (default `15`).
  - **Loop Mode:** Siklus pengulangan 3-arah: *Track* (ulang 1 lagu), *Queue* (ulang seluruh antrian), atau *Off*.
  - **Shuffle:** Mengacak urutan antrian lagu seketika secara acak.
  - **History Backtracking:** Menyimpan riwayat lagu yang baru diputar agar tombol `Back` dapat memutar ulang lagu sebelumnya.
- **AFK Guard (Auto-Disconnect & Hemat Daya):**
  - Bot otomatis mendeteksi saat tidak ada pendengar manusia di dalam voice channel.
  - Memulai timer tunggu (default 3 menit via `AFK_TIMEOUT_SECONDS`), otomatis melanjutkan lagu jika ada user yang masuk kembali, atau mematikan proses FFmpeg dan disconnect voice jika room tetap kosong guna menghemat CPU dan RAM STB.
- **Persistent Queue (Antrean Tahan Restart):**
  - Antrean lagu dan track yang sedang berjalan otomatis dicadangkan ke tmpfs (`/run/discord-music/queue_state.json`).
  - Saat bot di-restart (pembaruan mingguan, tombol **Mulai ulang** di panel, `systemctl restart`, atau crash yang di-restart otomatis), antrean dipulihkan; lagu yang sedang diputar kembali ke urutan pertama antrean. Unit memakai `RuntimeDirectoryPreserve=restart` agar berkas ini tidak dihapus systemd saat restart.
  - Karena disimpan di tmpfs (hemat tulis eMMC), antrean **tidak** bertahan saat server reboot atau saat service dihentikan penuh (`systemctl stop` / tombol **Matikan**).
- **Web Control Panel Mandiri & Pemantau Server/Pengguna:**
  - Web dashboard di port `9130` (dibangun murni dengan Python standard library HTTP, aman dengan proteksi CSRF token & nonce).
  - Konfigurasi token bot & ID server Discord langsung dari browser tanpa perlu SSH ke server.
  - Monitor status service & tombol kontrol start / restart / stop service dari web.
  - **Pemantau Server & Pengguna Aktif:** Menampilkan daftar server Discord yang dimasuki bot, channel voice yang sedang tersambung, judul lagu & antrean yang sedang berputar, serta jumlah & nama pengguna yang sedang mendengarkan secara realtime.
  - **Tombol Pembaruan Manual:** Jalankan `discord-music-update.service` (sebagai user `discord-music-updater`, bukan root) lewat tombol web lengkap dengan riwayat log keluaran terminal. Panel sendiri berjalan dengan `python3` sistem (stdlib saja), tidak memakai interpreter venv.
  - **Pembaruan Bot dari GitHub (manual):** Tombol **Cek pembaruan** menampilkan commit baru di branch `main` beserta file yang berubah; tombol **Terapkan pembaruan** menjalankan `discord-music-deploy.service` (lihat [Memperbarui Bot dari Web Panel](#-memperbarui-bot-dari-web-panel)).
  - **Pemantau Log Realtime:** Kotak log aktivitas bot (`journalctl`) yang dapat disegarkan langsung dari antarmuka web.
- **Auto-Update Mingguan yang Aman:**
  - **Systemd Timer Mingguan:** Setiap Minggu pukul 04:00 WIB, `discord-music-update.service` berjalan sebagai user khusus non-root `discord-music-updater` (bukan root).
  - **Hash-locked install:** Pembaruan memakai `pip install --require-hashes -r requirements.txt`. Setiap paket diverifikasi SHA-256 sebelum dipasang; paket yang hash-nya tidak cocok ditolak. `requirements.txt` di-generate dari `requirements.in` lewat `uv pip compile --universal --generate-hashes` sehingga satu lockfile berlaku untuk Python 3.10–3.13+ (termasuk dependensi bermarker seperti `audioop-lts` di Python 3.13).
  - **Restart hanya bila versi berubah:** Bot di-restart hanya jika versi yt-dlp terpasang benar-benar berubah. Bila tidak ada perubahan, updater keluar tanpa restart.
  - **Restart Aman Saat Ada Pendengar:** Bila masih ada yang mendengarkan musik (dibaca dari `listeners.json` yang world-readable), restart ditunda agar pemutaran tidak terputus; versi yt-dlp baru dipakai pada restart berikutnya.
  - **Integrasi JS Engine:** Terhubung ke Node.js runtime untuk menyelesaikan challenge player API YouTube (EJS) tanpa pesan warning deprecation. Skrip setup NodeSource diverifikasi SHA-256 statis sebelum dieksekusi `install.sh`.

## 🌐 Memperbarui Bot dari Web Panel

Bagian **Pembaruan Bot dari GitHub** di panel memperbarui kode bot ke versi terbaru branch `main`, tanpa SSH:

1. **Cek pembaruan** menjalankan `deploy.sh check`: `git fetch` lalu menampilkan commit baru, file yang berubah, dan tindakan yang akan dilakukan. Belum ada yang diubah.
2. **Terapkan pembaruan** menjalankan `discord-music-deploy.service` (`deploy.sh apply`, sebagai root) di latar belakang, lalu mencatat prosesnya ke `last_deploy.log` yang tampil di panel:
   - hanya *fast-forward* dari `origin/main`; ditolak bila ada perubahan lokal pada file yang dilacak git atau riwayat lokal berbeda;
   - `requirements.txt` berubah → `pip install --require-hashes` sebagai `discord-music-updater`;
   - menjalankan seluruh unit test sebagai `discord-music-updater`; **tes atau pip gagal → kode otomatis dikembalikan** ke commit sebelumnya dan bot tetap memakai versi lama;
   - unit systemd berubah → disalin ke `/etc/systemd/system` + `daemon-reload`;
   - `bot.py`/`requirements.txt` berubah → bot di-restart, **ditunda bila ada pendengar** (tekan *Mulai ulang* saat room kosong); `panel.py` berubah → panel di-restart.

Pembaruan tidak pernah berjalan otomatis; unit ini sengaja tanpa `[Install]` dan tanpa timer.

> [!IMPORTANT]
> Siapa pun yang bisa merge/push ke `main` di GitHub bisa menjalankan kode sebagai root di server lewat tombol ini. Aktifkan **2FA** di akun GitHub, jangan menambah collaborator sembarangan, dan lindungi `main` dengan ruleset (Settings → Rules → Rulesets: *Restrict deletions*, *Block force pushes*, *Require a pull request before merging*). Selalu periksa daftar commit di **Cek pembaruan** sebelum menerapkan.

Instalasi lama yang belum punya fitur ini perlu diperbarui manual sekali (`git pull` + `sudo ./install.sh`) agar `discord-music-deploy.service` terpasang. Fitur ini butuh `/opt/discord-music-bot` berupa checkout git (instalasi dengan `git clone` seperti di bawah).

## 🔄 Memperbarui yt-dlp (Untuk Maintainer)

Timer mingguan tidak menaikkan versi sendiri — ia hanya memasang versi yang ter-pin di `requirements.txt`. Untuk bump yt-dlp ke rilis terbaru:

```bash
# Di mesin dev (butuh uv). --universal WAJIB: tanpa itu lockfile hanya berlaku
# untuk versi Python yang menjalankan compile dan install gagal di versi lain.
uv pip compile requirements.in --universal --generate-hashes --python-version 3.10 \
    --upgrade-package yt-dlp -o requirements.txt
git add requirements.txt
git commit -m "chore: bump yt-dlp"
git push
```

```bash
# Di STB/server:
cd /opt/discord-music-bot
git pull
sudo -u discord-music-updater ./update.sh   # atau tunggu timer mingguan / tekan tombol update di panel
```

`update.sh` memverifikasi semua hash, memasang versi baru, dan me-restart bot bila tidak ada pendengar aktif.
- **Cookies Opsional (video age-restricted):** Taruh `cookies.txt` di direktori bot (atau set `YTDLP_COOKIES` di `.env`) untuk memutar video yang butuh login. Berkas dibaca ulang tiap ekstraksi, jadi tidak perlu restart. `cookies.txt` berisi sesi login — sudah masuk `.gitignore`, perlakukan seperti password.
- **Auto-Sync & Auto-Start:**
  - Sinkronisasi slash command otomatis ke seluruh server Discord saat bot dinyalakan atau diundang ke server baru (`on_guild_join`).
  - Service systemd terintegrasi untuk otomatis jalan saat server / STB dinyalakan ulang.

---

## 🎮 Tombol Panel & Slash Commands

### 🎛️ Tombol Kontrol Interaktif (10 Tombol)

| Baris | Tombol | Emoji | Fungsi |
| :--- | :--- | :---: | :--- |
| **Baris 1** | **Down** | 🔉 | Menurunkan volume lagu sebesar -10% |
| | **Back** | ⏮️ | Memutar ulang lagu sebelumnya (riwayat) atau dari awal |
| | **Pause** | ⏸️ | Menjeda atau melanjutkan pemutaran musik |
| | **Skip** | ⏭️ | Melewati lagu yang sedang diputar ke antrian berikutnya |
| | **Up** | 🔊 | Menaikkan volume lagu sebesar +10% (hingga 200%) |
| **Baris 2** | **Shuffle** | 🔀 | Mengacak seluruh urutan lagu di dalam antrian |
| | **Loop** | 🔁 | Mengubah mode perulangan: *Track* ➔ *Queue* ➔ *Off* |
| | **Stop** | ⏹️ | Menghentikan musik, mengosongkan antrian, dan keluar voice |
| | **AutoPlay** | 🔄 | Mengaktifkan/menonaktifkan rekomendasi lagu otomatis (berbasis YouTube Mix) |
| | **Playlist** | 🎵 | Melihat daftar antrian & tombol cepat tambah lagu |

### 💬 Slash Commands Discord

Semua fungsi tombol juga dapat diakses lewat perintah chat slash:

| Perintah | Argumen | Keterangan |
| :--- | :--- | :--- |
| `/musik` | - | Menampilkan panel interaktif musik dan memanggil bot ke voice channel |
| `/play` | `<lagu>` | Memutar lagu atau playlist dari judul atau URL YouTube |
| `/skip` | - | Melewati lagu yang sedang diputar |
| `/back` | - | Memutar lagu sebelumnya dari riwayat |
| `/stop` | - | Menghentikan musik dan mengeluarkan bot dari voice |
| `/quit` | - | Mengeluarkan bot dari voice, mereset antrian, dan membersihkan cache |
| `/antrian` | - | Menampilkan daftar antrian lagu saat ini |
| `/pause` | - | Menjeda atau melanjutkan pemutaran lagu |
| `/volume` | `<0-200>` | Mengatur tingkat volume suara lagu (persentase) |
| `/shuffle` | - | Mengacak urutan antrian lagu |
| `/loop` | `[mode]` | Mengatur mode perulangan (`track`, `queue`, atau `off`) |
| `/autoplay`| - | Mengaktifkan atau menonaktifkan fitur AutoPlay (berbasis YouTube Mix) |
| `/help` | - | Menampilkan daftar perintah dan cara pakai bot |

---

## 🚀 Instalasi Cepat (One-Line Installer)

Jalankan perintah berikut di terminal server Linux (STB Armbian, Debian, Ubuntu, atau VPS):

```bash
git clone https://github.com/chsprs/discord-music-bot.git /opt/discord-music-bot
cd /opt/discord-music-bot
sudo ./install.sh
```

Skrip installer otomatis:
1. Memeriksa dan menginstal paket sistem yang dibutuhkan (`python3`, `python3-venv`, `ffmpeg`, `nodejs`; skrip setup NodeSource diverifikasi SHA-256 sebelum dijalankan).
2. Menyiapkan Python virtual environment dan menginstal dependensi hash-locked dari `requirements.txt` (sebagai user `discord-music-updater`, bukan root).
3. Membuat user sistem non-root `discord-music-updater`, mengatur ownership `venv`/log, dan memasang aturan sudoers terbatas (`systemctl restart/is-active discord-music.service` saja).
4. Memasang service systemd `discord-music.service`, `discord-music-panel.service`, dan `discord-music-update.service` + timer.
5. Mengaktifkan auto-start saat boot sistem.
6. Menjalankan verifikasi unit test mandiri (**544/544 passing**) sebagai user non-root dengan path runtime sementara, sehingga tidak menyentuh antrean/state bot yang sedang hidup.
7. Menyalakan Web Control Panel di port `9130` dengan **password acak** (dicetak di akhir instalasi) kecuali `PANEL_PASSWORD` sudah diberikan, mis. `sudo PANEL_PASSWORD='rahasia' ./install.sh`.

---

## 🛠️ Langkah Penggunaan & Konfigurasi

1. Buka browser pada perangkat di jaringan LAN yang sama:
   ```
   http://<IP_SERVER_STB>:9130
   ```
2. Masukkan **Bot Token** dan **Guild ID** (Server ID Discord).
3. Anda dapat menambahkan atau mengosongkan **Password Panel** melalui menu Konfigurasi di web panel.
4. Klik **Simpan konfigurasi**, lalu klik **Nyalakan bot**.
5. Masuk ke Voice Channel di Discord, lalu ketik `/musik` atau `/play <judul/url>`.

> [!NOTE]
> **Manajemen Password Panel.**
> - `install.sh` membuat password panel acak dan mencetaknya di akhir instalasi. Tanpa password, siapa pun di LAN bisa mengganti token, mematikan bot, atau memasang password sendiri lalu mengunci Anda.
> - Password dapat diatur atau dihapus kapan saja melalui form **Konfigurasi** di panel web (mode tanpa password tetap tersedia bila memang diinginkan).
> - Jika lupa password atau ingin mereset via terminal server:
>   ```bash
>   ./tools/reset-password.sh           # Reset/hapus password (akses bebas di LAN)
>   ./tools/reset-password.sh <sandi>   # Atur password baru
>   ```
> - Untuk LAN tak-terpercaya, set `PANEL_HOST=127.0.0.1` di
>   `/opt/discord-music-panel.env` dan akses lewat SSH tunnel
>   (`ssh -L 9130:127.0.0.1:9130 user@host`).
> - `PANEL_ALLOWED_HOSTS` membatasi `Host` header yang diterima (proteksi
>   DNS-rebinding). `install.sh` mengisinya otomatis dengan `IP_LAN:PORT`.
>   Bila dikosongkan, panel mendeteksi sendiri alamat lokal mesin.
> - Panel memakai HTTP polos (tanpa TLS). Jangan ekspos ke internet.

---

## ⚙️ Variabel Lingkungan (`.env`)

Semua variabel opsional kecuali `DISCORD_TOKEN`. Lihat `.env.example` untuk templatnya.

| Variabel | Default | Keterangan |
| :--- | :---: | :--- |
| `DISCORD_TOKEN` | — | **Wajib.** Token bot dari Discord Developer Portal. |
| `DISCORD_GUILD_ID` | — | Opsional. Server uji untuk pendaftaran slash command cepat. |
| `DEFAULT_VOLUME` | `0.5` | Volume suara bawaan bot (0.0–2.0). |
| `YTDLP_COOKIES` | `./cookies.txt` | Lokasi `cookies.txt` untuk video age-restricted / butuh login. |
| `MIX_RESULT_LIMIT` | `15` | Jumlah lagu yang diambil dari YouTube Mix tiap rekomendasi AutoPlay (1–50). Makin besar makin banyak pilihan, tapi ekstraksi makin lambat. |

---

## ⚙️ Pengaturan di Discord Developer Portal

Saat membuat aplikasi bot di [Discord Developer Portal](https://discord.com/developers/applications):

1. **OAuth2 ➔ Default Authorization Link / Installation:**
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
2. **Bot ➔ Privileged Gateway Intents:**
   - Bot ini **TIDAK** membutuhkan *Message Content Intent* karena 100% menggunakan Slash Commands dan Button Interaction yang lebih aman dan efisien.
3. **Format Link Undangan Bot:**
   ```
   https://discord.com/oauth2/authorize?client_id=<YOUR_CLIENT_ID>&scope=bot+applications.commands&permissions=2150714368
   ```

---

## 📁 Struktur Berkas

```
/opt/discord-music-bot/
├── bot.py                        # Core bot Discord (audio pipeline, queue, commands, UI View)
├── panel.py                      # Web Control Panel LAN mandiri (stdlib HTTP, CSRF-safe, log viewer)
├── update.sh                     # Skrip pembaruan yt-dlp hash-locked & restart bot (jalan sbg discord-music-updater)
├── deploy.sh                     # Pembaruan kode dari GitHub main (cek / terapkan) yang dipicu dari web panel
├── requirements.txt              # Dependensi Python hash-locked (jangan edit manual; regenerate dari .in)
├── requirements.in               # Dependensi langsung; sumber untuk regenerate requirements.txt
├── install.sh                    # Skrip instalasi otomatis satu baris
├── LICENSE                       # Lisensi MIT
├── discord-music.service         # Service systemd bot musik
├── discord-music-panel.service   # Service systemd web dashboard
├── discord-music-update.service  # Service oneshot pembaruan yt-dlp (User=discord-music-updater)
├── discord-music-update.timer    # Timer mingguan auto-update
├── discord-music-deploy.service  # Service oneshot "Terapkan pembaruan" dari panel (manual, tanpa timer)
├── .env.example                  # Templat variabel lingkungan
├── .gitignore
├── README.md                     # Dokumentasi proyek
├── assets/
│   └── screenshots/              # Cuplikan antarmuka Discord UI & Web Control Panel
└── tests/
    ├── test_bot.py               # Unit test core bot, UI View, queue, AFK guard, persistent queue
    ├── test_panel.py             # Unit test web panel, update endpoint, CSRF, validasi DoS & input
    ├── test_update.py            # Unit test skrip update.sh & timer behaviour
    ├── test_systemd_units.py     # Unit test validasi hardening unit systemd
    ├── test_lockfile.py          # Lockfile hash-locked universal (Python 3.10–3.13+)
    ├── test_audit_fixes.py       # Regresi temuan audit (antrean, AutoPlay, ekstraksi, panel)
    ├── test_deploy.py            # deploy.sh: pembaruan kode dari GitHub (repo git sungguhan, systemd tiruan)
    └── test_prefetch.py          # Prefetch stream lagu berikutnya & intent gateway minimal
```

---

## 🧪 Pengujian Mandiri (Self-Contained Tests)

Jalankan rangkaian unit test lengkap:

```bash
cd /opt/discord-music-bot
./venv/bin/python -m unittest discover -s tests
```

Hasil uji:
```
Ran 544 tests in ~75s

OK
```

---

## 📊 Manajemen Service Linux

```bash
# Cek status bot & web panel
sudo systemctl status discord-music.service
sudo systemctl status discord-music-panel.service

# Melihat status timer auto-update mingguan
sudo systemctl status discord-music-update.timer
sudo systemctl list-timers | grep discord

# Melihat log bot secara realtime
sudo journalctl -u discord-music.service -f

# Menjalankan pembaruan yt-dlp manual via terminal (sebagai user updater,
# JANGAN `sudo ./update.sh` langsung: pip sebagai root meninggalkan berkas
# milik root di venv dan timer mingguan berikutnya gagal)
sudo systemctl start discord-music-update.service
```

---

## 📄 Lisensi

Didistribusikan di bawah **MIT License**. Dirancang dengan fokus pada efisiensi daya, nol beban disk, dan stabilitas jangka panjang untuk lingkungan homelab STB Armbian maupun server produksi.
