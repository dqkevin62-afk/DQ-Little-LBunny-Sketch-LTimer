# -*- coding: utf-8 -*-
"""桌面版验证脚本：跑 dist 里的 exe，检查页面窗口 / 桌宠窗口 / 资源目录，并截图。

用法（在 sketch-trainer 目录下）：
  C:/Users/admin/.workbuddy/binaries/python/envs/default/Scripts/python.exe tools/test-desktop.py
"""
import ctypes
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXE = os.path.join(ROOT, "dist", "DQ小兔速写计时姬.exe")
APP = "DQ小兔速写计时姬"      # 页面窗口标题 / 桌宠窗口标题
DATA = "DQ速写计时姬"          # 网页资源目录沿用旧名（改名不重生成）

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

u = ctypes.windll.user32
u.SystemParametersInfoW.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
u.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
u.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
u.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
u.IsWindowVisible.argtypes = [ctypes.c_void_p]


class RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                ("r", ctypes.c_long), ("b", ctypes.c_long)]


def work_area():
    a = RECT()
    u.SystemParametersInfoW(0x30, 0, ctypes.byref(a), 0)
    return a


def top_windows():
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    out = []

    def cb(h, _):
        if u.IsWindowVisible(h):
            n = u.GetWindowTextLengthW(h)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                u.GetWindowTextW(h, buf, n + 1)
                r = RECT()
                u.GetWindowRect(h, ctypes.byref(r))
                out.append((buf.value, r.l, r.t, r.r, r.b, r.r - r.l, r.b - r.t))
        return True

    u.EnumWindows(EnumProc(cb), None)
    return out


def main():
    fails = []
    if not os.path.exists(EXE):
        print("[X] 找不到 %s" % EXE)
        return 1
    print("[OK] exe 存在: %s (%.1f MB)" % (EXE, os.path.getsize(EXE) / 1048576.0))

    wa = work_area()
    print("[i] 工作区(物理): %d x %d" % (wa.r - wa.l, wa.b - wa.t))

    proc = subprocess.Popen([EXE])
    print("[i] 已启动 pid=%s，等待 7 秒…" % proc.pid)
    time.sleep(7.0)

    wins = top_windows()
    page = [w for w in wins if w[0].startswith(APP) and w[5] > 600]
    pet = [w for w in wins if w[0] == APP and w[5] < 400]

    if page:
        w = page[0]
        print("[OK] 页面窗口: '%s' %dx%d @ (%d,%d)" % (w[0], w[5], w[6], w[1], w[2]))
        if w[5] < 1100:
            fails.append("页面窗口偏窄: %d" % w[5])
        if w[3] > wa.r or w[4] > wa.b:
            fails.append("页面窗口超出工作区")
    else:
        fails.append("没有找到页面窗口")

    if pet:
        w = pet[0]
        print("[OK] 桌宠窗口: %dx%d @ (%d,%d)" % (w[5], w[6], w[1], w[2]))
        if abs(w[3] - wa.r) > 80 or abs(w[4] - wa.b) > 120:
            fails.append("桌宠不在右下角")
        if w[5] > 400:
            fails.append("桌宠太大: %d" % w[5])
    else:
        fails.append("没有找到桌宠窗口")

    web = os.path.join(os.environ.get("LOCALAPPDATA", ""), DATA, "web")
    if os.path.isdir(os.path.join(web, "assets", "voice")):
        print("[OK] 网页资源已落地: %s" % web)
    else:
        fails.append("网页资源目录不完整: %s" % web)

    log_path = os.path.join(os.environ.get("TEMP", ""), "DQ-speed-sketch.log")
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            tail = f.read().strip().splitlines()[-4:]
        print("[i] 最近日志:")
        for line in tail:
            print("     " + line)

    try:
        from PIL import ImageGrab
        shot = os.path.join(ROOT, "desktop", "_verify.png")
        ImageGrab.grab().save(shot)
        print("[OK] 截图: %s" % shot)
    except Exception as exc:
        print("[!] 截图失败: %r" % (exc,))

    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                   capture_output=True)
    print("[i] 已结束进程")

    if fails:
        print("\n失败项:")
        for f in fails:
            print("  [X] " + f)
        return 1
    print("\n全部检查通过 ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
