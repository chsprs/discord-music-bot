#!/bin/bash
# Reset atau atur password web panel Crspy Music via terminal server.
#
# Penggunaan:
#   ./tools/reset-password.sh           -> Hapus password (akses bebas tanpa login di LAN)
#   ./tools/reset-password.sh <sandi>   -> Atur password panel baru

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PANEL_ENV="${PANEL_ENV:-/opt/discord-music-panel.env}"
SERVICE="discord-music-panel.service"

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    echo "Penggunaan: $0 [password_baru]"
    echo ""
    echo "  Tanpa argumen: menghapus password panel (akses bebas tanpa login di LAN)."
    echo "  Dengan argumen: mengatur password panel ke nilai yang ditentukan."
    exit 0
fi

NEW_PASS="$1"

if [ -f "$PANEL_ENV" ]; then
    if grep -q '^PANEL_PASSWORD=' "$PANEL_ENV"; then
        sed -i "s|^PANEL_PASSWORD=.*|PANEL_PASSWORD=$NEW_PASS|" "$PANEL_ENV"
    else
        echo "PANEL_PASSWORD=$NEW_PASS" >> "$PANEL_ENV"
    fi
else
    cat <<EOF > "$PANEL_ENV"
PANEL_HOST=0.0.0.0
PANEL_PORT=9130
PANEL_PASSWORD=$NEW_PASS
EOF
    chmod 600 "$PANEL_ENV"
fi

chmod 600 "$PANEL_ENV"

# Restart service panel jika sedang berjalan
if systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
    systemctl restart "$SERVICE"
fi

if [ -z "$NEW_PASS" ]; then
    echo "Berhasil: Password web panel telah direset (dihapus)."
    echo "Web panel sekarang dapat diakses langsung tanpa password di jaringan lokal (LAN)."
else
    echo "Berhasil: Password web panel telah diatur ke: $NEW_PASS"
fi
