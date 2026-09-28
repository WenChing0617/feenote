# -*- coding: utf-8 -*-
"""生成程序图标 app.ico —— 只用 Python 标准库（无 Pillow 依赖）

画法：圆角方块（清透蓝竖向渐变）+ 白色闪电，每像素 3x3 超采样做抗锯齿。
配色与安卓版保持一致（同一个渐变），两边图标放一起看不出色差。
"""
import os
import struct

BG_TOP = (90, 160, 245)     # #5aa0f5
BG_BOT = (47, 121, 224)     # #2f79e0
WHITE = (255, 255, 255)

# 闪电多边形（归一化坐标，顺时针）
BOLT = [
    (0.615, 0.055),
    (0.300, 0.520),
    (0.480, 0.520),
    (0.400, 0.945),
    (0.745, 0.455),
    (0.545, 0.455),
]

RADIUS = 0.235
SS = 3  # 每像素每轴采样数


def in_poly(x, y, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def in_round_rect(x, y, r):
    if x < 0 or x > 1 or y < 0 or y > 1:
        return False
    if r <= x <= 1 - r or r <= y <= 1 - r:
        return True
    cx = r if x < r else 1 - r
    cy = r if y < r else 1 - r
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def sample(u, v):
    if not in_round_rect(u, v, RADIUS):
        return (0, 0, 0, 0)
    if in_poly(u, v, BOLT):
        return (WHITE[0], WHITE[1], WHITE[2], 255)
    t = max(0.0, min(1.0, v))
    r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
    g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
    b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
    return (r, g, b, 255)


def render_bgra(size):
    """返回自下而上的 BGRA 字节序列"""
    out = bytearray(size * size * 4)
    step = 1.0 / (size * SS)
    inv = 1.0 / (SS * SS)
    for row in range(size):
        v_base = row * SS
        for col in range(size):
            u_base = col * SS
            ar = ag = ab = aa = 0
            for sy in range(SS):
                v = (v_base + sy + 0.5) * step
                for sx in range(SS):
                    u = (u_base + sx + 0.5) * step
                    r, g, b, a = sample(u, v)
                    ar += r
                    ag += g
                    ab += b
                    aa += a
            r = int(ar * inv + 0.5)
            g = int(ag * inv + 0.5)
            b = int(ab * inv + 0.5)
            a = int(aa * inv + 0.5)
            # ICO 的 DIB 自下而上：第 0 行对应图像底部
            idx = ((size - 1 - row) * size + col) * 4
            out[idx] = b
            out[idx + 1] = g
            out[idx + 2] = r
            out[idx + 3] = a
    return bytes(out)


def make_dib(size, bgra):
    mask_row = ((size + 31) // 32) * 4
    mask = b'\x00' * (mask_row * size)
    header = struct.pack('<IiiHHIIiiII',
                         40,          # biSize
                         size,        # biWidth
                         size * 2,    # biHeight（XOR + AND）
                         1,           # biPlanes
                         32,          # biBitCount
                         0,           # biCompression
                         len(bgra) + len(mask),
                         0, 0, 0, 0)
    return header + bgra + mask


def build_ico(path, sizes=(16, 24, 32, 48, 64, 128, 256)):
    entries = []
    blobs = []
    offset = 6 + 16 * len(sizes)
    for s in sizes:
        data = make_dib(s, render_bgra(s))
        w = 0 if s >= 256 else s
        entries.append(struct.pack('<BBBBHHII', w, w, 0, 0, 1, 32, len(data), offset))
        blobs.append(data)
        offset += len(data)
    with open(path, 'wb') as f:
        f.write(struct.pack('<HHH', 0, 1, len(sizes)))
        for e in entries:
            f.write(e)
        for b in blobs:
            f.write(b)
    return os.path.getsize(path)


if __name__ == '__main__':
    target = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.ico')
    size = build_ico(target)
    print('已生成 %s （%d 字节）' % (target, size))
