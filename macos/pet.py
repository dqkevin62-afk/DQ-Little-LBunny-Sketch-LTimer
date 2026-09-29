# -*- coding: utf-8 -*-
"""DQ小兔速写计时姬 · macOS 原生桌宠（PyObjC）

用 Cocoa 原生透明无边框窗口显示小兔图片：
  - 左键拖动 = 移动桌宠
  - 左键单击（不拖动）= 打开速写页面
  - 右键 = 菜单（打开页面 / 小兔大小 小·中·大 / 退出桌宠）
  - 始终置顶、可穿透空格显示

依赖：pip install pyobjc-framework-Cocoa
单独运行：python3 pet.py  （会弹出桌宠，单击开页）
由 app.py（py2app 打包）导入后，开页 + 桌宠一起跑。

注：本文件在 Windows 上无法运行（无 Cocoa），仅做语法校验，最终需在 Mac 验证。
"""
import os
import sys
import subprocess
import urllib.parse

from AppKit import (
    NSApplication, NSWindow, NSView, NSImage, NSColor, NSScreen,
    NSMenu, NSMenuItem, NSRect, NSPoint, NSSize, NSMakeRect,
    NSBorderlessWindowMask, NSBackingStoreBuffered, NSFloatingWindowLevel,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSViewWidthSizable, NSViewHeightSizable,
)


# ---------------------------------------------------------------------------
# 资源定位：同时兼容「py2app 打包后的 .app」与「直接用 python3 跑脚本」
# ---------------------------------------------------------------------------
def _bundle_resources_dir():
    """py2app 打包后，资源在 .app/Contents/Resources。"""
    if getattr(sys, "frozen", False):
        exe = os.path.dirname(os.path.abspath(sys.executable))
        return os.path.normpath(os.path.join(exe, "..", "Resources"))
    return None


def find_index():
    """返回 index.html 的绝对路径，找不到返回 None。"""
    here = os.path.dirname(os.path.abspath(__file__))
    res = _bundle_resources_dir()
    candidates = []
    if res is not None:
        candidates.append(os.path.join(res, "web", "index.html"))
    candidates.append(os.path.join(here, "web", "index.html"))          # 打包时拷贝到 macos/web
    candidates.append(os.path.join(here, "..", "..", "index.html"))     # macos/ -> sketch-trainer/
    candidates.append(os.path.join(here, "..", "index.html"))
    for c in candidates:
        c = os.path.normpath(c)
        if os.path.exists(c):
            return c
    return None


def find_pet_image():
    """返回桌宠图片绝对路径，找不到返回 None。"""
    here = os.path.dirname(os.path.abspath(__file__))
    res = _bundle_resources_dir()
    candidates = []
    if res is not None:
        candidates.append(os.path.join(res, "web", "assets", "pet", "xiaotu-pet.png"))
    candidates.append(os.path.join(here, "web", "assets", "pet", "xiaotu-pet.png"))
    candidates.append(os.path.join(here, "..", "..", "assets", "pet", "xiaotu-pet.png"))
    candidates.append(os.path.join(here, "..", "assets", "pet", "xiaotu-pet.png"))
    for c in candidates:
        c = os.path.normpath(c)
        if os.path.exists(c):
            return c
    return None


def open_page():
    """打开速写页面：优先 Chrome 应用窗口，否则默认浏览器。"""
    idx = find_index()
    if not idx:
        return
    url = "file://" + urllib.parse.quote(idx, safe="/:")
    if os.path.exists("/Applications/Google Chrome.app"):
        subprocess.Popen(["open", "-a", "Google Chrome", "--args",
                          "--app=" + url, "--window-size=1280,820",
                          "--window-position=120,60"])
    elif os.path.exists("/Applications/Microsoft Edge.app"):
        subprocess.Popen(["open", "-a", "Microsoft Edge", "--args",
                          "--app=" + url, "--window-size=1280,820"])
    else:
        subprocess.Popen(["open", idx])


# ---------------------------------------------------------------------------
# 桌宠窗口
# ---------------------------------------------------------------------------
class PetWindow(NSWindow):
    def canBecomeKeyWindow(self):
        # 无边框窗口默认不能成为 key 窗口，重写以接收鼠标事件
        return True


class PetView(NSView):
    def initWithFrame_image_(self, frame, image):
        self = super(PetView, self).initWithFrame_(frame)
        if self is not None:
            self.image = image
            self._moved = False
            self._start = None
            self._origin = None
        return self

    def drawRect_(self, rect):
        if self.image is not None:
            self.image.drawInRect_(self.bounds())

    # ---- 左键：拖动 / 单击开页 ----
    def mouseDown_(self, event):
        self._moved = False
        self._start = event.locationInWindow()
        self._origin = self.window().frame().origin

    def mouseDragged_(self, event):
        self._moved = True
        p = event.locationInWindow()
        dx = p.x - self._start.x
        dy = p.y - self._start.y
        o = self._origin
        self.window().setFrameOrigin_(NSPoint(o.x + dx, o.y + dy))

    def mouseUp_(self, event):
        if not self._moved:
            open_page()

    # ---- 右键：菜单 ----
    def rightMouseDown_(self, event):
        menu = self._build_menu()
        menu.popUpMenuPositioningItem_atLocation_inView_(None,
                                                        event.locationInWindow(),
                                                        self)

    def _build_menu(self):
        menu = NSMenu.alloc().initWithTitle_("小兔")
        items = [
            ("打开页面", "openPage:"),
            (None, None),  # 分隔线
            ("小兔大小 · 小 (130)", "setSmall:"),
            ("小兔大小 · 中 (178)", "setMedium:"),
            ("小兔大小 · 大 (240)", "setLarge:"),
            (None, None),
            ("退出桌宠", "quit:"),
        ]
        for label, sel in items:
            if label is None:
                menu.addItem_(NSMenuItem.separatorItem())
                continue
            mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(label, sel, "")
            mi.setTarget_(self)
            menu.addItem_(mi)
        return menu

    # ---- 菜单动作 ----
    def openPage_(self, sender):
        open_page()

    def setSmall_(self, sender):
        self._resize_(130)

    def setMedium_(self, sender):
        self._resize_(178)

    def setLarge_(self, sender):
        self._resize_(240)

    def _resize_(self, s):
        win = self.window()
        win.setContentSize_(NSSize(s, s))
        self.setFrame_(NSMakeRect(0, 0, s, s))
        self.setNeedsDisplay_(True)

    def quit_(self, sender):
        NSApplication.sharedApplication().terminate_(None)


def run_pet():
    """创建并显示桌宠窗口，然后进入 Cocoa 主循环。"""
    NSApplication.sharedApplication()

    img = NSImage.alloc().initWithContentsOfFile_(find_pet_image())
    size = 178  # 默认「中」

    vf = NSScreen.mainScreen().visibleFrame()
    x = vf.origin.x + vf.size.width - size - 20
    y = vf.origin.y + 20  # Cocoa 原点在左下角，20 = 距底边的边距
    rect = NSMakeRect(x, y, size, size)

    win = PetWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        rect, NSBorderlessWindowMask, NSBackingStoreBuffered, False)
    win.setBackgroundColor_(NSColor.clearColor())
    win.setOpaque_(False)
    win.setHasShadow_(False)
    win.setLevel_(NSFloatingWindowLevel)
    win.setIgnoresMouseEvents_(False)
    win.setCollectionBehavior_(NSWindowCollectionBehaviorCanJoinAllSpaces)

    view = PetView.alloc().initWithFrame_image_(NSMakeRect(0, 0, size, size), img)
    view.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
    win.setContentView_(view)
    win.makeKeyAndOrderFront_(None)

    NSApplication.sharedApplication().run()


if __name__ == "__main__":
    run_pet()
