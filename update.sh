#!/bin/bash
set -euo pipefail

DIR="${BOT_DIR:-/opt/discord-music-bot}"
VENV_PIP="$DIR/venv/bin/pip"
VENV_PY="$DIR/venv/bin/python"
LOG_FILE="$DIR/last_update.log"
PIN="$DIR/requirements.txt"
STATE_FILE="${BOT_STATE_FILE:-/run/discord-music/state.json}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

exec 9>"$DIR/.update.lock"
if ! flock -n 9; then
    echo "[$TIMESTAMP] Pembaruan lain sedang berjalan, batal." >> "$LOG_FILE"
    exit 0
fi

log() { echo "[$TIMESTAMP] $*" >> "$LOG_FILE"; }

# Batasi pertumbuhan last_update.log (M2): pip menulis output penuh tiap minggu
# dan panel merender ekornya di tiap halaman. Simpan 300 baris terakhir. Dipanggil
# lewat trap EXIT agar berlaku di SEMUA jalur keluar (termasuk "restart ditunda").
trim_log() {
    [ -f "$LOG_FILE" ] || return 0
    TMP_LOG=$(mktemp)
    tail -n 300 "$LOG_FILE" > "$TMP_LOG" 2>/dev/null && cat "$TMP_LOG" > "$LOG_FILE" || true
    rm -f "$TMP_LOG"
}
trap trim_log EXIT

# ---------------------------------------------------------------- versi
# Versi terpasang sekarang. Pakai importlib.metadata (versi kanonik PyPI,
# mis. '2026.8.19') bukan yt_dlp.version.__version__ ('2026.08.19'), supaya pin
# yang ditulis kembali ke requirements.txt persis sama dengan nama rilis PyPI.
version_now() {
    "$VENV_PY" -c "from importlib.metadata import version; print(version('yt-dlp'))" 2>/dev/null \
        || "$VENV_PY" -c "import yt_dlp.version as v; print(v.__version__)" 2>/dev/null \
        || echo ""
}

# Apakah ada penonton aktif? Baca state exporter bot (tmpfs, diperbarui ~5 dtk).
# Kalau ada, restart bot akan memutus musik orang -> tunda.
listeners_active() {
    [ -f "$STATE_FILE" ] || return 1
    "$VENV_PY" - "$STATE_FILE" <<'PY' 2>/dev/null
import json, sys, time
try:
    with open(sys.argv[1], encoding='utf-8') as fh:
        data = json.load(fh)
except Exception:
    sys.exit(1)  # state tidak terbaca -> anggap tidak ada penonton
# State basi (>60 dtk) berarti exporter mati; jangan percaya.
if time.time() - float(data.get('updated_at') or 0) > 60:
    sys.exit(1)
sys.exit(0 if int(data.get('total_listeners') or 0) > 0 else 1)
PY
}

# ---------------------------------------------------------------- update
log "=== Memulai Pembaruan yt-dlp ==="
if [ ! -x "$VENV_PIP" ]; then
    log "Error: Pip virtualenv tidak ditemukan di $VENV_PIP"
    exit 1
fi

BEFORE="$(version_now)"

# --require-hashes WAJIB: memvalidasi integritas package sebelum instalasi.
# Jangan pernah menggunakan -U yt-dlp secara unpinned untuk mencegah supply chain attack.
if ! "$VENV_PIP" install --require-hashes -r "$PIN" >> "$LOG_FILE" 2>&1; then
    log "Status: Gagal saat pip install --require-hashes."
    exit 1
fi

AFTER="$(version_now)"
if [ -n "$AFTER" ] && [ "$AFTER" != "$BEFORE" ]; then
    log "yt-dlp diperbarui: ${BEFORE:-?} -> $AFTER"
else
    log "yt-dlp sudah versi terbaru (${AFTER:-tidak diketahui})."
fi

# Sinkronisasi ke requirements.txt ditiadakan (Security Audit Run-1).
# Pinning dan hash wajib diperbarui secara manual atau lewat CI yang aman.

# Hapus cache yt-dlp agar extractor baru tidak memakai cache lama yang rusak.
for cache in "${XDG_CACHE_HOME:-/run/discord-music}/yt-dlp" "${HOME:-/root}/.cache/yt-dlp" /tmp/yt-dlp; do
    [ -d "$cache" ] && rm -rf "$cache" 2>/dev/null || true
done

# ---------------------------------------------------------------- restart
if ! sudo systemctl is-active --quiet discord-music.service; then
    log "Bot tidak aktif, tidak perlu restart."
    log "Status: Sukses."
    exit 0
fi

# Jangan potong musik orang: kalau ada penonton, cukup tandai agar bot memuat
# yt-dlp baru pada restart berikutnya (bot memuat modul saat start).
if listeners_active; then
    log "Ada penonton aktif -> restart ditunda agar musik tidak terputus."
    log "Status: Sukses (restart ditunda, versi baru dipakai saat bot restart)."
    exit 0
fi

sudo systemctl restart discord-music.service
log "Service discord-music.service dimulai ulang."
log "Status: Sukses."
