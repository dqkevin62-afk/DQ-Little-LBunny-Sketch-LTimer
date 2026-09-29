# -*- coding: utf-8 -*-
"""端到端验证纯净模式：点开始 → 主界面一步隐藏 + 大图立刻弹出。

起真实桌宠（带页面），先记下主界面窗口，再用 HTTP 触发「进入纯净模式」，
然后看主界面是不是真的看不见了、大图窗口是不是真的出来了。测完自动收摊。
"""
import ctypes
import subprocess
import time
import urllib.request

import json as _json

PY = r"C:\Users\admin\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
BASE = "http://127.0.0.1:18765"
PET_CLASS = "DQXiaotuPetWnd"
APP_NAME = "DQ小兔速写计时姬"

u32 = ctypes.windll.user32
u32.IsWindowVisible.argtypes = [ctypes.c_void_p]
u32.IsWindowVisible.restype = ctypes.c_bool
u32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
u32.GetWindowTextLengthW.restype = ctypes.c_int
u32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
u32.GetWindowTextW.restype = ctypes.c_int
u32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
u32.FindWindowW.restype = ctypes.c_void_p
u32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
u32.GetClassNameW.restype = ctypes.c_int
u32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
u32.GetWindowLongW.restype = ctypes.c_long

fails = []


def check(name, cond, extra=""):
    print(("  [OK] " if cond else "  [X] ") + name + ("  -> " + extra if extra and not cond else ""))
    if not cond:
        fails.append(name)


def post(path, obj):
    req = urllib.request.Request(BASE + path, method="POST")
    raw = _json.dumps(obj).encode("utf-8")
    req.add_header("Content-Type", "application/json")
    try:
        r = urllib.request.urlopen(req, data=raw, timeout=10)
        return r.status
    except Exception as e:
        return getattr(e, "code", -1)


def find_page_hwnd():
    """枚举可见窗口，找标题里带应用名、有标题栏的那个（Chrome --app 窗口）。

    过滤条件必须和桌面端 find_page_window() 一致（标题栏那条不能少），
    否则会抓到 Chrome 内部的子窗口，看到的可见性不是一回事。
    """
    GWL_STYLE = -16
    WS_CAPTION = 0x00C00000
    hits = []
    EP = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(h, _l):
        try:
            if not u32.IsWindowVisible(h):
                return True
            cn = ctypes.create_unicode_buffer(256)
            u32.GetClassNameW(h, cn, 256)
            if cn.value.startswith(PET_CLASS):
                return True
            n = u32.GetWindowTextLengthW(h)
            if n <= 0:
                return True
            b = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(h, b, n + 1)
            if APP_NAME not in b.value:
                return True
            if not (u32.GetWindowLongW(h, GWL_STYLE) & WS_CAPTION):
                return True
            hits.append(h)
        except Exception:
            pass
        return True

    u32.EnumWindows(EP(cb), 0)
    return hits[0] if hits else 0


def big_img():
    import base64
    import io
    import os
    from PIL import Image
    im = Image.frombytes("RGB", (1200, 900), os.urandom(1200 * 900 * 3))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


proc = subprocess.Popen([PY, "desktop/xiaotu_pet.py"])
try:
    up = False
    for _ in range(100):
        try:
            if urllib.request.urlopen(BASE + "/ping", timeout=1).status == 200:
                up = True
                break
        except Exception:
            pass
        time.sleep(0.5)
    check("桌宠 + 页面起来了", up)
    if not up:
        raise SystemExit(1)

    hwnd = 0
    for _ in range(40):
        hwnd = find_page_hwnd()
        if hwnd:
            break
        time.sleep(0.5)
    check("找到速写主界面窗口", bool(hwnd))
    check("进入前主界面是可见的", bool(hwnd) and bool(u32.IsWindowVisible(hwnd)))

    d = big_img()
    check("预推参考图成功", post("/pet_preload", {"d": d}) == 200)

    t0 = time.time()
    st = post("/pet_pure", {"d": "", "on": True})     # 用缓存进入（真实点开始的路径）
    dt = time.time() - t0
    check("进入纯净模式成功（用预推的图）", st == 200, str(st))
    print("  [i] 从发请求到进入完成：%.3fs" % dt)
    check("进入耗时 < 0.5s（点下去基本就是立刻）", dt < 0.5, "%.3fs" % dt)

    time.sleep(0.6)
    check("主界面已经看不见了（一步隐藏，不是最小化动画）",
          bool(hwnd) and not u32.IsWindowVisible(hwnd))

    pure_hwnd = u32.FindWindowW(PET_CLASS + "Pure", None)
    check("大图窗口真的弹出来了", bool(pure_hwnd))
    check("大图窗口可见", bool(pure_hwnd) and bool(u32.IsWindowVisible(pure_hwnd)))

    # 退出：主界面应该回来
    post("/pet_pure", {"on": False})
    time.sleep(1.2)
    check("退出后主界面又回来了", bool(hwnd) and bool(u32.IsWindowVisible(hwnd)))
finally:
    # 只收我们自己起的那棵进程树；绝不按进程名杀 chrome（会误伤用户自己开的浏览器）
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    print("  [i] 已结束桌宠进程（万一有残留的页面窗口，手动关掉即可）")

print("\n结果：" + str(len(fails)) + " 项失败" if fails else "\n全部通过 ✔")
