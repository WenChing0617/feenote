# -*- coding: utf-8 -*-
"""端到端验收：在打包好的 exe 里**真的点一次**「一键导出」

用法：  python 验收导出.py
退出码：0 = 导出成功，1 = 失败

注意：会真实移动鼠标并点击（约 10 秒），运行期间别抢鼠标；
      需要非沙箱环境（沙箱会拦住 SendInput）。
      把窗口置顶 + SendInput 发真实点击 —— Tk 不理会 PostMessage 发来的合成消息。
（下面是原始说明）

要点：
  * WM_LBUTTONDOWN 用 PostMessage 发过去 Tk 不理会（合成消息），必须用 SendInput 发真实输入
  * 真实鼠标点击打的是「屏幕最上层那个窗口」，所以先把 exe 窗口 SetWindowPos 置顶
    并挪到左上角一块固定区域，免得点穿到 Edge / WorkBuddy 上
"""
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import 电费记账本 as app  # noqa: E402

EXE = os.path.join(HERE, 'dist', '电费记账本.exe')
OUTDIR = os.path.join(HERE, 'dist', app.EXPORT_DIR)
user32 = ctypes.windll.user32

SWP_SHOWWINDOW = 0x0040
HWND_TOPMOST = -1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG),
                ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_void_p)]


class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('mi', MOUSEINPUT)]


def send_mouse(flags, x=None, y=None):
    inp = INPUT()
    inp.type = 0                      # INPUT_MOUSE
    inp.mi = MOUSEINPUT()
    inp.mi.dwFlags = flags
    if x is not None:
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        inp.mi.dx = int(x * 65535 / (sw - 1))
        inp.mi.dy = int(y * 65535 / (sh - 1))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def click(x, y):
    send_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, x, y)
    time.sleep(0.25)
    send_mouse(MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.12)
    send_mouse(MOUSEEVENTF_LEFTUP)
    time.sleep(0.35)


# ---------- 1. 量按钮相对客户区的坐标 ----------
print('=== 1. 量按钮坐标 ===')
app.enable_dpi()
root = app.tk.Tk()
tmp = tempfile.mkdtemp(prefix='click_meas_')
st = app.Store(os.path.join(tmp, 'm.json'))
st.room = 'MEAS'
a = app.App(root, st)
for _ in range(10):
    root.update_idletasks(); root.update(); time.sleep(0.05)

found = []


def walk(x):
    for ch in x.winfo_children():
        if isinstance(ch, app.tk.Button) and '一键导出' in str(ch.cget('text')):
            found.append(ch)
        walk(ch)


walk(root)
if not found:
    print('没找到按钮'); sys.exit(1)
btn = found[0]
bx = btn.winfo_rootx() - root.winfo_rootx() + btn.winfo_width() // 2
by = btn.winfo_rooty() - root.winfo_rooty() + btn.winfo_height() // 2
print('按钮客户区中心 = (%d, %d)  尺寸 %dx%d  客户区 %dx%d'
      % (bx, by, btn.winfo_width(), btn.winfo_height(),
         root.winfo_width(), root.winfo_height()))
root.destroy()

# ---------- 2. 启动并摆好窗口 ----------
print()
print('=== 2. 启动 exe 并置顶到固定位置 ===')
before = set(os.listdir(OUTDIR)) if os.path.isdir(OUTDIR) else set()
proc = subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
print('pid =', proc.pid)

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
wins = []


def enum_cb(hwnd, _):
    if user32.IsWindowVisible(hwnd):
        tb = ctypes.create_unicode_buffer(512); user32.GetWindowTextW(hwnd, tb, 512)
        cb = ctypes.create_unicode_buffer(256); user32.GetClassNameW(hwnd, cb, 256)
        wins.append((hwnd, tb.value, cb.value))
    return True


hwnd = None
title = ''
for _ in range(60):
    wins.clear()
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    for h, t, c in wins:
        if c == 'TkTopLevel' or '电费记账本' in t:
            hwnd, title = h, t
            break
    if hwnd or proc.poll() is not None:
        break
    time.sleep(0.5)
print('窗口标题 =', repr(title))
if not hwnd:
    proc.kill(); sys.exit(1)

time.sleep(2.5)
# 置顶 + 挪到 (40, 40)，尺寸按客户区来
W, H = 1780, 1300
user32.SetWindowPos(hwnd, HWND_TOPMOST, 40, 40, W, H, SWP_SHOWWINDOW)
user32.SetForegroundWindow(hwnd)
time.sleep(1.0)
crect = wintypes.RECT()
user32.GetClientRect(hwnd, ctypes.byref(crect))
cpt = wintypes.POINT(0, 0)
user32.ClientToScreen(hwnd, ctypes.byref(cpt))
print('客户区 %dx%d  屏幕原点 (%d, %d)'
      % (crect.right, crect.bottom, cpt.x, cpt.y))
print('前台窗口是否就是它 =', user32.GetForegroundWindow() == hwnd)

# 按新的客户区宽度重算按钮 x（按钮贴右边，左边缘到右边缘的距离是常量）
off_right = 1768 - bx
cx_new = crect.right - off_right
sx, sy = cpt.x + cx_new, cpt.y + by
print('点击目标屏幕坐标 = (%d, %d)' % (sx, sy))

# ---------- 3. 点击 ----------
print()
print('=== 3. 真实点击 ===')
click(sx, sy)
time.sleep(4.0)
fresh = sorted((set(os.listdir(OUTDIR)) if os.path.isdir(OUTDIR) else set()) - before)
print('第一次点击后新增:', fresh if fresh else '（无）')

# 没成就在附近补几下（±12 px），防止差一两个像素
if not fresh:
    for dx in (-12, 12, 0):
        for dy in (-8, 8):
            print('  重试 (%+d, %+d)' % (dx, dy))
            click(sx + dx, sy + dy)
            time.sleep(1.5)
            fresh = sorted((set(os.listdir(OUTDIR)) if os.path.isdir(OUTDIR) else set()) - before)
            if fresh:
                break
        if fresh:
            break

print()
print('=== 4. 结果 ===')
wins.clear()
user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
print('  可见窗口：')
for h, t, c in wins:
    if t.strip() and ('导出' in t or 'Excel' in t or '电费' in t):
        print('      class=%-16s title=%r' % (c, t[:70]))
print('导出目录:', OUTDIR)
print('新增文件:', fresh if fresh else '（无）')

ok = (len(fresh) == 2 and any(n.endswith('.txt') for n in fresh)
      and any(n.endswith('.xlsx') for n in fresh))
if ok:
    for n in fresh:
        p = os.path.join(OUTDIR, n)
        print('  %-50s %8d B' % (n, os.path.getsize(p)))
        if n.endswith('.xlsx'):
            z = zipfile.ZipFile(p)
            print('      xlsx 部件 %d 个，坏成员 = %s' % (len(z.namelist()), z.testzip()))
            shutil.copy2(p, os.path.join(HERE, '_exe导出.xlsx'))
        else:
            shutil.copy2(p, os.path.join(HERE, '_exe导出.txt'))
print()
print('结论:', 'exe 里真点「一键导出」→ 落盘 txt + xlsx：PASS' if ok else 'FAIL')
proc.kill()
time.sleep(0.5)
for n in fresh:
    try:
        os.remove(os.path.join(OUTDIR, n))
    except Exception:
        pass
if os.path.isdir(OUTDIR) and not os.listdir(OUTDIR):
    os.rmdir(OUTDIR)
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(0 if ok else 1)
