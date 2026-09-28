# -*- coding: utf-8 -*-
"""启动打包好的 exe，验证窗口能否正常显示，并截一张图回来"""
import ctypes
import json
import os
import struct
import subprocess
import sys
import time
import zlib
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(HERE, 'dist', '电费记账本.exe')
DATA = os.path.join(HERE, 'dist', '电费记账数据.json')
DATABAK = DATA + '.verify.bak'
SHOT = os.path.join(HERE, '窗口截图.png')
CAL_SHOT = os.path.join(HERE, '日历截图.png')


def restore_data():
    """验证会用示例数据覆盖真实数据文件，跑完必须还原，别把主人的账本冲掉"""
    global _restored
    if _restored:
        return
    _restored = True
    if os.path.exists(DATABAK):
        import shutil
        shutil.move(DATABAK, DATA)
        print('已还原真实数据 →', DATA)
    elif not KEEP and os.path.exists(DATA):
        # 只有「确实写入了示例数据」的情况下才允许清理，
        # 否则 --keep 模式会把主人自己的账本删掉
        os.remove(DATA)
        print('已清理示例数据（原本没有真实数据文件）')


_restored = False
import atexit
atexit.register(restore_data)

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

print('exe 存在:', os.path.exists(EXE), '大小 %.1f MB' % (os.path.getsize(EXE) / 1048576))

# 预置一份示例数据，用来验证 exe 会读本地文件
# 加 --keep 则不碰数据文件：直接拿主人自己的真实账本来截图（收尾验证用）
KEEP = '--keep' in sys.argv
if not KEEP:
    if os.path.exists(DATA):
        import shutil
        shutil.move(DATA, DATABAK)
        print('已备份原有数据 →', DATABAK)
    sample = {
        'app': '电费记账本', 'version': '1.3', 'room': 'A-302',
        'members': ['张三', '李四', '王五'],
        'memberIds': {'张三': 1, '李四': 2, '王五': 3},
        'records': [
            {'id': 'a0', 'date': '2025-09-09', 'member': '张三', 'amount': 350,
             'method': '校园卡', 'note': '期初首笔（原始表首行，无 * 标记）',
             'createdAt': 1, 'initial': True},
            {'id': 'a1', 'date': '2026-09-01', 'member': '张三', 'amount': 100, 'method': '微信', 'note': '9月电费', 'createdAt': 2},
            {'id': 'a2', 'date': '2026-09-05', 'member': '李四', 'amount': 200, 'method': '支付宝', 'note': '', 'createdAt': 3},
            {'id': 'a3', 'date': '2026-09-12', 'member': '王五', 'amount': 150, 'method': '微信', 'note': '补交', 'createdAt': 4},
        ],
        'deleted': [
            {'id': 'd1', 'date': '2026-08-20', 'member': '李四', 'amount': 60,
             'method': '现金', 'note': '录错了，先删掉', 'createdAt': 5, 'deletedAt': 1767000000000},
        ],
    }
    with open(DATA, 'w', encoding='utf-8') as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)
    print('已预置示例数据 →', DATA)
else:
    print('（--keep）不修改数据文件，直接验证真实数据 →', DATA)

proc = subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
print('已启动 exe，pid =', proc.pid)

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
allwins = []


def enum_cb(hwnd, _):
    if user32.IsWindowVisible(hwnd):
        n = user32.GetWindowTextLengthW(hwnd)
        tbuf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, tbuf, 512)
        cbuf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cbuf, 256)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        allwins.append((hwnd, tbuf.value, cbuf.value, pid.value, n))
    return True


hwnd = None
title = ''
for i in range(60):
    allwins.clear()
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    # Tk 顶层窗口类名固定为 TkTopLevel；也兼容标题匹配
    for h, t, c, pid, n in allwins:
        if c == 'TkTopLevel' or '电费记账本' in t:
            hwnd, title = h, t
            break
    if hwnd:
        break
    if proc.poll() is not None:
        break
    time.sleep(0.5)

print('进程存活:', proc.poll() is None, '退出码:', proc.poll())
print('窗口标题:', repr(title))
if not hwnd:
    print('（未找到 Tk 窗口，可见窗口清单如下）')
    for h, t, c, pid, n in allwins[:25]:
        print('   pid=%-6d class=%-22s title=%r' % (pid, c, t[:50]))

ok_shot = False
if hwnd:
    time.sleep(1.5)
    user32.SetForegroundWindow(hwnd)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    print('窗口尺寸: %dx%d' % (w, h))

    hdc_win = user32.GetWindowDC(hwnd)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_win, w, h)
    gdi32.SelectObject(hdc_mem, hbmp)

    # 置顶并抢焦点
    user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0040)
    user32.SetForegroundWindow(hwnd)
    time.sleep(1.5)

    SRCCOPY = 0x00CC0020

    def blt_from_screen():
        hdc_screen = user32.GetDC(0)
        ok = gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, rect.left, rect.top, SRCCOPY)
        user32.ReleaseDC(0, hdc_screen)
        return ok

    # 优先 PrintWindow：直接让窗口把自己画一遍，别的窗口（QQ 弹窗之类）挡在前面也不影响
    PW_RENDERFULLCONTENT = 0x00000002
    ok_pw = user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)
    print('PrintWindow 返回:', ok_pw)
    if not ok_pw:
        ok_blt = blt_from_screen()
        print('BitBlt(屏幕) 返回:', ok_blt)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG),
                    ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD),
                    ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                    ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
                    ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD),
                    ('biClrImportant', wintypes.DWORD)]

    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h  # 自上而下
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    got = gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bi), 0)
    print('GetDIBits 取到行数:', got)

    def looks_blank(px, w, h):
        """PrintWindow 有时会返回全黑/全白，抽样判一下，真是空的就退回屏幕抓取"""
        step = max(1, (w * h) // 2000)
        first = None
        for k in range(0, w * h, step):
            i = k * 4
            c = (px[i], px[i + 1], px[i + 2])
            if first is None:
                first = c
            elif c != first:
                return False
        return True

    if ok_pw and looks_blank(buf.raw, w, h):
        print('PrintWindow 拿到的是空图，退回屏幕抓取')
        ok_blt = blt_from_screen()
        print('BitBlt(屏幕) 返回:', ok_blt)
        got = gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bi), 0)
        print('GetDIBits 取到行数:', got)

    def save_png(path, px, w, h):
        rows = []
        for y in range(h):
            row = bytearray()
            for x in range(w):
                i = (y * w + x) * 4
                row += bytes((px[i + 2], px[i + 1], px[i], 255))  # BGR -> RGB
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

    if got:
        save_png(SHOT, buf.raw, w, h)
        ok_shot = True
        print('屏幕截图已保存:', SHOT)

    # ---- 可选：点开某个下拉/弹窗，再截一张 ----
    #   --cal            真的用鼠标点开日期框，把「一整月日期表」截下来
    #   DF_CLICK=x,y     直接点窗口客户区某个坐标（配 DF_SHOT=输出路径）
    if ('--cal' in sys.argv) or os.environ.get('DF_CLICK'):
        try:
            class POINT(ctypes.Structure):
                _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]

            me_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(me_pid))
            me_pid = me_pid.value

            def click_client(cx, cy):
                pt = POINT(int(cx), int(cy))
                user32.ClientToScreen(hwnd, ctypes.byref(pt))
                user32.SetCursorPos(pt.x, pt.y)
                time.sleep(0.10)
                user32.mouse_event(0x0002, 0, 0, 0, 0)   # 左键按下
                time.sleep(0.06)
                user32.mouse_event(0x0004, 0, 0, 0, 0)   # 左键抬起

            def find_popup():
                res = []

                def cb2(h, _):
                    if user32.IsWindowVisible(h) and h != hwnd:
                        p = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(h, ctypes.byref(p))
                        if p.value == me_pid:
                            cc = ctypes.create_unicode_buffer(64)
                            user32.GetClassNameW(h, cc, 64)
                            if cc.value == 'TkTopLevel':
                                res.append(h)
                    return True

                user32.EnumWindows(WNDENUMPROC(cb2), 0)
                return res[0] if res else None

            pop = None
            _env_click = os.environ.get('DF_CLICK')
            _out = os.environ.get('DF_SHOT') or CAL_SHOT
            if _env_click:
                # DF_CLICK 支持多个候选点（用 ; 分隔），挨个点直到有弹窗为止 ——
                # 因为按钮的客户区坐标会随 DPI 缩放变化，写死一个点很容易点空
                _r = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(_r))
                _o = POINT(0, 0)
                user32.ClientToScreen(hwnd, ctypes.byref(_o))
                print('窗口矩形 (%d,%d)-(%d,%d)' % (_r.left, _r.top, _r.right, _r.bottom))
                print('客户区原点 (屏幕坐标) = (%d,%d)  → 客户区偏移 (%d,%d)'
                      % (_o.x, _o.y, _o.x - _r.left, _o.y - _r.top))
                print('截图是从「窗口左上角」开始算的：客户区坐标 = 截图像素 − 偏移')
                cands = []
                for part in _env_click.split(';'):
                    part = part.strip()
                    if not part:
                        continue
                    _cx, _cy = [int(v) for v in part.split(',')]
                    cands.append((_cx, _cy))
                for _cx, _cy in cands:
                    click_client(_cx, _cy)
                    time.sleep(1.0)
                    pop = find_popup()
                    print('DF_CLICK=(%d,%d) → %s' % (_cx, _cy, '弹窗已出现' if pop else '没看到弹窗'))
                    if pop:
                        break
            else:
                for cy in (242, 250, 234, 226, 258, 218, 266):
                    click_client(200, cy)
                    time.sleep(0.7)
                    pop = find_popup()
                    if pop:
                        print('日历已弹出（点 client y=%d 命中）' % cy)
                        break
            if pop:
                time.sleep(0.7)
                r2 = wintypes.RECT()
                user32.GetWindowRect(pop, ctypes.byref(r2))
                cw, ch = r2.right - r2.left, r2.bottom - r2.top
                dc2 = user32.GetWindowDC(pop)
                m2 = gdi32.CreateCompatibleDC(dc2)
                b2 = gdi32.CreateCompatibleBitmap(dc2, cw, ch)
                gdi32.SelectObject(m2, b2)
                user32.PrintWindow(pop, m2, PW_RENDERFULLCONTENT)
                bi2 = BITMAPINFOHEADER()
                bi2.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                bi2.biWidth = cw
                bi2.biHeight = -ch
                bi2.biPlanes = 1
                bi2.biBitCount = 32
                bi2.biCompression = 0
                buf2 = ctypes.create_string_buffer(cw * ch * 4)
                g2 = gdi32.GetDIBits(m2, b2, 0, ch, buf2, ctypes.byref(bi2), 0)
                print('日历窗口尺寸: %dx%d 取到行数: %d' % (cw, ch, g2))
                if g2 and cw > 100 and ch > 100:
                    save_png(_out, buf2.raw, cw, ch)
                    print('弹窗截图已保存:', _out)
                else:
                    print('弹窗太小，判定为没弹出来')
                gdi32.DeleteObject(b2)
                gdi32.DeleteDC(m2)
                user32.ReleaseDC(pop, dc2)
                user32.keybd_event(0x1B, 0, 0, 0)        # Esc 收起
                user32.keybd_event(0x1B, 0, 2, 0)
                time.sleep(0.5)
            else:
                print('没能点开（窗口坐标没对上），跳过弹窗截图')
        except Exception as ex:
            print('日历截图失败:', ex)

    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(hwnd, hdc_win)

    user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
    time.sleep(1.0)

if proc.poll() is None:
    proc.terminate()
    time.sleep(0.5)

restore_data()

print('--- 结论 ---')
print('窗口出现:', bool(hwnd))
print('截图成功:', ok_shot)
print('最终退出码:', proc.poll())
sys.exit(0 if hwnd else 2)
