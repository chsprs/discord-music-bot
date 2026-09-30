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

# Pastikan Node.js terpasang (untuk JS runtime yt-dlp)
if ! command -v node &>/dev/null; then
    echo "Node.js tidak ditemukan, menginstal Node.js LTS..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

# 2. Siapkan direktori jika dijalankan dari lokasi berbeda
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$SCRIPT_DIR" != "$INSTALL_DIR" ]]; then
    echo "[2/6] Menyalin berkas ke $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR"/
    cp -r "$SCRIPT_DIR"/.[!.]* "$INSTALL_DIR"/ 2>/dev/null || true
fi

cd "$INSTALL_DIR"

# 3. Virtual Environment Python
echo "[3/6] Menyiapkan Python virtual environment..."
if [[ ! -d "venv" ]]; then
    python3 -m venv venv
fi
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

# 4. Berkas Konfigurasi
echo "[4/6] Menyiapkan konfigurasi..."
if [[ ! -f ".env" ]]; then
    cp .env.example .env
    chmod 600 .env
fi

PANEL_ENV="/opt/discord-music-panel.env"
if [[ ! -f "$PANEL_ENV" ]]; then
    PANEL_PASS="$(openssl rand -base64 24 2>/dev/null || head -c 18 /dev/urandom | base64)"
    cat <<EOF > "$PANEL_ENV"
PANEL_HOST=$PANEL_HOST
PANEL_PORT=$PANEL_PORT
PANEL_PASSWORD=$PANEL_PASS
EOF
    chmod 600 "$PANEL_ENV"
    echo ""
    echo ">>> PANEL_PASSWORD awal: $PANEL_PASS (tersimpan di $PANEL_ENV, mode 0600). Ganti bila perlu."
fi

# 5. Pasang dan Aktifkan systemd service & timer
echo "[5/6] Memasang dan mengaktifkan service systemd..."
cp "$INSTALL_DIR/discord-music.service" /etc/systemd/system/discord-music.service
cp "$INSTALL_DIR/discord-music-panel.service" /etc/systemd/system/discord-music-panel.service
cp "$INSTALL_DIR/discord-music-update.service" /etc/systemd/system/discord-music-update.service
cp "$INSTALL_DIR/discord-music-update.timer" /etc/systemd/system/discord-music-update.timer
chmod +x "$INSTALL_DIR/update.sh"

systemctl daemon-reload
systemctl enable discord-music.service discord-music-panel.service discord-music-update.timer
systemctl start discord-music-update.timer
systemctl restart discord-music-panel.service

# 6. Jalankan unit test
echo "[6/6] Menjalankan verifikasi tes..."
PYTHONPATH="$INSTALL_DIR" "$INSTALL_DIR/venv/bin/python" -m unittest discover -s "$INSTALL_DIR/tests" -v

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
echo "=========================================="
