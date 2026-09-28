# -*- coding: utf-8 -*-
"""生成「电费记账本」的应用图标（纯标准库，不依赖 Pillow）。

设计：清透天蓝**竖向渐变**圆角方块 + 白色闪电。
上一版是 #2E7D32 的深绿平涂，太沉；这一版用渐变做出通透感。

输出：app/src/main/res/mipmap-*/ic_launcher.png（5 档）
用法：python tools/make_icon.py
"""
import math
import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "app", "src", "main", "res")

# 渐变：自上而下的清透蓝
BG_TOP = (0x5A, 0xA0, 0xF5)     # #5AA0F5
BG_BOT = (0x2F, 0x79, 0xE0)     # #2F79E0
FG = (255, 255, 255)            # 白色闪电

# 闪电多边形（归一化坐标 0~1）
LIGHTNING = [
    (0.575, 0.155),
    (0.360, 0.545),
    (0.472, 0.545),
    (0.425, 0.845),
    (0.648, 0.452),
    (0.532, 0.452),
]


def in_polygon(x, y, poly):
    """射线法判断点是否在多边形内"""
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            if x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


def render(size):
    """返回逐行 RGBA 字节"""
    radius = size * 0.225
    rows = []
    for py in range(size):
        row = bytearray()
        y = py + 0.5
        # 当前这一行在渐变里的位置（0=顶 1=底）
        t = py / max(size - 1, 1)
        bg = (
            round(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t),
            round(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t),
            round(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t),
        )
        for px in range(size):
            x = px + 0.5
            # 圆角矩形距离场
            cx = min(max(x, radius), size - radius)
            cy = min(max(y, radius), size - radius)
            if math.hypot(x - cx, y - cy) > radius:
                row += b"\x00\x00\x00\x00"
                continue
            if in_polygon(x / size, y / size, LIGHTNING):
                row += bytes((FG[0], FG[1], FG[2], 255))
            else:
                row += bytes((bg[0], bg[1], bg[2], 255))
        rows.append(bytes(row))
    return rows


def write_png(path, size, rows):
    raw = b"".join(b"\x00" + r for r in rows)

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


DENSITIES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}

total = 0
for density, size in DENSITIES.items():
    folder = os.path.join(OUT, "mipmap-" + density)
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, "ic_launcher.png")
    n = write_png(target, size, render(size))
    total += n
    print("%-9s %3dx%-3d  %6d bytes" % (density, size, size, n))

print("共生成 %d 个图标文件，合计 %d bytes" % (len(DENSITIES), total))
