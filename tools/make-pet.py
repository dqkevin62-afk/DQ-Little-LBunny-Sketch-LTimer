# -*- coding: utf-8 -*-
"""把抠图结果去黄边、裁边，生成桌宠素材（PNG24 透明）。"""
import os
import sys
import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets", "pet")
BG = np.array([244.0, 215.0, 97.0])  # 原图黄色背景


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


def main(src):
    img = Image.open(src).convert("RGBA")
    print("源:", src, img.size)
    print("去边前 黄边占比: %.2f%%" % yellow_ratio(img))

    fixed = defringe(img, shrink=1.0)
    print("去边后 黄边占比: %.2f%%" % yellow_ratio(fixed))

    # 按 alpha 裁掉四周空白
    bbox = fixed.getchannel("A").getbbox()
    fixed = fixed.crop(bbox)
    print("裁边后:", fixed.size)

    os.makedirs(OUT_DIR, exist_ok=True)
    full = os.path.join(OUT_DIR, "xiaotu-pet.png")
    fixed.save(full, "PNG")
    print("输出:", full, os.path.getsize(full) // 1024, "KB")

    # 生成用于窗口显示的尺寸（长边 220，够 2x 高清显示）
    for edge, name in ((220, "xiaotu-pet-220.png"), (64, "xiaotu-pet-64.png")):
        w, h = fixed.size
        s = edge / max(w, h)
        small = fixed.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
        p = os.path.join(OUT_DIR, name)
        small.save(p, "PNG", optimize=True)
        print("输出:", p, small.size, os.path.getsize(p) // 1024, "KB")

    # 应用图标：方形画布居中
    for size, name in ((256, "xiaotu-icon.png"), (64, "xiaotu-icon-64.png")):
        w, h = fixed.size
        s = (size * 0.94) / max(w, h)
        r = fixed.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.paste(r, ((size - r.width) // 2, (size - r.height) // 2), r)
        p = os.path.join(OUT_DIR, name)
        canvas.save(p, "PNG", optimize=True)
        print("输出:", p, os.path.getsize(p) // 1024, "KB")

    # .ico（多尺寸），供 exe 使用
    ico = os.path.join(OUT_DIR, "xiaotu.ico")
    w, h = fixed.size
    s = (256 * 0.94) / max(w, h)
    r = fixed.resize((round(w * s), round(h * s)), Image.LANCZOS)
    canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    canvas.paste(r, ((256 - r.width) // 2, (256 - r.height) // 2), r)
    canvas.save(ico, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("输出:", ico, os.path.getsize(ico) // 1024, "KB")


if __name__ == "__main__":
    default = r"C:\Users\admin\.workbuddy\binaries\python\envs\default\processed_image_img90232414-999e3c00-553d-4ce5-ba31-a147dc9f1318_1.png"
    main(sys.argv[1] if len(sys.argv) > 1 else default)
