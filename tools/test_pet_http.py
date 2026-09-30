# -*- coding: utf-8 -*-
"""打包前最后一次真实链路自检：起源码桌宠（--no-page），逐个打 HTTP 接口。

重点覆盖「打卡」相关链路（提醒气泡 / 置顶 / 陪画状态），并确认已删接口确实没了。
跑完自动关掉桌宠进程。
"""
import subprocess
import sys
import time
import urllib.error
import urllib.request

PY = r"C:\Users\admin\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
BASE = "http://127.0.0.1:18765"

fails = []
total = 0


def check(name, cond, extra=""):
    global total
    total += 1
    if cond:
        print("  [OK] " + name)
    else:
        print("  [X] " + name + ("  -> " + extra if extra else ""))
        fails.append(name)


def make_test_image(w=1400, h=1000):
    """造一张大参考图（data:uri），用来量「预推 / 直接进入」的耗时差。"""
    import base64
    import io
    import os
    from PIL import Image
    im = Image.frombytes("RGB", (w, h), os.urandom(w * h * 3))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def code(path, method="GET", body=None):
    req = urllib.request.Request(BASE + path, method=method)
    data = None
    if body is not None:
        data = body.encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        r = urllib.request.urlopen(req, data=data, timeout=4)
        return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return -1, str(e)


def _find_class(cls):
    """按窗口类名找窗口（小兔主窗 / 纯净大图窗）。"""
    import ctypes
    u = ctypes.windll.user32
    u.EnumWindows.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    u.EnumWindows.restype = ctypes.c_bool
    u.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    u.GetClassNameW.restype = ctypes.c_int
    u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                               ctypes.c_size_t, ctypes.c_ssize_t]
    u.PostMessageW.restype = ctypes.c_bool
    hit = []

    def cb(h, _):
        b = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(h, b, 256)
        if b.value == cls:
            hit.append(h)
        return True

    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                     ctypes.c_void_p)(cb), None)
    return (u, hit[0]) if hit else (u, None)


def ensure_no_pet(wait=10.0):
    """跑真进程测试前先把上次残留的小兔请走。

    ⚠️ 2026-09-30 踩：残留实例占着**单实例互斥体**和 **~ / Ctrl+1 全局热键**，
    新起的进程一看「已有小兔在运行」就退出，后面所有断言都会串到那只旧小兔身上。
    """
    if code("/ping")[0] != 200:
        return True
    u, hwnd = _find_class("DQXiaotuPetWnd")
    if hwnd:
        u.PostMessageW(hwnd, 0x0010, 0, 0)      # WM_CLOSE：让窗口线程自己收尾
    t0 = time.time()
    while time.time() - t0 < wait:
        if code("/ping")[0] != 200:
            return True
        time.sleep(0.4)
    return code("/ping")[0] != 200


check("跑之前没有残留的小兔实例（不然单实例锁 + 全局热键会串台）",
      ensure_no_pet())

proc = subprocess.Popen([PY, "desktop/xiaotu_pet.py", "--no-page"])
try:
    up = False
    for _ in range(80):
        s, _ = code("/ping")
        if s == 200:
            up = True
            break
        time.sleep(0.5)
    check("桌宠本地服务起来了（/ping 200）", up)

    s, body = code("/pet_state")
    check("/pet_state 返回 200", s == 200, str(s))
    j = {}
    try:
        import json
        j = json.loads(body)
    except Exception:
        pass
    check("pet_state 带 ok / on / companion / phase（待机提醒靠它判断）",
          all(k in j for k in ("ok", "on", "companion", "phase")), body[:120])
    check("桌宠在线（on=true）", j.get("on") is True, str(j))

    s, _ = code("/pet?cmd=say&secs=8&text=" + urllib.parse.quote("恭喜主人今日速写打卡成功！"))
    check("打卡气泡通道 cmd=say 可用", s == 200, str(s))
    s, _ = code("/pet?cmd=expr&kind=happy")
    check("cmd=expr 可用", s == 200, str(s))
    s, _ = code("/pet?cmd=topmost&on=1")
    check("cmd=topmost 可用", s == 200, str(s))
    s, _ = code("/pet?cmd=pure_end")
    check("cmd=pure_end 可用（纯净模式收尾）", s == 200, str(s))
    s, _ = code("/huaban_search?q=test")
    check("搜索代理仍在（桌宠能力）", s in (200, 400, 500), str(s))

    s, _ = code("/pet?cmd=image_off")
    check("已删的 cmd=image_off 确实没了（400）", s == 400, str(s))
    s, _ = code("/pet?cmd=follow&on=1")
    check("已删的 cmd=follow 确实没了（400）", s == 400, str(s))
    s, _ = code("/pet_image", "POST", '{"d":"x"}')
    check("已删的 POST /pet_image 确实没了（404）", s == 404, str(s))
    s, _ = code("/pet_pure", "POST", '{"d":"","on":false}')
    check("纯净模式入口 /pet_pure 仍在（不能误删）", s in (200, 400, 500), str(s))

    # ---- 参考图预推：点开始就该立刻出图，不该让人等 ----
    import json as _json
    big = make_test_image()
    t0 = time.time()
    s, _ = code("/pet_preload", "POST", _json.dumps({"d": big}))
    t_pre = time.time() - t0
    check("/pet_preload 预推成功", s == 200, str(s))

    t0 = time.time()
    s, _ = code("/pet_pure", "POST", '{"d":"","on":true}')   # 不带图：用缓存进入
    t_in = time.time() - t0
    check("用缓存进入纯净模式（不带图也能起来）", s == 200, str(s))
    code("/pet_pure", "POST", '{"on":false}')                # 退出，准备对比

    t0 = time.time()
    s, _ = code("/pet_pure", "POST", _json.dumps({"d": big, "on": True}))  # 带图进入（老路径）
    t_full = time.time() - t0
    check("带图直接进入也能成功", s == 200, str(s))
    code("/pet_pure", "POST", '{"on":false}')

    print("  [i] 耗时：预推 %.2fs → 用缓存进入 %.2fs（带图直接进入 %.2fs）"
          % (t_pre, t_in, t_full))
    check("预推过的进入明显更快（不用再编码/传输/解码）",
          t_in < t_full * 0.6 or t_in < 0.35, "缓存 %.2fs / 带图 %.2fs" % (t_in, t_full))

    # ---- 点「继续」回到参考图模式：位置和大小都沿用上一次（真窗口矩形）----
    import ctypes
    from ctypes import wintypes
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    u32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    u32.FindWindowW.restype = wintypes.HWND
    u32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    u32.GetWindowRect.restype = wintypes.BOOL

    def pure_rect():
        h = u32.FindWindowW("DQXiaotuPetWndPure", None)
        if not h:
            return None
        r = wintypes.RECT()
        if not u32.GetWindowRect(h, ctypes.byref(r)):
            return None
        return (r.left, r.top, r.right - r.left, r.bottom - r.top)

    code("/pet_pure", "POST", '{"on":false}')
    time.sleep(0.5)
    code("/pet_pure", "POST", _json.dumps({"d": big, "on": True}))   # ① 正常出大图
    time.sleep(0.9)
    r1 = pure_rect()
    check("参考图大窗建出来了（读得到窗口矩形）", r1 is not None, str(r1))
    code("/pet_pure", "POST", '{"on":false}')          # ② 相当于右键「显示主界面」
    time.sleep(0.5)
    code("/pet_pure", "POST", '{"d":"","on":true}')    # ③ 网页点「继续」：回大图
    time.sleep(0.9)
    r2 = pure_rect()
    check("点继续回到大图：还是上一次的位置和大小",
          r1 is not None and r2 is not None and r2 == r1, "%s -> %s" % (r1, r2))

    # ---- 参考图模式：右键「跳过」/ Ctrl+1 / ~ 是不是真能传到网页 ----
    # 桌面端只置信号，网页每秒来取一次；这里就按真实链路验「置了 → 心跳带回去 → 清掉」
    u32.PostMessageW.argtypes = [wintypes.HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_size_t]
    u32.PostMessageW.restype = wintypes.BOOL
    pet_hwnd = u32.FindWindowW("DQXiaotuPetWnd", None)
    check("找得到小兔本体窗口（快捷键由它接收）", bool(pet_hwnd), str(pet_hwnd))
    code("/pet_pure", "POST", _json.dumps({"d": big, "on": True}))
    time.sleep(0.8)

    u32.PostMessageW(pet_hwnd, 0x0312, 0x51B3, 0)          # WM_HOTKEY + Ctrl+1
    time.sleep(0.4)
    _, b = code("/pet?cmd=timer&left=100")
    j = _json.loads(b)
    check("按 Ctrl+1 → 心跳带回 skip（网页据此跳下一张）", j.get("skip") is True, b)
    _, b = code("/pet?cmd=timer&left=100")
    check("skip 取过一次就清零（不会连跳两张）",
          _json.loads(b).get("skip") is False, b)

    u32.PostMessageW(pet_hwnd, 0x0312, 0x51B1, 0)          # WM_HOTKEY + ~
    time.sleep(0.4)
    _, b = code("/pet?cmd=timer&left=100")
    check("按 ~ → 心跳带回 pause=1（网页据此暂停）",
          _json.loads(b).get("pause") == 1, b)
    _, b = code("/pet?cmd=timer&left=100")
    check("pause 取过一次就没了（不会重复下指令）",
          "pause" not in _json.loads(b), b)
    # 再按一次 ~：恢复要等「继续速写 → 3 2 1」播完才放行（不是一按就放）
    u32.PostMessageW(pet_hwnd, 0x0312, 0x51B1, 0)
    time.sleep(0.4)
    _, b = code("/pet?cmd=timer&left=100")
    check("倒数还没播完时，不急着让网页继续", "pause" not in _json.loads(b), b)
    time.sleep(4.2)
    _, b = code("/pet?cmd=timer&left=100")
    check("3 2 1 播完 → 心跳带回 pause=0（网页接着暂停前的计时）",
          _json.loads(b).get("pause") == 0, b)
    code("/pet_pure", "POST", '{"on":false}')
finally:
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except Exception:
        proc.kill()

print("\n结果：" + str(total - len(fails)) + " 通过 / " + str(len(fails)) + " 失败")
sys.exit(1 if fails else 0)
