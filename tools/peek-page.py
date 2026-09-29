# -*- coding: utf-8 -*-
"""可视化自查：用 Chrome 应用窗口打开 index.html，截取指定区域后关闭。

用法：python tools/peek-page.py [输出名] [裁剪区域 x1,y1,x2,y2（相对窗口左上，物理px）]
默认截取侧栏头部。

环境变量 PEEK_PAGE_FILE：改成打开根目录下另一个 html（例如临时改过状态的
_kw_preview.html），用于给折叠卡片 / 非默认状态截图，免动 index.html。
"""
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

from PIL import ImageGrab, Image  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
u = ctypes.windll.user32
u.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
u.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
u.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
u.IsWindowVisible.argtypes = [ctypes.c_void_p]


class R(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                ("r", ctypes.c_long), ("b", ctypes.c_long)]


def win_process_name(hwnd):
    """取窗口所属进程的可执行文件名（小写），用于区分同标题窗口。"""
    try:
        pid = ctypes.c_ulong()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)  # QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = ctypes.c_ulong(1024)
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value).lower()
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    except Exception:
        pass
    return ""


def find(prefix):
    EP = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    hit = []

    def cb(h, _):
        if u.IsWindowVisible(h):
            n = u.GetWindowTextLengthW(h)
            if n > 0:
                b = ctypes.create_unicode_buffer(n + 1)
                u.GetWindowTextW(h, b, n + 1)
                if b.value.startswith(prefix):
                    r = R()
                    u.GetWindowRect(h, ctypes.byref(r))
                    hit.append((h, r.l, r.t, r.r, r.b))
        return True

    u.EnumWindows(EP(cb), None)
    # 同标题窗口可能不止一个（比如 WorkBuddy 自己的项目窗），优先取 chrome.exe 的
    for h in hit:
        if win_process_name(h[0]) == "chrome.exe":
            return h
    return hit[0] if hit else None


def to_front(hwnd):
    """把窗口提到最前并激活。否则 ImageGrab 会抓到压在上面的别的窗口。"""
    u.ShowWindow(hwnd, 5)          # SW_SHOW
    u.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)  # HWND_TOPMOST, NOSIZE|NOMOVE
    u.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002)  # HWND_NOTOPMOST
    try:
        u.SetForegroundWindow(hwnd)
        u.BringWindowToTop(hwnd)
    except Exception:
        pass
    time.sleep(1.2)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "_vis"
    box = None
    if len(sys.argv) > 2:
        box = tuple(int(v) for v in sys.argv[2].split(","))
    chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    page = os.environ.get("PEEK_PAGE_FILE") or "index.html"
    uri = "file://" + quote(os.path.join(ROOT, page).replace("\\", "/"), safe="/:")
    prof = os.path.join(tempfile.gettempdir(), "dq_peek_prof_%d" % os.getpid())
    p = subprocess.Popen([chrome, "--app=" + uri, "--user-data-dir=" + prof,
                          "--no-first-run", "--no-default-browser-check",
                          "--window-size=1180,860", "--window-position=120,60"])
    try:
        time.sleep(6)
        hit = find("DQ小兔速写计时姬")
        if not hit:
            print("[X] 没找到页面窗口")
            return 1
        hwnd, l, t, r_, b_ = hit
        print("[i] 页面窗口:", (l, t, r_, b_))
        to_front(hwnd)
        shot = ImageGrab.grab()
        crop = (l + box[0], t + box[1], l + box[2], t + box[3]) if box else (l, t, r_, b_)
        img = shot.crop(crop)
        scale = 3 if (crop[2] - crop[0]) < 600 else 1
        if scale > 1:
            img = img.resize(((crop[2] - crop[0]) * scale, (crop[3] - crop[1]) * scale),
                             Image.LANCZOS)
        dst = os.path.join(ROOT, "desktop", out + ".png")
        img.save(dst)
        print("[OK]", dst, img.size)
    finally:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
        shutil.rmtree(prof, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
