#!/bin/bash
# DQ小兔速写计时姬 · Mac 版（完整版：页面 + 原生小兔桌宠，需 py2app）
#
# 前置依赖（在 Mac 上一次性安装）：
#   pip install py2app pyobjc-framework-Cocoa
#   （需要 Mac 上有 Python 3，建议 python.org 或 Homebrew 版本）
#
# 用法：
#   cd 项目目录/sketch-trainer/macos
#   bash build_app.sh
#
# 产物：./DQ小兔速写计时姬.app（双击即开页 + 弹出小兔桌宠）
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/.."            # sketch-trainer 根目录
APP_NAME="DQ小兔速写计时姬"
WEB="$SCRIPT_DIR/web"

echo "==> 检查 py2app / PyObjC"
if ! python3 -c "import py2app, Cocoa" 2>/dev/null; then
  echo "[X] 未安装 py2app / PyObjC，请先执行："
  echo "      pip install py2app pyobjc-framework-Cocoa"
  exit 1
fi

echo "==> 拷贝网页资源到 macos/web（供 py2app 打包）"
rm -rf "$WEB"
mkdir -p "$WEB"
cp "$ROOT/index.html" "$WEB/"
cp -R "$ROOT/assets" "$WEB/"

echo "==> py2app 打包中（首次较慢，会自动下载/编译依赖）"
cd "$SCRIPT_DIR"
rm -rf build dist
python3 setup.py py2app

echo "==> 整理为 $APP_NAME.app"
rm -rf "$SCRIPT_DIR/$APP_NAME.app"
if [ -d "$SCRIPT_DIR/dist/app.app" ]; then
  mv "$SCRIPT_DIR/dist/app.app" "$SCRIPT_DIR/$APP_NAME.app"
else
  echo "[X] 未找到 dist/app.app，打包可能失败，请查看上方输出"
  exit 1
fi

echo "==> 完成: $SCRIPT_DIR/$APP_NAME.app"
echo "   双击打开即可：会自动打开速写页面并弹出右下角小兔桌宠。"
echo "   首次若被拦截：右键 → 打开；或运行  xattr -dr com.apple.quarantine \"$SCRIPT_DIR/$APP_NAME.app\""
echo "   桌宠操作：左键拖动移动 / 左键单击开页 / 右键菜单切大小或退出。"
