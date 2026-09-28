# -*- coding: utf-8 -*-
"""单独给「回收站」弹窗截一张图（源码版，不依赖鼠标点击坐标）

为什么不复用 验证exe.py 的 DF_CLICK：exe 的 onefile 启动 + 窗口坐标系
在不同 DPI 下很难一次点准，脚本容易变成「猜坐标」。
这里直接调 `App.open_trash()` 把窗口打开，再用和 验证exe.py 一样的
PrintWindow 手法截图 —— 界面代码完全一样，证据同样有效。

用法： python 截图回收站.py   →  回收站截图.png
"""
import ctypes
import os
import struct
import sys
import tempfile
import time
import zlib
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OUT = os.path.join(HERE, '回收站截图.png')
WIN = os.path.join(HERE, '成员管理截图.png')

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

import 电费记账本 as app  # noqa: E402


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
    time.sleep(0.8)
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


WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)


def find_toplevel(pid, title):
    res = []

    def cb(h, _):
        if user32.IsWindowVisible(h):
            p = wintypes.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(p))
            if p.value == pid:
                cc = ctypes.create_unicode_buffer(64)
                user32.GetClassNameW(h, cc, 64)
                tb = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(h, tb, 256)
                if cc.value == 'TkTopLevel' and (title in tb.value or not tb.value):
                    res.append(h)
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return res


def main():
    tmp = tempfile.mkdtemp(prefix='trash_shot_')
    st = app.Store(os.path.join(tmp, '电费记账数据.json'))
    st.room = 'A-302'
    st.add('2025-09-09', '张三', 350, '校园卡', '期初首笔（原始表首行，无 * 标记）')
    st.add('2026-09-01', '张三', 100, '微信', '9月电费')
    st.add('2026-09-05', '李四', 200, '支付宝', '')
    st.add('2026-09-12', '王五', 150, '微信', '补交')
    st.delete_many([r['id'] for r in st.records if r['member'] == '李四'])
    st.add('2026-08-20', '李四', 60, '现金', '录错了，先删掉')
    st.delete_many([r['id'] for r in st.records if r['member'] == '李四'])
    st.save()

    root = app.tk.Tk()
    a = app.App(root, st)
    root.update()
    pid = os.getpid()

    for opener, title, out in ((a.open_trash, '回收站', OUT),
                              (a.open_members, '成员管理', WIN)):
        opener()
        for _ in range(6):
            root.update_idletasks()
            root.update()
            time.sleep(0.15)
        wins = [h for h in find_toplevel(pid, title)]
        # 取面积最大的那个（排除隐藏的小窗）
        best = None
        for h in wins:
            r = wintypes.RECT()
            user32.GetWindowRect(h, ctypes.byref(r))
            area = (r.right - r.left) * (r.bottom - r.top)
            if r.right - r.left > 300 and (best is None or area > best[0]):
                best = (area, h)
        if best:
            w, h, got = shot(best[1], out)
            print('%s 弹窗 %dx%d 取到行数 %d → %s' % (title, w, h, got, out))
        else:
            print('%s 弹窗没找到' % title)
        for h in wins:
            user32.PostMessageW(h, 0x0010, 0, 0)      # WM_CLOSE
        for _ in range(4):
            root.update_idletasks()
            root.update()
            time.sleep(0.1)

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
