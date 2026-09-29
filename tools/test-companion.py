# -*- coding: utf-8 -*-
"""陪画模式气泡预览：把两种气泡（文字 / 表情）渲染成一张对照图，用于自查版式。
运行后产物：desktop/_companion_preview.png
说明：只做离屏渲染，不创建真实窗口，因此可随时反复跑。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "desktop"))

from PIL import Image  # noqa: E402

import xiaotu_pet as P  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "desktop", "_companion_preview.png")


def cell(pet, kind, payload):
    """渲染一个「桌宠 + 头顶那一块」的单元，贴在淡紫底上便于观察。

    kind = text / expr 走陪画气泡；timer 走计时圆盘（payload = (秒数, 状态词)）。
    """
    w, h = pet._pil.size
    band = int(round(0.58 * h))
    canvas = Image.new("RGBA", (w, h + band), (0, 0, 0, 0))
    canvas.paste(pet._pil, (0, band))
    if kind == "text":
        canvas = pet._draw_text_bubble(canvas, band, payload)
    elif kind == "expr":
        canvas = pet._draw_expr_bubble(canvas, band, payload)
    else:
        pet.timer_left, pet.timer_label = payload
        canvas = pet._draw_timer_dial(canvas, band)
    bg = Image.new("RGB", (w, h + band), (239, 232, 249))
    bg.paste(canvas, (0, 0), canvas)
    return bg


def main():
    pet = P.PetWindow()
    pet._ensure_pet(int(round(178 * pet.scale)))
    w, h = pet._pil.size
    band = int(round(0.58 * h))
    ch = h + band

    cells = [
        ("timer", (50, "绘制中")),
        ("timer", (3, "准备起笔")),
        ("timer", (128, "已画")),
        ("timer", (600, "")),
        ("timer", (-1, "")),          # 不计时：空白的白圆
        ("timer", (5, "最后冲刺")),
        ("text", "陪你一起画~"),
        ("expr", "happy"),
        ("expr", "focused"),
        ("text", "唔…有点累了"),
        ("expr", "tired"),
        ("expr", "sleep"),
    ]
    cols, rows = 3, 4
    gap = 12
    sheet = Image.new("RGB", (cols * w + (cols + 1) * gap,
                              rows * ch + (rows + 1) * gap), (239, 232, 249))
    for i, (kind, payload) in enumerate(cells):
        c = cell(pet, kind, payload)
        x = gap + (i % cols) * (w + gap)
        y = gap + (i // cols) * (ch + gap)
        sheet.paste(c, (x, y))
    sheet.save(OUT)
    print("saved:", OUT, sheet.size)
    print("pet size:", pet._pil.size, "band:", band, "font:", pet._font)
    # 单出一张：重复双击 exe 时小兔的提示气泡（「小兔已经在运行了哦」）
    one = cell(pet, "text", P.ALREADY_TEXT)
    one_path = os.path.join(ROOT, "desktop", "_already_preview.png")
    one.save(one_path)
    print("saved:", one_path, one.size)
    # 一键生成：表情包 / 社媒卡片 / 贴在作品上
    print("sticker:", pet.make_card("sticker"))
    print("social:", pet.make_card("social"))
    demo = Image.new("RGB", (900, 600), (250, 245, 255))
    dump = os.path.join(ROOT, "cards", "_demo_base.png")
    os.makedirs(os.path.dirname(dump), exist_ok=True)
    demo.save(dump)
    print("on:", pet.make_card("on", dump))


if __name__ == "__main__":
    main()
