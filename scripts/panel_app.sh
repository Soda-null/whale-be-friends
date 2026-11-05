#!/bin/sh
# Make 大肥鱼.app in ~/Applications: double-click it instead of opening a terminal (decision 54).
#
#   scripts/panel_app.sh              make or update it
#   scripts/panel_app.sh --uninstall  remove it
set -eu
cd "$(dirname "$0")/.."
REPO="$(pwd)"
APP="$HOME/Applications/大肥鱼.app"
[ "$(uname)" = Darwin ] || { echo "this one is for the Mac; elsewhere run: .venv/bin/python -m fish.panel" >&2; exit 2; }
if [ "${1:-}" = --uninstall ]; then
    rm -rf "$APP"
    echo "删掉了 ${APP}"
    exit 0
fi
[ -x .venv/bin/python ] || { echo "no .venv here yet: run ./install.sh first" >&2; exit 2; }
mkdir -p "$HOME/Applications"
rm -rf "$APP"
osacompile -o "$APP" -e "do shell script \"cd \" & quoted form of \"$REPO\" & \" && nohup .venv/bin/python -m fish.panel >/dev/null 2>&1 &\""
echo "做好了：${APP}（Spotlight 搜“大肥鱼”，或者拖到程序坞）"
