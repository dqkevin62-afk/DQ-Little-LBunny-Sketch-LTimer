# -*- coding: utf-8 -*-
"""单实例自检：连开两次桌宠，确认「只有一个小兔在跑 + 第二次会提示 + 退出不留残图」。

分两段：
  ① 真实进程：起源码桌宠 A（--no-page），再起 B，断言 B 自动退出、窗口只有一个、
     日志里出现「已有小兔在运行」与「小兔已在运行，跳一下并提示：小兔已经在运行了哦」。
  ② 进程内：造几个临时图片，调 sweep_temp_images()，确认全部清掉（残留图片缓存）。

用法：python tools/test_single_instance.py
"""
import ctypes
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "desktop", "xiaotu_pet.py")
LOG_PATH = os.path.join(os.environ.get("TEMP", "."), "DQ-speed-sketch.log")

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
EP = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)


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


class RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                ("r", ctypes.c_long), ("b", ctypes.c_long)]


def sample_hop(frames=26, gap=0.05):
    """采几帧小兔窗口的上边缘 Y：返回 (最大抬起量, 结束时与起始的偏差)。"""
    ws = pet_windows()
    if not ws:
        return (0, 999)
    hwnd = ws[0]
    ys = []
    for _ in range(frames):
        r = RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))
        ys.append(r.t)
        time.sleep(gap)
    top = min(ys)               # 抬起 = Y 变小
    return (ys[0] - top, abs(ys[-1] - ys[0]))


def read_log():
    try:
        with open(LOG_PATH, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def part_processes():
    print("\n【真实进程：连开两次 exe】")
    base = len(read_log())
    a = subprocess.Popen([sys.executable, SRC, "--no-page"])
    try:
        for _ in range(40):
            if ping():
                break
            time.sleep(0.4)
        ok("第一个实例起来了（/ping 通）", ping())

        b = subprocess.Popen([sys.executable, SRC, "--no-page"])
        t0 = time.time()
        while time.time() - t0 < 8 and b.poll() is None:
            time.sleep(0.3)
        ok("第二个实例自己退出了（不再重复起桌宠）", b.poll() is not None,
           "exitcode=%s" % b.poll())
        ok("第二个实例退得干脆（5 秒内）", time.time() - t0 < 5, "耗时 %.1fs" % (time.time() - t0))
        ok("屏幕上只有一个小兔窗口", len(pet_windows()) == 1, "窗口数=%d" % len(pet_windows()))
        ok("小兔仍然活着（第一个实例没被带崩）", a.poll() is None and ping())

        time.sleep(1.0)
        tail = read_log()[base:]
        ok("第二个实例记下「已有小兔在运行」", "已有小兔在运行" in tail, tail[-300:])
        ok("正在跑的小兔收到通知并提示：小兔已经在运行了哦",
           "小兔已在运行，跳一下并提示：小兔已经在运行了哦" in tail, tail[-300:])

        # 自己再打一次通知，紧跟着采几帧，量「跳一下」的位移（第二个实例那一跳
        # 会因为进程退出的延迟错过峰值，所以这里单独量一次）
        try:
            with urllib.request.urlopen("http://127.0.0.1:18765/pet?cmd=already",
                                        timeout=3):
                pass
        except Exception:
            pass
        jump = sample_hop()
        ok("小兔真的跳了一下（抬起明显）", jump[0] >= 8, "最大位移 %d px" % jump[0])
        ok("跳完落回原位（不是卡在上面）", jump[1] <= 6, "落回偏差 %d px" % jump[1])
    finally:
        try:
            a.terminate()
        except Exception:
            pass
        time.sleep(1.5)
        ok("收尾后小兔窗口已关掉", len(pet_windows()) == 0, "窗口数=%d" % len(pet_windows()))


def part_temp_images():
    print("\n【退出不留残图：临时图片清理】")
    sys.path.insert(0, os.path.join(ROOT, "desktop"))
    import tempfile
    import glob
    import xiaotu_pet as P

    tmpdir = tempfile.gettempdir()
    # ① 模拟上次异常退出留下的孤儿图
    orphan = os.path.join(tmpdir, "dq_pet_orphan_test.png")
    with open(orphan, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    # ② 本次运行生成的（走 materialize_image，会被记进 TMP_FILES 名单）
    import base64
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(buf, format="PNG")
    tiny = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    made = P.materialize_image(tiny)
    ok("materialize_image 能落地临时图片", bool(made) and os.path.exists(made or ""), str(made))
    ok("落地的图片被记进待清理名单", (made in P.TMP_FILES) if made else False)
    ok("孤儿图确实存在（清理前）", os.path.exists(orphan))

    n = P.sweep_temp_images()
    ok("sweep_temp_images 清掉了这批图", n >= 2, "清掉 %d 个" % n)
    ok("「本次生成的」已删掉", not (made and os.path.exists(made)))
    ok("「上次残留的」也一起扫掉", not os.path.exists(orphan))
    ok("临时目录里没有 dq_pet_*.png 残留",
       not glob.glob(os.path.join(tmpdir, "dq_pet_*.png")),
       str(glob.glob(os.path.join(tmpdir, "dq_pet_*.png"))[:3]))
    ok("清理名单已清空（不会重复记账）", len(P.TMP_FILES) == 0)


def main():
    print("【单实例自检】" + SRC)
    if pet_windows():
        print("[!] 已经有小兔在跑，先退出它再测")
        return 2
    part_processes()
    part_temp_images()
    print("\n结果：%d 通过 / %d 失败" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
