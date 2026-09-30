# -*- coding: utf-8 -*-
"""把角色图加工成小兔的素材：桌宠 PNG / 各档尺寸 / 应用图标 / .ico，以及网页用的形象与头像。

用法（在 sketch-trainer 目录下）：
  C:/Users/admin/.workbuddy/binaries/python/envs/default/Scripts/python.exe tools/make-pet.py
  ... tools/make-pet.py <角色图.png> [--avatar <头像.png>]

源图两种都吃：
  ① 已抠好的透明图（四角 alpha≈0）→ 直接按 alpha 裁边，**不做**去黄边；
  ② 带纯色背景的图 → 按 BG 反解去边 + 收缩一圈（老流程，原图是黄底）。

产物：
  assets/pet/xiaotu-pet.png        桌宠本体（原生分辨率，透明）
  assets/pet/xiaotu-pet-220.png    窗口显示用（长边 220，够 2x）
  assets/pet/xiaotu-pet-64.png
  assets/pet/xiaotu-icon.png       应用图标（256 方形居中，透明）
  assets/pet/xiaotu-icon-64.png
  assets/pet/xiaotu.ico            exe 图标（多尺寸）
  assets/dq-chibi.png              favicon（512 方形居中，透明）
  assets/dq-timer-hime.png         欢迎页「小兔角色形象」（长边 900，白底不透明，
                                   这样 .hime-img 的圆角+细边照旧成立，不用改 CSS）
  assets/xiaotu-avatar.png         侧栏标题前的圆形头像（直接用头像源图，不缩放）
"""
import os
import sys
import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
OUT_DIR = os.path.join(ASSETS, "pet")

BG = np.array([244.0, 215.0, 97.0])      # 老原图的黄色背景
HIME_EDGE = 900                          # 欢迎页形象长边
HIME_BG = (255, 255, 255)                # 欢迎页形象垫白（不透明）

DEFAULT_SRC = r"E:\小兔速写姬\小兔.png"
DEFAULT_AVATAR = r"E:\小兔速写姬\未标题-1.png"


def is_cutout(img):
    """四角透明 + 有一定比例的透明像素 → 认为源图已经抠好了。"""
    a = np.asarray(img.convert("RGBA"))[..., 3]
    h, w = a.shape
    k = max(4, min(h, w) // 20)
    corners = np.concatenate([a[:k, :k].ravel(), a[:k, -k:].ravel(),
                              a[-k:, :k].ravel(), a[-k:, -k:].ravel()])
    return corners.mean() < 8 and (a < 10).mean() > 0.03


def defringe(img, bg=BG, shrink=1.0):
    """对半透明边缘做「去背景色」反解，消除黄边。"""
    a = np.asarray(img.convert("RGBA")).astype(np.float64)
    rgb, al = a[..., :3], a[..., 3] / 255.0
    soft = (al > 0.004) & (al < 0.996)
    if soft.any():
        fg = (rgb[soft] - (1.0 - al[soft])[:, None] * bg) / np.maximum(al[soft], 1e-6)[:, None]
        rgb[soft] = np.clip(fg, 0, 255)
    a[..., :3] = rgb
    if shrink > 0:
        # 整体收缩 alpha，把最外侧受污染的一圈彻底切掉
        alpha_img = Image.fromarray(a[..., 3].astype(np.uint8), "L")
        alpha_img = alpha_img.filter(ImageFilter.MinFilter(3))  # 3x3 腐蚀 ≈ 收缩 1px
        a[..., 3] = np.asarray(alpha_img).astype(np.float64)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def yellow_ratio(img):
    a = np.asarray(img.convert("RGBA")).astype(np.int16)
    al = a[..., 3]
    m = (al > 40) & (al < 230)
    if not m.any():
        return 0.0
    px = a[m][:, :3]
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    y = (r > 150) & (g > 140) & (b < 130) & ((r - b) > 50) & ((g - b) > 40)
    return y.mean() * 100


def square_canvas(img, size, fill=0.94):
    """等比缩到 size*fill 以内，居中放到 size×size 的透明画布上。"""
    w, h = img.size
    s = (size * fill) / max(w, h)
    r = img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(r, ((size - r.width) // 2, (size - r.height) // 2), r)
    return canvas


def save(img, path, **kw):
    img.save(path, **kw)
    print("输出:", path, img.size, os.path.getsize(path) // 1024, "KB")


def main(src, avatar_src=None):
    img = Image.open(src).convert("RGBA")
    cutout = is_cutout(img)
    print("源:", src, img.size, "| 已是抠好的透明图:", cutout)

    if cutout:
        fixed = img
    else:
        print("去边前 黄边占比: %.2f%%" % yellow_ratio(img))
        fixed = defringe(img, shrink=1.0)
        print("去边后 黄边占比: %.2f%%" % yellow_ratio(fixed))

    # 按 alpha 裁掉四周空白
    bbox = fixed.getchannel("A").getbbox()
    fixed = fixed.crop(bbox)
    print("裁边后:", fixed.size)

    os.makedirs(OUT_DIR, exist_ok=True)
    save(fixed, os.path.join(OUT_DIR, "xiaotu-pet.png"), format="PNG")

    # 生成用于窗口显示的尺寸（长边 220，够 2x 高清显示）
    for edge, name in ((220, "xiaotu-pet-220.png"), (64, "xiaotu-pet-64.png")):
        w, h = fixed.size
        s = edge / max(w, h)
        small = fixed.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
        save(small, os.path.join(OUT_DIR, name), format="PNG", optimize=True)

    # 应用图标：方形画布居中
    for size, name in ((256, "xiaotu-icon.png"), (64, "xiaotu-icon-64.png")):
        save(square_canvas(fixed, size), os.path.join(OUT_DIR, name), format="PNG", optimize=True)

    # .ico（多尺寸），供 exe 使用
    ico = os.path.join(OUT_DIR, "xiaotu.ico")
    square_canvas(fixed, 256).save(
        ico, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("输出:", ico, os.path.getsize(ico) // 1024, "KB")

    # ---------- 网页用的两张 ----------
    # favicon：方形居中透明（index.html 的 <link rel="icon"> 一直指着这个名字，不用改 HTML）
    save(square_canvas(fixed, 512), os.path.join(ASSETS, "dq-chibi.png"),
         format="PNG", optimize=True)

    # 欢迎页「小兔 角色形象」：垫白 + 不透明
    #   为什么垫白不透明：.hime-img 有 `border-radius:16px; border:1px solid var(--line)`，
    #   透明图套一圈细边会变成一个「空框」。垫白后照旧是「圆角卡片 + 细边」，
    #   和全站白卡片一致，一行 CSS 都不用动。
    w, h = fixed.size
    s = HIME_EDGE / max(w, h)
    hime = fixed.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    flat = Image.new("RGB", hime.size, HIME_BG)
    flat.paste(hime, (0, 0), hime)
    save(flat, os.path.join(ASSETS, "dq-timer-hime.png"), format="PNG", optimize=True)

    # ---------- 侧栏标题前的圆形头像 ----------
    if avatar_src:
        av = Image.open(avatar_src).convert("RGBA")
        print("头像源:", avatar_src, av.size)
        # 不缩放（源图 80×80，显示 34px，2 倍屏也够）；只统一成 RGBA 存 PNG
        save(av, os.path.join(ASSETS, "xiaotu-avatar.png"), format="PNG", optimize=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    avatar = DEFAULT_AVATAR
    if "--avatar" in args:
        i = args.index("--avatar")
        avatar = args[i + 1]
        del args[i:i + 2]
    main(args[0] if args else DEFAULT_SRC, avatar)
