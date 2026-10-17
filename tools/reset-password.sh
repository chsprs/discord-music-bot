#!/bin/bash
# Reset atau atur password web panel Crspy Music via terminal server.
#
# Penggunaan:
#   ./tools/reset-password.sh           -> Hapus password (akses bebas tanpa login di LAN)
#   ./tools/reset-password.sh <sandi>   -> Atur password panel baru

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# python3 sistem, bukan venv: panel.py hanya butuh stdlib, dan skrip ini
# biasanya dijalankan sebagai root sedangkan venv bisa ditulis user updater.
PYTHON="${PYTHON:-/usr/bin/python3}"
if [ ! -x "$PYTHON" ]; then
    PYTHON="python3"
fi
SERVICE="discord-music-panel.service"

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    echo "Penggunaan: $0 [password_baru]"
    echo ""
    echo "  Tanpa argumen: menghapus password panel (akses bebas tanpa login di LAN)."
    echo "  Dengan argumen: mengatur password panel ke nilai yang ditentukan."
    exit 0
fi

NEW_PASS="$1"

if [ -z "$NEW_PASS" ]; then
    "$PYTHON" "$DIR/panel.py" --reset-password
else
    "$PYTHON" "$DIR/panel.py" --set-password "$NEW_PASS"
fi

# Restart service panel jika sedang berjalan agar perubahan langsung efektif
if systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
    systemctl restart "$SERVICE"
fi
