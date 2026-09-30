#!/bin/bash
set -euo pipefail

DIR="/opt/discord-music-bot"
VENV_PIP="$DIR/venv/bin/pip"
LOG_FILE="$DIR/last_update.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

exec 9>"$DIR/.update.lock"
if ! flock -n 9; then
    echo "[$TIMESTAMP] Pembaruan lain sedang berjalan, batal." >> "$LOG_FILE"
    exit 0
fi

PIN="$DIR/requirements.txt"
echo "[$TIMESTAMP] === Memulai Pembaruan yt-dlp ===" >> "$LOG_FILE"
if [ -x "$VENV_PIP" ]; then
    if [ -f "$PIN" ]; then
        TARGET="$(grep -E '^yt-dlp' "$PIN" | head -n 1)"
    else
        TARGET="yt-dlp"
    fi
    if "$VENV_PIP" install "$TARGET" >> "$LOG_FILE" 2>&1; then
        echo "[$TIMESTAMP] Instalasi paket $TARGET berhasil." >> "$LOG_FILE"
        if systemctl is-active --quiet discord-music.service; then
            systemctl restart discord-music.service
            echo "[$TIMESTAMP] Service discord-music.service dimulai ulang." >> "$LOG_FILE"
        fi
        echo "[$TIMESTAMP] Status: Sukses." >> "$LOG_FILE"
    else
        echo "[$TIMESTAMP] Status: Gagal saat pip install." >> "$LOG_FILE"
        exit 1
    fi
else
    echo "[$TIMESTAMP] Error: Pip virtualenv tidak ditemukan di $VENV_PIP" >> "$LOG_FILE"
    exit 1
fi
