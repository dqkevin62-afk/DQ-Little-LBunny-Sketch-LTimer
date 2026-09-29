#!/bin/bash
# DQ小兔速写计时姬 · Mac 版（简单版，零依赖，仅打开页面，不含桌宠）
# 在 Mac 的「终端」里：
#   cd 项目目录/sketch-trainer/macos
#   bash build_app_simple.sh
# 产物：./DQ小兔速写计时姬.app（双击即用；首次若被拦截，见 README_mac.md）
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_SRC="$SCRIPT_DIR/.."            # sketch-trainer 根目录（含 index.html / assets）
APP_NAME="DQ小兔速写计时姬"
APP="$SCRIPT_DIR/$APP_NAME.app"
WEB_DST="$APP/Contents/Resources/web"

echo "==> 清理旧 .app"
rm -rf "$APP"

echo "==> 建立 .app 结构"
mkdir -p "$APP/Contents/MacOS"
mkdir -p "$WEB_DST"

echo "==> 拷贝网页资源 (index.html + assets)"
cp "$WEB_SRC/index.html" "$WEB_DST/"
cp -R "$WEB_SRC/assets" "$WEB_DST/"

echo "==> 写入启动器（仅开页，无桌宠）"
cat > "$APP/Contents/MacOS/$APP_NAME" <<'LAUNCHER'
#!/bin/bash
# DQ小兔速写计时姬 · macOS 启动器（简单版）
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
INDEX="$HERE/../Resources/web/index.html"
if [ ! -f "$INDEX" ]; then
  osascript -e 'display dialog "找不到网页资源，请重新安装 DQ小兔速写计时姬。" buttons {"好"} default button "好"' 2>/dev/null
  exit 1
fi
encode_url() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe='/:'))" "$1"
  else
    printf '%s' "$1"
  fi
}
FILE_URL="file://$(encode_url "$INDEX")"
if [ -d "/Applications/Google Chrome.app" ]; then
  open -a "Google Chrome" --args "--app=$FILE_URL" "--window-size=1280,820" "--window-position=120,60"
elif [ -d "/Applications/Microsoft Edge.app" ]; then
  open -a "Microsoft Edge" --args "--app=$FILE_URL" "--window-size=1280,820"
else
  open "$INDEX"
fi
LAUNCHER
chmod +x "$APP/Contents/MacOS/$APP_NAME"

echo "==> 写入 Info.plist"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>DQ小兔速写计时姬</string>
  <key>CFBundleDisplayName</key>
  <string>DQ小兔速写计时姬</string>
  <key>CFBundleIdentifier</key>
  <string>com.dq.speedsketch</string>
  <key>CFBundleVersion</key>
  <string>0.1</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1</string>
  <key>CFBundleExecutable</key>
  <string>DQ小兔速写计时姬</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSMinimumSystemVersion</key>
  <string>10.13</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>CFBundleGetInfoString</key>
  <string>DQ小兔速写计时姬 · 二次元美少女速写计时工具</string>
</dict>
</plist>
PLIST

echo "==> 完成: $APP"
echo "   双击打开即可（首次若被拦截：右键 → 打开；或运行  xattr -dr com.apple.quarantine \"$APP\" ）"
echo "   ⚠️ 简单版不含小兔桌宠。要桌宠请用 bash build_app.sh（需装 py2app / PyObjC）。"
