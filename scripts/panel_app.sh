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
# Her face as the icon; a picture the app does not get is no reason to fail.
ICONSET="$(mktemp -d)/her.iconset"
mkdir -p "$ICONSET"
if for size in 16 32 64 128 256 512; do
       sips -z "$size" "$size" src/fish/panel/img/app_icon.png --out "$ICONSET/icon_${size}x${size}.png" >/dev/null 2>&1 || exit 1
       half=$((size / 2))
       [ "$half" -lt 16 ] || cp "$ICONSET/icon_${size}x${size}.png" "$ICONSET/icon_${half}x${half}@2x.png"
   done && iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/applet.icns" 2>/dev/null; then
    codesign --force --sign - "$APP" >/dev/null 2>&1 || true
    touch "$APP"
fi
rm -rf "$(dirname "$ICONSET")"
echo "做好了：${APP}（Spotlight 搜“大肥鱼”，或者拖到程序坞）"
