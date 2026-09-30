# -*- coding: utf-8 -*-
"""打包 DQ速写计时姬 桌面版 exe。

用法（在 sketch-trainer 目录下）：
  C:/Users/admin/.workbuddy/binaries/python/envs/default/Scripts/python.exe tools/build-exe.py

产物：sketch-trainer/dist/DQ速写计时姬.exe（单文件，双击即用）
依赖：pip install pyinstaller pillow

打包完成后会自动打开根目录的 CHANGELOG.md（更新记录），并把当前版本的更新内容
打印到控制台，方便确认这一版改了什么。
"""
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = r"C:\Users\admin\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
PYI = r"C:\Users\admin\.workbuddy\binaries\python\envs\default\Scripts\pyinstaller.exe"

ARGS = [
    "--noconfirm", "--clean", "--onefile", "--noconsole",
    "--name", "DQ小兔速写计时姬",
    "--icon", "assets/pet/xiaotu.ico",
    "--add-data", "index.html;.",
    "--add-data", "assets;assets",
    # 瘦身：这些库一个都用不到
    "--exclude-module", "numpy",
    "--exclude-module", "tkinter",
    "--exclude-module", "matplotlib",
    "--exclude-module", "scipy",
    "--exclude-module", "pandas",
    "--exclude-module", "PyQt5",
    "--exclude-module", "PySide6",
    "--exclude-module", "IPython",
    "--exclude-module", "pytest",
    "--exclude-module", "setuptools",
    "--distpath", "dist",
    "--workpath", "build",
    "desktop/xiaotu_pet.py",
]


def read_version():
    """版本号**只认 index.html 里的 APP_VER**（和网页侧栏、exe 分享卡片同一个来源）。

    ⚠️ 别再去正则侧栏那个 `<span class="ver">`：它带 `id="app-ver"` 属性，
    写死 `<span class="ver">` 是**永远匹配不到**的（一直静默兜底成 V0.2 →
    打包完打印出上一个版本的更新记录，2026-09-30 打包 V1.3 时才发现）。
    """
    try:
        html = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
        m = re.search(r'APP_VER\s*=\s*"([^"]+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'<span class="ver"[^>]*>\s*(V[\d.]+)\s*</span>', html)
        return m.group(1) if m else ""
    except Exception:
        return ""


def changelog_notes(tag):
    """截取 CHANGELOG.md 里某个版本条目的正文。"""
    path = os.path.join(ROOT, "CHANGELOG.md")
    if not os.path.exists(path):
        return "", ""
    text = io.open(path, encoding="utf-8").read()
    i = text.find("## [" + tag + "]")
    if i < 0:
        return path, ""
    j = text.find("\n## [", i + 5)
    body = text[i:j].strip() if j > 0 else text[i:].strip()
    return path, body


def main():
    for f in ("desktop/xiaotu_pet.py", "index.html", "assets/pet/xiaotu.ico",
              "assets/pet/xiaotu-pet.png"):
        if not os.path.exists(os.path.join(ROOT, f)):
            print("[X] 缺少文件: %s" % f)
            return 1
    # 坑①：安全删除机制会拦截 PyInstaller 覆盖旧 exe，必须关掉
    os.environ.setdefault("CODEBUDDY_SAFE_DELETE_ENABLED", "0")
    # 坑②：旧 exe 正在运行会被 Windows 锁文件 → WinError 5，先结束掉
    subprocess.run(["taskkill", "/IM", "DQ小兔速写计时姬.exe", "/F"],
                   capture_output=True)
    exe = PY if os.path.exists(PY) else sys.executable
    pyi = PYI if os.path.exists(PYI) else "pyinstaller"
    print("[i] 用 %s 打包…" % pyi)
    r = subprocess.run([pyi] + ARGS, cwd=ROOT)
    if r.returncode != 0:
        print("[X] 打包失败")
        return r.returncode
    out = os.path.join(ROOT, "dist", "DQ小兔速写计时姬.exe")
    print("[OK] 完成: %s (%.1f MB)" % (out, os.path.getsize(out) / 1048576.0))
    print("[i] 验证: %s tools/test-desktop.py" % exe)

    # 打包后显示更新记录：控制台打印 + 用默认程序打开 CHANGELOG.md
    ver = read_version() or "V0.2"
    cl_path, notes = changelog_notes(ver)
    if not cl_path:
        print("[!] 未找到 CHANGELOG.md，建议补一份更新记录")
    elif not notes:
        print("[!] CHANGELOG.md 里没有 %s 的条目，记得补上本次更新内容" % ver)
    else:
        print("\n———— 本次更新（%s）————" % ver)
        print(notes)
        print("——————————————————————\n")
    if cl_path:
        try:
            os.startfile(cl_path)          # 用系统默认程序打开更新记录
            print("[i] 已打开更新记录: %s" % cl_path)
        except Exception as e:
            print("[!] 无法自动打开更新记录（%s），请手动查看: %s" % (e, cl_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
