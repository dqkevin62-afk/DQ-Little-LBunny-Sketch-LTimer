# -*- coding: utf-8 -*-
"""参考图翻转自检：像素级镜像 + 右键菜单入口 + 「不许抢 H 键」。

A 段（离屏，不建窗）：左右不对称的图，_flip_source() 应给出镜像结果，缓存可复用、换图会作废；
   再走一次 menu_cmd(24)（就是右键菜单那一项）验证开/关来回切。
B 段（真进程）：起桌宠 → 送图进纯净模式 → 找到大图窗口 →
   ① 测试进程**还能注册到 H**（说明小兔没抢键，这就是「打字打不出 H」的根因回归点）；
   ② 强行投一条 WM_HOTKEY 过去，**不应该翻转**（热键链路已删干净）。

⚠️ 2026-09-29：全局快捷键 H 已整条删除，翻转只保留参考图上右键菜单那一项。

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
PET_CLASS = "DQXiaotuPetWnd"
WM_HOTKEY = 0x0312
WM_CLOSE = 0x0010
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


def find_class(cls):
    hit = []

    def cb(h, _):
        b = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(h, b, 256)
        if b.value == cls:
            hit.append(h)
        return True

    u.EnumWindows(EP(cb), None)
    return hit[0] if hit else None


def find_pure():
    return find_class(PURE_CLASS)


def ping(timeout=1.0):
    try:
        with urllib.request.urlopen("http://127.0.0.1:18765/ping", timeout=timeout):
            return True
    except Exception:
        return False


def ensure_no_pet(wait=10.0):
    """跑真进程那段之前，先把上次留下的小兔请走。

    ⚠️ 2026-09-30 踩：残留实例占着**单实例互斥体**和 **~ / Ctrl+1 全局热键**，
    新起的进程一看「已有小兔在运行」就直接退出了，请求全被那只旧小兔接走 ——
    它早就注册过热键，不会再打「参考图模式快捷键：已注册」，断言就莫名其妙地红。
    这里先礼貌地 WM_CLOSE 掉旧窗口，等端口放开再开始。
    """
    if not ping():
        return True
    hwnd = find_class(PET_CLASS)
    if hwnd:
        u.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    t0 = time.time()
    while time.time() - t0 < wait:
        if not ping():
            return True
        time.sleep(0.4)
    return not ping()


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

    # 右键菜单那一项：命令 24 → toggle_flip（现在是唯一入口）
    ok("菜单文案是「水平翻转参考图」（不带快捷键提示）",
       getattr(P, "FLIP_MENU_TEXT", "") == "水平翻转参考图", getattr(P, "FLIP_MENU_TEXT", ""))
    pw._pure_img = asym_image()
    pw._pure_base = pw._pure_img.size
    pw.menu_cmd(24)
    ok("右键菜单 24 打开翻转", pw.flip_h is True)
    pw.menu_cmd(24)
    ok("再点一次关掉翻转", pw.flip_h is False)


def part_hotkey():
    print("\n【B 真进程：小兔不许抢 H 键】")
    ok("跑之前没有残留的小兔实例（不然单实例锁 + 全局热键会串台）",
       ensure_no_pet())
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
        ok("这次跑的就是刚起的这只小兔（没被旧实例截胡）",
           "已有小兔在运行" not in tail)
        ok("进纯净模式只注册 ~ / Ctrl+1（翻转热键 H 依然没有）",
           "参考图模式快捷键：已注册" in tail and "翻转快捷键 H 已注册" not in tail,
           tail[-300:])
        # H 必须一直是自由的（以前打字打不出 H 就是它抢的）

        # 关键点：纯净模式里 H 还是自由的（别的程序 / 主人打字能正常用）
        got = u.RegisterHotKey(None, 0x7AB1, MOD_NOREPEAT, VK_H)
        ok("纯净模式里 H 仍可注册（小兔没抢键，打字不受影响）", bool(got))
        if got:
            u.UnregisterHotKey(None, 0x7AB1)

        # 就算有人硬塞一条 WM_HOTKEY 过来，也不该翻转
        u.PostMessageW(hwnd, WM_HOTKEY, HOTKEY_FLIP_ID, 0)
        time.sleep(0.8)
        ok("热键消息不再触发翻转", "参考图镜像翻转：开" not in logtext()[base:])

        try:
            urllib.request.urlopen("http://127.0.0.1:18765/pet?cmd=pure_end", timeout=5).read()
        except Exception:
            pass
        time.sleep(1.2)
        ok("退出纯净模式也没有「释放 H 热键」这类日志",
           "翻转快捷键 H 已释放" not in logtext()[base:])
        ok("退出参考图模式后 ~ / Ctrl+1 立刻还给系统",
           "参考图模式快捷键：已注销" in logtext()[base:], logtext()[base:][-300:])
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
