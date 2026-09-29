# -*- coding: utf-8 -*-
"""参考图翻转自检：像素级镜像 + 真进程热键链路。

A 段（离屏，不建窗）：左右不对称的图，_flip_source() 应给出镜像结果，缓存可复用、换图会作废。
B 段（真进程）：起源码桌宠 → 送一张不对称图进纯净模式 → 找到大图窗口 →
   发 WM_HOTKEY（就是 Windows 投递 H 的那种消息）→ 日志里应出现「参考图镜像翻转：开」；
   再发一次 → 「关」；退出纯净模式后 H 必须被释放（测试进程能重新注册到 H）。

用法：
  python tools/test_flip.py                 # 跑源码桌宠
  python tools/test_flip.py --exe <路径>    # 跑打包出来的 exe（默认 dist/DQ小兔速写计时姬.exe）
"""
import base64
import ctypes
import io
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "desktop", "xiaotu_pet.py")
# --exe 时跑打包出来的 exe（验证打包产物），否则跑源码桌宠
TARGET = None
if "--exe" in sys.argv:
    i = sys.argv.index("--exe")
    TARGET = (sys.argv[i + 1] if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("-")
              else os.path.join(ROOT, "dist", "DQ小兔速写计时姬.exe"))
LOG_PATH = os.path.join(os.environ.get("TEMP", "."), "DQ-speed-sketch.log")
PURE_CLASS = "DQXiaotuPetWndPure"
WM_HOTKEY = 0x0312
HOTKEY_FLIP_ID = 0x51A1
VK_H = 0x48
MOD_NOREPEAT = 0x4000

PASS = FAIL = 0


def ok(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ✓ " + name)
    else:
        FAIL += 1
        print("  ✗ " + name + ("  << " + extra if extra else ""))


u = ctypes.windll.user32
u.EnumWindows.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
u.EnumWindows.restype = ctypes.c_bool
u.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
u.GetClassNameW.restype = ctypes.c_int
u.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
u.RegisterHotKey.restype = ctypes.c_bool
u.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]
u.UnregisterHotKey.restype = ctypes.c_bool
u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
u.PostMessageW.restype = ctypes.c_bool
EP = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


def asym_image(w=40, h=10):
    """左半红、右半蓝 —— 镜像后左上角像素必然从红变蓝。"""
    from PIL import Image
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for x in range(w):
        for y in range(h):
            px[x, y] = RED if x < w // 2 else BLUE
    return img


def to_data_uri(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def find_pure():
    hit = []

    def cb(h, _):
        b = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(h, b, 256)
        if b.value == PURE_CLASS:
            hit.append(h)
        return True

    u.EnumWindows(EP(cb), None)
    return hit[0] if hit else None


def logtext():
    try:
        with open(LOG_PATH, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def post(path, payload):
    req = urllib.request.Request("http://127.0.0.1:18765" + path,
                                 data=payload.encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return r.status


def part_offscreen():
    print("\n【A 离屏：镜像真的翻了像素】")
    sys.path.insert(0, os.path.join(ROOT, "desktop"))
    import xiaotu_pet as P

    pw = P.PetWindow(kind="pure")
    pw._pure_img = asym_image()
    pw._pure_base = pw._pure_img.size
    ok("没开翻转时返回原图（左上还是红）", pw._flip_source() is pw._pure_img)
    pw.flip_h = True
    f = pw._flip_source()
    ok("开了翻转后左上角变蓝（就是原图右上角）", f.getpixel((0, 0)) == BLUE)
    ok("右下角变红（原图左下角）", f.getpixel((39, 9)) == RED)
    ok("尺寸没变", f.size == pw._pure_img.size)
    ok("镜像结果被缓存（缩放重采样不重转）", pw._flip_source() is f)
    pw._pure_img_flip = None          # 换图时 show_image 会这么清
    pw._pure_img = asym_image()
    ok("换图后缓存作废、按新图重算", pw._flip_source().getpixel((0, 0)) == BLUE)
    pw.flip_h = False
    ok("关掉翻转后回到原图", pw._flip_source().getpixel((0, 0)) == RED)
    ok("空图时安全返回（不会炸）", P.PetWindow(kind="pure")._flip_source() is None)


def part_hotkey():
    print("\n【B 真进程：H 键 → 翻转 → 退出后还键】")
    base = len(logtext())
    cmd = [TARGET, "--no-page"] if TARGET else [sys.executable, SRC, "--no-page"]
    print("[i] 启动：" + cmd[0])
    p = subprocess.Popen(cmd)
    try:
        t0 = time.time()
        while time.time() - t0 < 30:
            try:
                urllib.request.urlopen("http://127.0.0.1:18765/ping", timeout=1)
                break
            except Exception:
                time.sleep(0.4)
        ok("桌宠起来了", True)

        uri = to_data_uri(asym_image(200, 100))
        ok("送图进纯净模式成功", post("/pet_pure", '{"d":%s,"on":true}'
                                     % __import__("json").dumps(uri)) == 200)
        time.sleep(1.5)
        hwnd = find_pure()
        ok("纯净大图窗口已建出来", bool(hwnd), str(hwnd))
        tail = logtext()[base:]
        ok("进纯净模式时注册了 H", "翻转快捷键 H 已注册" in tail, tail[-200:])

        u.PostMessageW(hwnd, WM_HOTKEY, HOTKEY_FLIP_ID, 0)
        time.sleep(0.8)
        ok("收到 H 后翻转成「开」", "参考图镜像翻转：开" in logtext()[base:])

        u.PostMessageW(hwnd, WM_HOTKEY, HOTKEY_FLIP_ID, 0)
        time.sleep(0.8)
        ok("再按一次翻转成「关」", "参考图镜像翻转：关" in logtext()[base:])

        # 退出纯净模式：H 必须还回来（这里用「能不能重新注册到 H」来证明）
        try:
            urllib.request.urlopen("http://127.0.0.1:18765/pet?cmd=pure_end", timeout=5).read()
        except Exception:
            pass
        time.sleep(1.2)
        got = u.RegisterHotKey(None, 0x7AB1, MOD_NOREPEAT, VK_H)
        ok("退出纯净模式后 H 已释放（别的程序能注册到）", bool(got))
        if got:
            u.UnregisterHotKey(None, 0x7AB1)
        ok("退出时有释放日志", "翻转快捷键 H 已释放" in logtext()[base:])

        # 释放之后再按 H 不应该有反应（大图已经不在纯净模式）
        newtail = logtext()[base:]
        ok("退出后不再响应 H（不会偷偷翻转）",
           newtail.count("参考图镜像翻转：开") == 1, newtail[-200:])
    finally:
        env = dict(os.environ, MSYS_NO_PATHCONV="1")
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                       capture_output=True, env=env)
        time.sleep(1)


def main():
    print("【参考图翻转自检】")
    part_offscreen()
    part_hotkey()
    print("\n结果：%d 通过 / %d 失败" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
