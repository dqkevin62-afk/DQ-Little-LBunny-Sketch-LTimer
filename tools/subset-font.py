# -*- coding: utf-8 -*-
"""把 MiSans Demibold / Bold 子集化：保留页面实际用字 + GB2312 常用字 + 日文假名 + 拉丁与标点"""
import io, os, sys
from fontTools.subset import Subsetter, Options

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = r"F:\字体\MiSans_Global_ALL\MiSans Global _ALL\MiSans\ttf"
OUT = os.path.join(ROOT, "assets", "fonts")

chars = set()

# 1) 页面与教程数据文件里出现过的所有字符
for rel in ("index.html", "assets/guides.js"):
    p = os.path.join(ROOT, rel)
    if os.path.exists(p):
        with io.open(p, encoding="utf-8") as f:
            chars |= set(f.read())

# 2) GB2312 常用汉字（6763 字）
for hi in range(0xB0, 0xF8):
    for lo in range(0xA1, 0xFF):
        try:
            chars.add(bytes([hi, lo]).decode("gb2312"))
        except Exception:
            pass

# 3) 固定区间：拉丁、标点、假名、全角、CJK 符号、常用符号
ranges = [
    (0x0020, 0x007E), (0x00A0, 0x00FF), (0x0100, 0x017F),
    (0x2000, 0x206F), (0x20A0, 0x20BF), (0x2100, 0x214F),
    (0x2190, 0x21FF), (0x2460, 0x24FF), (0x25A0, 0x25FF),
    (0x3000, 0x303F), (0x3040, 0x309F), (0x30A0, 0x30FF),
    (0x4E00, 0x4E10), (0xFF00, 0xFFEF),
]
for a, b in ranges:
    chars |= {chr(c) for c in range(a, b + 1)}

chars = {c for c in chars if ord(c) > 31 and ord(c) not in (0xFFFE, 0xFFFF)}
print("charset size:", len(chars))


def subset(name, out_prefix):
    from fontTools.ttLib import TTFont
    src = os.path.join(SRC, name + ".ttf")
    font = TTFont(src, fontNumber=0)
    opts = Options()
    opts.unicodes = [ord(c) for c in chars]
    opts.layout_features = ["*"]
    opts.name_IDs = [1, 2, 3, 4, 6]
    opts.notdef_outline = True
    opts.drop_tables += ["DSIG"]
    opts.desubroutinize = True
    opts.flavor = None
    sub = Subsetter(options=opts)
    sub.populate(text="".join(sorted(chars)))
    sub.subset(font)
    ttf_path = os.path.join(OUT, out_prefix + ".ttf")
    woff2_path = os.path.join(OUT, out_prefix + ".woff2")
    font.flavor = None
    font.save(ttf_path)
    font.flavor = "woff2"
    font.save(woff2_path)
    print("%-18s ttf %6.2f MB   woff2 %6.2f MB" % (
        out_prefix,
        os.path.getsize(ttf_path) / 1048576.0,
        os.path.getsize(woff2_path) / 1048576.0))


# 项目只使用一款字体：MiSans-Regular（正文与标题同一个字重，避免合成假粗体）
FACES = [("MiSans-Regular", "MiSans Regular")]
for src_name, family in FACES:
    subset(src_name, src_name)

# 生成内嵌 base64 的 CSS：file:// 双击直接打开也能正常加载（Chrome 会按 CORS 拦截本地字体文件）
import base64
def face(family, prefix, wmax):
    with open(os.path.join(OUT, prefix + ".woff2"), "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    return ("@font-face{font-family:'%s';src:url(data:font/woff2;base64,%s) format('woff2');"
            "font-weight:100 %d;font-style:normal;font-display:swap;}" % (family, b64, wmax))

css_path = os.path.join(OUT, "misans.css")
with io.open(css_path, "w", encoding="utf-8") as fh:
    fh.write("/* MiSans 内嵌字体（小米 · 免费商用）· 由 tools/subset-font.py 生成，请勿手改 */\n")
    for src_name, family in FACES:
        fh.write(face(family, src_name, 900) + "\n")
print("misans.css %.2f MB" % (os.path.getsize(css_path) / 1048576.0))
print("done")
