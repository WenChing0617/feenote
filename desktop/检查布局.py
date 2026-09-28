# -*- coding: utf-8 -*-
"""界面布局体检：在**真实 DPI 缩放**下，把窗口拉成各种尺寸，检查每一列

检查两件事：
  1. 列宽之和 > 控件宽  → 说明最后一列被挤出可视区（看上去像「列不见了」）
  2. 某列宽度 < 该列表头/最长内容的像素宽 → 文字被截断

为什么需要它：主人的机器是 150% 文字缩放（tk scaling ≈ 2.0，2560x1440）。
写死 `width=104` 的列在 100% 下放得下 `2026-09-18`，到 150% 就被截成
`2026-09-1`。这种 bug 在开发机上（如果缩放不同）完全看不出来。

用法：  python 检查布局.py
退出码：0 = 全绿，1 = 有问题
"""
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import 电费记账本 as app  # noqa: E402
import tkinter.font as tkfont  # noqa: E402

PAD = 8                     # Treeview 单元格左右内边距


def make_store():
    tmp = tempfile.mkdtemp(prefix='layout_check_')
    st = app.Store(os.path.join(tmp, 'g.json'))
    st.room = 'A-302'
    # 故意塞进「最长可能值」：大金额、长备注、期初、零头、空成员
    st.add('2025-09-09', '2号床', 350, '校园卡', '期初首笔（原始表首行，无 * 标记）')
    st.add('2026-09-01', '1号床', 100)
    st.add('2026-09-05', '2号床', 200)
    st.add('2026-09-12', '3号床', 150)
    st.add('2026-09-18', '5号床', 0.5)
    st.add('2026-09-18', '6号床', 1234.56, '支付宝', '一条比较长的备注，用来测试备注列')
    st.add('2026-08-01', '', 88, '银行卡', '没写是谁充的')
    st.delete_many([st.records[0]['id']])      # 回收站里也放一条，检查回收站弹窗的列
    st.save()
    return st


def problems(tv, head_font, cell_font):
    cols = list(tv.cget('columns'))
    fh = tkfont.Font(font=head_font)
    fc = tkfont.Font(font=cell_font)
    bad = []
    total = sum(tv.column(c)['width'] for c in cols)
    if total > tv.winfo_width() + 2:
        bad.append('整体溢出：列宽和 %d > 控件宽 %d（最后一列会被裁掉）'
                   % (total, tv.winfo_width()))
    for c in cols:
        need = fh.measure(str(tv.heading(c)['text'])) + PAD
        for iid in tv.get_children():
            v = tv.item(iid)['values']
            need = max(need, fc.measure(str(v[cols.index(c)])) + PAD)
        if tv.column(c)['width'] < need:
            bad.append('列 %-8s 宽 %d < 需要 %d → 文字被截断'
                       % (c, tv.column(c)['width'], need))
    return bad


def header_problems(w, win_w):
    """顶栏按钮排不下时会被悄悄挤掉一截，这里量一下所需宽度对不对得上"""
    need = w.winfo_reqwidth()
    if need > win_w - 4:
        names = []
        for ch in w.winfo_children():
            try:
                names.append(ch.cget('text'))
            except Exception:
                pass
        return ['顶栏需要 %d px，窗口只有 %d px → 右边按钮会被挤掉（%s）'
                % (need, win_w, ' / '.join(names))]
    return []


def main():
    app.enable_dpi()                      # 和 exe 完全一致的 DPI 条件
    root = app.tk.Tk()
    a = app.App(root, make_store())
    scale = a.ui_scale
    print('屏幕 %dx%d   DPI 缩放 %.2fx   tk scaling %.3f'
          % (root.winfo_screenwidth(), root.winfo_screenheight(),
             scale, float(root.tk.call('tk', 'scaling'))))
    print('窗口默认 %dx%d' % (root.winfo_width(), root.winfo_height()))
    print()

    # 顶栏那一排按钮（含「一键导出」和「更多导出」下拉）所在的容器
    hdr_inner = getattr(a, 'hdr_inner', None)

    def settle(n=8):
        for _ in range(n):
            root.update_idletasks()
            root.update()
            time.sleep(0.06)

    sizes = ['默认']
    w0, h0 = root.winfo_width(), root.winfo_height()
    for f in (1.0, 0.9, 0.8, 1.05, 1.2, 1.4):
        sizes.append('%dx%d' % (int(w0 * f), int(h0 * f)))

    allbad = 0
    for tag in sizes:
        if tag != '默认':
            root.geometry(tag)
            root.update()
        settle()
        if hdr_inner is not None:
            print('      顶栏内容所需宽度 %d px' % hdr_inner.winfo_reqwidth())
        bad = []
        for nm, tv in (('明细表', a.tv_rec), ('汇总表', a.tv_sum)):
            for b in problems(tv, a.FB, a.F):
                bad.append('%s %s' % (nm, b))
        if hdr_inner is not None:
            for b in header_problems(hdr_inner, root.winfo_width()):
                bad.append('顶栏 ' + b)
        allbad += len(bad)
        print('%-14s 窗口 %dx%d  → %s'
              % (tag, root.winfo_width(), root.winfo_height(),
                 '全绿 OK' if not bad else '有问题'))
        for b in bad:
            print('      ! ' + b)

    print()
    print('占比列：格子文字 ' + (str(a.tv_sum.item(a.tv_sum.get_children()[0])['values'][4])
                              if a.tv_sum.get_children() else '（无）')
          + '，Canvas 上的柱子图元 %d 个' % len(a.bar_canvas.find_all()))

    # 弹窗也要查：回收站 / 成员管理的列同样容易在缩放后截断
    for name, opener, title in (('回收站', a.open_trash, '回收站'),
                                ('成员管理', a.open_members, '成员管理')):
        opener()
        settle(4)
        tw = None
        for w in root.winfo_children():
            if isinstance(w, app.tk.Toplevel) and w.title() == title:
                tw = w
        if tw is None:
            print('%-6s 弹窗没能打开' % name)
            allbad += 1
            continue
        tvs = []

        def walk(x):
            for ch in x.winfo_children():
                if isinstance(ch, app.ttk.Treeview):
                    tvs.append(ch)
                walk(ch)
        walk(tw)
        bad = []
        for tv in tvs:
            bad += problems(tv, a.FB, a.F)
        print('%-6s 弹窗 %dx%d  → %s' % (name, tw.winfo_width(), tw.winfo_height(),
                                      '全绿 OK' if not bad else '有问题'))
        for b in bad:
            print('      ! ' + b)
        allbad += len(bad)
        tw.destroy()
        root.update()

    root.destroy()
    print('结论：%s' % ('布局全部通过' if not allbad else '发现 %d 处布局问题' % allbad))
    return 1 if allbad else 0


if __name__ == '__main__':
    sys.exit(main())
