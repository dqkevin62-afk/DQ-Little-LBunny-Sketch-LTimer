# -*- coding: utf-8 -*-
"""
DQ速写计时姬 · 桌面版启动器
1) 优先以「应用窗口」模式打开速写页面（无浏览器地址栏，像原生程序）
2) 同时在屏幕右下角显示一只置顶的小兔桌宠（PNG24 真透明、可拖动）

交互：
  左键拖动 = 移动小兔
  左键单击 = 重新打开速写页面
  右键单击 = 功能菜单（打开页面 / 大小 / 置顶 / 呼吸动画 / 退出）
"""
import ctypes
import ctypes.wintypes as wt
import glob
import hashlib
import http.server
import json
import math
import os
import queue
import random
import shutil
import re
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import urllib.request
from urllib.parse import quote, urlparse, parse_qs

APP_NAME = "DQ小兔速写计时姬"      # 显示用（exe 名 / 桌宠窗口标题）
APP_VER_FALLBACK = "V1.2"         # 只有读不到 index.html 时才用它（真正来源是 APP_VER）
# 数据目录沿用最初的名字，改名也不会导致网页资源和浏览器档案重新生成一遍
DATA_NAME = "DQ速写计时姬"
PET_CLASS = "DQXiaotuPetWnd"
PET = None        # 桌宠实例（供 HTTP 处理器调用陪画模式）
PURE_WIN = None   # 纯净参考图模式的独立大图窗口实例
PURE_LAST_POS = None  # 参考图大窗上次待的位置（左上角 x,y）：跳过 / 自动换图都接着开在这儿
PAGE_HWND = None  # 速写主界面（浏览器 --app 窗口）句柄，打开后记住它，别靠标题临时找
PAGE_PID = None   # 自己拉起的浏览器进程号：退出桌宠时如需强关，只动这一个实例


def set_pure_last_pos(x, y):
    """记住参考图大窗的位置。

    主人把大图拖到哪儿、从哪儿关掉，下次换图（点「跳过」或自动轮播到下一张）
    就还开在同一个地方 —— 以前每次换图都按屏幕中心重排，拖好的位置白拖。
    只活在本次运行里（退出程序就回到「鼠标那块屏居中」的默认行为）。
    """
    global PURE_LAST_POS
    try:
        PURE_LAST_POS = (int(x), int(y))
    except Exception:
        PURE_LAST_POS = None


def pure_last_pos():
    """上次参考图大窗的位置；没开过就是 None（走默认的屏幕居中）。"""
    return PURE_LAST_POS


def _clamp_v(v, lo, hi):
    """把 v 夹进 [lo,hi]；区间反了（窗口比工作区还大）就取 lo。"""
    try:
        v = int(v)
    except Exception:
        return int(lo)
    lo, hi = int(lo), int(hi)
    if hi < lo:
        return lo
    return max(lo, min(v, hi))


def ensure_pure_window():
    """惰性创建/复用纯净参考图大窗（不开小兔、不冒气泡，只显示一张图）。"""
    global PURE_WIN
    if PURE_WIN is None:
        pw = PetWindow(kind="pure")
        pw.anim = False
        pw.topmost = True
        PURE_WIN = pw
    return PURE_WIN


def list_monitor_work_areas():
    """列出所有显示器的工作区矩形（按 左→右、上→下 排序）。

    多屏用户要能把参考图大窗放到任意一块屏上，所以不能只认主屏。
    枚举失败返回空列表，调用方自行回退到「主屏工作区」。
    """
    out = []

    def _cb(hmon, hdc, lprc, data):
        try:
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                out.append(RECT(mi.rcWork.left, mi.rcWork.top,
                                mi.rcWork.right, mi.rcWork.bottom))
            elif lprc:
                r = lprc[0]
                out.append(RECT(r.left, r.top, r.right, r.bottom))
        except Exception:
            pass
        return True

    try:
        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_cb), 0)
    except Exception:
        log("枚举显示器失败\n" + traceback_str())
    seen, uniq = set(), []
    for a in out:
        key = (a.left, a.top, a.right, a.bottom)
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    uniq.sort(key=lambda a: (a.left, a.top))
    return uniq

ERROR_ALREADY_EXISTS = 183
MONITOR_DEFAULTTOPRIMARY = 1     # 找不到所在屏时回主屏
MONITOR_DEFAULTTONEAREST = 2     # 取离窗口最近的那块屏
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SW_SHOWNOACTIVATE = 4
SW_SHOW = 5
SW_HIDE = 0
SW_MINIMIZE = 6
SW_RESTORE = 9
WM_CLOSE = 0x0010
GWL_STYLE = -16
WS_CAPTION = 0x00C00000
ASFW_ANY = 0xFFFFFFFF
SPI_GETWORKAREA = 0x0030
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

WM_DESTROY = 0x0002
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_MOUSEMOVE = 0x0200
WM_RBUTTONUP = 0x0205
WM_MOUSEWHEEL = 0x020A
WM_TIMER = 0x0113
WM_EXITSIZEMOVE = 0x0232
WM_ENTERSIZEMOVE = 0x0231
HWND_BROADCAST = 0xFFFF          # PostMessage 的目标：广播给所有顶层窗口

# 单实例：又双击了一次 exe 时，第二个实例靠这条「注册消息」把正在跑的小兔叫醒
# （同一个字符串在同一会话里注册到的消息号一致，所以两个进程能对上）
WM_ALREADY_MSG = "DQXiaotuPet_AlreadyRunning"
ALREADY_TEXT = "小兔已经在运行了哦"

# ⚠️ 翻转参考图**只走右键菜单**，不注册任何全局快捷键。
#    以前把 H 注册成全局热键（RegisterHotKey），结果主人速写时打字打不出 H
#    —— 2026-09-29 整条热键链路删干净，别再回加。
FLIP_MENU_TEXT = "水平翻转参考图"

MF_STRING = 0x0000
MF_POPUP = 0x0010
MF_SEPARATOR = 0x0800
MF_CHECKED = 0x0008
MF_GRAYED = 0x0001
TPM_RETURNCMD = 0x0100
TPM_RIGHTBUTTON = 0x0002
TPM_NONOTIFY = 0x0080

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
HANDLE = ctypes.c_void_p

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

# --- 明确声明签名，否则 64 位下 WPARAM/LPARAM 会被当成 int 溢出 ---
user32.DefWindowProcW.argtypes = [HANDLE, ctypes.c_uint, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LRESULT
# 同上：不声明的话，DIB 指针地址一旦超过 2^31 就会 OverflowError（画面直接画不出来）
ctypes.memmove.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
ctypes.memmove.restype = ctypes.c_void_p
user32.CreateWindowExW.argtypes = [
    ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    HANDLE, HANDLE, HANDLE, ctypes.c_void_p]
user32.CreateWindowExW.restype = HANDLE
user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
user32.RegisterClassExW.restype = ctypes.c_ushort
user32.GetMessageW.argtypes = [ctypes.c_void_p, HANDLE, ctypes.c_uint, ctypes.c_uint]
user32.GetMessageW.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.c_void_p]
user32.DispatchMessageW.argtypes = [ctypes.c_void_p]
user32.DispatchMessageW.restype = LRESULT
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.DestroyWindow.argtypes = [HANDLE]
user32.ShowWindow.argtypes = [HANDLE, ctypes.c_int]
user32.SetWindowPos.argtypes = [HANDLE, HANDLE, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.GetWindowRect.argtypes = [HANDLE, ctypes.c_void_p]
user32.GetCursorPos.argtypes = [ctypes.c_void_p]
user32.GetCursorPos.restype = ctypes.c_bool
user32.SetCapture.argtypes = [HANDLE]
user32.ReleaseCapture.argtypes = []
user32.SetTimer.argtypes = [HANDLE, ctypes.c_size_t, ctypes.c_uint, ctypes.c_void_p]
user32.SetTimer.restype = ctypes.c_size_t
user32.KillTimer.argtypes = [HANDLE, ctypes.c_size_t]
user32.GetDC.argtypes = [HANDLE]
user32.GetDC.restype = HANDLE
user32.ReleaseDC.argtypes = [HANDLE, HANDLE]
user32.LoadCursorW.argtypes = [HANDLE, ctypes.c_wchar_p]
user32.LoadCursorW.restype = HANDLE
user32.SystemParametersInfoW.argtypes = [ctypes.c_uint, ctypes.c_uint,
                                         ctypes.c_void_p, ctypes.c_uint]
user32.CreatePopupMenu.restype = HANDLE
user32.AppendMenuW.argtypes = [HANDLE, ctypes.c_uint, ctypes.c_size_t, ctypes.c_wchar_p]
user32.DestroyMenu.argtypes = [HANDLE]
user32.TrackPopupMenu.argtypes = [HANDLE, ctypes.c_uint, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, HANDLE, ctypes.c_void_p]
user32.TrackPopupMenu.restype = ctypes.c_int
user32.SetForegroundWindow.argtypes = [HANDLE]
user32.SetForegroundWindow.restype = ctypes.c_bool
user32.EnumWindows.argtypes = [ctypes.c_void_p, LPARAM]
user32.EnumWindows.restype = ctypes.c_bool
user32.IsWindowVisible.argtypes = [HANDLE]
user32.IsWindowVisible.restype = ctypes.c_bool
user32.IsIconic.argtypes = [HANDLE]
user32.IsIconic.restype = ctypes.c_bool
user32.GetWindowTextLengthW.argtypes = [HANDLE]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [HANDLE, ctypes.c_wchar_p, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [HANDLE, ctypes.c_wchar_p, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowLongW.argtypes = [HANDLE, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.AllowSetForegroundWindow.argtypes = [ctypes.c_uint]
user32.UpdateLayeredWindow.argtypes = [
    HANDLE, HANDLE, ctypes.c_void_p, ctypes.c_void_p, HANDLE,
    ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
user32.SetProcessDPIAware.restype = ctypes.c_bool
user32.MessageBoxW.argtypes = [HANDLE, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
user32.MessageBoxW.restype = ctypes.c_int

gdi32.CreateCompatibleDC.argtypes = [HANDLE]
gdi32.CreateCompatibleDC.restype = HANDLE
gdi32.CreateDIBSection.argtypes = [HANDLE, ctypes.c_void_p, ctypes.c_uint,
                                   ctypes.c_void_p, HANDLE, ctypes.c_uint32]
gdi32.CreateDIBSection.restype = HANDLE
gdi32.SelectObject.argtypes = [HANDLE, HANDLE]
gdi32.SelectObject.restype = HANDLE

kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
kernel32.GetModuleHandleW.restype = HANDLE
kernel32.CreateMutexW.argtypes = [HANDLE, ctypes.c_bool, ctypes.c_wchar_p]
kernel32.CreateMutexW.restype = HANDLE
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = ctypes.c_uint32

# --- 其余 Win32 调用也必须声明签名 ----------------------------------------
# ⚠️ 教训：ctypes 默认把 Python int 当 32 位 C int 传参。GDI/USER 句柄一旦
#    大于 2^31 就会抛「OverflowError: int too long to convert」。
#    之前 gdi32.DeleteObject 就踩了这个坑：enter_pure() 重绘时崩在函数内部，
#    导致「收起主界面」那一步永远执行不到 —— 练 Brooks 的主界面一直显示。
#    所以这里统一补齐，不留任何一个裸调用。
gdi32.DeleteObject.argtypes = [HANDLE]
gdi32.DeleteObject.restype = ctypes.c_bool
gdi32.GetDeviceCaps.argtypes = [HANDLE, ctypes.c_int]
gdi32.GetDeviceCaps.restype = ctypes.c_int
user32.IsWindow.argtypes = [HANDLE]
user32.IsWindow.restype = ctypes.c_bool
user32.ShowWindow.restype = ctypes.c_bool
user32.SetWindowPos.restype = ctypes.c_bool
user32.DestroyWindow.restype = ctypes.c_bool
user32.SetCapture.restype = HANDLE
user32.ReleaseCapture.argtypes = []
user32.ReleaseCapture.restype = ctypes.c_bool
user32.SetProcessDPIAware.argtypes = []
user32.SetProcessDPIAware.restype = ctypes.c_bool
user32.GetDpiForSystem.argtypes = []
user32.GetDpiForSystem.restype = ctypes.c_uint
user32.CreatePopupMenu.argtypes = []
user32.CreatePopupMenu.restype = HANDLE
# --- 系统托盘图标（Shell_NotifyIconW）---
shell32.Shell_NotifyIconW.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
shell32.Shell_NotifyIconW.restype = ctypes.c_bool
user32.LoadImageW.argtypes = [HANDLE, ctypes.c_wchar_p, ctypes.c_uint,
                              ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.LoadImageW.restype = HANDLE

kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
kernel32.OpenProcess.restype = HANDLE
kernel32.WaitForSingleObject.argtypes = [HANDLE, ctypes.c_uint32]
kernel32.WaitForSingleObject.restype = ctypes.c_uint32
kernel32.CloseHandle.argtypes = [HANDLE]
kernel32.CloseHandle.restype = ctypes.c_bool
user32.DestroyMenu.restype = ctypes.c_bool
user32.AppendMenuW.restype = ctypes.c_bool
user32.PostMessageW.argtypes = [HANDLE, ctypes.c_uint, WPARAM, LPARAM]
user32.PostMessageW.restype = ctypes.c_bool
# 注册消息：必须声明签名，否则 64 位下返回值会被截断
user32.RegisterWindowMessageW.argtypes = [ctypes.c_wchar_p]
user32.RegisterWindowMessageW.restype = ctypes.c_uint
WM_ALREADY = user32.RegisterWindowMessageW(WM_ALREADY_MSG)
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.TranslateMessage.argtypes = [ctypes.c_void_p]
user32.TranslateMessage.restype = ctypes.c_bool

WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HANDLE, ctypes.c_uint, WPARAM, LPARAM)
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, HANDLE, LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("style", ctypes.c_uint),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", HANDLE),
        ("hIcon", HANDLE),
        ("hCursor", HANDLE),
        ("hbrBackground", HANDLE),
        ("lpszMenuName", ctypes.c_wchar_p),
        ("lpszClassName", ctypes.c_wchar_p),
        ("hIconSm", HANDLE),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", ctypes.c_uint)]


# --- 多显示器（参考图大窗要能搬到任意一块屏）-----------------------------
# ⚠️ 同上：argtypes + restype 都补齐，句柄 > 2^31 才不会被截断
user32.MonitorFromWindow.argtypes = [HANDLE, ctypes.c_uint32]
user32.MonitorFromWindow.restype = HANDLE
user32.MonitorFromRect.argtypes = [ctypes.POINTER(RECT), ctypes.c_uint32]
user32.MonitorFromRect.restype = HANDLE
user32.MonitorFromPoint.argtypes = [POINT, ctypes.c_uint32]
user32.MonitorFromPoint.restype = HANDLE
user32.GetMonitorInfoW.argtypes = [HANDLE, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = ctypes.c_bool
MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, HANDLE, HANDLE,
                                     ctypes.POINTER(RECT), LPARAM)
user32.EnumDisplayMonitors.argtypes = [HANDLE, HANDLE, MONITORENUMPROC, LPARAM]
user32.EnumDisplayMonitors.restype = ctypes.c_bool


# ---------------------------------------------------------------- 资源定位
def res_root():
    """打包后从 _MEIPASS 取资源，开发时用项目根目录。"""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource(*parts):
    return os.path.join(res_root(), *parts)


# ------------------------------------------------- 网页资源落地到固定目录
def web_home():
    """网页资源长期存放目录（打包后临时目录会消失，必须落盘）。"""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, DATA_NAME, "web")


def _fingerprint(root):
    """网页资源的「指纹」：文件数 + 总大小 + **内容 md5**。

    ⚠️ 只比大小是不够的（2026-09-29 实测踩到）：V1.1 → V1.2 这种改动字节数一模一样，
       指纹不变 → exe 不会把新网页同步到固定目录 → 桌面端还读着上一版，
       版本号、文案改了但 exe 里没跟上。加上内容 md5 后，任何一处文字变化都会触发同步。
    """
    n = 0
    size = 0
    h = hashlib.md5()
    for p in (os.path.join(root, "index.html"), os.path.join(root, "assets", "guides.js")):
        if os.path.exists(p):
            with open(p, "rb") as f:
                b = f.read()
            size += len(b)
            h.update(b)
    for dirpath, _, files in os.walk(os.path.join(root, "assets")):
        n += len(files)
        for f in files:
            try:
                with open(os.path.join(dirpath, f), "rb") as f2:
                    size += len(f2.read())
            except OSError:
                pass
    return "%d_%d_%s" % (n, size, h.hexdigest())


def materialize_web():
    """把打包在 exe 里的网页资源同步到固定目录，返回该目录。"""
    src = res_root()
    dst = web_home()
    if not getattr(sys, "frozen", False):
        return src          # 开发模式直接用项目目录
    if dst == src or os.path.abspath(dst) == os.path.abspath(src):
        return src
    try:
        ver_now = _fingerprint(src)
        ver_file = os.path.join(dst, ".ver")
        os.makedirs(dst, exist_ok=True)
        if os.path.exists(ver_file):
            with open(ver_file, "r", encoding="utf-8") as f:
                ver_old = f.read().strip()
        else:
            ver_old = ""
        if ver_old != ver_now:
            import shutil
            shutil.copy2(os.path.join(src, "index.html"), os.path.join(dst, "index.html"))
            assets_dst = os.path.join(dst, "assets")
            if os.path.exists(assets_dst):
                shutil.rmtree(assets_dst)
            shutil.copytree(os.path.join(src, "assets"), assets_dst)
            with open(ver_file, "w", encoding="utf-8") as f:
                f.write(ver_now)
    except Exception:
        import traceback
        log("materialize_web 失败，退回临时目录\n" + traceback.format_exc())
        return src
    return dst


def page_path():
    return os.path.join(materialize_web(), "index.html")


def app_version():
    """版本号**只认 index.html 里的 APP_VER**（网页侧栏与 exe 分享卡片都跟着它走）。

    ⚠️ 别在桌面端另外写死版本号：以前 V1.0.0 写死在这儿，改版本时漏一处，
       打包出来的 exe 就还印着旧版本号（2026-09-29 改成都从网页读）。
    """
    try:
        with open(page_path(), encoding="utf-8") as f:
            m = re.search(r'APP_VER\s*=\s*"([^"]+)"', f.read())
        if m:
            return m.group(1)
    except Exception:
        pass
    return APP_VER_FALLBACK


# ---------------------------------------------------------------- 打开页面
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
]


def utf8_env():
    """给浏览器进程一份环境变量副本（保持 UTF-8 相关设置不变）。"""
    return os.environ.copy()


def page_uri():
    path = page_path()
    p = path.replace("\\", "/")
    if not p.startswith("/"):
        p = "/" + p
    # 关键：路径里的中文必须百分号编码，否则浏览器会丢弃这个地址、只弹一个新标签页
    return "file://" + quote(p, safe="/:")


def browser_profile():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, DATA_NAME, "browser")


def app_window_args(uri):
    """按当前工作区算一个舒服的窗口位置和大小。
    注意：Chrome/Edge 的 --window-size / --window-position 用的是 DIP 逻辑像素，
    在 125% 缩放下会被再乘 1.25，所以这里要先除以缩放比。"""
    area = RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(area), 0)
    scale = dpi_scale() or 1.0
    aw = max(800.0, (area.right - area.left) / scale)
    ah = max(600.0, (area.bottom - area.top) / scale)
    w = int(min(1500, max(1000, aw - 140)))
    h = int(min(940, max(680, ah - 140)))
    x = int(area.left / scale + (aw - w) / 2)
    y = int(area.top / scale + (ah - h) / 2 - 10)
    return [
        "--app=" + uri,
        "--user-data-dir=" + browser_profile(),
        # 打开就是中文：浏览器自己的界面（右键菜单、对话框）也固定简体中文。
        # 只作用于本软件这份独立 profile，不会动你平时用的那个 Chrome。
        "--lang=zh-CN",
        "--accept-lang=zh-CN",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=msEdgeWelcomePage,msImplicitSignin,msEdgeFirstRunExperience",
        # 纯净参考图模式会收起页面窗口：必须关掉后台节流，否则计时/语音会卡住。
        # 最后一味(--disable-intensive-wake-up-throttling)是防「页面隐藏 5 秒后
        # 定时器被激进节流到每分钟一次」的关键开关，缺了它桌宠旁边的倒计时会冻住。
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-intensive-wake-up-throttling",
        "--disable-features=CalculateNativeWinOcclusion",
        "--window-size=%d,%d" % (w, h),
        "--window-position=%d,%d" % (max(0, x), max(0, y)),
    ]


def _class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def find_page_window():
    """查找已经打开的速写页面窗口（浏览器 --app 窗口：标题含应用名、有标题栏、
    且不是桌宠本身）。找到就复用它，避免每次点桌宠都开出新网页。

    ⚠️ 必须先用记住的句柄：主界面被收起（最小化/隐藏）后 IsWindowVisible 会变，
    纯枚举可能找不到，导致「唤不回来」。记住的句柄只要 IsWindow 为真就继续用。"""
    global PAGE_HWND
    if PAGE_HWND and user32.IsWindow(PAGE_HWND):
        return PAGE_HWND
    PAGE_HWND = None
    found = []

    def cb(hwnd, lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            if _class_name(hwnd) == PET_CLASS:
                return True                     # 排除桌宠窗口
            n = user32.GetWindowTextLengthW(hwnd)
            if n <= 0:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if APP_NAME not in buf.value:
                return True
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            if not (style & WS_CAPTION):
                return True                     # 只认有标题栏的浏览器窗口
            found.append(hwnd)
        except Exception:
            pass
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(cb), 0)
    except Exception:
        pass
    if found:
        PAGE_HWND = found[0]
    return found[0] if found else None


def remember_page_window(timeout=25.0):
    """后台记住刚打开的页面窗口句柄。
    Chrome 起来到窗口出现有几百毫秒延迟，直接找会 miss，所以轮询等一等。"""
    def worker():
        end = time.time() + timeout
        while time.time() < end:
            h = find_page_window()
            if h:
                log("记住页面窗口 hwnd=%s" % h)
                return
            time.sleep(0.4)
        log("提示：没能记住页面窗口句柄，收起主界面时会再枚举一次")

    threading.Thread(target=worker, daemon=True).start()


def hide_page_window():
    """收起速写主界面：纯净参考图模式下桌面只留大图 + 小兔，别的 UI 一个不留。

    ⚠️ 用 SW_HIDE **一步隐藏**，不再走最小化：
      · 最小化会有「窗口缩到任务栏」的动画，看着像界面在缩小，不够干净；
      · 而且原来还要轮询等 Chrome 报告「已最小化」（最多 600ms），白白拖慢出图。
    隐藏的窗口靠 PAGE_HWND 记住句柄，唤回时 SW_SHOW 即可（见 find_page_window）。
    Chrome 启动时已关掉后台节流，隐藏不影响页面计时。
    """
    global PAGE_HWND
    hwnd = find_page_window()
    if not hwnd:
        log("hide_page_window：没找到页面窗口，主界面没能收起")
        return False
    PAGE_HWND = hwnd                      # 记牢：隐藏后枚举不到，靠它唤回来
    user32.ShowWindow(hwnd, SW_HIDE)
    log("主界面已隐藏 hwnd=%s" % hwnd)
    return True


def restore_page_window():
    """把收起的主界面唤回来（从最小化或隐藏态都能恢复）。"""
    hwnd = find_page_window()
    if not hwnd:
        log("restore_page_window：没找到页面窗口")
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.ShowWindow(hwnd, SW_SHOW)
    return focus_page_window(hwnd)


def close_page_window(timeout=6.0):
    """关掉速写主界面（浏览器窗口）。
    先礼貌地发 WM_CLOSE；万一赖着不走，也只结束**我们自己拉起的那个**浏览器实例
    （PAGE_PID），绝不动用户自己开的 Chrome。"""
    global PAGE_HWND
    hwnd = find_page_window()
    if not hwnd:
        return True
    user32.ShowWindow(hwnd, SW_SHOW)      # 隐藏/最小化时也要能收到关闭
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    end = time.time() + timeout
    while time.time() < end:
        if not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd):
            break
        time.sleep(0.2)
    if PAGE_PID and user32.IsWindowVisible(hwnd):
        subprocess.run(["taskkill", "/PID", str(PAGE_PID), "/F", "/T"],
                       capture_output=True)
        time.sleep(0.6)
    # 等浏览器进程真正退出：它还活着的话网页文件被占用，缓存删不掉
    if PAGE_PID:
        _wait_pid_exit(PAGE_PID, 6.0)
    gone = (not user32.IsWindow(hwnd)) or (not user32.IsWindowVisible(hwnd))
    if gone:
        PAGE_HWND = None
    return gone


def _wait_pid_exit(pid, timeout=5.0):
    """等某个进程退出（退出桌宠时要等浏览器放手文件，最多等 timeout 秒）。"""
    SYNCHRONIZE = 0x00100000
    WAIT_OBJECT_0 = 0
    try:
        h = kernel32.OpenProcess(SYNCHRONIZE, False, int(pid))
        if not h:
            return True
        try:
            return kernel32.WaitForSingleObject(h, int(timeout * 1000)) == WAIT_OBJECT_0
        finally:
            kernel32.CloseHandle(h)
    except Exception:
        return False


def destroy_pure_window():
    """收掉纯净参考图的独立大窗。"""
    global PURE_WIN
    pw = PURE_WIN
    if pw is None:
        return
    try:
        pw.hide()
    except Exception:
        pass
    try:
        if pw.hwnd:
            user32.DestroyWindow(pw.hwnd)
    except Exception:
        pass
    PURE_WIN = None


# 只删这些「缓存」目录，绝不碰用户的练习记录
# ⚠️ Local Storage / IndexedDB 里存着 sketchUsersV1（账号）、打卡日志、速写值、
#    速写设置等，删了就全没了，所以这里**只能按名单删缓存**。
CHROME_CACHE_DIRS = {"Cache", "Code Cache", "GPUCache", "ShaderCache", "GrShaderCache",
                     "DawnWebGPUCache", "DawnGraphiteCache", "blob_storage",
                     "Session Storage", "Service Worker", "CacheStorage",
                     "VideoDecodeStats", "BrowserMetrics"}
CHROME_KEEP_FILES = {"Preferences", "Secure Preferences", "Bookmarks", "Cookies",
                     "History", "Login Data", "Web Data", "Favicons", "Shortcuts",
                     "Current Session", "Current Tabs", "Last Session", "Last Tabs"}


def _rmtree_retry(path, tries=4, gap=0.8):
    """删目录，删不掉就重试几次（浏览器刚退出时文件可能还被短暂占用）。"""
    for i in range(tries):
        if not os.path.exists(path):
            return True
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass
        if not os.path.exists(path):
            return True
        if i < tries - 1:
            time.sleep(gap)
    return not os.path.exists(path)


def clear_app_cache():
    """清掉本软件产生的缓存：浏览器缓存目录、落地网页资源、临时图。
    用户的练习记录 / 打卡 / 速写值 / 账号一律保留。"""
    removed = []
    prof = browser_profile()
    if os.path.isdir(prof):
        for dirpath, dirnames, _ in os.walk(prof, topdown=True):
            keep = []
            for d in dirnames:
                if d in CHROME_CACHE_DIRS:
                    p = os.path.join(dirpath, d)
                    if _rmtree_retry(p, tries=2, gap=0.4):
                        removed.append(os.path.relpath(p, prof))
                else:
                    keep.append(d)
            dirnames[:] = keep          # 已经删掉的不必再往里走
    web = web_home()
    if _rmtree_retry(web):
        removed.append(web)             # 下次启动会重新落地
    # 参考图 / 一键生成的临时图片：本次生成的逐个删，顺带把以前残留的也扫掉
    n_img = sweep_temp_images()
    if n_img:
        removed.append("临时图片×%d" % n_img)
    # 预解码缓存也一并放掉（纯内存，顺手清）
    global PURE_PRE_IMG
    PURE_PRE_IMG = None
    log("退出清理缓存 %d 项：%s" % (len(removed), "、".join(removed[:8]) or "无"))
    return removed


def quit_app():
    """退出桌宠：关掉本软件打开的所有 UI（页面窗口 + 参考图大窗），清掉缓存，
    最后才收掉桌宠自己。放在后台线程做，避免关窗口那段卡住界面。"""
    def worker():
        try:
            close_page_window()
        except Exception:
            log("退出：关闭页面失败\n" + traceback_str())
        try:
            destroy_pure_window()
        except Exception:
            log("退出：关闭参考图大窗失败\n" + traceback_str())
        try:
            clear_app_cache()
        except Exception:
            log("退出：清理缓存失败\n" + traceback_str())
        try:
            if PET is not None and PET.hwnd:
                user32.PostMessageW(PET.hwnd, WM_CLOSE, 0, 0)   # 让窗口线程自己收尾
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()


def focus_page_window(hwnd):
    """把已打开的页面窗口还原并置前。"""
    try:
        user32.AllowSetForegroundWindow(ASFW_ANY)
    except Exception:
        pass
    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        user32.ShowWindow(hwnd, SW_SHOW)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        log("focus_page_window 失败\n" + traceback_str())
        return False


def open_page():
    """以「应用窗口」模式打开速写页面（无地址栏，像原生程序）。
    用独立浏览器档案，不打扰用户正在用的浏览会话。
    若页面已经打开过，则只把它唤到前台，不再新开窗口。"""
    path = page_path()
    uri = page_uri()
    hwnd = find_page_window()
    if hwnd and focus_page_window(hwnd):
        log("open_page 复用已打开页面 hwnd=%s" % hwnd)
        return
    try:
        os.makedirs(browser_profile(), exist_ok=True)
    except Exception:
        pass
    remember_page_window()      # 后台轮询记住窗口句柄，纯净模式要靠它收起主界面
    global PAGE_PID
    for exe in BROWSERS:
        if exe and os.path.exists(exe):
            try:
                pr = subprocess.Popen([exe] + app_window_args(uri), env=utf8_env(),
                                      close_fds=True)
                PAGE_PID = pr.pid          # 记下来：退出桌宠时只可能结束这一个实例
                log("open_page via %s pid=%s" % (exe, PAGE_PID))
                return
            except Exception:
                log("open_page 失败: %s\n%s" % (exe, traceback_str()))
                continue
    remember_page_window()      # 兜底路径（默认浏览器）同样要记住窗口
    try:
        webbrowser.open(uri)      # 兜底：用系统默认浏览器
        log("open_page fallback webbrowser")
    except Exception:
        try:
            os.startfile(path)
        except Exception:
            log("open_page 彻底失败\n" + traceback_str())


# ---------------------------------------------------- 本地搜索代理（关键词开画）
# 浏览器从 file:// 直接请求 api.huaban.com 会被 CORS 拦截，故由本进程做代理。
# 仅暴露 /huaban_search 与 /ping，并带 CORS 头，JS 用 fetch 即可跨域访问。
SEARCH_PORT = 18765


def _huaban_search(text, limit=40):
    """调用花瓣搜索 API，返回 [{key,thumb,full,title,link}, ...]。"""
    url = ("https://api.huaban.com/search/file?text=" + quote(text) +
           "&sort=all&limit=%d&page=1&position=search_pin" % limit)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    pins = []
    for p in (data.get("pins") or []):
        f = p.get("file") or {}
        key = f.get("key")
        if not key:
            continue
        pins.append({
            "key": key,
            "thumb": "https://hbimg.huabanimg.com/" + key + "_fw658",
            "full": "https://hbimg.huabanimg.com/" + key,
            "title": (p.get("raw_text") or "").strip(),
            "link": "https://huaban.com/pins/" + str(p.get("pin_id") or ""),
        })
    return pins


class _SearchHandler(http.server.BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def _send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        try:
            u = urlparse(self.path)
            if u.path == "/ping":
                self._send_json({"ok": True})
                return
            if u.path == "/huaban_search":
                q = (parse_qs(u.query).get("q") or [""])[0]
                if not q.strip():
                    self._send_json({"ok": False, "error": "empty keyword"}, 400)
                    return
                try:
                    pins = _huaban_search(q)
                except Exception as e:
                    self._send_json({"ok": False, "error": str(e)[:200]}, 502)
                    return
                if not pins:
                    self._send_json({"ok": False, "error": "no results"}, 404)
                else:
                    self._send_json({"ok": True, "pins": pins[:48]})
                return
            if u.path == "/pet_state":
                self._send_json(pet_state_json())
                return
            if u.path == "/pet":
                qs = parse_qs(u.query)
                cmd = (qs.get("cmd") or [""])[0]
                if cmd == "companion_start":
                    try:
                        dur = int((qs.get("dur") or ["1500"])[0])
                    except Exception:
                        dur = 1500
                    set_companion_global(True, dur)
                    self._send_json({"ok": True, "companion": True})
                elif cmd == "companion_stop":
                    set_companion_global(False)
                    self._send_json({"ok": True, "companion": False})
                elif cmd == "say":
                    pet_call("say", (qs.get("text") or [""])[0],
                             _int((qs.get("secs") or ["6"])[0], 6))
                    self._send_json({"ok": True})
                elif cmd == "expr":
                    pet_call("show_expr", (qs.get("kind") or ["happy"])[0], 6)
                    self._send_json({"ok": True})
                elif cmd == "already":
                    # 又双击了一次 exe：让已经在跑的这只小兔跳一下并说句话
                    pet_call("notify_running")
                    self._send_json({"ok": True, "already": True})
                elif cmd == "topmost":
                    on = (qs.get("on") or ["1"])[0] not in ("0", "false", "")
                    pet_call("set_topmost", on)
                    self._send_json({"ok": True, "topmost": bool(on)})
                elif cmd == "pure_start":
                    okk = bool(pet_call("enter_pure"))
                    self._send_json({"ok": okk, "pure": okk})
                elif cmd == "pure_end":
                    pet_call("exit_pure", True)
                    clear_pure_quit()
                    self._send_json({"ok": True, "pure": False})
                elif cmd == "timer":
                    # 纯净模式下把小兔旁边的倒计时小牌刷新（left=-1 表示不显示）
                    # 顺带回一个 quit 信号：网页右键「退出速写」后，靠这条把「结束这一组」送达
                    left = _int((qs.get("left") or ["-1"])[0], -1)
                    label = (qs.get("label") or [""])[0]
                    pet_call("set_timer", left, label)
                    self._send_json({"ok": True, "left": left, "quit": pure_quit_active()})
                elif cmd == "card":
                    path = pet_call("export_card", (qs.get("kind") or ["sticker"])[0])
                    self._send_json({"ok": bool(path), "path": path or ""})
                else:
                    self._send_json({"ok": False, "error": "unknown cmd"}, 400)
                return
            self._send_json({"ok": False, "error": "not found"}, 404)
        except Exception:
            try:
                self._send_json({"ok": False, "error": "server error"}, 500)
            except Exception:
                pass

    def do_POST(self):
        try:
            u = urlparse(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            if u.path == "/pet_preload":
                # 预备参考图：只解码缓存起来，不建窗、不改界面。
                # 网页端在上传/切图时先打这一发，点「开始练习」时桌面端就不用再等解码了。
                try:
                    obj = json.loads(raw.decode("utf-8"))
                except Exception:
                    obj = {}
                self._send_json({"ok": bool(preload_pure(obj.get("d")))})
                return
            if u.path == "/pet_pure":
                # 纯净参考图模式：原子完成「换图 + 进入」，避免分两次请求的竞争
                try:
                    obj = json.loads(raw.decode("utf-8"))
                except Exception:
                    obj = {}
                if obj.get("on", True):
                    if obj.get("d"):
                        preload_pure(obj.get("d"))      # 顺手解码缓存（只是解码，线程安全）
                        set_image_global(obj.get("d"))
                    clear_pure_quit()        # 新的一组：清掉上一次的退出信号
                    okk = bool(pet_call("enter_pure"))
                    self._send_json({"ok": okk, "pure": okk})
                else:
                    pet_call("exit_pure", True)
                    self._send_json({"ok": True, "pure": False})
                return
            if u.path == "/pet_card":
                try:
                    obj = json.loads(raw.decode("utf-8"))
                except Exception:
                    obj = {}
                kind = obj.get("kind") or "sticker"
                if kind == "on":
                    tmp = materialize_image(obj.get("d")) if obj.get("d") else None
                    path = pet_call("make_card", "on", tmp) if tmp else None
                else:
                    path = pet_call("make_card", kind)
                if path:
                    try:
                        os.startfile(path)
                    except Exception:
                        pass
                self._send_json({"ok": bool(path), "path": path or ""})
                return
            self._send_json({"ok": False, "error": "not found"}, 404)
        except Exception:
            try:
                self._send_json({"ok": False, "error": "server error"}, 500)
            except Exception:
                pass

    def log_message(self, *a):
        pass  # 静默，避免刷日志


def start_search_server():
    """启动本地搜索代理（daemon 线程）。成功返回端口，失败返回 None。"""
    try:
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", SEARCH_PORT), _SearchHandler)
    except OSError as e:
        log("search server 启动失败（端口 %d 被占用）：%s" % (SEARCH_PORT, e))
        return None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log("search server 已启动：127.0.0.1:%d" % SEARCH_PORT)
    return SEARCH_PORT


# -------------------------------------------- 陪画模式（桌宠陪伴用户作画）
# 桌宠进入一段专注：focus → tired → doze → done。中途会累、会打瞌睡。
# 头顶气泡分两种「不同设计」：文字气泡（圆角矩形 + 尾巴 + 白底紫边）与
# 表情气泡（圆形贴纸 + 虚线边 + 画脸），二者绝不混用。
# 慵懒困困音色在陪画模式里成为真正功能：相位切换时由网页用该音色播报。
COMP_TEXT = {
    "focus": ["陪你一起画~", "我们一起加油！", "专注中，笔尖动起来~", "今天也要进步一点点"],
    "tired": ["唔…有点累了", "手腕歇一下下", "画得手酸酸", "偷偷打了个哈欠"],
    "doze":  ["困了…zzz", "陪你画得想睡觉", "眼皮好重呀", "眯一会儿…"],
    "done":  ["画完啦，辛苦啦~"],
}
COMP_EXPR = {
    "focus": ["happy", "focused"],
    "tired": ["tired"],
    "doze":  ["sleep"],
    "done":  ["happy"],
}


def pet_state_json():
    p = PET
    pw = PURE_WIN
    pure = bool(pw is not None and pw.visible and pw.pure)
    zoom = round(pw.zoom, 2) if pure else 1.0
    if p is None or not p.hwnd:
        return {"ok": True, "companion": False, "on": False, "phase": "idle",
                "elapsed": 0, "dur": 0, "pure": False, "zoom": 1.0, "timer": -1}
    el = (time.time() - p.comp_start) if p.companion_on else 0
    # ⚠️ on 与 companion 不是一回事：
    #   on        = 桌宠本体是否在线（网页的待机提醒靠它判断「小兔开着吗」）
    #   companion = 是否正在陪画（练习中）
    # 以前把 on 写成 companion，导致桌宠正常运行但没练习时 on 恒为 false，
    # 网页端「今天还没打卡就提醒」的判断永远进不去（真实 HTTP 链路才测得出来）。
    return {"ok": True, "companion": bool(p.companion_on), "on": bool(p.hwnd),
            "phase": p.comp_phase, "elapsed": int(el), "dur": int(p.comp_dur),
            "pure": pure, "zoom": zoom, "timer": int(p.timer_left)}


def set_companion_global(on, dur=None):
    pet_call("set_companion", on, dur)


# --- 系统托盘图标 ---
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
TRAY_ID = 1
NIN_SELECT = 0x0400          # 托盘图标被选中（左键单击/回车）
WM_CONTEXTMENU = 0x007B


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("hWnd", HANDLE),
        ("uID", ctypes.c_uint32),
        ("uFlags", ctypes.c_uint32),
        ("uCallbackMessage", ctypes.c_uint32),
        ("hIcon", HANDLE),
        ("szTip", ctypes.c_wchar * 128),
        ("dwState", ctypes.c_uint32),
        ("dwStateMask", ctypes.c_uint32),
        ("szInfo", ctypes.c_wchar * 256),
        ("uTimeoutOrVersion", ctypes.c_uint32),
        ("szInfoTitle", ctypes.c_wchar * 64),
        ("dwInfoFlags", ctypes.c_uint32),
        ("guidItem", ctypes.c_ubyte * 16),
        ("hBalloonIcon", HANDLE),
    ]


WM_PET_CALL = 0x8000 + 81    # WM_APP+81：让别的线程把任务切到窗口线程执行
WM_TRAY = 0x8000 + 82        # WM_APP+82：托盘图标的回调消息
PET_THREAD_ID = 0            # 桌宠窗口所在线程（UI 线程）
_PET_TASKS = queue.Queue()   # (method, args, event, box)


def drain_pet_tasks():
    """在 UI 线程里执行排队的任务。"""
    while True:
        try:
            method, args, ev, box = _PET_TASKS.get_nowait()
        except Exception:
            return
        try:
            box["v"] = _pet_call_ui(method, *args)
        except Exception:
            box["v"] = None
        finally:
            ev.set()


def _pet_call_ui(method, *args):
    p = PET
    if p is None:
        return None
    fn = getattr(p, method, None)
    if fn is None:
        return None
    try:
        return fn(*args)
    except Exception:
        log("pet_call %s 失败\n%s" % (method, traceback_str()))
        return None


def pet_call(method, *args):
    """在桌宠窗口线程里调用方法。

    ⚠️ 必须切线程，不能直接在 HTTP 线程上跑：本地服务是 ThreadingHTTPServer，
    每个请求一个线程，请求结束线程就退出，而**线程一退它创建的窗口会被销毁**。
    之前 enter_pure 在请求线程里建参考图大窗 → 窗口刚出来就被销毁，桌面只剩
    小兔、看不到参考图。现在统一投递给窗口线程排队执行。
    """
    p = PET
    if p is None or not p.hwnd:
        return None
    if PET_THREAD_ID and PET_THREAD_ID == kernel32.GetCurrentThreadId():
        return _pet_call_ui(method, *args)      # 已经在 UI 线程，直接执行（避免自锁）
    ev = threading.Event()
    box = {}
    try:
        _PET_TASKS.put((method, args, ev, box))
    except Exception:
        return None
    if not user32.PostMessageW(p.hwnd, WM_PET_CALL, 0, 0):
        return None
    return box.get("v") if ev.wait(timeout=20.0) else None


# 纯净模式「退出速写」：右键菜单触发，把「结束这一组 + 回到主界面」一次做完。
# 桌面端负责关掉参考图大窗并唤回主界面；「结束这一组」由网页完成 —— 网页每秒都在推
# 倒计时，桌面端在响应里带上 quit=True，网页收到就执行 finish()（等同于点「结束」）。
PURE_QUIT_TS = 0
PURE_QUIT_TTL = 120          # 兜底：网页长时间没回应就作废，避免下次误触发


def pure_quit_active():
    return PURE_QUIT_TS > 0 and (time.time() - PURE_QUIT_TS) < PURE_QUIT_TTL


def clear_pure_quit():
    global PURE_QUIT_TS
    PURE_QUIT_TS = 0


def request_pure_quit():
    """退出速写：关掉参考图大窗 + 唤回主界面，并通知网页结束这一组。"""
    global PURE_QUIT_TS
    PURE_QUIT_TS = time.time()
    try:
        if PET is not None:
            PET.exit_pure(True)      # 先把主界面唤回来（页面恢复后计时才不会被节流）
    except Exception:
        log("request_pure_quit 失败\n" + traceback_str())
    log("退出速写：大图已关、主界面已唤回，等待网页结束这一组")


def set_image_global(data_uri):
    """让桌宠显示一张图（data:uri 或 http 地址）；None = 恢复小兔本体。"""
    return pet_call("set_display_image", data_uri)


# 预解码好的参考图（PIL RGBA）。网页端在上传/切图时就用 /pet_preload 把图送过来，
# 这样点「开始练习」时桌面端不用再解码，大图能立刻弹出来（省掉一整段等待）。
PURE_PRE_IMG = None


def decode_image_from_uri(data_uri):
    """data:uri / http 地址 → PIL RGBA。纯解码，不碰任何窗口（可以在 HTTP 线程里跑）。"""
    import base64
    import io
    from PIL import Image
    if data_uri.startswith("data:"):
        raw = base64.b64decode(data_uri.split(",", 1)[1])
    else:
        raw = urllib.request.urlopen(data_uri, timeout=10).read()
    return Image.open(io.BytesIO(raw)).convert("RGBA")


def preload_pure(data_uri):
    """后台把参考图解码好缓存起来：不建窗、不改界面，只做准备。

    ⚠️ 只做解码，不碰窗口，所以可以直接在 HTTP 线程里执行（建窗/动窗仍然必须 pet_call）。
    """
    global PURE_PRE_IMG
    if not data_uri:
        return False
    try:
        PURE_PRE_IMG = decode_image_from_uri(data_uri)
        return True
    except Exception:
        log("preload_pure 失败\n" + traceback_str())
        return False


# 本进程落地过的临时图片：退出时逐个删掉，不留残图（glob 是兜底，这份是精确名单）
TMP_FILES = set()


def materialize_image(data_uri):
    """把 data:uri 或 http 地址落地成临时 PNG，返回路径（失败返回 None）。"""
    import base64
    import io
    import tempfile
    from PIL import Image
    try:
        if data_uri.startswith("data:"):
            raw = base64.b64decode(data_uri.split(",", 1)[1])
        else:
            raw = urllib.request.urlopen(data_uri, timeout=10).read()
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        fd, p = tempfile.mkstemp(suffix=".png", prefix="dq_pet_")
        os.close(fd)
        img.save(p)
        TMP_FILES.add(p)
        return p
    except Exception:
        log("materialize_image 失败\n" + traceback_str())
        return None


def sweep_temp_images():
    """删掉本软件的临时图片：本次生成的（精确名单）+ 上次异常退出留下的（glob 兜底）。"""
    n = 0
    for p in list(TMP_FILES):
        try:
            os.remove(p)
            n += 1
        except Exception:
            pass
        TMP_FILES.discard(p)
    try:
        for f in glob.glob(os.path.join(tempfile.gettempdir(), "dq_pet_*.png")):
            try:
                os.remove(f)
                n += 1
            except Exception:
                pass
    except Exception:
        pass
    return n


def _int(v, d):
    try:
        return int(v)
    except Exception:
        return d


def traceback_str():
    import traceback
    return traceback.format_exc()


# ---------------------------------------------------------------- 桌宠窗口
def dpi_scale():
    """当前系统 DPI 缩放（1.0 = 96dpi）。"""
    try:
        user32.GetDpiForSystem.restype = ctypes.c_uint
        d = user32.GetDpiForSystem()
        if d:
            return d / 96.0
    except Exception:
        pass
    try:
        hdc = user32.GetDC(None)
        d = gdi32.GetDeviceCaps(hdc, 88)   # LOGPIXELSX
        user32.ReleaseDC(None, hdc)
        if d:
            return d / 96.0
    except Exception:
        pass
    return 1.0


class PetWindow:
    SIZES = [("小", 130), ("中", 178), ("大", 240)]

    def __init__(self, kind="pet"):
        self.kind = kind               # "pet" 桌宠本体 / "pure" 纯净参考图大窗
        self.cls_name = PET_CLASS + ("Pure" if kind == "pure" else "")
        self.hwnd = None
        self.visible = False
        self._tray = None              # 系统托盘图标数据（退出时要 NIM_DELETE 收掉）
        self.size_idx = 1          # 默认「中」
        self.topmost = True
        self.anim = True
        self.phase = 0.0
        self.amp = 3.0
        # 「又点了一次 exe」时跳一下：hop_until 之前按半周期正弦抬起再落回
        self.hop_t0 = 0.0
        self.hop_until = 0.0
        self.hop_dur = 0.9
        self.hop_amp = 0.0
        self.timer_id = 1
        self.dragging = False
        self.drag_start = (0, 0)
        self.drag_win = (0, 0)
        self.drag_moved = 0
        self.base_y = 0
        self.x = 0
        self.y = 0
        # 主人拖过之后记住的位置：左边 x + 底边 y（None = 还没拖过，用默认角）
        # ⚠️ 记「底边」不记「顶边」：头顶那条带子（气泡 / 计时圆盘）会变高，
        #    底边不动 → 带子往上长，小兔的脚不会跟着挪。
        self.anchor = None
        self.hbmp = None
        self.hdc_mem = None
        self.scale = dpi_scale()
        self._wndproc = WNDPROC(self._on_message)
        self._cls = None
        self._pil = None
        self._pet_h = None
        self._w = 10
        self._h = 10
        # 气泡 / 陪画模式状态
        self.companion_on = False      # 陪画模式开关
        self.comp_start = 0
        self.comp_dur = 1500
        self.comp_phase = "idle"
        self.band = 0                  # 头顶气泡带高度（0 = 不显示）
        self.bubble_kind = None        # None | "text" | "expr"
        self.bubble_text = ""
        self.bubble_expr = "happy"
        self.bubble_next = 0           # 陪画时下一次轮换气泡的时间
        self.bubble_until = 0          # 临时气泡自动消失时间（0 = 不自动消失）
        self._display_src = None       # 当前显示的参考图（None = 小兔本体）
        # 倒计时（纯净模式下显示在小兔旁边）
        self.timer_left = -1           # 秒数，-1 = 不显示
        self.timer_label = ""
        # 纯净参考图模式：只留置顶大图，主界面最小化（滚轮缩放 / 右键另存）
        self.pure = False              # 是否处于纯净参考图模式
        self._last_pure_src = None     # 最近一次进参考图模式用的那张图（右键「返回当前参考图模式」要用）
        self.zoom = 1.0                # 缩放倍率 0.5 ~ 2.0
        self._pure_img = None          # 原图（RGBA，全分辨率，供缩放重采样）
        self._pure_base = None         # 基准显示尺寸 (w, h)，zoom=1.0 时的大小
        self.flip_h = False            # 左右镜像显示参考图（只有右键菜单能切）
        self._pure_img_flip = None     # 镜像后的缓存（省得每次缩放都重转一遍）
        self._font = self._load_font()

    # -- 载入透明 PNG（按高度缓存，免重复读盘）-----------------------
    def _load_font(self):
        from PIL import ImageFont
        size = int(round(30 * self.scale))
        for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyh.ttf",
                     "C:/Windows/Fonts/simhei.ttf"):
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        return None

    def _ensure_pet(self, height):
        """按给定高度载入/缓存桌宠 PNG，返回 (w, h)。"""
        from PIL import Image, ImageChops
        if self._pil is not None and self._pet_h == height:
            return self._pil.size
        src = resource("assets", "pet", "xiaotu-pet.png")
        if not os.path.exists(src):
            src = resource("assets", "dq-chibi.png")
        img = Image.open(src).convert("RGBA")
        w, h = img.size
        scale = height / float(h)
        img = img.resize((max(1, int(round(w * scale))), height), Image.LANCZOS)
        self._pil = img
        self._pet_h = height
        return img.size

    def _make_dib(self, img):
        """把 RGBA 图写入分层窗口用的 32 位 DIB（预乘 alpha）。"""
        from PIL import Image, ImageChops
        w, h = img.size
        r, g, b, a = img.split()
        prem = ImageChops.multiply(Image.merge("RGB", (r, g, b)),
                                    Image.merge("RGB", (a, a, a)))
        pr, pg, pb = prem.split()
        out = Image.merge("RGBA", (pr, pg, pb, a))
        raw = out.tobytes("raw", "BGRA")
        hdc_screen = user32.GetDC(None)
        if self.hdc_mem is None:
            self.hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h                      # 负数 = 自上而下
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0                  # BI_RGB
        bits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(hdc_screen, ctypes.byref(bmi), 0,
                                      ctypes.byref(bits), None, 0)
        ctypes.memmove(bits, raw, len(raw))
        if self.hbmp:
            gdi32.DeleteObject(self.hbmp)
        self.hbmp = hbmp
        gdi32.SelectObject(self.hdc_mem, self.hbmp)
        user32.ReleaseDC(None, hdc_screen)
        self._w, self._h = w, h

    def _blit(self):
        hdc_screen = user32.GetDC(None)
        pt_dst = POINT(self.x, self.y)
        pt_src = POINT(0, 0)
        size = wt.SIZE(self._w, self._h)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(self.hwnd, hdc_screen, ctypes.byref(pt_dst),
                                   ctypes.byref(size), self.hdc_mem,
                                   ctypes.byref(pt_src), 0, ctypes.byref(blend),
                                   ULW_ALPHA)
        user32.ReleaseDC(None, hdc_screen)

    def repaint(self):
        """重绘窗口：桌宠 + 头顶那一块（计时圆盘 / 陪画气泡，二选一）。"""
        from PIL import Image
        if self._pil is None:
            self._ensure_pet(self._pet_h or int(round(178 * self.scale)))
        pet = self._pil
        w, h = pet.size
        band = self.band
        canvas = Image.new("RGBA", (w, h + band), (0, 0, 0, 0))
        canvas.paste(pet, (0, band))
        # 头顶只有一块地方：练习中（有倒计时）就当计时圆盘，其余时间留给陪画气泡。
        if self.timer_left >= 0 and self.kind == "pet":
            canvas = self._draw_timer_dial(canvas, band)
        elif self.bubble_kind:
            if self.bubble_kind == "text":
                canvas = self._draw_text_bubble(canvas, band, self.bubble_text or "")
            else:
                canvas = self._draw_expr_bubble(canvas, band, self.bubble_expr or "happy")
        self._make_dib(canvas)
        self._blit()

    # -- 窗口位置（含气泡带时把桌宠贴到工作区底部，气泡在头顶上方）----
    def _update_window_rect(self):
        """重排小兔窗口：**主人拖过就留在主人放的位置**，没拖过才回默认角。

        ⚠️ 2026-09-29 修：以前这里每次都硬算「工作区右下角」，于是小兔一说话、
        一开倒计时、一进/出参考图模式就被拽回那个角 —— 拖到哪儿都白拖。
        现在拖过之后按 anchor=(左边, 底边) 还原：带子变高只是往上长，小兔的脚不动；
        位置还会夹进当前工作区，改分辨率 / 拔掉副屏也不会把它丢到屏幕外。
        """
        if not self.hwnd:
            return
        h = (self._pil.size[1] if self._pil
             else int(round(178 * self.scale)))
        w = (self._pil.size[0] if self._pil
             else int(round(178 * self.scale)))
        band = self.band
        wa = self._work_area()
        margin = int(round(24 * self.scale))
        total_h = h + band
        total_w = w                       # 倒计时改到头顶圆盘里，窗口不再向左加宽
        if self.anchor:
            ax, abottom = self.anchor
            self.x = _clamp_v(ax, wa.left + margin, wa.right - total_w - margin)
            self.y = _clamp_v(abottom, wa.top + margin + total_h,
                              wa.bottom - margin) - total_h
        else:
            self.x = wa.right - total_w - margin
            self.y = wa.bottom - total_h - margin
        self.base_y = self.y
        user32.SetWindowPos(self.hwnd, None, self.x, self.y, 0, 0,
                            SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)

    # -- 陪画模式：开/关 -------------------------------------------------
    def _ensure_band(self):
        if self.band <= 0:
            pet_h = (self._pil.size[1] if self._pil
                     else int(round(178 * self.scale)))
            self.band = int(round(0.58 * pet_h))   # 头顶气泡带高度

    def _kick_timer(self):
        if self.hwnd:
            user32.SetTimer(self.hwnd, self.timer_id, 40, None)

    def set_companion(self, on, dur=None):
        if on:
            self.companion_on = True
            self.comp_start = time.time()
            self.comp_dur = int(dur) if dur and dur > 0 else 1500
            self.comp_phase = "focus"
            self._ensure_band()
            self.bubble_kind = "text"
            self.bubble_text = random.choice(COMP_TEXT["focus"])
            self.bubble_expr = "happy"
            self.bubble_until = 0
            self.bubble_next = time.time() + 5
            self._update_window_rect()
            self._kick_timer()
            self.repaint()
        else:
            self.companion_on = False
            self.comp_phase = "idle"
            self._clear_bubble()

    # -- 临时气泡（点评 / 「看看这个」等，不进入陪画状态）----------------
    def say(self, text, secs=6):
        self._set_bubble("text", text, secs)

    def show_expr(self, kind, secs=6):
        self._set_bubble("expr", kind, secs)

    # -- 又双击了一次 exe：跳一下 + 说「小兔已经在运行了哦」----------------
    def notify_running(self):
        """第二个 exe 实例发现小兔已经在跑，就走到这里给个反应。

        ⚠️ 这个方法只在窗口线程里被调用（HTTP 走 pet_call，广播消息由消息循环直接派发），
        所以可以直接动窗口，不用再排队。
        """
        if not self.visible:
            self.show_pet()                      # 之前被「关闭桌宠」收起来的话，先放回来
        self.hop_t0 = time.time()
        self.hop_until = self.hop_t0 + self.hop_dur
        self.hop_amp = 26.0 * self.scale         # 明显的「跳一下」，比呼吸幅度大得多
        self._set_bubble("text", ALREADY_TEXT, 6)
        log("小兔已在运行，跳一下并提示：%s" % ALREADY_TEXT)

    def _set_bubble(self, kind, payload, secs):
        self._ensure_band()
        self.bubble_kind = kind
        if kind == "text":
            self.bubble_text = payload or ""
        else:
            self.bubble_expr = payload or "happy"
        self.bubble_until = time.time() + max(1, int(secs))
        self.bubble_next = 0
        self._update_window_rect()
        self._kick_timer()
        self.repaint()

    def _clear_bubble(self):
        self.bubble_kind = None
        self.bubble_until = 0
        self.band = 0
        self._update_window_rect()
        self.repaint()

    # -- 一键生成：表情包 / 社媒卡片 / 贴在作品上 -----------------------
    def _font_at(self, px):
        from PIL import ImageFont
        for path in ("C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc",
                     "C:/Windows/Fonts/simhei.ttf"):
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, px)
                except Exception:
                    continue
        return self._font

    def _card_dir(self):
        base = web_home() if getattr(sys, "frozen", False) else res_root()
        d = os.path.join(base, "cards")
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        return d

    def make_card(self, kind="sticker", src=None):
        """生成图片并返回路径：sticker=表情包 / social=社媒卡片 / on=贴在作品上。"""
        from PIL import Image, ImageDraw
        if self._pil is None:
            self._ensure_pet(int(round(178 * self.scale)))
        pet = self._pil
        cap = random.choice(COMP_TEXT["doze"] + COMP_TEXT["tired"] + COMP_TEXT["focus"])
        out_dir = self._card_dir()
        if kind == "social":
            W, H = 1080, 1350
            card = Image.new("RGB", (W, H), (239, 232, 249))
            d = ImageDraw.Draw(card)
            for y in range(H):                      # 竖向淡紫渐变
                t = y / float(H)
                d.line([(0, y), (W, y)],
                       fill=(int(239 - 16 * t), int(232 - 14 * t), int(249 - 12 * t)))
            d.text((W // 2, 90), "DQ小兔速写计时姬", font=self._font_at(58),
                   fill=(127, 95, 192), anchor="mm")
            d.text((W // 2, 160), "每一次落笔，都算数", font=self._font_at(30),
                   fill=(140, 130, 163), anchor="mm")
            ph = 760
            pw = int(pet.size[0] * ph / pet.size[1])
            p = pet.resize((pw, ph), Image.LANCZOS)
            card.paste(p, ((W - pw) // 2, 250), p)
            d.text((W // 2, 1130), cap, font=self._font_at(40), fill=(59, 51, 80), anchor="mm")
            d.text((W // 2, 1225), "%s · 一起练速写吧" % app_version(),
                   font=self._font_at(26), fill=(140, 130, 163), anchor="mm")
            path = os.path.join(out_dir, "social_card.png")
            card.save(path)
            return path
        if kind == "on" and src:
            try:
                base = Image.open(src).convert("RGBA")
            except Exception:
                log("贴纸合成失败\n" + traceback_str())
                return None
            bw, bh = base.size
            ph = int(bh * 0.42)
            pw = int(pet.size[0] * ph / pet.size[1])
            p2 = pet.resize((pw, ph), Image.LANCZOS)
            out = base.copy()
            out.alpha_composite(p2, (bw - pw - int(bw * 0.04), bh - ph - int(bh * 0.02)))
            path = os.path.join(out_dir, "pet_on_result.png")
            out.convert("RGB").save(path)
            return path
        # 表情包：透明底 + 顶部圆角文字气泡（沿用文字气泡的设计；气泡宽度按文字自适应）
        pad = 40
        font = self._font_at(40)
        tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        max_text_w = 560
        lines, cur = [], ""
        for ch in cap:
            if tmp.textlength(cur + ch, font=font) > max_text_w and cur:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        line_h = 56
        tw = max((tmp.textlength(l, font=font) for l in lines), default=0)
        bubble_w = int(tw) + 64
        bubble_h = line_h * len(lines) + 36
        W = max(pet.size[0], bubble_w) + pad * 2
        H = pet.size[1] + pad * 2 + bubble_h + 24
        card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        card.alpha_composite(pet, ((W - pet.size[0]) // 2, bubble_h + 24))
        d = ImageDraw.Draw(card)
        bx = (W - bubble_w) // 2
        d.rounded_rectangle([bx, 0, bx + bubble_w, bubble_h], radius=28,
                            fill=(255, 255, 255, 255), outline=(127, 95, 192, 255), width=6)
        ty = 18
        for l in lines:
            d.text((W // 2, ty + line_h // 2), l, font=font, fill=(59, 51, 80), anchor="mm")
            ty += line_h
        path = os.path.join(out_dir, "sticker.png")
        card.save(path)
        return path

    def export_card(self, kind="sticker", src=None):
        path = self.make_card(kind, src)
        if path:
            try:
                os.startfile(path)
            except Exception:
                pass
        return path

    # -- 让桌宠显示一张图（开始速写时变成参考图的样子）------------------
    def set_display_image(self, data_uri):
        import base64
        import io
        from PIL import Image
        try:
            if not data_uri:
                self._display_src = None
                self._pil = None
                self._pet_h = None
                self._ensure_pet(int(round(self.SIZES[self.size_idx][1] * self.scale)))
            else:
                if data_uri.startswith("data:"):
                    b64 = data_uri.split(",", 1)[1]
                    raw = base64.b64decode(b64)
                else:
                    raw = urllib.request.urlopen(data_uri, timeout=6).read()
                img = Image.open(io.BytesIO(raw)).convert("RGBA")
                h = int(round(self.SIZES[self.size_idx][1] * self.scale))
                w = int(round(img.size[0] * h / float(img.size[1] or 1)))
                self._pil = img.resize((max(1, w), h), Image.LANCZOS)
                self._pet_h = h
                self._display_src = data_uri
            self._update_window_rect()
            self.repaint()
            return True
        except Exception:
            log("set_display_image 失败\n" + traceback_str())
            return False

    # -- 纯净参考图模式：只留一张置顶大图，其他 UI 框（页面窗口）最小化 ----
    PURE_ZOOM_MIN = 0.5                  # 最小缩小到 50%
    PURE_ZOOM_MAX = 2.0                  # 最大放大到 200%（再大就顶出屏幕了）
    PURE_ZOOM_STEP = 0.15                # 每格 15%：0.5 → 2.0 正好 10 格

    def _decode_display_image(self):
        """把 self._display_src 解码成全分辨率 RGBA 图（另存/缩放都用原图）。"""
        import base64
        import io
        from PIL import Image
        src = self._display_src
        if not src:
            return None
        if src.startswith("data:"):
            raw = base64.b64decode(src.split(",", 1)[1])
        else:
            raw = urllib.request.urlopen(src, timeout=6).read()   # 别久占 UI 线程
        return Image.open(io.BytesIO(raw)).convert("RGBA")

    # -- 纯净参考图模式：参考图独立大窗（置顶）+ 小兔留在右下角显示倒计时
    #    enter_pure 由主桌宠调用：把图交给独立大窗，自己恢复成本体
    def enter_pure(self):
        """进入纯净参考图模式：大图置顶 + 小兔回到本体 + 主界面收起。

        ⚠️ 这里每一步都单独容错。之前整段 try 包在一起，中间任何一个
        OverflowError 都会让「收起主界面」执行不到 —— 桌面还是一片 UI。

        顺序（2026-09-29 调整）：**先一步隐藏主界面，再建大图**。
        以前是先建大图再最小化收 UI，中间还夹着最小化的动画和等待，
        看起来就是「界面慢慢缩小」；现在点下去界面瞬间就没了。
        万一大图没起来，再把主界面还回去（回滚），不会把用户晾在空白桌面。
        """
        if self._display_src:
            self._last_pure_src = self._display_src   # 记住这张图：右键「返回当前参考图模式」要能回到它
        try:
            hide_page_window()               # ① 主界面立刻消失（SW_HIDE，无动画）
        except Exception:
            log("enter_pure：收起主界面失败\n" + traceback_str())
        pw = None
        try:
            pw = ensure_pure_window()
            if not pw.show_image(self._display_src):
                log("enter_pure：参考图加载失败")
                restore_page_window()        # 回滚：图没起来就把界面还给人家
                return False
        except Exception:
            log("enter_pure：大图窗口构建失败\n" + traceback_str())
            restore_page_window()
            return False
        try:
            self.set_display_image(None)     # 小兔本体留在右下角（牌子显示倒计时）
        except Exception:
            log("enter_pure：小兔恢复本体失败\n" + traceback_str())
        self.pure = True
        try:
            self.set_topmost(True)
        except Exception:
            log("enter_pure：置顶失败\n" + traceback_str())
        self.timer_left = -1
        self.timer_label = ""
        try:
            self._update_window_rect()
            self.repaint()
        except Exception:
            log("enter_pure：重排/重绘失败\n" + traceback_str())
        log("enter_pure 完成 base=%s" % (pw._pure_base,))
        return True

    def has_pure_src(self):
        """现在有没有「能回到参考图模式」的那张图（决定右键菜单要不要显示那一项）。"""
        if self._last_pure_src:
            return True
        pw = PURE_WIN
        return bool(pw is not None and getattr(pw, "_display_src", None))

    def back_to_pure(self):
        """右键「返回当前参考图模式」：把刚才那张参考图的大窗再唤回来。

        网页模式下（主界面开着）想回到只剩一张图的纯净画面时用它。
        ⚠️ 只负责「回到画面」，不会重开计时、不会跳到下一张——当前这一组照常继续。
        """
        if self.pure:
            return True                       # 已经在参考图模式里了
        src = self._last_pure_src
        if not src:
            pw = PURE_WIN
            src = getattr(pw, "_display_src", None) if pw is not None else None
        if not src:
            self.say("还没有参考图，先在页面上传一张吧", 6)
            log("返回参考图模式：手上没有可参考的图")
            return False
        self._display_src = src
        ok = self.enter_pure()
        if ok:
            log("已返回当前参考图模式")
        else:
            self.say("没能把参考图唤回来，看看页面还在不在", 6)
        return ok

    def _monitor_work_area(self, rect=None):
        """取「窗口（或给定矩形）所在那块显示器」的工作区。

        多屏时不能一律用主屏工作区 —— 否则把大图拖到副屏后再缩放，
        会被一把拽回主屏。找不到就回退到主屏工作区。
        """
        try:
            hmon = 0
            if rect is not None:
                hmon = user32.MonitorFromRect(ctypes.byref(rect),
                                              MONITOR_DEFAULTTONEAREST)
            elif self.hwnd:
                hmon = user32.MonitorFromWindow(self.hwnd, MONITOR_DEFAULTTONEAREST)
            if hmon:
                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)
                if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                    return RECT(mi.rcWork.left, mi.rcWork.top,
                                mi.rcWork.right, mi.rcWork.bottom)
        except Exception:
            log("取所在显示器失败\n" + traceback_str())
        return self._work_area()

    def _pointer_work_area(self):
        """鼠标所在那块屏的工作区（第一次弹大图就开在你正在用的那块屏）。"""
        try:
            pt = POINT()
            if user32.GetCursorPos(ctypes.byref(pt)):
                return self._monitor_work_area(RECT(pt.x, pt.y, pt.x + 1, pt.y + 1))
        except Exception:
            log("取鼠标所在显示器失败\n" + traceback_str())
        return self._work_area()

    def _fit_pure_size(self, w, h, wa, margin):
        """等比夹进工作区：放大到最大也不顶出上下左右，且不会拉变形。

        之前宽高各自 min() 截断，一旦某一维先到边就会把图拉扁，这里改成
        按同一个比例缩，保证原图比例。
        """
        max_w = wa.right - wa.left - margin * 2
        max_h = wa.bottom - wa.top - margin * 2
        r = 1.0
        if max_w > 0 and w > max_w:
            r = min(r, max_w / float(w))
        if max_h > 0 and h > max_h:
            r = min(r, max_h / float(h))
        if r < 1.0:
            w = max(1, int(round(w * r)))
            h = max(1, int(round(h * r)))
        return w, h

    def _clamp_into_area(self, cx, cy, wa, margin):
        """按中心点 (cx,cy) 定位，并把窗口夹进工作区四条边（比工作区大就居中）。"""
        if self._w >= (wa.right - wa.left - margin * 2):
            x = (wa.left + wa.right - self._w) // 2
        else:
            x = max(wa.left + margin,
                    min(cx - self._w // 2, wa.right - margin - self._w))
        if self._h >= (wa.bottom - wa.top - margin * 2):
            y = (wa.top + wa.bottom - self._h) // 2
        else:
            y = max(wa.top + margin,
                    min(cy - self._h // 2, wa.bottom - margin - self._h))
        return x, y

    def _apply_pure_zoom(self, keep_center="cur", anchor=None, pos=None):
        """按 self.zoom 重采样大图；keep_center='cur' 时保持窗口中心不动。

        anchor=(mx,my) 时改成**以鼠标为中心**缩放：鼠标指着图上的哪一点，
        缩放后那一点还在鼠标底下（2026-09-29 改，以前一律按窗口中心，放大后就飘了）。

        pos=(x,y)：换图时用，把窗口左上角放到这个位置（跳过 / 自动轮播都走它，
        免得每次换图都按屏幕中心重排、把主人拖好的位置弄丢）。仍然会夹进
        所在的那一块工作区，换张长图也不会跑出屏幕。

        ⚠️ 宽高始终按同一个倍率走（`_fit_pure_size` 等比夹取），顶到屏幕/工作区
           边缘时只会停下不再变大，**绝不会把图横向拉宽、拉变形**。
        多屏：一律按「窗口当前所在那块屏」夹取，不会把图拽回主屏。
        """
        from PIL import Image
        bw, bh = self._pure_base
        # 换图：回到上次那个位置所在的那块屏；首次弹图：开在鼠标所在那块屏；
        # 之后缩放：始终留在窗口当前所在那块屏
        if pos is not None:
            wa = self._monitor_work_area(RECT(int(pos[0]), int(pos[1]),
                                             int(pos[0]) + 1, int(pos[1]) + 1))
        elif keep_center == "cur":
            wa = self._monitor_work_area()
        else:
            wa = self._pointer_work_area()
        margin = int(round(16 * self.scale))
        w, h = self._fit_pure_size(max(1, int(round(bw * self.zoom))),
                                   max(1, int(round(bh * self.zoom))), wa, margin)
        src = self._flip_source()
        self._pil = src.resize((w, h), Image.LANCZOS)
        self._pet_h = h
        if anchor and self._w and self._h:
            # 以鼠标为中心：记下鼠标在窗口里的相对位置 (rx,ry)，缩放后让同一点回到鼠标下
            # ⚠️ _clamp_into_area 收的是「中心点」，所以这里要把左上角换算回中心
            mx, my = anchor
            rx = min(1.0, max(0.0, (mx - self.x) / float(self._w)))
            ry = min(1.0, max(0.0, (my - self.y) / float(self._h)))
            cx = int(round(mx - rx * w + w / 2.0))
            cy = int(round(my - ry * h + h / 2.0))
        elif pos is not None:
            # 换了新图：还是开在上次那个左上角（_clamp_into_area 会把超出的部分夹回来）
            cx = int(pos[0]) + w // 2
            cy = int(pos[1]) + h // 2
        elif keep_center == "cur" and self.hwnd:
            cx = self.x + (self._w or w) // 2
            cy = self.y + (self._h or h) // 2
        else:
            cx = (wa.left + wa.right) // 2
            cy = (wa.top + wa.bottom) // 2
        self.repaint()                                  # _make_dib 记录新 _w/_h
        self.x, self.y = self._clamp_into_area(cx, cy, wa, margin)
        self.base_y = self.y
        user32.SetWindowPos(self.hwnd, None, self.x, self.y, 0, 0,
                            SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)

    # -- 参考图镜像翻转（只走右键菜单）------------------------------------
    def _flip_source(self):
        """按当前翻转状态取原图：翻转后缓存一份，缩放重采样时不用每次重转。"""
        from PIL import Image
        if self._pure_img is None:
            return None
        if not self.flip_h:
            return self._pure_img
        if self._pure_img_flip is None:
            self._pure_img_flip = self._pure_img.transpose(Image.FLIP_LEFT_RIGHT)
        return self._pure_img_flip

    def toggle_flip(self):
        """左右镜像当前参考图；返回切换后的状态。窗口位置、缩放倍率都不动。"""
        if self._pure_img is None or not self._pure_base:
            return self.flip_h
        self.flip_h = not self.flip_h
        self._pure_img_flip = None            # 下次用的时候再生成
        try:
            if self._pure_base:
                self._apply_pure_zoom(keep_center="cur")   # 就地重绘，中心不动
        except Exception:
            log("toggle_flip 重绘失败\n" + traceback_str())
        log("参考图镜像翻转：%s" % ("开" if self.flip_h else "关"))
        return self.flip_h

    def pure_zoom_step(self, sign, mx=None, my=None):
        """鼠标滚轮缩放：0.5x ~ 2.0x，**以鼠标为中心**（mx,my 给了就用鼠标锚点）。

        ⚠️ 只改等比倍率：顶到屏幕/work area 边缘就停在那儿，不会横向拉宽、不会变形。
        """
        if self._pure_img is None or not self._pure_base:
            return
        old = self.zoom
        self.zoom = max(self.PURE_ZOOM_MIN,
                        min(self.PURE_ZOOM_MAX, self.zoom + sign * self.PURE_ZOOM_STEP))
        if abs(self.zoom - old) > 1e-6:
            self._apply_pure_zoom(keep_center="cur",
                                  anchor=(mx, my) if mx is not None else None)

    def pure_to_next_monitor(self):
        """把参考图大窗搬到下一块显示器（多屏时想放哪块屏就放哪块，仍然置顶）。

        拖到副屏后再缩放也留在副屏；只有一块屏时什么都不做。
        """
        areas = list_monitor_work_areas()
        if len(areas) < 2 or not self.hwnd:
            return False
        try:
            cx = self.x + (self._w or 0) // 2
            cy = self.y + (self._h or 0) // 2
            idx = 0
            for i, a in enumerate(areas):
                if a.left <= cx < a.right and a.top <= cy < a.bottom:
                    idx = i
                    break
            nxt = areas[(idx + 1) % len(areas)]
            self.x = (nxt.left + nxt.right - (self._w or 0)) // 2
            self.y = (nxt.top + nxt.bottom - (self._h or 0)) // 2
            self.base_y = self.y
            user32.SetWindowPos(self.hwnd, None, self.x, self.y, 0, 0,
                                SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
            set_pure_last_pos(self.x, self.y)     # 搬过屏之后，换图也留在这块屏
            log("参考图已移到第 %d 块屏幕 (%d,%d)" % ((idx + 1) % len(areas) + 1, self.x, self.y))
            return True
        except Exception:
            log("搬去下一块屏幕失败\n" + traceback_str())
            return False

    def exit_pure(self, restore_page=True):
        """退出纯净模式：关掉大图窗口，小兔恢复常态；restore_page=True 唤回主界面。"""
        if self.kind == "pure":
            self.hide()                      # 大图窗口自己隐藏即可
            self._pure_img = None
            self._pure_img_flip = None
            self._pure_base = None
            self._display_src = None
            self.zoom = 1.0
            self.flip_h = False
        else:
            pw = PURE_WIN
            if pw is not None and pw.hwnd:
                pw.exit_pure(restore_page=False)
            self.pure = False
            self.timer_left = -1
            self.timer_label = ""
            try:
                self._update_window_rect()
                self.repaint()
            except Exception:
                log("exit_pure：重排/重绘失败\n" + traceback_str())
        if restore_page:
            try:
                restore_page_window()        # 从最小化/隐藏态都能唤回来
            except Exception:
                log("exit_pure：唤回主界面失败\n" + traceback_str())
        return True

    def save_display_image(self):
        """把当前参考图按原图另存为 PNG 到 cards/ 并打开所在文件夹。"""
        try:
            img = self._pure_img or self._decode_display_image()
            if img is None:
                return None
            out = self._card_dir()
            path = os.path.join(out, "ref_" + time.strftime("%Y%m%d_%H%M%S") + ".png")
            img.save(path)
            log("参考图已保存: %s" % path)
            try:
                os.startfile(out)
            except Exception:
                pass
            return path
        except Exception:
            log("save_display_image 失败\n" + traceback_str())
            return None

    # -- 独立大图窗口：加载图 / 显示 / 隐藏 ---------------------------------
    def show_image(self, data_uri):
        """在独立窗口里显示这张参考图（按屏幕适配出基准尺寸，居中置顶）。"""
        from PIL import Image
        try:
            self._display_src = data_uri
            # 用预解码好的那张（网页端提前 /pet_preload 送过来的），没有再现场解码
            img = PURE_PRE_IMG if PURE_PRE_IMG is not None else self._decode_display_image()
            if img is None:
                return False
            if not self.hwnd:
                self.create_raw()
            self._pure_img = img
            self._pure_img_flip = None       # 换了图：镜像缓存作废（翻转状态本身保留）
            self.zoom = 1.0
            wa = self._work_area()
            max_w = int((wa.right - wa.left) * 0.46)
            max_h = int((wa.bottom - wa.top) * 0.62)
            r = min(max_w / float(img.size[0]), max_h / float(img.size[1]))
            self._pure_base = (max(1, int(round(img.size[0] * r))),
                               max(1, int(round(img.size[1] * r))))
            self.pure = True
            self.band = 0
            self.bubble_kind = None
            # 上次的大图停在哪儿，这次（点跳过 / 自动轮播的下一张）就还开在哪儿；
            # 从来没开过才按「鼠标那块屏居中」弹出来。
            self._apply_pure_zoom(keep_center=None, pos=pure_last_pos())
            set_pure_last_pos(self.x, self.y)            # 夹过边界的也认，下次别再漂
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self.visible = True
            return True
        except Exception:
            log("show_image 失败\n" + traceback_str())
            return False

    def hide(self):
        """收起窗口。参考图大窗关之前先把位置记下来，下次换图接着开在这儿。"""
        if self.kind == "pure":
            try:
                r = RECT()
                if self.hwnd and user32.GetWindowRect(self.hwnd, ctypes.byref(r)):
                    if (r.right - r.left) > 1 and (r.bottom - r.top) > 1:
                        set_pure_last_pos(r.left, r.top)
            except Exception:
                pass
        self.pure = False
        if self.hwnd:
            user32.ShowWindow(self.hwnd, SW_HIDE)
        self.visible = False

    # -- 倒计时：显示在小兔左侧的小牌上（不进图片，不影响大图）--------------
    def set_timer(self, left, label=""):
        try:
            left = int(left)
        except Exception:
            left = -1
        self.timer_left = left
        self.timer_label = label or ""
        # 计时圆盘长在头顶那条带子里：要显示就把带子留出来，不显示且没陪画就收回去
        if left >= 0:
            self._ensure_band()
        elif not self.companion_on and self.bubble_kind is None:
            self.band = 0
        self._update_window_rect()
        self.repaint()

    def _text_fit(self, draw, text, maxw, size_hint):
        """挑一个能把 text 塞进 maxw 的字号（从大到小退让）。"""
        f = None
        for ratio in (1.0, 0.86, 0.74, 0.63, 0.54):
            f = self._font_at(max(9, int(round(size_hint * ratio))))
            if f is None:
                return None
            try:
                if draw.textlength(text, font=f) <= maxw:
                    return f
            except Exception:
                return f
        return f

    def _draw_timer_dial(self, canvas, band):
        """头顶的计时圆盘：白底紫边正圆，中间放秒数大字，下面一行状态小字。

        圆里默认什么都不画 —— 没有倒计时（不计时模式）时就是一个空白的白圆，
        专门留给数字用。
        """
        from PIL import ImageDraw
        draw = ImageDraw.Draw(canvas)
        W, H = canvas.size
        sc = self.scale
        pad = int(round(10 * sc))
        avail = band - 2 * pad
        c = min(avail, W - 2 * pad)                # 圆的直径
        c = max(c, int(round(70 * sc)))
        r = c // 2
        cx = W // 2
        cy = pad + r
        ring = max(2, int(round(3 * sc)))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=(255, 255, 255, 255),
                     outline=(127, 95, 192, 255), width=ring)
        if self.timer_left < 0:
            return canvas            # 没有倒计时：圆里什么都不放（默认就是一块空白）
        num = str(max(0, int(self.timer_left)))
        try:
            f_num = self._text_fit(draw, num, c * 0.80, c * 0.54)
            f_lab = (self._text_fit(draw, self.timer_label, c * 0.70, c * 0.20)
                     if self.timer_label else None)
            if f_num is not None:
                draw.text((cx, cy - int(round(c * 0.05))), num,
                          font=f_num, fill=(127, 95, 192, 255), anchor="mm")
            if f_lab is not None:
                draw.text((cx, cy + int(round(c * 0.29))), self.timer_label,
                          font=f_lab, fill=(150, 130, 190, 255), anchor="mm")
        except Exception:
            pass
        return canvas


    # -- 气泡文字换行（中文按字符断行）----------------------------------
    def _wrap(self, text, maxw):
        font = self._font
        lines, cur = [], ""
        for ch in text:
            test = cur + ch
            try:
                w = font.getlength(test) if font else len(test) * 20
            except Exception:
                w = len(test) * 20
            if w > maxw and cur:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        return lines or [text]

    # -- 虚线圆（表情气泡的边框，明显区别于文字气泡的实线圆角矩形）--------
    def _dashed_circle(self, draw, cx, cy, r, color, width):
        import math
        circ = 2 * math.pi * r
        dash = max(6, int(round(16 * self.scale)))
        gap = max(4, int(round(10 * self.scale)))
        step = dash + gap
        n = max(8, int(circ // step))
        for i in range(n):
            a0 = (i * step) / r
            a1 = (i * step + dash) / r
            draw.arc([cx - r, cy - r, cx + r, cy + r],
                     start=math.degrees(a0), end=math.degrees(a1),
                     fill=color, width=width)

    # -- 文字气泡：圆角矩形 + 朝下小尾巴 + 白底紫边 ----------------------
    def _draw_text_bubble(self, canvas, band, text):
        from PIL import ImageDraw
        if self._font is None:
            self._font = self._load_font()
        draw = ImageDraw.Draw(canvas)
        W, H = canvas.size
        sc = self.scale
        pad = int(round(10 * sc))
        maxw = W - 2 * pad
        lines = self._wrap(text, maxw)
        font = self._font
        lh = 0
        for ln in lines:
            bb = draw.textbbox((0, 0), ln, font=font)
            lh = max(lh, bb[3] - bb[1])
        line_h = int(lh * 1.18) + 1
        th = line_h * len(lines)
        bw = maxw
        bh = th + 2 * pad
        bx = pad
        by = pad
        radius = int(round(18 * sc))
        fill = (255, 255, 255, 255)
        outline = (127, 95, 192, 255)    # --pink #7f5fc0
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=radius,
                               fill=fill, outline=outline,
                               width=max(2, int(round(3 * sc))))
        cx = W // 2
        tail_w = int(round(15 * sc))
        tip = by + bh + int(round(16 * sc))
        draw.polygon([(cx - tail_w, by + bh - 1),
                      (cx + tail_w, by + bh - 1),
                      (cx, tip)], fill=fill, outline=outline)
        ty = by + pad
        for ln in lines:
            bb = draw.textbbox((0, 0), ln, font=font)
            tw = bb[2] - bb[0]
            tx = (W - tw) // 2
            draw.text((tx, ty), ln, fill=(59, 51, 80, 255), font=font)
            ty += line_h
        return canvas

    # -- 表情气泡：圆形贴纸 + 虚线边 + 画脸 ------------------------------
    def _draw_expr_bubble(self, canvas, band, expr):
        from PIL import ImageDraw
        draw = ImageDraw.Draw(canvas)
        W, H = canvas.size
        sc = self.scale
        pad = int(round(10 * sc))
        avail = band - 2 * pad
        c = min(avail, W - 2 * pad)
        c = max(c, int(round(70 * sc)))
        r = c // 2
        cx = W // 2
        cy = pad + r
        fill = (255, 255, 255, 255)
        outline = (127, 95, 192, 255)
        wmax = max(2, int(round(3 * sc)))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=None)
        self._dashed_circle(draw, cx, cy, r, outline, wmax)
        self._draw_face(draw, cx, cy, r, expr, wmax)
        return canvas

    # -- 在表情气泡里画脸（happy/focused/tired/sleep 四种明显不同）-------
    def _draw_face(self, draw, cx, cy, r, expr, wmax):
        ink = (59, 51, 80, 255)
        eye_y = cy - int(0.12 * r)
        eye_dx = int(0.36 * r)
        eye_r = max(2, int(0.12 * r))
        if expr == "happy":
            for sx in (-1, 1):
                ex = cx + sx * eye_dx
                draw.arc([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                         start=200, end=340, fill=ink, width=wmax)
            my = cy + int(0.28 * r)
            draw.arc([cx - int(0.42 * r), my - int(0.18 * r),
                      cx + int(0.42 * r), my + int(0.34 * r)],
                     start=20, end=160, fill=ink, width=wmax)
        elif expr == "focused":
            for sx in (-1, 1):
                ex = cx + sx * eye_dx
                draw.ellipse([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                             fill=ink)
            draw.line([cx - int(0.26 * r), cy + int(0.34 * r),
                       cx + int(0.26 * r), cy + int(0.34 * r)],
                      fill=ink, width=wmax)
        elif expr == "tired":
            for sx in (-1, 1):
                ex = cx + sx * eye_dx
                draw.arc([ex - eye_r, eye_y - eye_r * 0.5,
                          ex + eye_r, eye_y + eye_r * 1.5],
                         start=20, end=160, fill=ink, width=wmax)
            my = cy + int(0.34 * r)
            draw.line([cx - int(0.30 * r), my,
                       cx - int(0.10 * r), my - int(0.08 * r),
                       cx + int(0.10 * r), my + int(0.08 * r),
                       cx + int(0.30 * r), my], fill=ink, width=wmax)
            hx = cx + int(0.58 * r)
            hy = cy - int(0.52 * r)
            draw.ellipse([hx - int(0.10 * r), hy,
                          hx + int(0.10 * r), hy + int(0.18 * r)],
                         fill=(120, 170, 220, 255))
        elif expr == "sleep":
            for sx in (-1, 1):
                ex = cx + sx * eye_dx
                draw.arc([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                         start=20, end=160, fill=ink, width=wmax)
            mo = cy + int(0.30 * r)
            draw.ellipse([cx - int(0.09 * r), mo,
                          cx + int(0.09 * r), mo + int(0.14 * r)],
                         outline=ink, width=wmax)
            zc = (127, 95, 192, 255)
            for i, zs in enumerate(["z", "Z", "Z"]):
                zx = cx + int(0.45 * r) + i * int(0.14 * r)
                zy = cy - int(0.6 * r) + i * int(0.20 * r)
                draw.text((zx, zy), zs, fill=zc, font=self._font)
        else:
            for sx in (-1, 1):
                ex = cx + sx * eye_dx
                draw.ellipse([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                             fill=ink)
            draw.line([cx - int(0.22 * r), cy + int(0.32 * r),
                       cx + int(0.22 * r), cy + int(0.32 * r)],
                      fill=ink, width=wmax)

    # -- 每帧推进陪画相位 / 轮换气泡（文字↔表情）/ 清理临时气泡 ----------
    def _tick_bubble(self):
        now = time.time()
        if self.companion_on:
            el = now - self.comp_start
            if el >= self.comp_dur:
                ph = "done"
            elif el >= self.comp_dur * 0.8:
                ph = "doze"
            elif el >= self.comp_dur * 0.5:
                ph = "tired"
            else:
                ph = "focus"
            changed = False
            if ph != self.comp_phase:
                self.comp_phase = ph
                self.bubble_kind = "text"
                self.bubble_text = random.choice(COMP_TEXT.get(ph, ["陪你一起画~"]))
                self.bubble_next = now + 5
                changed = True
            if now >= self.bubble_next:
                if self.bubble_kind == "text":
                    self.bubble_kind = "expr"
                    self.bubble_expr = random.choice(
                        COMP_EXPR.get(self.comp_phase, ["happy"]))
                else:
                    self.bubble_kind = "text"
                    self.bubble_text = random.choice(
                        COMP_TEXT.get(self.comp_phase, ["陪你一起画~"]))
                self.bubble_next = now + 5
                changed = True
            if ph == "done" and el >= self.comp_dur + 6:
                self.set_companion(False)
                return
            if changed:
                self.repaint()
            return
        # 非陪画：临时气泡到点自动消失
        if self.bubble_kind and self.bubble_until and now >= self.bubble_until:
            self._clear_bubble()

    # -- 窗口创建 ------------------------------------------------------
    def _register_class(self):
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = 0x0002 | 0x0001 | 0x0008    # CS_HREDRAW | CS_VREDRAW | CS_DBLCLKS（双击唤回主界面）
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.hCursor = user32.LoadCursorW(None, ctypes.c_wchar_p(32512))  # IDC_ARROW
        wc.lpszClassName = self.cls_name
        self._cls = wc
        if not user32.RegisterClassExW(ctypes.byref(wc)):
            raise ctypes.WinError(ctypes.get_last_error())

    def _work_area(self):
        r = RECT()
        user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(r), 0)
        return r

    def create_raw(self):
        """只创建分层窗口（不载小兔、不定位），纯净大图窗与桌宠共用。"""
        if self.hwnd:
            return self.hwnd
        self._register_class()
        ex_style = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        if self.topmost:
            ex_style |= WS_EX_TOPMOST
        hinst = kernel32.GetModuleHandleW(None)
        self.hwnd = user32.CreateWindowExW(
            ex_style, self.cls_name, APP_NAME, WS_POPUP,
            0, 0, 10, 10, None, None, hinst, None)
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        return self.hwnd

    def create(self, size_idx=None, x=None, y=None):
        if size_idx is not None:
            self.size_idx = size_idx
        if not self.hwnd:
            self.create_raw()

        label, h = self.SIZES[self.size_idx]
        h = int(round(h * self.scale))          # 按 DPI 放大，保证视觉大小一致
        w, h = self._ensure_pet(h)
        wa = self._work_area()
        margin = int(round(24 * self.scale))
        total_h = h + self.band        # 头顶计时圆盘 / 陪画气泡都在这一条带子里
        total_w = w
        if x is None:
            self.x = wa.right - total_w - margin
        else:
            self.x = x
        if y is None:
            self.y = wa.bottom - total_h - margin
        else:
            self.y = y
        self.base_y = self.y
        self.amp = 3.0 * self.scale
        self.repaint()
        if not self.visible:
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self.visible = True
        if self.anim and not self.dragging:
            user32.SetTimer(self.hwnd, self.timer_id, 40, None)
        return w, h

    def resize(self, idx):
        rect = RECT()
        user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        if self.companion_on:
            # 陪画时窗口含气泡带，保持桌宠底部不动：用 None 让 create 重新贴底排版
            self.create(idx)
            if self.anchor:
                self._update_window_rect()   # 拖过就回主人放的位置，别被拽回默认角
        else:
            self.create(idx, x=rect.left, y=rect.top)
        r2 = RECT()                          # 换了尺寸：按新高度重新记一遍底边
        user32.GetWindowRect(self.hwnd, ctypes.byref(r2))
        self.anchor = (r2.left, r2.bottom)

    def set_topmost(self, on):
        self.topmost = bool(on)
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST if on else HWND_NOTOPMOST,
                            0, 0, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE)

    def set_anim(self, on):
        self.anim = bool(on)
        if on:
            user32.SetTimer(self.hwnd, self.timer_id, 40, None)
        else:
            # 陪画进行时即便关闭呼吸动画，也要保留计时器来推进相位
            if not self.companion_on:
                user32.KillTimer(self.hwnd, self.timer_id)
            r = RECT()
            user32.GetWindowRect(self.hwnd, ctypes.byref(r))
            self.base_y = r.top
            user32.SetWindowPos(self.hwnd, None, r.left, self.base_y, 0, 0,
                                SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)

    # -- 右键菜单 ------------------------------------------------------
    def _menu(self):
        hmenu = user32.CreatePopupMenu()
        if self.kind == "pure":
            # 大图窗口只给这几项：另存为 / 翻转 / 唤回主界面 / 退出速写
            # （纯净画面不放任何按钮，操作都走右键菜单；⚠️ 没有任何快捷键，
            #  免得抢走打字时的按键）
            user32.AppendMenuW(hmenu, MF_STRING, 20, "图片另存为…")
            user32.AppendMenuW(hmenu, MF_STRING | (MF_CHECKED if self.flip_h else 0),
                               24, FLIP_MENU_TEXT)
            user32.AppendMenuW(hmenu, MF_STRING, 21, "显示主界面")
            if len(list_monitor_work_areas()) > 1:
                user32.AppendMenuW(hmenu, MF_STRING, 23, "移到下一个屏幕")
            user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(hmenu, MF_STRING, 22, "退出速写（回到主界面）")
            return hmenu
        if self.pure:
            user32.AppendMenuW(hmenu, MF_STRING, 21, "显示主界面")
            user32.AppendMenuW(hmenu, MF_STRING, 22, "退出速写（回到主界面）")
        user32.AppendMenuW(hmenu, MF_STRING, 1, "打开速写页面")
        # 网页模式下（主界面开着）才显示：一键回到「只剩一张参考图」的纯净画面
        if not self.pure and self.has_pure_src():
            user32.AppendMenuW(hmenu, MF_STRING, 25, "返回当前参考图模式")
        if self._display_src:
            user32.AppendMenuW(hmenu, MF_STRING, 20, "图片另存为…")

        sub = user32.CreatePopupMenu()
        for i, (label, _) in enumerate(self.SIZES):
            flag = MF_STRING | (MF_CHECKED if i == self.size_idx else 0)
            user32.AppendMenuW(sub, flag, 10 + i, "小兔大小 · " + label)
        user32.AppendMenuW(hmenu, MF_POPUP, sub, "小兔大小")

        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(hmenu, MF_STRING | (MF_CHECKED if self.topmost else 0),
                           2, "窗口置顶")
        user32.AppendMenuW(hmenu, MF_STRING | (MF_CHECKED if self.anim else 0),
                           3, "呼吸动画")
        user32.AppendMenuW(hmenu, MF_STRING | (MF_CHECKED if self.companion_on else 0),
                           6, "陪画模式")
        gen = user32.CreatePopupMenu()
        user32.AppendMenuW(gen, MF_STRING, 7, "表情包（透明 PNG）")
        user32.AppendMenuW(gen, MF_STRING, 8, "社媒卡片（1080×1350）")
        user32.AppendMenuW(hmenu, MF_POPUP, gen, "一键生成")
        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(hmenu, MF_STRING, 5, "打开网页文件夹")
        user32.AppendMenuW(hmenu, MF_STRING, 4, "退出桌宠")
        return hmenu

    def run_menu(self, hmenu):
        """弹出菜单并执行选中项（桌宠右键与托盘右键共用同一套命令）。"""
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenu(hmenu, TPM_RETURNCMD | TPM_RIGHTBUTTON | TPM_NONOTIFY,
                                    pt.x, pt.y, 0, self.hwnd, None)
        user32.PostMessageW(self.hwnd, 0, 0, 0)   # 经典做法：确保菜单收干净
        user32.DestroyMenu(hmenu)
        self.menu_cmd(cmd)

    def show_menu(self):
        self.run_menu(self._menu())

    def menu_cmd(self, cmd):
        if cmd == 1:
            open_page()
        elif cmd == 20:
            self.save_display_image()
        elif cmd == 21:
            self.exit_pure(True)
        elif cmd == 22:
            request_pure_quit()          # 退出速写：结束这一组 + 自动回到主界面
        elif cmd == 23:
            self.pure_to_next_monitor()  # 多屏：把参考图搬到下一块屏（仍置顶）
        elif cmd == 24:
            self.toggle_flip()           # 左右镜像参考图（只有右键菜单这一个入口）
        elif cmd == 25:
            self.back_to_pure()          # 网页模式 → 回到当前这张参考图的纯净画面
        elif cmd == 2:
            self.set_topmost(not self.topmost)
        elif cmd == 3:
            self.set_anim(not self.anim)
        elif cmd == 6:
            self.set_companion(not self.companion_on, 1500)
        elif cmd == 7:
            self.export_card("sticker")
        elif cmd == 8:
            self.export_card("social")
        elif cmd == 4:
            quit_app()      # 退出桌宠：关页面 + 关参考图大窗 + 清缓存
        elif cmd == 5:
            try:
                os.startfile(materialize_web())
            except Exception:
                pass
        elif cmd == 30:
            self.hide_pet()              # 关闭桌宠：只收起小兔，托盘还在
        elif cmd == 31:
            self.show_pet()              # 把小兔放回来
        elif 10 <= cmd < 10 + len(self.SIZES):
            self.resize(cmd - 10)

    # -- 系统托盘小图标 --------------------------------------------------
    def hide_pet(self):
        """关闭桌宠（从屏幕收起小兔）；程序与托盘图标仍在，可从托盘把它放回来。"""
        if self.hwnd:
            user32.ShowWindow(self.hwnd, SW_HIDE)
            self.visible = False
            log("小兔已收起（托盘图标仍在，右键可「显示小兔」）")

    def show_pet(self):
        """把收起的小兔放回屏幕。"""
        if not self.hwnd:
            return
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        self.visible = True
        try:
            self.repaint()
        except Exception:
            pass
        if self.anim:
            user32.SetTimer(self.hwnd, self.timer_id, 40, None)
        log("小兔已放回屏幕")

    def _tray_menu(self):
        """托盘图标的右键菜单：打开页面 / 设置桌宠 / 关闭桌宠 / 退出桌宠。"""
        m = user32.CreatePopupMenu()
        user32.AppendMenuW(m, MF_STRING, 1, "打开速写页面")

        user32.AppendMenuW(m, MF_SEPARATOR, 0, None)
        setting = user32.CreatePopupMenu()
        size_sub = user32.CreatePopupMenu()
        for i, (label, _) in enumerate(self.SIZES):
            flag = MF_STRING | (MF_CHECKED if i == self.size_idx else 0)
            user32.AppendMenuW(size_sub, flag, 10 + i, label)
        user32.AppendMenuW(setting, MF_POPUP, size_sub, "小兔大小")
        user32.AppendMenuW(setting, MF_STRING | (MF_CHECKED if self.topmost else 0),
                           2, "窗口置顶")
        user32.AppendMenuW(setting, MF_STRING | (MF_CHECKED if self.anim else 0),
                           3, "呼吸动画")
        user32.AppendMenuW(setting, MF_STRING | (MF_CHECKED if self.companion_on else 0),
                           6, "陪画模式")
        user32.AppendMenuW(m, MF_POPUP, setting, "设置桌宠")

        user32.AppendMenuW(m, MF_SEPARATOR, 0, None)
        if self.visible:
            user32.AppendMenuW(m, MF_STRING, 30, "关闭桌宠")
        else:
            user32.AppendMenuW(m, MF_STRING, 31, "显示小兔")
        user32.AppendMenuW(m, MF_STRING, 4, "退出桌宠")
        return m

    def _tray_data(self):
        data = NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        data.hWnd = self.hwnd
        data.uID = TRAY_ID
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.uCallbackMessage = WM_TRAY
        try:
            ico = resource("assets", "pet", "xiaotu.ico")
            if os.path.exists(ico):
                data.hIcon = user32.LoadImageW(
                    None, ico, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
        except Exception:
            pass
        data.szTip = APP_NAME
        return data

    def add_tray_icon(self):
        """在系统托盘放一个小兔图标：右键它有「打开速写页面 / 设置桌宠 / 关闭桌宠 / 退出桌宠」。"""
        try:
            self._tray = self._tray_data()
            ok = shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._tray))
            log("托盘图标 %s" % ("已添加" if ok else "添加失败"))
            return bool(ok)
        except Exception:
            log("add_tray_icon 失败\n" + traceback_str())
            return False

    def remove_tray_icon(self):
        try:
            data = getattr(self, "_tray", None) or self._tray_data()
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))
        except Exception:
            pass

    # -- 消息处理 ------------------------------------------------------
    def _on_message(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_PET_CALL:
                drain_pet_tasks()            # 别的线程排过来任务，在这里（UI 线程）执行
                return 0
            if WM_ALREADY and msg == WM_ALREADY:
                # 又有人双击了一次 exe（第二个实例广播过来的）：跳一下 + 说一句
                self.notify_running()
                return 0
            if msg == WM_TRAY:
                # 托盘图标：左键/双击开页面，右键弹菜单
                if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK, NIN_SELECT):
                    open_page()
                elif lparam in (WM_RBUTTONUP, WM_CONTEXTMENU):
                    self.run_menu(self._tray_menu())
                return 0
            if msg == WM_LBUTTONDOWN:
                self.dragging = True
                self.drag_moved = 0
                pt = POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                r = RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                self.drag_start = (pt.x, pt.y)
                self.drag_win = (r.left, r.top)
                user32.SetCapture(hwnd)
                return 0
            if msg == WM_MOUSEMOVE:
                if self.dragging:
                    pt = POINT()
                    user32.GetCursorPos(ctypes.byref(pt))
                    dx = pt.x - self.drag_start[0]
                    dy = pt.y - self.drag_start[1]
                    self.drag_moved = max(self.drag_moved, abs(dx) + abs(dy))
                    self.x = self.drag_win[0] + dx
                    self.y = self.drag_win[1] + dy
                    self.base_y = self.y
                    user32.SetWindowPos(hwnd, None, self.x, self.y, 0, 0,
                                        SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
                return 0
            if msg == WM_LBUTTONUP:
                if self.dragging:
                    self.dragging = False
                    user32.ReleaseCapture()
                    if self.drag_moved >= 5:
                        # 真的拖过了：把位置记住，之后说话 / 计时 / 换图都不会把它拽回去
                        r = RECT()
                        if user32.GetWindowRect(hwnd, ctypes.byref(r)):
                            if self.kind == "pure":
                                set_pure_last_pos(r.left, r.top)
                            else:
                                # 记底边（用 base_y，别把呼吸动画那几像素算进去）
                                self.anchor = (r.left,
                                               self.base_y + (r.bottom - r.top))
                    # 纯净模式下单击不开页：只留大图，唤回走右键菜单/双击
                    if self.drag_moved < 5 and not self.pure:
                        open_page()
                return 0
            if msg == WM_LBUTTONDBLCLK:
                if self.pure:
                    self.exit_pure(True)     # 双击大图：唤回主界面
                else:
                    open_page()
                return 0
            if msg == WM_MOUSEWHEEL:
                if self.pure or self._pure_img is not None:
                    delta = ctypes.c_short((wparam >> 16) & 0xFFFF).value
                    # WM_MOUSEWHEEL 的 lparam 就是鼠标的屏幕坐标（c_short：副屏负坐标也正确）
                    mx = ctypes.c_short(lparam & 0xFFFF).value
                    my = ctypes.c_short((lparam >> 16) & 0xFFFF).value
                    if self.kind == "pure":
                        # 以鼠标为中心缩放：鼠标指着哪儿就放大哪儿
                        self.pure_zoom_step(1 if delta > 0 else -1, mx, my)
                    elif PURE_WIN is not None:
                        # 在小兔身上滚：鼠标不在图上，按大图自己的中心缩放
                        PURE_WIN.pure_zoom_step(1 if delta > 0 else -1)
                return 0
            if msg == WM_RBUTTONUP:
                if not self.dragging:
                    self.show_menu()
                return 0
            if msg == WM_TIMER and wparam == self.timer_id:
                self._tick_bubble()
                ny = self.y
                if self.anim and not self.dragging:
                    self.phase += 0.10
                    ny = self.base_y + int(round(self.amp * math.sin(self.phase)))
                if self.hop_until and not self.dragging:
                    # 一次完整的「起跳—落回」：半个正弦周期，结束自然回到原位
                    now = time.time()
                    if now >= self.hop_until:
                        self.hop_until = 0.0
                        self.hop_amp = 0.0
                    else:
                        k = (now - self.hop_t0) / max(0.01, self.hop_dur)
                        ny -= int(round(self.hop_amp * math.sin(math.pi * min(1.0, k))))
                if ny != self.y:
                    self.y = ny
                    user32.SetWindowPos(hwnd, None, self.x, ny, 0, 0,
                                        SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
                return 0
            if msg == WM_ENTERSIZEMOVE:
                user32.KillTimer(hwnd, self.timer_id)
                return 0
            if msg == WM_EXITSIZEMOVE:
                r = RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                self.base_y = r.top
                self.y = r.top
                if self.anim:
                    user32.SetTimer(hwnd, self.timer_id, 40, None)
                return 0
            if msg == WM_DESTROY:
                user32.KillTimer(hwnd, self.timer_id)
                self.remove_tray_icon()      # 退出时把托盘图标收掉，别留残影
                user32.PostQuitMessage(0)
                return 0
        except Exception:
            pass
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def run(self):
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


# ---------------------------------------------------------------- 单实例
LOG_PATH = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "DQ-speed-sketch.log")


def log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def fatal(msg):
    log("FATAL " + msg)
    try:
        user32.MessageBoxW(None, msg, APP_NAME, 0x00000010 | 0x00040000)
    except Exception:
        pass


def single_instance():
    kernel32.CreateMutexW(None, False, "Local\\DQXiaotuPet_SingleInstance")
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


def notify_running_instance():
    """又点了一次 exe：让已经在跑的小兔跳一下并说句话（本实例随后直接退出）。

    主通道走本地 HTTP（能确认对方收到了）；万一服务没起来（比如端口被别的程序占着），
    退化成广播注册消息——消息由窗口线程直接接住，一样有效。
    """
    url = "http://127.0.0.1:%d/pet?cmd=already" % SEARCH_PORT
    for i in range(4):                    # 第一个实例刚启动时服务可能还没起来，重试几次
        try:
            with urllib.request.urlopen(url, timeout=1.2) as r:
                if r.status == 200:
                    log("已通知正在运行的小兔（HTTP）")
                    return True
        except Exception:
            if i < 3:
                time.sleep(0.5)
    try:
        if WM_ALREADY and user32.PostMessageW(HWND_BROADCAST, WM_ALREADY, 0, 0):
            log("已通知正在运行的小兔（广播消息）")
            return True
    except Exception:
        log("通知已运行的小兔失败\n" + traceback_str())
    return False


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    no_page = "--no-page" in sys.argv
    log("%s %s 启动" % (APP_NAME, app_version()))   # 版本号直接写进日志，方便核对 exe 是哪一版

    if not single_instance():
        # 已经有小兔在跑了：不再重复启动，只让它跳一下并提示一句
        log("已有小兔在运行，本次不再重复启动")
        notify_running_instance()
        if not no_page:
            open_page()                  # 顺手把已经打开的页面唤到前台
        return

    # 只有真正在跑的那一个实例会走到这里：先把上次异常退出留下的临时图片扫掉
    n = sweep_temp_images()
    if n:
        log("启动时清掉残留临时图片 %d 个" % n)

    if not no_page:
        open_page()                          # ① 优先运行页面
        time.sleep(1.2)                      # 让页面先起来、拿到焦点

    start_search_server()                    # ② 本地搜索代理（关键词开画用）

    global PET, PET_THREAD_ID
    PET_THREAD_ID = kernel32.GetCurrentThreadId()   # 之后所有窗口操作都回到这条线程
    try:
        pet = PetWindow()
        pet.create(size_idx=1)               # ② 右下角小小显示、置顶
        PET = pet
        pet.add_tray_icon()                  # ③ 系统托盘放个小兔，右键可操作/设置/退出
        log("pet created hwnd=%s size=%sx%s at %s,%s"
            % (pet.hwnd, pet._pil.size[0], pet._pil.size[1], pet.x, pet.y))
        pet.run()
    except Exception:
        import traceback
        tb = traceback.format_exc()
        log(tb)
        fatal("小兔桌宠启动失败，速写页面仍可正常使用。\n\n" + tb.strip().splitlines()[-1])


if __name__ == "__main__":
    main()
