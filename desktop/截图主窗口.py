# -*- coding: utf-8 -*-
"""重做「窗口截图.png」—— 主界面截图，但用**假数据**，不露任何真实信息。

为什么不用 dist 里那份真账本截图：
真账本里有房间号、真实姓氏、真实累计金额，还在底部状态栏显示了本机文件路径。
这三样一起出现在公开仓库的 README 里是不合适的。

这里用 Store 直接造一份脱敏数据（房间号 A-302、成员甲乙丙丁戊、金额整体换过），
再走和 截图回收站.py 一样的 PrintWindow 手法截图 —— 界面代码完全相同，
所以图依然是「真程序真界面」的证据，只是数据是假的。

用法： python 截图主窗口.py   →  窗口截图.png
"""
import ctypes
from ctypes import wintypes
import os
import sys
import tempfile
import time
import zlib
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OUT = os.path.join(HERE, '窗口截图.png')

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

import 电费记账本 as app  # noqa: E402

# ------------------------------------------------------------------ 假数据
# 房间号用 A-302（不是真实宿舍号）；成员用甲乙丙丁戊（不是真实姓氏）；
# 金额整体重排过，任何人拿这张图也算不出真实账目。
MARK = 'A-302'
PEOPLE = ['甲', '乙', '丙', '丁', '戊']
ROWS = [
    # (日期,      成员, 金额,  方式,   备注)
    ('2025-09-09', '甲', 350, '校园卡', '期初首笔'),
    ('2026-07-07', '乙', 100, '校园卡', ''),
    ('2026-07-11', '丙', 100, '校园卡', ''),
    ('2026-07-11', '戊', 100, '校园卡', ''),
    ('2026-07-15', '丁', 100, '校园卡', ''),
    ('2026-07-21', '乙', 100, '校园卡', ''),
    ('2026-07-28', '丙', 100, '校园卡', ''),
    ('2026-08-01', '乙', 100, '校园卡', ''),
    ('2026-08-06', '乙', 100, '校园卡', ''),
    ('2026-08-14', '戊', 100, '校园卡', ''),
    ('2026-08-19', '戊', 100, '校园卡', ''),
    ('2026-08-24', '乙', 100, '校园卡', ''),
    ('2026-08-28', '丙', 100, '校园卡', ''),
    ('2026-08-28', '丁', 100, '校园卡', ''),
    ('2026-09-01', '甲', 100, '微信',   '9月电费'),
    ('2026-09-05', '丁', 200, '支付宝', ''),
    ('2026-09-07', '丙', 100, '校园卡', ''),
    ('2026-09-12', '戊', 150, '微信',   '补交'),
    ('2026-09-18', '丁', 100, '校园卡', ''),
    ('2026-09-20', '甲', 100, '校园卡', ''),
    ('2026-09-24', '戊', 100, '校园卡', ''),
    ('2026-09-25', '甲', 100, '微信',   ''),
    ('2026-09-26', '乙', 100, '校园卡', ''),
    ('2026-09-27', '丙', 100, '支付宝', ''),
]


def save_png(path, px, w, h):
    rows = []
    for y in range(h):
        row = bytearray()
        for x in range(w):
            i = (y * w + x) * 4
            row += bytes((px[i + 2], px[i + 1], px[i], 255))
        rows.append(bytes(row))
    raw = b''.join(b'\x00' + r for r in rows)

    def chunk(tag, payload):
        return (struct.pack('>I', len(payload)) + tag + payload +
                struct.pack('>I', zlib.crc32(tag + payload) & 0xffffffff))

    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 6))
    png += chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(png)


def shot(hwnd, path):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    dc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(dc)
    bmp = gdi32.CreateCompatibleBitmap(dc, w, h)
    gdi32.SelectObject(mem, bmp)
    user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0040)
    user32.SetForegroundWindow(hwnd)
    time.sleep(1.0)
    user32.PrintWindow(hwnd, mem, 0x00000002)

    class BIH(ctypes.Structure):
        _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG),
                    ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD),
                    ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                    ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
                    ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD),
                    ('biClrImportant', wintypes.DWORD)]

    bi = BIH()
    bi.biSize = ctypes.sizeof(BIH)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    got = gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd, dc)
    if got:
        save_png(path, buf.raw, w, h)
    return w, h, got


def main():
    # 数据文件不能落在临时目录里 —— 底部状态栏会原样打印它的完整路径，
    # 那样截图上就会出现 C:\Users\<用户名>\AppData\Local\Temp\...，
    # 等于把本机用户名连同目录结构一起公开了。
    # 这里伪造一个中性的路径（只用于截图这一件事，真实文件写在临时目录）。
    real_tmp = tempfile.mkdtemp(prefix='window_shot_')
    st = app.Store(os.path.join(real_tmp, '电费记账数据.json'))
    st.room = MARK
    for date, who, amt, way, note in ROWS:
        st.add(date, who, amt, way, note)
    st.save()
    # 只改显示用的路径字符串，不真的往那儿写文件
    st.path = r'D:\电费记账本\电费记账数据.json'

    root = app.tk.Tk()
    a = app.App(root, st)
    root.update()
    # 主窗口按设计尺寸摆好，别让 DPI 缩放把比例弄歪
    root.geometry('1100x820+80+60')
    for _ in range(12):
        root.update_idletasks()
        root.update()
        time.sleep(0.15)

    hwnd = root.winfo_id()
    # winfo_id() 给的是子窗口，往上找到 TkTopLevel 才是整窗
    for _ in range(6):
        cc = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cc, 64)
        if cc.value == 'TkTopLevel':
            break
        hwnd = user32.GetParent(hwnd)

    w, h, got = shot(hwnd, OUT)
    print('主窗口 %dx%d 取到行数 %d → %s' % (w, h, got, OUT))
    print('数据文件显示路径（应为中性，不含用户名）：%s' % st.path)

    user32.PostMessageW(root.winfo_id(), 0x0010, 0, 0)
    for _ in range(4):
        try:
            root.update()
        except Exception:
            break
        time.sleep(0.1)
    print('完成')


if __name__ == '__main__':
    main()
