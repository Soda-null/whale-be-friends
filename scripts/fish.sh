#!/bin/sh
# Look at her on the always-on box from your laptop, every time shown in your timezone
# (TZ= in this checkout's .env; the box's own clock may be elsewhere). See docs/box_zh.md.
#
# Short form: `yu` (a one-line wrapper in ~/.local/bin, see docs/box_zh.md) is this script.
#
#   yu                her day: what she is doing, her room, today, the last 3 diaries
#   yu 7              the same with a week of diaries (any number)
#   yu mem            what she remembers (same as show)
#   yu room           her cottage; yu put 鸡蛋 [顿数] / yu sill 一盆薄荷 put something in
#   yu me             your status as she sees it; yu me 躺在她沙发上 says what you are up to (decision 51)
#   yu 往冰箱放两盒牛奶   anything else is plain words for her room: put things in, take things out
#   yu 把窗台上的小葱拿走   (one model call to understand it; the room's rules do it; decision 36)
#   yu log            live WeChat log
#   yu panel          the same things as a page in the browser (decision 54)
#   yu backup         copy her to this Mac now (it also happens by itself once a day; decision 53)
#   yu review [天数]   how she really did this week, counted (default 7 days; read-only, no model)
#
#   scripts/fish.sh show      what she remembers right now
#   scripts/fish.sh notebook  last night's exported notebook (diary, notes, phase)
#   scripts/fish.sh logs      live WeChat log (Ctrl-C to stop)
#   scripts/fish.sh sent      the last 20 messages she sent, with message_id
#   scripts/fish.sh timers    when the nightly routine runs next
#   scripts/fish.sh browse    make her browse now (by hand; on her own she browses only when she likes)
#   scripts/fish.sh stickers <folder>   give her every picture in a folder on this Mac; she names each now
#   scripts/fish.sh cottage [put 鸡蛋 [顿数] | sill 一盆薄荷]   her cottage as it is now, or put something in (decision 26)
set -eu
cd "$(dirname "$0")/.."
BOX="${BOX:-$(sed -n 's/^BOX=//p' .env 2>/dev/null | tail -1)}"
BOX="${BOX:-box}"  # your SSH alias for the box: BOX= in .env
TZ_USER="$(sed -n 's/^TZ=//p' .env 2>/dev/null | tail -1)"
TZ_USER="${TZ_USER:-UTC}"
case "${1:-life}" in
    life)     scripts/backup_box.sh --check; ssh "$BOX" "cd Dafeiyu && TZ=$TZ_USER .venv/bin/python -m fish life ${2:-}" ;;
    [0-9]*)   scripts/backup_box.sh --check; ssh "$BOX" "cd Dafeiyu && TZ=$TZ_USER .venv/bin/python -m fish life $1" ;;
    backup)   exec scripts/backup_box.sh ;;
    panel)    exec .venv/bin/python -m fish.panel ;;
    put|sill) ssh "$BOX" "cd Dafeiyu && TZ=$TZ_USER .venv/bin/python -m fish cottage $*" ;;
    room)     ssh "$BOX" "cd Dafeiyu && TZ=$TZ_USER .venv/bin/python -m fish cottage" ;;
    me)       ssh "$BOX" "cd Dafeiyu && TZ=$TZ_USER .venv/bin/python -m fish $*" ;;
    review)   ssh "$BOX" "cd Dafeiyu && TZ=$TZ_USER .venv/bin/python - ${2:-7}" < scripts/review.py ;;  # piped: needs no deploy
    mem|show) ssh "$BOX" "cd Dafeiyu && TZ=$TZ_USER .venv/bin/python -m fish show" ;;
    notebook) ssh "$BOX" "cat Dafeiyu/data/notebook_export.md" ;;
    log|logs) ssh -t "$BOX" "TZ=$TZ_USER journalctl --user -u dafeiyu-wechat -f -o short-iso" ;;
    sent)     ssh "$BOX" "TZ=$TZ_USER journalctl --user -u dafeiyu-wechat -o short-iso --no-pager | grep '→' | tail -20" ;;
    timers)   ssh "$BOX" "TZ=$TZ_USER systemctl --user list-timers --no-pager | grep -E 'NEXT|dafeiyu'" ;;
    browse)   ssh "$BOX" "cd Dafeiyu && TZ=$TZ_USER .venv/bin/python -m fish browse" ;;
    stickers)
        folder="${2:?usage: scripts/fish.sh stickers <folder>}"
        [ -d "$folder" ] || { echo "没有这个文件夹：$folder" >&2; exit 2; }
        # Pictures only, into a staging folder on the box; `fish stickers` flattens them into the inbox.
        stage="Dafeiyu/data/stickers/incoming/$(date +%Y%m%d-%H%M%S)"
        ssh "$BOX" "mkdir -p $stage"
        rsync -a --prune-empty-dirs --include='*/' \
            --include='*.[jJ][pP][gG]' --include='*.[jJ][pP][eE][gG]' --include='*.[pP][nN][gG]' \
            --include='*.[gG][iI][fF]' --include='*.[wW][eE][bB][pP]' --exclude='*' \
            "$folder/" "$BOX:$stage/"
        ssh "$BOX" "cd Dafeiyu && TZ=$TZ_USER .venv/bin/python -m fish stickers ~/$stage && rm -rf ~/$stage" ;;
    cottage)  shift; ssh "$BOX" "cd Dafeiyu && TZ=$TZ_USER .venv/bin/python -m fish cottage $*" ;;
    -h|--help|help) echo "用法：yu [天数] | review [天数] | mem | room | put 东西 [顿数] | sill 东西 | log | backup | sent | notebook | timers | browse | stickers <文件夹> | 一句大白话（往冰箱放两盒牛奶、把窗台上的小葱拿走）" ;;
    *)        printf '%s' "$*" | ssh "$BOX" "cd Dafeiyu && TZ=$TZ_USER .venv/bin/python -m fish home -" ;;
esac
