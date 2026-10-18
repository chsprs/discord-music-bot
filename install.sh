#!/usr/bin/env bash
set -euo pipefail

# Discord Music Bot Installer
# Usage: sudo ./install.sh [PORT] [HOST]

if [[ $EUID -ne 0 ]]; then
   echo "Error: Skrip ini harus dijalankan sebagai root (atau pakai sudo)." >&2
   exit 1
fi

INSTALL_DIR="/opt/discord-music-bot"
PANEL_PORT="${1:-9130}"
PANEL_HOST="${2:-0.0.0.0}"

echo "=== Memulai Instalasi Discord Music Bot ==="

# 1. Update paket & dependensi sistem
echo "[1/6] Memeriksa dependensi sistem..."
apt-get update -y
apt-get install -y --no-install-recommends python3 python3-venv python3-pip ffmpeg curl git openssl

# Bot memakai asyncio.Semaphore/Lock tingkat modul sehingga butuh Python >= 3.10.
# Interpreter yang sama dipakai untuk venv bot dan untuk menjalankan panel
# (ExecStart=/usr/bin/python3 di discord-music-panel.service).
PYTHON3=/usr/bin/python3
PY_VER="$("$PYTHON3" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo '0.0')"
PY_MAJOR="${PY_VER%%.*}"
PY_MINOR="${PY_VER##*.}"
if (( PY_MAJOR < 3 || (PY_MAJOR == 3 && PY_MINOR < 10) )); then
    echo "Error: butuh Python >= 3.10, terdeteksi $PY_VER." >&2
    echo "Di Debian/Ubuntu lama pasang python3 dari backports, atau pakai distro yang lebih baru." >&2
    exit 1
fi

# Pastikan Node.js terpasang (untuk JS runtime yt-dlp)
if ! command -v node &>/dev/null; then
    echo "Node.js tidak ditemukan, menginstal Node.js LTS..."
    # L7: jangan pipe langsung `curl | bash` — kalau unduhan terpotong/MITM,
    # bash mengeksekusi teks separuh tanpa peringatan. Unduh dulu ke berkas,
    # verifikasi bentuknya (shebang + berisi setup NodeSource), baru jalankan.
    NODESOURCE_SETUP="$(mktemp /tmp/nodesource-setup.XXXXXX.sh)"
    trap 'rm -f "$NODESOURCE_SETUP"' EXIT
    if ! curl -fsSL https://deb.nodesource.com/setup_20.x -o "$NODESOURCE_SETUP"; then
        echo "Error: gagal mengunduh skrip NodeSource." >&2
        exit 1
    fi
    # Verifikasi SHA-256 (Security Audit Run-1)
    EXPECTED_HASH="2c4c6683a17b6f4128898a7b521e3c8bb725a99ffaf1b5e32ac97c6fa7d381be"
    if ! echo "$EXPECTED_HASH  $NODESOURCE_SETUP" | sha256sum -c -; then
        echo "Error: Hash skrip NodeSource tidak cocok!" >&2
        exit 1
    fi
    if [[ ! -s "$NODESOURCE_SETUP" ]] || ! head -n1 "$NODESOURCE_SETUP" | grep -q '^#!'; then
        echo "Error: skrip NodeSource tidak valid (bukan skrip shell)." >&2
        exit 1
    fi
    if ! grep -q 'nodesource' "$NODESOURCE_SETUP"; then
        echo "Error: skrip NodeSource tidak memuat penanda 'nodesource' yang diharapkan." >&2
        exit 1
    fi
    bash "$NODESOURCE_SETUP"
    rm -f "$NODESOURCE_SETUP"
    trap - EXIT
    apt-get install -y nodejs
fi

# 2. Siapkan direktori jika dijalankan dari lokasi berbeda
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$SCRIPT_DIR" != "$INSTALL_DIR" ]]; then
    echo "[2/6] Menyalin berkas ke $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
    # Salin hanya artefak yang memang bagian aplikasi. Jangan salin .git atau
    # .env (berisi token) dari direktori sumber ke /opt.
    for f in bot.py panel.py update.sh deploy.sh install.sh requirements.txt README.md \
             discord-music.service discord-music-panel.service \
             discord-music-update.service discord-music-update.timer \
             discord-music-deploy.service \
             .env.example .gitignore; do
        if [[ -e "$SCRIPT_DIR/$f" ]]; then
            cp -r "$SCRIPT_DIR/$f" "$INSTALL_DIR"/
        fi
    done
    if [[ -d "$SCRIPT_DIR/tests" ]]; then
        cp -r "$SCRIPT_DIR/tests" "$INSTALL_DIR"/
    fi
    # tools/ (mis. cleanup_panels.py) dan docs/ ikut dipasang: docstring tools
    # menyuruh menjalankannya dari /opt/discord-music-bot (L6).
    for d in tools docs; do
        if [[ -d "$SCRIPT_DIR/$d" ]]; then
            cp -r "$SCRIPT_DIR/$d" "$INSTALL_DIR"/
        fi
    done
fi

cd "$INSTALL_DIR"

# 3. Virtual Environment Python & User Setup
echo "[3/6] Menyiapkan Python virtual environment dan user updater..."

if ! id "discord-music-updater" &>/dev/null; then
    useradd -r -s /usr/sbin/nologin discord-music-updater
fi

if [[ ! -d "venv" ]]; then
    "$PYTHON3" -m venv venv
fi

touch last_update.log .update.lock
chown -R discord-music-updater:discord-music-updater venv last_update.log .update.lock

# Pasang dependensi SEBAGAI user updater, bukan root: venv milik updater (timer
# mingguan memakai pip yang sama), jadi berkas milik root di venv membuat update
# berikutnya gagal, dan root tidak boleh mengeksekusi kode yang bisa ditulis
# user lain.
as_updater() {
    runuser -u discord-music-updater -- env HOME=/nonexistent PIP_NO_CACHE_DIR=1 "$@"
}
as_updater venv/bin/pip install --upgrade pip
as_updater venv/bin/pip install --require-hashes -r requirements.txt

# Sudoers untuk updater agar bisa restart bot
echo "discord-music-updater ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart discord-music.service, /usr/bin/systemctl is-active --quiet discord-music.service" > /etc/sudoers.d/discord-music-updater
chmod 0440 /etc/sudoers.d/discord-music-updater

# 4. Berkas Konfigurasi
echo "[4/6] Menyiapkan konfigurasi..."
if [[ ! -f ".env" ]]; then
    cp .env.example .env
    chmod 600 .env
fi

PANEL_ENV="/opt/discord-music-panel.env"
PANEL_PASS_GENERATED=""
if [[ ! -f "$PANEL_ENV" ]]; then
    # Default AMAN: panel tanpa password di 0.0.0.0 membuat siapa pun di LAN bisa
    # mengganti token, mematikan bot, menjalankan update, bahkan memasang
    # password sendiri lalu mengunci pemiliknya. Buat password acak bila
    # PANEL_PASSWORD tidak diberikan; mode tanpa password tetap bisa dipilih
    # lewat panel / tools/reset-password.sh.
    PANEL_PASS="${PANEL_PASSWORD:-}"
    if [[ -z "$PANEL_PASS" ]]; then
        PANEL_PASS="$(openssl rand -base64 18 | tr -dc 'A-Za-z0-9' | head -c 20)"
        PANEL_PASS_GENERATED="$PANEL_PASS"
    fi
    LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    cat <<EOF > "$PANEL_ENV"
PANEL_HOST=$PANEL_HOST
PANEL_PORT=$PANEL_PORT
# Batasi Host header yang diterima (proteksi DNS-rebinding). Pisahkan dengan koma.
# Kosongkan untuk deteksi otomatis dari alamat lokal mesin.
PANEL_ALLOWED_HOSTS=${LAN_IP:+$LAN_IP:$PANEL_PORT}
EOF
    chmod 600 "$PANEL_ENV"
    # Ditulis lewat panel.py agar nilai di-quote benar untuk EnvironmentFile
    # systemd (password berisi kutip/backslash/spasi tidak berubah saat dibaca).
    PANEL_ENV="$PANEL_ENV" "$PYTHON3" "$INSTALL_DIR/panel.py" --set-password "$PANEL_PASS" >/dev/null
    echo ""
    if [[ -n "$PANEL_PASS_GENERATED" ]]; then
        echo ">>> PANEL_PASSWORD dibuat acak: $PANEL_PASS_GENERATED"
        echo "    Simpan password ini. Ubah via web panel atau ./tools/reset-password.sh <sandi>."
    else
        echo ">>> PANEL_PASSWORD diambil dari variabel lingkungan PANEL_PASSWORD."
    fi
    echo ">>> Panel bind ke $PANEL_HOST. Untuk LAN tak-terpercaya, set PANEL_HOST=127.0.0.1"
    echo "    dan akses lewat SSH tunnel: ssh -L 9130:127.0.0.1:9130 user@host"
    if [[ -n "$LAN_IP" ]]; then
        echo ">>> PANEL_ALLOWED_HOSTS=$LAN_IP:$PANEL_PORT (tambahkan IP/host lain bila perlu)."
    fi
fi

# 5. Pasang dan Aktifkan systemd service & timer
echo "[5/6] Memasang dan mengaktifkan service systemd..."
cp "$INSTALL_DIR/discord-music.service" /etc/systemd/system/discord-music.service
cp "$INSTALL_DIR/discord-music-panel.service" /etc/systemd/system/discord-music-panel.service
cp "$INSTALL_DIR/discord-music-update.service" /etc/systemd/system/discord-music-update.service
cp "$INSTALL_DIR/discord-music-update.timer" /etc/systemd/system/discord-music-update.timer
# Tanpa enable: hanya dijalankan lewat tombol "Terapkan pembaruan" di panel.
cp "$INSTALL_DIR/discord-music-deploy.service" /etc/systemd/system/discord-music-deploy.service
chmod +x "$INSTALL_DIR/update.sh" "$INSTALL_DIR/deploy.sh"

systemctl daemon-reload
systemctl enable discord-music.service discord-music-panel.service discord-music-update.timer
systemctl start discord-music-update.timer
systemctl restart discord-music-panel.service

# 6. Jalankan unit test
# Sebagai user updater (bukan root) dan dengan semua path runtime diarahkan ke
# direktori sementara: installer sering dijalankan ulang di mesin yang botnya
# sedang hidup, dan suite tidak boleh menyentuh /run/discord-music (antrean,
# listeners.json) atau panel.env/.env produksi.
echo "[6/6] Menjalankan verifikasi tes..."
TEST_TMP="$(mktemp -d /tmp/discord-music-tests.XXXXXX)"
chown discord-music-updater "$TEST_TMP"
TEST_RC=0
runuser -u discord-music-updater -- env \
    HOME="$TEST_TMP" TMPDIR="$TEST_TMP" PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="$INSTALL_DIR" \
    QUEUE_STATE_FILE="$TEST_TMP/queue_state.json" \
    BOT_STATE_FILE="$TEST_TMP/state.json" \
    PANEL_ENV="$TEST_TMP/panel.env" \
    BOT_CONFIG="$TEST_TMP/bot.env" \
    UPDATE_LOG="$TEST_TMP/last_update.log" \
    "$INSTALL_DIR/venv/bin/python" -m unittest discover -s "$INSTALL_DIR/tests" -v || TEST_RC=$?
rm -rf "$TEST_TMP"
if [[ $TEST_RC -ne 0 ]]; then
    echo "Error: verifikasi tes gagal (exit $TEST_RC). Periksa output di atas." >&2
    exit "$TEST_RC"
fi

LAN_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "=========================================="
echo "Instalasi Berhasil & Siap Digunakan!"
echo "Panel Web: http://${LAN_IP}:${PANEL_PORT}"
echo ""
echo "Cara Penggunaan:"
echo "1. Buka browser: http://${LAN_IP}:${PANEL_PORT}"
echo "2. Masukkan Bot Token & Guild ID (Server ID Discord)"
echo "3. Klik 'Simpan konfigurasi' lalu 'Nyalakan bot'"
echo "4. Di Discord ketik /musik untuk membuka panel"
if [[ -n "$PANEL_PASS_GENERATED" ]]; then
    echo ""
    echo "Password panel: $PANEL_PASS_GENERATED"
fi
echo "=========================================="
