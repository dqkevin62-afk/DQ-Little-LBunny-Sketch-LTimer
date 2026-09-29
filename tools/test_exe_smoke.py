# -*- coding: utf-8 -*-
"""打包后的 exe 冒烟：单实例 + 重复双击提示 + 启动清残图。

用 `--no-page` 起，不会开浏览器窗口，不会打扰正在用的浏览器。
用法：python tools/test_exe_smoke.py
产物要求：先跑过 tools/build-exe.py（dist/DQ小兔速写计时姬.exe）。
"""
import ctypes
import os
import subprocess
import sys
import time
import urllib.request

EXE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "dist", "DQ小兔速写计时姬.exe")
LOG_PATH = os.path.join(os.environ.get("TEMP", "."), "DQ-speed-sketch.log")

u = ctypes.windll.user32
u.EnumWindows.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
u.EnumWindows.restype = ctypes.c_bool
u.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
u.GetClassNameW.restype = ctypes.c_int
EP = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

P = F = 0


def ok(name, cond, extra=""):
    global P, F
    if cond:
        P += 1
        print("  ✓ " + name)
    else:
        F += 1
        print("  ✗ " + name + ("  << " + extra if extra else ""))


def pet_windows():
    out = []

    def cb(h, _):
        b = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(h, b, 256)
        if b.value.startswith("DQXiaotuPetWnd"):
            out.append(h)
        return True

    u.EnumWindows(EP(cb), None)
    return out


def ping():
    try:
        with urllib.request.urlopen("http://127.0.0.1:18765/ping", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def logtext():
    try:
        with open(LOG_PATH, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def main():
    print("【exe 验证】" + EXE)
    if not os.path.exists(EXE):
        print("[X] 没有 exe")
        return 2
    ok("exe 存在（%.1f MB）" % (os.path.getsize(EXE) / 1048576.0), True)

    import tempfile
    orphan = os.path.join(tempfile.gettempdir(), "dq_pet_orphan_verify.png")
    with open(orphan, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    ok("先放一个「上次残留」的临时图片", os.path.exists(orphan))

    base = len(logtext())
    a = subprocess.Popen([EXE, "--no-page"])
    try:
        t0 = time.time()
        while time.time() - t0 < 45 and not ping():
            time.sleep(0.5)
        ok("exe 起来了（/ping 通）", ping(), "等了 %.1fs" % (time.time() - t0))
        ok("exe 把上次残留的临时图片清掉了", not os.path.exists(orphan))

        b = subprocess.Popen([EXE, "--no-page"])
        t1 = time.time()
        while time.time() - t1 < 10 and b.poll() is None:
            time.sleep(0.3)
        ok("再双击一次：第二个 exe 自己退出", b.poll() is not None, "exitcode=%s" % b.poll())
        ok("屏幕上仍然只有一个小兔", len(pet_windows()) == 1, "窗口数=%d" % len(pet_windows()))
        tail = logtext()[base:]
        ok("日志里有「已有小兔在运行」", "已有小兔在运行" in tail, tail[-200:])
        ok("日志里有提示「小兔已经在运行了哦」",
           "跳一下并提示：小兔已经在运行了哦" in tail, tail[-200:])
        try:
            with urllib.request.urlopen("http://127.0.0.1:18765/pet?cmd=already", timeout=3) as r:
                ok("exe 里 /pet?cmd=already 可用", r.status == 200)
        except Exception as e:
            ok("exe 里 /pet?cmd=already 可用", False, str(e))
    finally:
        # PyInstaller 单文件模式：exe 是启动器，真正的程序在子进程里，
        # 只 terminate 父进程不够 —— 要按进程树一起杀（MSYS_NO_PATHCONV 防 /PID 被当路径）
        env = dict(os.environ, MSYS_NO_PATHCONV="1")
        subprocess.run(["taskkill", "/PID", str(a.pid), "/T", "/F"],
                       capture_output=True, env=env)
        for _ in range(20):
            if not pet_windows():
                break
            time.sleep(0.5)
        ok("收尾后小兔窗口关掉", len(pet_windows()) == 0, "窗口数=%d" % len(pet_windows()))
    print("\n结果：%d 通过 / %d 失败" % (P, F))
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
