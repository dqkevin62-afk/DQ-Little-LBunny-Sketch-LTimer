# 纯净参考图大窗：缩放范围 / 等比夹进屏幕 / 多屏搬家 —— 离屏自测（不建窗、不打包）
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop"))
import xiaotu_pet as X  # noqa: E402

R = X.RECT
ok_n = 0
bad_n = 0


def ok(name, cond, extra=""):
    global ok_n, bad_n
    if cond:
        ok_n += 1
        print("  ✓ " + name)
    else:
        bad_n += 1
        print("  ✗ " + name + ("  → " + str(extra) if extra else ""))


class FakeImg(object):
    """代替 PIL 图片：只记尺寸，避免为了跑测试去建真窗口。"""

    def __init__(self, w, h):
        self.size = (w, h)

    def resize(self, size, resample=None):
        return FakeImg(size[0], size[1])


def make_pure(base=(400, 300), wa=(0, 0, 1920, 1080)):
    pw = X.PetWindow.__new__(X.PetWindow)      # 不走 __init__，不建窗
    pw.kind = "pure"
    pw.hwnd = None
    pw.scale = 1.0
    pw.zoom = 1.0
    pw.x, pw.y = 0, 0
    pw._w, pw._h = base
    pw._pure_base = base
    pw._pure_img = FakeImg(base[0], base[1])
    pw._pil = FakeImg(base[0], base[1])
    pw.base_y = 0
    area = R(*wa)
    pw._work_area = lambda: area
    pw._monitor_work_area = lambda rect=None: area
    pw._pointer_work_area = lambda: area

    def repaint():                             # 真 repaint 会 _make_dib 记录 _w/_h
        pw._w, pw._h = pw._pil.size
    pw.repaint = repaint
    return pw


print("【缩放范围：最小 50% / 最大 200%】")
pw = make_pure()
for _ in range(40):
    pw.pure_zoom_step(1)
ok("一直放大最多只到 200%", abs(pw.zoom - 2.0) < 1e-6, pw.zoom)
for _ in range(40):
    pw.pure_zoom_step(-1)
ok("一直缩小最少只到 50%", abs(pw.zoom - 0.5) < 1e-6, pw.zoom)
ok("上限常量就是 2.0", X.PetWindow.PURE_ZOOM_MAX == 2.0, X.PetWindow.PURE_ZOOM_MAX)
ok("下限常量就是 0.5", X.PetWindow.PURE_ZOOM_MIN == 0.5, X.PetWindow.PURE_ZOOM_MIN)
ok("步进 15%：0.5→2.0 正好 10 格",
   abs((X.PetWindow.PURE_ZOOM_MAX - X.PetWindow.PURE_ZOOM_MIN)
       / X.PetWindow.PURE_ZOOM_STEP - 10) < 1e-6)

print("\n【放大到最大也不出屏幕四边，且不拉变形】")
pw = make_pure(base=(1200, 900))               # 3:4 的图
for _ in range(40):
    pw.pure_zoom_step(1)
m = int(round(16 * pw.scale))
ok("等比：宽高比与原图一致",
   abs((pw._w / float(pw._h)) - (1200 / 900.0)) < 0.01, "%sx%s" % (pw._w, pw._h))
ok("高度不超出工作区（上下留边）", pw._h <= 1080 - m * 2, pw._h)
ok("宽度不超出工作区（左右留边）", pw._w <= 1920 - m * 2, pw._w)
ok("窗口左边不出屏", pw.x >= m, pw.x)
ok("窗口右边不出屏", pw.x + pw._w <= 1920 - m, pw.x + pw._w)
ok("窗口上边不出屏", pw.y >= m, pw.y)
ok("窗口下边不出屏", pw.y + pw._h <= 1080 - m, pw.y + pw._h)

print("\n【拖到角落再放大：会被拉回屏幕内，不会顶出去】")
pw = make_pure(base=(600, 400))
pw.x, pw.y = 1900, 1060                        # 故意贴着右下角外面
pw._w, pw._h = 600, 400
pw.pure_zoom_step(1)
ok("放大后仍完整在屏内",
   pw.x >= m and pw.y >= m and pw.x + pw._w <= 1920 - m and pw.y + pw._h <= 1080 - m,
   "x=%s y=%s w=%s h=%s" % (pw.x, pw.y, pw._w, pw._h))

print("\n【多屏：参考图可以搬到任意一块显示器（仍置顶）】")
monitors = [R(0, 0, 1920, 1080), R(1920, 0, 3840, 1080), R(-1920, 0, 0, 1080)]
X.list_monitor_work_areas = lambda: sorted(monitors, key=lambda a: a.left)
pw = make_pure(base=(800, 600))
pw.hwnd = 12345                                # 假装窗口已建（真建窗要起消息循环）
pw.x, pw.y = 1920 + 400, 200                   # 先在副屏上
pw._w, pw._h = 800, 600
src = open(os.path.join(ROOT, "desktop", "xiaotu_pet.py"), encoding="utf-8").read()
ok("多屏时菜单会多出「移到下一个屏幕」",
   "移到下一个屏幕" in src and "cmd == 23" in src
   and "list_monitor_work_areas()) > 1" in src)
seen = []
for _ in range(3):
    pw.pure_to_next_monitor()
    seen.append(pw.x + pw._w // 2)             # 依次落在三块屏的中心附近
ok("连搬三次分别落在三块不同的屏上",
   seen[0] < 0 and 0 <= seen[1] < 1920 and seen[2] >= 1920, seen)
ok("搬完仍在某块屏的可视范围内（没掉到屏外）",
   all(-1920 <= c <= 3840 for c in seen), seen)
X.list_monitor_work_areas = lambda: [R(0, 0, 1920, 1080)]     # 只剩一块屏
before = (pw.x, pw.y)
ok("只有一块屏时不乱跳（返回 False）", pw.pure_to_next_monitor() is False)
ok("只有一块屏时位置不动", (pw.x, pw.y) == before)
ok("搬家用的是所在屏工作区，不会拽回主屏",
   "_monitor_work_area()" in src and "MonitorFromWindow" in src)

print("\n结果：%d 通过 / %d 失败" % (ok_n, bad_n))
sys.exit(1 if bad_n else 0)
