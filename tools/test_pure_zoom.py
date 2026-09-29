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
    pw.flip_h = False                          # _flip_source() 要用到（翻转相关状态）
    pw._pure_img_flip = None
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

print("\n【以鼠标为中心放大：鼠标底下那一点不动】")
pw = make_pure(base=(400, 300))
pw.x, pw.y, pw._w, pw._h = 100, 100, 400, 300
mx, my = 200, 250                              # 鼠标正好指在图的 25% 宽 / 50% 高 处
pw.pure_zoom_step(1, mx, my)                   # 给了鼠标坐标 = 以鼠标为中心
ok("放大一格后倍率是 1.15", abs(pw.zoom - 1.15) < 1e-6, pw.zoom)
rx = (mx - pw.x) / float(pw._w)
ry = (my - pw.y) / float(pw._h)
ok("鼠标指的仍是图上同一个点（横向 25%）", abs(rx - 0.25) < 0.01, rx)
ok("鼠标指的仍是图上同一个点（纵向 50%）", abs(ry - 0.5) < 0.01, ry)
ok("等比放大，没被横向拉宽/拉变形",
   abs((pw._w / float(pw._h)) - (400 / 300.0)) < 0.01, "%sx%s" % (pw._w, pw._h))

print("\n【不给鼠标坐标时（在小兔身上滚）：按大图自己的中心缩放】")
pw2 = make_pure(base=(400, 300))
pw2.hwnd = 12345                               # 假装窗口已建（否则会当首次弹图、居中到屏幕）
pw2.x, pw2.y, pw2._w, pw2._h = 300, 200, 400, 300
c0 = (pw2.x + pw2._w // 2, pw2.y + pw2._h // 2)
pw2.pure_zoom_step(1)
c1 = (pw2.x + pw2._w // 2, pw2.y + pw2._h // 2)
ok("中心基本不动（1~2px 的整数误差可以接受）",
   abs(c1[0] - c0[0]) <= 2 and abs(c1[1] - c0[1]) <= 2, (c0, c1))

print("\n【右键「返回当前参考图模式」：什么时候该出现】")
pet = X.PetWindow.__new__(X.PetWindow)
pet.kind = "pet"
pet.pure = False
pet._last_pure_src = None
ok("一次都没进过参考图模式 → 菜单里不显示这一项", pet.has_pure_src() is False)
pet._last_pure_src = "data:image/png;base64,AAAA"
ok("进过参考图模式 → 能回到刚才那张图", pet.has_pure_src() is True)
pet._last_pure_src = None


class FakePure(object):
    _display_src = "data:image/png;base64,BBBB"


old_pure = X.PURE_WIN
X.PURE_WIN = FakePure()
ok("大图窗口里还留着那张图时，也能回去", pet.has_pure_src() is True)
X.PURE_WIN = old_pure
src = open(os.path.join(ROOT, "desktop", "xiaotu_pet.py"), encoding="utf-8").read()
ok("菜单里有「返回当前参考图模式」（命令 25）",
   '"返回当前参考图模式"' in src and "25, " in src and "cmd == 25" in src)
ok("命令 25 接到 back_to_pure", "self.back_to_pure()" in src and "def back_to_pure" in src)
ok("网页模式下才显示（纯净模式里不重复出现）", "if not self.pure and self.has_pure_src()" in src)

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

print("\n【换图（点跳过 / 自动轮播）接着上次那个位置打开】")
src = open(os.path.join(ROOT, "desktop", "xiaotu_pet.py"), encoding="utf-8").read()
X.PURE_LAST_POS = None
pw = make_pure(base=(400, 300))
pw._apply_pure_zoom(keep_center=None, pos=X.pure_last_pos())      # 第一次：从没开过
ok("第一次弹图按屏幕居中（没有可记的位置）",
   (pw.x, pw.y) == ((1920 - 400) // 2, (1080 - 300) // 2), (pw.x, pw.y))
X.set_pure_last_pos(1200, 100)                                    # 主人把大图拖到这儿
pw2 = make_pure(base=(400, 300))                                  # 下一张图（跳过 / 轮播）
pw2._apply_pure_zoom(keep_center=None, pos=X.pure_last_pos())
ok("换图后还开在上次那个位置", (pw2.x, pw2.y) == (1200, 100), (pw2.x, pw2.y))
ok("换图走的是「上次位置」这条分支", "pos=pure_last_pos()" in src)
ok("换图后把（夹过边界的）位置认下来，下次不再漂",
   "set_pure_last_pos(self.x, self.y)" in src)
X.set_pure_last_pos(1900, 1050)                                   # 贴着右下角外面
pw3 = make_pure(base=(400, 300))
pw3._apply_pure_zoom(keep_center=None, pos=X.pure_last_pos())
ok("记下的位置贴边时会被夹回屏幕内",
   pw3.x >= 16 and pw3.y >= 16
   and pw3.x + pw3._w <= 1920 - 16 and pw3.y + pw3._h <= 1080 - 16,
   (pw3.x, pw3.y))
keep = X.pure_last_pos()
pw4 = make_pure(base=(400, 300))
pw4.hwnd = 12345
pw4.x, pw4.y, pw4._w, pw4._h = 100, 100, 400, 300
pw4.pure_zoom_step(1)
ok("滚轮缩放不会改写记住的位置（只有换图才用）", X.pure_last_pos() == keep)
ok("拖动结束 / 关掉大图都会把位置记下来",
   src.count("set_pure_last_pos(r.left, r.top)") >= 2,
   src.count("set_pure_last_pos(r.left, r.top)"))
ok("搬去下一块屏后也记新位置", "set_pure_last_pos(self.x, self.y)     # 搬过屏之后" in src)

print("\n【小兔：拖到哪儿就在哪儿，说话 / 计时都不再跳回默认角】")
pet = X.PetWindow.__new__(X.PetWindow)
pet.kind = "pet"
pet.hwnd = 999                        # 假装窗口已建（真建窗要起消息循环）
pet.scale = 1.0
pet._pil = FakeImg(180, 180)
pet.band = 0
pet.x, pet.y, pet.base_y = 0, 0, 0
pet.anchor = None
pet._work_area = lambda: R(0, 0, 1920, 1080)
pet._update_window_rect()
ok("没拖过时待在默认角（右下角）",
   (pet.x, pet.y) == (1920 - 180 - 24, 1080 - 180 - 24), (pet.x, pet.y))
pet.anchor = (300, 380)               # 主人把它拖到左边：记「左边 + 底边」
pet.band = 100                        # 说句话：头顶带子变高
pet._update_window_rect()
ok("说了话也没被拽回默认角", (pet.x, pet.y) == (300, 100), (pet.x, pet.y))
ok("带子往上长，小兔的脚（底边）不动", pet.y + 180 + pet.band == 380, pet.y)
pet.anchor = (5000, 5000)             # 改分辨率 / 拔掉副屏，记的位置跑到屏幕外
pet.band = 0
pet._update_window_rect()
ok("记下的位置出界时会被夹回屏幕内",
   0 <= pet.x <= 1920 - 180 and 0 <= pet.y <= 1080 - 180, (pet.x, pet.y))
ok("_clamp_v 正常夹取", X._clamp_v(50, 10, 100) == 50)
ok("_clamp_v 区间反了（窗口比工作区还大）取上界", X._clamp_v(50, 100, 10) == 100)
ok("拖动结束会把位置记下来（记底边，不算呼吸动画那几像素）",
   "self.anchor = (r.left," in src and "self.base_y + (r.bottom - r.top)" in src)
ok("重排时以记住的位置为准，没拖过才回默认角",
   "if self.anchor:" in src and "self.anchor = None" in src)
ok("切换大小（陪画时带子变了）也不会被拽回默认角",
   "self._update_window_rect()   # 拖过就回主人放的位置" in src)

print("\n结果：%d 通过 / %d 失败" % (ok_n, bad_n))
sys.exit(1 if bad_n else 0)
