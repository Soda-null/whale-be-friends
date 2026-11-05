#!/bin/sh
# Copy her from the always-on box to this Mac, so one dead disk cannot take her (decision 53).
#
#   scripts/backup_box.sh              back up now
#   scripts/backup_box.sh --auto       the same, unless the last one is under 20 hours old (launchd runs this)
#   scripts/backup_box.sh --check      say something only if the last backup is over 3 days old; no network
#   scripts/backup_box.sh --install    have launchd try every 6 hours, also after the Mac wakes up
#   scripts/backup_box.sh --uninstall  stop that; the backups stay
#
# Each backup is backups/auto/<date-time>/ (gitignored, only you can read it), a whole copy of data/.
# The newest 30 stay. How to put one back: docs/box_zh.md.
set -eu
cd "$(dirname "$0")/.."
REPO="$(pwd)"
BOX="${BOX:-$(sed -n 's/^BOX=//p' .env 2>/dev/null | tail -1)}"
BOX="${BOX:-box}"
REMOTE_DIR="Dafeiyu"
DEST="${FISH_BACKUP_DIR:-$REPO/backups/auto}"
KEEP="${FISH_BACKUP_KEEP:-30}"
LABEL="com.dafeiyu.backup"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python

latest() { ls -1d "$DEST"/20* 2>/dev/null | sort | tail -1; }

# True if the newest backup finished within this many minutes.
fresh() {
    last="$(latest)"
    [ -n "$last" ] && [ -n "$(find "$last/.done" -mmin "-$1" 2>/dev/null)" ]
}

back_up() {
    mkdir -p "$DEST"
    chmod 700 "$DEST"
    stamp="$(date +%Y-%m-%d-%H%M%S)"
    tmp="$DEST/.partial-$stamp"
    trap 'rm -rf "$tmp"' EXIT
    prev="$(latest)"
    # The live database goes through SQLite's own copy; everything else is plain files.
    ssh -o BatchMode=yes -o ConnectTimeout=15 "$BOX" \
        "cd $REMOTE_DIR && .venv/bin/python scripts/snapshot_db.py data/fish.db data/.snapshot-fish.db >/dev/null"
    rsync -az --exclude=/fish.db --exclude=/fish.db-journal --exclude=/fish.db-wal --exclude=/fish.db-shm \
        --exclude='/.snapshot-fish.db*' --exclude=/wechat.lock ${prev:+--link-dest="$prev"} \
        "$BOX:$REMOTE_DIR/data/" "$tmp/"
    rsync -az "$BOX:$REMOTE_DIR/data/.snapshot-fish.db" "$tmp/fish.db"
    ssh -o BatchMode=yes -o ConnectTimeout=15 "$BOX" "rm -f $REMOTE_DIR/data/.snapshot-fish.db"
    count="$("$PY" scripts/snapshot_db.py --check "$tmp/fish.db")" || {
        echo "$(date '+%F %T') 备份失败：拿到的数据库打不开，旧备份没动" >&2
        exit 1
    }
    mv "$tmp" "$DEST/$stamp"
    trap - EXIT
    touch "$DEST/$stamp/.done"
    before=0
    [ -n "$prev" ] && [ -f "$prev/fish.db" ] && before="$("$PY" scripts/snapshot_db.py --check "$prev/fish.db" 2>/dev/null || echo 0)"
    # Fewer messages than last time means something ate her: keep every old copy and shout.
    if [ "$count" -lt "$before" ]; then
        echo "$(date '+%F %T') ！聊天记录比上一份少了（${before} → ${count} 条），这次没删任何旧备份，赶紧看看：${DEST}" >&2
        exit 1
    fi
    ls -1d "$DEST"/20* | sort -r | tail -n "+$((KEEP + 1))" | while IFS= read -r old; do
        rm -rf "$old"
    done
    echo "$(date '+%F %T') 备份好了：${stamp}，${count} 条聊天"
}

install_timer() {
    [ "$(uname)" = Darwin ] || { echo "--install is for the Mac" >&2; exit 2; }
    mkdir -p "$DEST" "$(dirname "$PLIST")"
    chmod 700 "$DEST"
    cat > "$PLIST" <<PLIST_END
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/sh</string><string>$REPO/scripts/backup_box.sh</string><string>--auto</string></array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>StartInterval</key><integer>21600</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$DEST/backup.log</string>
  <key>StandardErrorPath</key><string>$DEST/backup.log</string>
</dict></plist>
PLIST_END
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    echo "装好了：每 6 小时试一次，一天备份一份。日志在 ${DEST}/backup.log"
}

case "${1:-now}" in
    now)    back_up ;;
    --auto) fresh 1200 || back_up ;;
    --check)
        if [ -z "$(latest)" ]; then
            echo "！还没有自动备份：跑一次 scripts/backup_box.sh --install"
        elif ! fresh 4320; then
            echo "！最新的备份已经超过 3 天了：$(basename "$(latest)")，看 ${DEST}/backup.log"
        fi ;;
    --install) install_timer ;;
    --uninstall)
        launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
        rm -f "$PLIST"
        echo "定时备份停了，已有的备份还在 ${DEST}" ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
esac
