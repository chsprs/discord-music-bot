#!/bin/bash
# Pembaruan kode bot dari GitHub (branch main), dipicu MANUAL dari web panel.
#
#   deploy.sh check   Ambil info origin/main dan tampilkan commit baru beserta
#                     file yang berubah. Tidak mengubah apa pun.
#   deploy.sh apply   Fast-forward ke origin/main, pasang dependensi bila
#                     requirements.txt berubah (sebagai user updater), jalankan
#                     tes, lalu restart service yang terdampak. Tes atau pip
#                     gagal -> kode dikembalikan ke commit sebelumnya.
#
# Dijalankan sebagai root: `check` langsung oleh panel, `apply` lewat
# discord-music-deploy.service. Jangan jalankan sebagai user updater.
set -euo pipefail

# Salin diri ke berkas sementara lalu exec: `git merge` bisa mengganti
# deploy.sh selagi bash masih membacanya baris demi baris.
if [[ -z "${DEPLOY_REEXEC:-}" ]]; then
    SELF_COPY="$(mktemp "${TMPDIR:-/tmp}/discord-music-deploy.XXXXXX")"
    cp "$0" "$SELF_COPY"
    DEPLOY_REEXEC="$SELF_COPY" exec bash "$SELF_COPY" "$@"
fi

DIR="${BOT_DIR:-/opt/discord-music-bot}"
REMOTE="${DEPLOY_REMOTE:-origin}"
BRANCH="${DEPLOY_BRANCH:-main}"
TARGET_REF="refs/remotes/$REMOTE/$BRANCH"
LOG_FILE="${DEPLOY_LOG:-$DIR/last_deploy.log}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
UPDATER_USER="${UPDATER_USER:-discord-music-updater}"
PYTHON3="${PYTHON3:-/usr/bin/python3}"
STATE_FILE="${BOT_STATE_FILE:-/run/discord-music/state.json}"
LISTENERS_FILE="${STATE_FILE%/*}/listeners.json"
UNITS=(discord-music.service discord-music-panel.service discord-music-update.service
       discord-music-update.timer discord-music-deploy.service)
MODE="${1:-}"

cleanup() {
    rm -f "$DEPLOY_REEXEC"
    # Batasi pertumbuhan log (output tes cukup panjang).
    if [[ "$MODE" == apply && -f "$LOG_FILE" ]]; then
        local tmp
        tmp="$(mktemp)"
        tail -n 400 "$LOG_FILE" > "$tmp" 2>/dev/null && cat "$tmp" > "$LOG_FILE" || true
        rm -f "$tmp"
    fi
}
trap cleanup EXIT

# safe.directory: checkout bisa dimiliki user lain bila di-clone tanpa sudo.
git() { command git -c safe.directory="$DIR" -C "$DIR" "$@"; }

log() {
    local line
    line="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$line"
    if [[ "$MODE" == apply ]]; then
        echo "$line" >> "$LOG_FILE"
    fi
}

as_updater() {
    runuser -u "$UPDATER_USER" -- env HOME=/nonexistent PIP_NO_CACHE_DIR=1 "$@"
}

short() { git log -1 --format='%h %s (%cr)' "$1"; }

fetch() {
    git fetch --quiet "$REMOTE" "+refs/heads/$BRANCH:$TARGET_REF"
}

dirty() {
    [[ -n "$(git status --porcelain --untracked-files=no)" ]]
}

# Tentukan tindakan dari daftar file yang berubah (satu per baris di $CHANGED).
# Ditulis dengan case + `return 0` eksplisit: pola `[[ ... ]] && x` yang salah
# bisa menjadi status akhir fungsi dan menghentikan skrip lewat `set -e`.
plan() {
    NEED_PIP=0; NEED_UNITS=0; RESTART_BOT=0; RESTART_PANEL=0; INSTALL_CHANGED=0
    local file
    while IFS= read -r file; do
        case "$file" in
            requirements.txt) NEED_PIP=1; RESTART_BOT=1 ;;
            bot.py) RESTART_BOT=1 ;;
            panel.py) RESTART_PANEL=1 ;;
            install.sh) INSTALL_CHANGED=1 ;;
            discord-music.service) NEED_UNITS=1; RESTART_BOT=1 ;;
            discord-music-panel.service) NEED_UNITS=1; RESTART_PANEL=1 ;;
            discord-music-update.service|discord-music-update.timer|discord-music-deploy.service) NEED_UNITS=1 ;;
        esac
    done <<< "$CHANGED"
    return 0
}

describe_plan() {
    local actions=()
    if [[ $NEED_PIP -eq 1 ]]; then actions+=("pasang dependensi (requirements.txt)"); fi
    if [[ $NEED_UNITS -eq 1 ]]; then actions+=("pasang ulang unit systemd"); fi
    if [[ $RESTART_BOT -eq 1 ]]; then actions+=("restart bot (ditunda bila ada pendengar)"); fi
    if [[ $RESTART_PANEL -eq 1 ]]; then actions+=("restart panel"); fi
    if [[ ${#actions[@]} -eq 0 ]]; then
        echo "Tindakan saat diterapkan: tidak ada service yang perlu di-restart"
    else
        local IFS=', '
        echo "Tindakan saat diterapkan: ${actions[*]}"
    fi
    if [[ $INSTALL_CHANGED -eq 1 ]]; then
        echo "Catatan: install.sh berubah. Bila ada langkah instalasi baru, jalankan 'sudo ./install.sh' manual."
    fi
    return 0
}

# Ada pendengar manusia? Sama dengan update.sh, tetapi memakai python3 sistem:
# skrip ini berjalan sebagai root dan tidak boleh mengeksekusi interpreter venv
# (bisa ditulis user updater).
listeners_active() {
    [[ -f "$LISTENERS_FILE" ]] || return 1
    "$PYTHON3" -I - "$LISTENERS_FILE" <<'PY' 2>/dev/null
import json, sys, time
try:
    with open(sys.argv[1], encoding='utf-8') as fh:
        data = json.load(fh)
except Exception:
    sys.exit(1)
if time.time() - float(data.get('updated_at') or 0) > 60:
    sys.exit(1)
sys.exit(0 if int(data.get('total_listeners') or 0) > 0 else 1)
PY
}

install_deps() {
    log "Memasang dependensi dari requirements.txt (sebagai $UPDATER_USER)..."
    as_updater "$DIR/venv/bin/pip" install --require-hashes -r "$DIR/requirements.txt" >> "$LOG_FILE" 2>&1
}

run_tests() {
    if [[ "${DEPLOY_SKIP_TESTS:-0}" == 1 ]]; then
        log "Tes dilewati (DEPLOY_SKIP_TESTS=1)."
        return 0
    fi
    log "Menjalankan tes (sebagai $UPDATER_USER, path runtime sementara)..."
    local tmp rc=0
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/discord-music-tests.XXXXXX")"
    chown "$UPDATER_USER" "$tmp" 2>/dev/null || true
    as_updater env HOME="$tmp" TMPDIR="$tmp" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$DIR" \
        QUEUE_STATE_FILE="$tmp/queue_state.json" BOT_STATE_FILE="$tmp/state.json" \
        PANEL_ENV="$tmp/panel.env" BOT_CONFIG="$tmp/bot.env" UPDATE_LOG="$tmp/last_update.log" \
        "$DIR/venv/bin/python" -m unittest discover -s "$DIR/tests" >> "$LOG_FILE" 2>&1 || rc=$?
    rm -rf "$tmp"
    return $rc
}

install_units() {
    local unit
    for unit in "${UNITS[@]}"; do
        if [[ -f "$DIR/$unit" ]]; then
            install -m 0644 "$DIR/$unit" "$SYSTEMD_DIR/$unit"
        fi
    done
    systemctl daemon-reload
    log "Unit systemd diperbarui (daemon-reload)."
}

rollback() {
    log "GAGAL: $1. Mengembalikan kode ke $(short "$PREV")."
    git reset --hard --quiet "$PREV"
    if [[ $NEED_PIP -eq 1 ]]; then
        install_deps || log "Peringatan: pemasangan ulang dependensi versi lama juga gagal."
    fi
    log "Status: Gagal. Kode dikembalikan; bot tetap memakai versi sebelumnya."
    exit 1
}

do_check() {
    fetch
    local head target count
    head="$(git rev-parse HEAD)"
    target="$(git rev-parse "$TARGET_REF")"
    echo "Terpasang : $(short "$head")"
    echo "Terbaru   : $(short "$target")"
    if [[ "$head" == "$target" ]]; then
        echo "Status    : sudah versi terbaru."
        return 0
    fi
    if ! git merge-base --is-ancestor "$head" "$target"; then
        echo "Status    : TIDAK bisa diterapkan otomatis (riwayat lokal berbeda dari $REMOTE/$BRANCH)."
        return 0
    fi
    count="$(git rev-list --count "$head..$target")"
    if dirty; then
        echo "Status    : $count commit baru, tetapi ada perubahan lokal pada file yang dilacak git -> akan ditolak."
    else
        echo "Status    : $count commit baru siap diterapkan."
    fi
    echo ""
    echo "Commit baru:"
    git log --format='  %h %s' "$head..$target"
    echo ""
    echo "File berubah:"
    CHANGED="$(git diff --name-only "$head" "$target")"
    sed 's/^/  /' <<< "$CHANGED"
    echo ""
    plan
    describe_plan
}

do_apply() {
    exec 9>"$DIR/.deploy.lock"
    if ! flock -n 9; then
        log "Pembaruan lain sedang berjalan, batal."
        exit 0
    fi
    log "=== Memulai pembaruan dari $REMOTE/$BRANCH ==="
    fetch
    if dirty; then
        log "Batal: ada perubahan lokal pada file yang dilacak git. Tidak ada yang diubah."
        git status --short --untracked-files=no >> "$LOG_FILE"
        exit 1
    fi
    PREV="$(git rev-parse HEAD)"
    local target
    target="$(git rev-parse "$TARGET_REF")"
    if [[ "$PREV" == "$target" ]]; then
        log "Sudah versi terbaru: $(short "$PREV")."
        log "Status: Sukses (tidak ada perubahan)."
        exit 0
    fi
    if ! git merge-base --is-ancestor "$PREV" "$target"; then
        log "Batal: riwayat lokal berbeda dari $REMOTE/$BRANCH (bukan fast-forward). Tidak ada yang diubah."
        exit 1
    fi
    CHANGED="$(git diff --name-only "$PREV" "$target")"
    plan
    log "Commit baru:"
    git log --format='  %h %s' "$PREV..$target" | tee -a "$LOG_FILE"
    describe_plan | tee -a "$LOG_FILE"

    git merge --ff-only --quiet "$target"
    log "Kode diperbarui: $(short "$PREV") -> $(short "$target")"

    if [[ $NEED_PIP -eq 1 ]]; then
        install_deps || rollback "pip install gagal"
    fi
    run_tests || rollback "tes gagal (lihat output di atas)"
    log "Tes lulus."

    if [[ $NEED_UNITS -eq 1 ]]; then
        install_units
    fi

    if [[ $RESTART_BOT -eq 1 ]]; then
        if ! systemctl is-active --quiet discord-music.service; then
            log "Bot tidak aktif; kode baru dipakai saat bot dinyalakan."
        elif listeners_active; then
            log "Ada pendengar aktif -> restart bot ditunda agar musik tidak terputus. Tekan 'Mulai ulang' di panel saat room kosong."
        else
            systemctl restart discord-music.service
            log "discord-music.service dimulai ulang."
        fi
    fi
    if [[ $RESTART_PANEL -eq 1 ]]; then
        # --no-block: panel yang memicu pembaruan ini ikut di-restart; jangan tunggu.
        systemctl restart --no-block discord-music-panel.service
        log "discord-music-panel.service dimulai ulang (muat ulang halaman panel)."
    fi
    log "Status: Sukses. Versi sekarang: $(short HEAD)"
}

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    log "Batal: $DIR bukan checkout git (instalasi lama disalin tanpa .git)."
    log "Clone ulang: sudo git clone https://github.com/chsprs/discord-music-bot.git $DIR lalu sudo ./install.sh"
    exit 1
fi

case "$MODE" in
    check) do_check ;;
    apply) do_apply ;;
    *)
        echo "Penggunaan: $0 check|apply" >&2
        exit 2
        ;;
esac
