# -*- coding: utf-8 -*-
"""
电费记账本 · 桌面版  v1.5
--------------------------------------------------
记录本次谁充的电费、充了多少，自动汇总每个人分别充了多少。
纯本地运行：数据保存在程序同目录的「电费记账数据.json」，可直接备份/拷走。
依赖：Python 标准库（tkinter / http.server），无第三方包。
和手机互通：顶栏「手机同步」可以在局域网里起一个小服务，手机上的安卓版
            连同一个 WiFi 就能直接对账（要配对码，数据不出局域网）。
"""
import sys
import os
import json
import csv
import io
import time
import uuid
import random
import shutil
import socket
import calendar
import zipfile
import threading
import traceback
import urllib.parse
import http.server
import queue
from datetime import datetime, timedelta

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# ============================================================
# 常量
# ============================================================
APP_NAME = '电费记账本'
APP_VERSION = '1.5'
DATA_FILE = '电费记账数据.json'
BACKUP_DIR = '数据备份'
BACKUP_KEEP = 12
EXPORT_DIR = '导出'          # 「一键导出」默认落盘的地方（跟着程序走）
METHODS = ['校园卡', '微信', '支付宝', '现金', '银行卡', '其他']
DATE_FMT = '%Y-%m-%d'

# 期初那几条（开学第一次、原始表首行）只把钱记进账，不算「充值笔数」
INITIAL_TAG = '期初'
# 撤销栈最多记多少步（每步存一份全量快照）
UNDO_LIMIT = 60
# 回收站最多留多少条（超了就从最旧的开始彻底清掉）
TRASH_KEEP = 200

# 明细表（下面那一大张记录表）的排序方式：(下拉里显示的名字, 排序字段, 是否倒序)
SORT_OPTIONS = [
    ('日期（新→旧）', 'date', True),
    ('日期（旧→新）', 'date', False),
    ('金额（高→低）', 'amount', True),
    ('金额（低→高）', 'amount', False),
    ('充值人', 'member', False),
    ('支付方式', 'method', False),
    ('备注', 'note', False),
]
SORT_MAP = {o[0]: (o[1], o[2]) for o in SORT_OPTIONS}

# 「每个人分别充了多少」那张表的排序方式。
# 注意「序号」是每个人固定的编号（见 Store.member_no），排序只挪行、不改编号。
SUM_SORT_OPTIONS = [
    ('序号（小→大）', 'no', False),
    ('序号（大→小）', 'no', True),
    ('成员名', 'name', False),
    ('笔数（多→少）', 'count', True),
    ('笔数（少→多）', 'count', False),
    ('累计充值（高→低）', 'amount', True),
    ('累计充值（低→高）', 'amount', False),
    ('最近充值（新→旧）', 'last', True),
    ('最近充值（旧→新）', 'last', False),
]
SUM_SORT_MAP = {o[0]: (o[1], o[2]) for o in SUM_SORT_OPTIONS}


def sort_label_of(key, reverse, options=None):
    """反查：当前排序字段对应下拉里的哪一项"""
    opts = options or SORT_OPTIONS
    for name, k, rv in opts:
        if k == key and rv == reverse:
            return name
    return opts[0][0]

# 配色：清透天蓝（与安卓版同一套，去掉了原来的青绿）
C_BG = '#f5f8fc'              # 页面底色：极浅蓝灰
C_CARD = '#ffffff'
C_LINE = '#e3ecf7'
C_TEXT = '#1b2733'
C_MUTED = '#6b7c8c'
C_PRIMARY = '#3a87f0'         # 主色：清透天蓝
C_PRIMARY_D = '#2b6fd1'
C_PRIMARY_L = '#e7f1ff'       # 主色浅底（选中行 / soft 按钮）
C_PRIMARY_HOVER = '#cfe2fc'   # 浅底悬停
C_AMBER = '#c2761b'
C_BLUE = '#2b6fd1'
C_RED = '#e04e6a'
C_HEADER = '#eef5ff'          # 顶栏：极浅蓝，做出通透感
C_HEADER_LINE = '#dbe7f8'     # 顶栏下沿细线
C_HEADER_TITLE = '#1f5bb5'
C_HEADER_SUB = '#7b8ea3'
C_HEADER_INPUT = '#ffffff'
C_ROW_ALT = '#fafcff'
C_INPUT_BG = '#f7fafd'
C_INPUT_LINE = '#c3d3e6'
# 占比条的颜色：按成员顺序循环取，低饱和、通透，跟主色同族
BAR_COLORS = ['#3a87f0', '#8b7cf0', '#f2994a', '#ec6b8a', '#35b6c9', '#7a8ca8']
C_BAR_TRACK = '#e4eefb'        # 占比条的底槽
C_BAR_TRACK_SEL = '#cfe2fc'    # 选中行时底槽加深一点，免得选中看不出来


# ============================================================
# 工具函数
# ============================================================
def money(v):
    """金额格式化：1234.5 -> '1,234.50'"""
    try:
        return '{:,.2f}'.format(float(v))
    except (TypeError, ValueError):
        return '0.00'


def num(v):
    try:
        n = float(v)
        return n if n == n and abs(n) != float('inf') else 0.0
    except (TypeError, ValueError):
        return 0.0


def pad2(n):
    return str(n) if len(str(n)) > 1 else '0' + str(n)


def today_str():
    d = datetime.now()
    return '%04d-%02d-%02d' % (d.year, d.month, d.day)


def now_stamp():
    d = datetime.now()
    return '%04d-%02d-%02d_%02d%02d%02d' % (d.year, d.month, d.day, d.hour, d.minute, d.second)


def fmt_date(s):
    """2026-09-01 -> 09月01日"""
    try:
        d = datetime.strptime(str(s)[:10], DATE_FMT)
        return '%02d月%02d日' % (d.month, d.day)
    except Exception:
        return str(s)


def fmt_date_short(s):
    try:
        d = datetime.strptime(str(s)[:10], DATE_FMT)
        return '%02d-%02d' % (d.month, d.day)
    except Exception:
        return str(s)


def new_id():
    return uuid.uuid4().hex[:12]


def app_dir():
    """程序所在目录（打包成 exe 后是 exe 所在目录）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(name):
    """读取随程序打包的资源（图标等）"""
    base = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, name)


def resolve_data_path():
    """数据文件跟着程序走；目录不可写时退回用户目录"""
    primary = os.path.join(app_dir(), DATA_FILE)
    try:
        d = os.path.dirname(primary)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        probe = os.path.join(d or '.', '.write_probe')
        with open(probe, 'w', encoding='utf-8') as f:
            f.write('ok')
        os.remove(probe)
        return primary
    except Exception:
        fallback_dir = os.path.join(os.path.expanduser('~'), APP_NAME)
        try:
            os.makedirs(fallback_dir, exist_ok=True)
        except Exception:
            fallback_dir = os.path.expanduser('~')
        return os.path.join(fallback_dir, DATA_FILE)


# ============================================================
# 纯文本排版小工具（按**显示宽度**补空格，中文算 2 格）
# ============================================================
def disp_width(s):
    return sum(2 if ord(c) > 0x2E7F else 1 for c in str(s))


def pad(s, width, right=False):
    """把文字补齐到指定显示宽度（记事本里等宽字体下才能对齐）"""
    gap = ' ' * max(0, width - disp_width(s))
    s = str(s)
    return gap + s if right else s + gap


def row_cells(cells, widths, aligns, gap=2):
    """widths/aligns 与 cells 一一对应；aligns 里 'r' 表示右对齐

    列之间留 gap 个空格，否则「占比」和「最近充值」会黏成一坨。
    """
    sep = ' ' * gap
    return sep.join(pad(v, w, a == 'r') for v, w, a in zip(cells, widths, aligns))


# ============================================================
# xlsx 生成（纯标准库：zipfile + 手写 OOXML，不依赖 openpyxl）
# ============================================================
# 样式名 → cellXfs 下标，顺序必须和下面 XLSX_STYLES_XML 里一致
XLSX_STYLES = {
    'text': 2, 'center': 4, 'int': 7, 'money': 3,
    'bold': 5, 'boldint': 5, 'boldmoney': 6,
}
XLSX_HEAD_STYLE = 1          # 第 1 行固定用「表头」样式

XLSX_STYLES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<numFmts count="2">'
    '<numFmt numFmtId="164" formatCode="#,##0.00"/>'
    '<numFmt numFmtId="165" formatCode="0"/>'
    '</numFmts>'
    '<fonts count="2">'
    '<font><sz val="11"/><color theme="1"/><name val="微软雅黑"/></font>'
    '<font><b/><sz val="11"/><color theme="1"/><name val="微软雅黑"/></font>'
    '</fonts>'
    '<fills count="3">'
    '<fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill>'
    '<fill><patternFill patternType="solid">'
    '<fgColor rgb="FFE7F1FF"/><bgColor indexed="64"/></patternFill></fill>'
    '</fills>'
    '<borders count="2">'
    '<border><left/><right/><top/><bottom/><diagonal/></border>'
    '<border><left style="thin"><color rgb="FFD7E4F5"/></left>'
    '<right style="thin"><color rgb="FFD7E4F5"/></right>'
    '<top style="thin"><color rgb="FFD7E4F5"/></top>'
    '<bottom style="thin"><color rgb="FFD7E4F5"/></bottom><diagonal/></border>'
    '</borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    #                                                 numFmt font fill border
    '<cellXfs count="8">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'                        # 0 默认
    '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyNumberFormat="0"'
    ' applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">'
    '<alignment horizontal="center" vertical="center"/></xf>'                                # 1 表头
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0"'
    ' applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>'                # 2 文本
    '<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1"'
    ' applyBorder="1" applyAlignment="1">'
    '<alignment horizontal="right" vertical="center"/></xf>'                                 # 3 金额
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0"'
    ' applyBorder="1" applyAlignment="1">'
    '<alignment horizontal="center" vertical="center"/></xf>'                                # 4 居中
    '<xf numFmtId="0" fontId="1" fillId="0" borderId="1" xfId="0" applyFont="1"'
    ' applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>'                # 5 加粗文本
    '<xf numFmtId="164" fontId="1" fillId="0" borderId="1" xfId="0" applyNumberFormat="1"'
    ' applyFont="1" applyBorder="1" applyAlignment="1">'
    '<alignment horizontal="right" vertical="center"/></xf>'                                 # 6 加粗金额
    '<xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1"'
    ' applyBorder="1" applyAlignment="1">'
    '<alignment horizontal="right" vertical="center"/></xf>'                                 # 7 整数
    '</cellXfs>'
    '<cellStyles count="1"><cellStyle name="常规" xfId="0" builtinId="0"/></cellStyles>'
    '</styleSheet>'
)


def xlsx_escape(s):
    """XML 转义 + 丢掉控制字符

    坑：备注里万一混进 \\x0b、\\x1f 这类控制字符，转义做对了 Excel 也会说
    「文件已损坏」——必须先把它们滤掉。
    """
    out = []
    for ch in str(s):
        if ord(ch) < 0x20 and ch not in '\t\n':
            continue
        out.append(ch)
    return ''.join(out).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def xlsx_col(i):
    """列号 1 → A，27 → AA"""
    s = ''
    while i > 0:
        i, r = divmod(i - 1, 26)
        s = chr(ord('A') + r) + s
    return s


def xlsx_num(v):
    """数字写进 <v> 里的字面量（不要科学计数法，也别拖一串 0）"""
    if isinstance(v, int) or (isinstance(v, float) and v == int(v)):
        return str(int(v))
    return ('%.10f' % float(v)).rstrip('0').rstrip('.') or '0'


def xlsx_cell(cell):
    """单元格 → (值, 样式下标)

    接受：None / str / int / float，或 (值, 样式名)；
    不写样式时按类型猜：int → 整数、float → 金额、str → 文本。
    """
    style = 'text'
    if isinstance(cell, tuple) and len(cell) == 2:
        cell, style = cell
    if cell is None:
        return None, XLSX_STYLES['text']
    if isinstance(cell, str):
        if not cell.strip():
            return None, XLSX_STYLES['text']
        return cell, XLSX_STYLES.get(style, XLSX_STYLES['text'])
    if isinstance(cell, bool):
        return ('是' if cell else '否'), XLSX_STYLES.get(style, XLSX_STYLES['text'])
    if isinstance(cell, (int, float)):
        if style == 'text':
            style = 'int' if isinstance(cell, int) else 'money'
        return cell, XLSX_STYLES.get(style, XLSX_STYLES['text'])
    return str(cell), XLSX_STYLES.get(style, XLSX_STYLES['text'])


def build_xlsx(sheets):
    """把若干张表打成 .xlsx 的字节串

    sheets = [(工作表名, 行列表)]
      行 = 单元格列表；单元格见 xlsx_cell；第 1 行固定按表头渲染。
    冻结首行 + 表头自动筛选 + 按内容估列宽，双击就能直接看。
    """
    titles, grids = [], []
    seen = {}
    for title, rows in sheets:
        name = ''.join(c for c in str(title) if c not in '[]:*?/\\')[:31] or 'Sheet'
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:                      # 同名工作表 Excel 会拒绝打开
            name = '%s%d' % (name[:28], seen[name])
        titles.append(name)
        grids.append([list(r) for r in rows])

    sheet_parts = []
    for rows in grids:
        ncol = max([len(r) for r in rows] + [1])
        widths = []
        for c in range(ncol):
            w = 8
            for r in rows:
                if c < len(r):
                    v = xlsx_cell(r[c])[0]
                    if v is not None:
                        w = max(w, disp_width(v) + 3)
            widths.append(min(w, 44))
        cols_xml = '<cols>' + ''.join(
            '<col min="%d" max="%d" width="%.1f" customWidth="1"/>' % (i, i, w)
            for i, w in enumerate(widths, 1)) + '</cols>'

        row_xml = []
        for ri, row in enumerate(rows, 1):
            cells = []
            for ci, cell in enumerate(row, 1):
                v, style = xlsx_cell(cell)
                if v is None:
                    continue
                ref = xlsx_col(ci) + str(ri)
                s = XLSX_HEAD_STYLE if ri == 1 else style
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    cells.append('<c r="%s" s="%d"><v>%s</v></c>' % (ref, s, xlsx_num(v)))
                else:
                    cells.append('<c r="%s" t="inlineStr" s="%d">'
                                 '<is><t xml:space="preserve">%s</t></is></c>'
                                 % (ref, s, xlsx_escape(v)))
            if cells:
                row_xml.append('<row r="%d">%s</row>' % (ri, ''.join(cells)))

        last = xlsx_col(ncol) + str(max(len(rows), 1))
        sheet_parts.append(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<dimension ref="A1:%s"/>'
            '<sheetViews><sheetView workbookViewId="0">'
            '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
            '</sheetView></sheetViews>'
            '<sheetFormatPr defaultRowHeight="16"/>'
            '%s<sheetData>%s</sheetData>'
            '<autoFilter ref="A1:%s"/>'
            '</worksheet>' % (last, cols_xml, ''.join(row_xml), last))

    n = len(sheet_parts)
    ct = ['<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
          '<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
    ct += ['<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % i
           for i in range(1, n + 1)]

    parts = {
        '[Content_Types].xml': (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            + ''.join(ct) + '</Types>'),
        '_rels/.rels': (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'),
        'xl/workbook.xml': (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
            ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets>' + ''.join(
                '<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (xlsx_escape(t), i, i)
                for i, t in enumerate(titles, 1)) + '</sheets></workbook>'),
        'xl/_rels/workbook.xml.rels': (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + ''.join('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>'
                      % (i, i) for i in range(1, n + 1))
            + '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' % (n + 1)
            + '</Relationships>'),
        'xl/styles.xml': XLSX_STYLES_XML,
    }
    for i, part in enumerate(sheet_parts, 1):
        parts['xl/worksheets/sheet%d.xml' % i] = part

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        # [Content_Types].xml 放最前面，有些老解析器按顺序找它
        z.writestr('[Content_Types].xml', parts.pop('[Content_Types].xml'))
        for name, data in parts.items():
            z.writestr(name, data)
    return buf.getvalue()


# ============================================================
# 数据层（不依赖界面，可单独测试）
# ============================================================
class Store(object):
    def __init__(self, path):
        self.path = path
        self.room = ''
        self.members = []
        # 每个人一个**固定编号**（相当于身份证号）：{成员名: 编号}
        # 新增成员顺延，删除成员也不会把号回收给后来的人，改名跟着一起改。
        self.member_ids = {}
        self.records = []
        # 回收站：删掉的记录先挪到这里，随时能恢复（防误删）
        self.deleted = []
        # 撤销 / 重做：每一步存一份全量快照（只活在内存里，关掉程序就清了）
        self._undo = []
        self._redo = []
        self.load_error = None
        # 磁盘上那份文件里到底有没有东西（用来防止「空账本把好数据覆盖掉」）
        self.file_had_data = False
        # 数据文件读坏时留的隔离副本路径
        self.quarantine_path = None
        self.load()

    # ---------- 读写 ----------
    def load(self):
        self.load_error = None
        self.file_had_data = False
        self.quarantine_path = None
        if not os.path.exists(self.path):
            return
        self.file_had_data = self._read_has_data(self.path)
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.load_error = '数据文件读取失败，已从空账本开始：%s' % e
            self.quarantine_bad_file()
            self._append_quarantine_hint()
            return
        try:
            self.apply(data, replace=True)
        except Exception as e:
            self.load_error = '数据文件内容异常：%s' % e
            self.quarantine_bad_file()
            self._append_quarantine_hint()

    def _append_quarantine_hint(self):
        if self.quarantine_path:
            self.load_error += ('\n\n原文件已原样留了一份：\n%s\n'
                                '（为避免覆盖它，这次空账本不会被写回磁盘）'
                                % self.quarantine_path)
        elif self.file_had_data:
            self.load_error += '\n\n为避免把原记录覆盖成空白，这次不会自动保存。'

    @staticmethod
    def _read_has_data(path):
        """看某个数据文件里是否真的有内容（记录 / 成员 / 回收站 / 房间名）"""
        try:
            if not os.path.exists(path):
                return False
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return False
            return bool(data.get('records') or data.get('members')
                        or data.get('deleted')
                        or str(data.get('room') or '').strip())
        except Exception:
            # 解析不了（多半是损坏了）——只要文件不是空的，就保守当成「有内容」
            try:
                return os.path.getsize(path) > 0
            except Exception:
                return False

    def is_empty(self):
        return (not self.records and not self.members and not self.deleted
                and not str(self.room or '').strip())

    def quarantine_bad_file(self):
        """数据文件读不出来时，先原样留一份到备份目录，之后才可能被覆盖"""
        try:
            if not os.path.exists(self.path):
                return None
            bdir = os.path.join(os.path.dirname(self.path), BACKUP_DIR)
            os.makedirs(bdir, exist_ok=True)
            target = os.path.join(bdir, '损坏_%s.json' % now_stamp())
            shutil.copy2(self.path, target)
            self.quarantine_path = target
            return target
        except Exception:
            return None

    def payload(self):
        return {
            'app': APP_NAME,
            'version': APP_VERSION,
            'room': self.room,
            'members': list(self.members),
            'memberIds': {str(k): int(v) for k, v in self.member_ids.items()},
            'records': [dict(r) for r in self.records],
            'deleted': [dict(r) for r in self.deleted],
            'savedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    def save(self, force=False):
        """原子写入 + 每日自动备份

        安全阀：当前账本是空的、而磁盘上那份文件里有内容时，拒绝写入。
        这样可以避免「数据文件读坏 / 被挪走 → 程序以空账本启动 → 关窗时把
        原本好好的记录覆盖成空」这种最糟糕的情况。
        """
        try:
            if not force and self.is_empty() and self._read_has_data(self.path):
                return False, ('磁盘上的数据文件里还有内容，但当前账本是空的，'
                               '为避免把你的记录清空，已取消这次保存。\n'
                               '如果确实要清空，请先自己备份好那份 json 再手动删除。')
            d = os.path.dirname(self.path)
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.payload(), f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            self.file_had_data = not self.is_empty()
            self._auto_backup()
            return True, None
        except Exception as e:
            return False, str(e)

    def _auto_backup(self):
        try:
            if not os.path.exists(self.path):
                return
            bdir = os.path.join(os.path.dirname(self.path), BACKUP_DIR)
            os.makedirs(bdir, exist_ok=True)
            target = os.path.join(bdir, '%s_%s.json' % (os.path.splitext(DATA_FILE)[0], datetime.now().strftime('%Y%m%d')))
            # 今天的备份已存在时：若那份是空的而现有数据是有内容的，就用有内容的覆盖掉，
            # 免得哪天第一次保存恰好是空账本，把当天的备份位占掉一整天
            if os.path.exists(target) and (self._read_has_data(target) or not self._read_has_data(self.path)):
                return
            shutil.copy2(self.path, target)
            files = sorted(f for f in os.listdir(bdir) if f.endswith('.json'))
            for old in files[:-BACKUP_KEEP]:
                try:
                    os.remove(os.path.join(bdir, old))
                except Exception:
                    pass
        except Exception:
            pass

    # ---------- 数据规范化 ----------
    @staticmethod
    def normalize_record(r):
        r = r if isinstance(r, dict) else {}
        date = str(r.get('date') or '').strip()[:10]
        if len(date) != 10:
            date = today_str()
        note = str(r.get('note') or '')
        # 「期初」这条：钱照样算进账本，但不占「充值笔数」。
        # 老数据里没有 initial 字段时，靠备注里的「期初」认出来。
        if 'initial' in r:
            initial = bool(r.get('initial'))
        else:
            initial = INITIAL_TAG in note
        out = {
            'id': str(r.get('id') or new_id()),
            'date': date,
            'member': str(r.get('member') or '').strip(),
            'amount': max(0.0, num(r.get('amount'))),
            'method': str(r.get('method') or '微信').strip() or '微信',
            'note': note,
            'createdAt': int(num(r.get('createdAt')) or int(time.time() * 1000)),
            'initial': initial,
        }
        # 回收站里的记录多带一个删除时间
        if r.get('deletedAt'):
            out['deletedAt'] = int(num(r.get('deletedAt')))
        return out

    def apply(self, data, replace=True):
        """把导入的数据并入账本。replace=False 时按 id 去重合并"""
        if not isinstance(data, dict):
            raise ValueError('不是有效的账本数据')
        recs = data.get('records')
        if recs is None:
            recs = []
        if not isinstance(recs, list):
            raise ValueError('records 字段格式不对')
        recs = [self.normalize_record(r) for r in recs]
        dels = data.get('deleted')
        dels = [self.normalize_record(r) for r in dels] if isinstance(dels, list) else []
        mems = [str(m).strip() for m in (data.get('members') or []) if str(m).strip()]
        # 每个人的固定编号（老数据文件里没有这一项，加载后会自动补号）
        ids = data.get('memberIds')
        ids = {str(k).strip(): int(v) for k, v in ids.items()
               if str(k).strip() and str(v).strip().lstrip('-').isdigit()} \
            if isinstance(ids, dict) else {}

        if replace:
            self.room = str(data.get('room') or '')
            self.members = list(dict.fromkeys(mems))
            self.member_ids = dict(ids)
            self.records = recs
            self.deleted = dels
        else:
            if not self.room:
                self.room = str(data.get('room') or '')
            exist = {r['id'] for r in self.records}
            for r in recs:
                if r['id'] not in exist:
                    exist.add(r['id'])
                    self.records.append(r)
            dexit = {r['id'] for r in self.deleted}
            for r in dels:
                if r['id'] in dexit:
                    continue
                dexit.add(r['id'])
                self.deleted.append(r)
                # 对端已经把这条删了 → 本地还留着的话跟着进回收站。
                # 「删除」必须能传播，否则手机删完、电脑上又冒出来，两边永远对不上。
                # 注意是移进回收站（不是销毁），误删还能恢复。
                if r['id'] in exist:
                    self.records = [x for x in self.records if x['id'] != r['id']]
            for m in mems:
                if m not in self.members:
                    self.members.append(m)
            used = set(self.member_ids.values())
            for k, v in sorted(ids.items(), key=lambda kv: kv[1]):
                if k in self.member_ids:
                    continue
                if v in used:                     # 号码撞了就往后顺延一个
                    v = (max(used) if used else 0) + 1
                self.member_ids[k] = v
                used.add(v)
        # 记录里出现的人自动登记为成员
        for r in self.records:
            if r['member'] and r['member'] not in self.members:
                self.members.append(r['member'])
        # 没有编号的人（老数据 / 记录里冒出来的新面孔）按顺序补号
        self._ensure_member_ids()

    # ---------- 撤销 / 重做 ----------
    def _dump_state(self):
        return {
            'room': self.room,
            'members': list(self.members),
            'records': [dict(r) for r in self.records],
            'deleted': [dict(r) for r in self.deleted],
        }

    def _restore_state(self, s):
        self.room = s.get('room', '')
        self.members = list(s.get('members', []))
        self.records = [dict(r) for r in s.get('records', [])]
        self.deleted = [dict(r) for r in s.get('deleted', [])]

    def snapshot(self, label='操作'):
        """做任何改动之前先调一次：把当前状态存进撤销栈

        撤销 = 把这份快照放回去。动作做得越密，栈越深，
        但每一步都是一份全量快照，所以「撤销」永远准确，不会漏字段。
        """
        self._undo.append({'label': label, 'state': self._dump_state()})
        if len(self._undo) > UNDO_LIMIT:
            self._undo.pop(0)
        self._redo = []          # 有了新动作，之前重做的分支就作废了
        return True

    def undo_label(self):
        return self._undo[-1]['label'] if self._undo else ''

    def redo_label(self):
        return self._redo[-1]['label'] if self._redo else ''

    def can_undo(self):
        return bool(self._undo)

    def can_redo(self):
        return bool(self._redo)

    def undo(self):
        """撤销上一步，返回被撤销的动作名（没得撤就返回 None）"""
        if not self._undo:
            return None
        entry = self._undo.pop()
        self._redo.append({'label': entry['label'], 'state': self._dump_state()})
        self._restore_state(entry['state'])
        return entry['label']

    def redo(self):
        """重做刚被撤销的那一步"""
        if not self._redo:
            return None
        entry = self._redo.pop()
        self._undo.append({'label': entry['label'], 'state': self._dump_state()})
        self._restore_state(entry['state'])
        return entry['label']

    def clear_history(self):
        self._undo = []
        self._redo = []

    def discard_snapshot(self):
        """操作最后失败了：把刚压进去的那份快照丢掉，别留在撤销栈里"""
        if self._undo:
            self._undo.pop()

    # ---------- 记录操作 ----------
    def add(self, date, member, amount, method='微信', note=''):
        r = self.normalize_record({
            'date': date, 'member': member, 'amount': amount,
            'method': method, 'note': note,
        })
        self.records.append(r)
        if r['member'] and r['member'] not in self.members:
            self.members.append(r['member'])
        return r

    def get(self, rid):
        for r in self.records:
            if r['id'] == rid:
                return r
        return None

    def update(self, rid, **kw):
        r = self.get(rid)
        if not r:
            return None
        for k in ('date', 'member', 'amount', 'method', 'note', 'initial'):
            if k in kw:
                r[k] = kw[k]
        r = self.normalize_record(r)
        for i, x in enumerate(self.records):
            if x['id'] == rid:
                self.records[i] = r
                break
        if r['member'] and r['member'] not in self.members:
            self.members.append(r['member'])
        return r

    def delete(self, rid):
        """删除 = 先挪进回收站（软删除），随时能恢复，不怕手滑"""
        return self.delete_many([rid])

    def delete_many(self, ids):
        ids = set(ids)
        moved, keep = [], []
        for r in self.records:
            (moved if r['id'] in ids else keep).append(r)
        if not moved:
            return 0
        now_ms = int(time.time() * 1000)
        for r in moved:
            r = dict(r)
            r['deletedAt'] = now_ms
            self.deleted.append(r)
        self.records = keep
        self._trim_trash()
        return len(moved)

    def _trim_trash(self):
        if len(self.deleted) <= TRASH_KEEP:
            return
        self.deleted.sort(key=lambda r: r.get('deletedAt') or 0)
        self.deleted = self.deleted[-TRASH_KEEP:]

    # ---------- 回收站 ----------
    def trash(self):
        """回收站里的记录（最近删的排前面）"""
        return sorted(self.deleted, key=lambda r: r.get('deletedAt') or 0, reverse=True)

    def restore(self, ids):
        """从回收站恢复，返回恢复条数"""
        ids = set(ids)
        back, stay = [], []
        for r in self.deleted:
            (back if r['id'] in ids else stay).append(r)
        if not back:
            return 0
        for r in back:
            r = {k: v for k, v in r.items() if k != 'deletedAt'}
            self.records.append(self.normalize_record(r))
            if r['member'] and r['member'] not in self.members:
                self.members.append(r['member'])
        self.deleted = stay
        return len(back)

    def restore_all(self):
        return self.restore([r['id'] for r in self.deleted])

    def purge(self, ids):
        """彻底删除（不可恢复），返回删掉条数"""
        ids = set(ids)
        before = len(self.deleted)
        self.deleted = [r for r in self.deleted if r['id'] not in ids]
        return before - len(self.deleted)

    def purge_all(self):
        n = len(self.deleted)
        self.deleted = []
        return n

    def rename_member(self, old, new):
        """改名并同步历史记录（含回收站），返回影响的记录数"""
        new = str(new).strip()
        if not new or new == old:
            return 0
        if new in self.members:
            raise ValueError('已经有一个叫「%s」的成员了' % new)
        if old in self.members:
            self.members[self.members.index(old)] = new
        # 改名的同时把固定编号搬过去，号不变
        if old in self.member_ids:
            self.member_ids[new] = self.member_ids.pop(old)
        n = 0
        for r in self.records:
            if r['member'] == old:
                r['member'] = new
                n += 1
        for r in self.deleted:
            if r['member'] == old:
                r['member'] = new
        return n

    def remove_member(self, name, with_records=True):
        if name in self.members:
            self.members.remove(name)
        n = 0
        if with_records:
            n = self.delete_many([r['id'] for r in self.records if r['member'] == name])
        return n

    def count_of(self, name, include_initial=False):
        """某人的充值笔数（默认不含期初那条）"""
        return sum(1 for r in self.records
                   if r['member'] == name and (include_initial or not r.get('initial')))

    # ---------- 每个人的固定编号 ----------
    def _ensure_member_ids(self):
        """把还没有编号的人按「成员列表顺序 → 记录里出现的先后」补上号

        只在加载 / 导入后调用，保证同一份数据每次算出来的编号都一样。
        已经发出去的号一个都不会变，删掉的人也不会把号让给别人。
        """
        if not isinstance(getattr(self, 'member_ids', None), dict):
            self.member_ids = {}
        self.member_ids = {str(k): int(v) for k, v in self.member_ids.items()
                           if str(k).strip() and str(v).strip().lstrip('-').isdigit()}
        used = set(self.member_ids.values())
        nxt = max(used) if used else 0
        order = []
        for m in list(self.members) + [r['member'] for r in self.records] \
                + [r['member'] for r in self.deleted]:
            m = (m or '').strip()
            if m and m not in order:
                order.append(m)
        for m in order:
            if m in self.member_ids:
                continue
            nxt += 1
            self.member_ids[m] = nxt
        return self.member_ids

    def member_no(self, name):
        """取某人的固定编号；新面孔就地发一个新号（最大的号 +1）"""
        name = (name or '').strip()
        if not name:
            return None
        if name in self.member_ids:
            return self.member_ids[name]
        self._ensure_member_ids()
        if name in self.member_ids:
            return self.member_ids[name]
        nxt = (max(self.member_ids.values()) if self.member_ids else 0) + 1
        self.member_ids[name] = nxt
        return nxt

    @staticmethod
    def _sum_sort_key(key):
        """「每个人分别充了多少」那张表的排序键

        排序只改变行的先后，人身上的编号不动 —— 所以「按笔数排」之后
        序号那一列还是乱的，这正是固定 id 该有的样子。
        """
        if key == 'name':
            return lambda x: x['name']
        if key == 'count':
            return lambda x: (x['count'], x['amount'])
        if key == 'amount':
            return lambda x: (x['amount'], x['name'])
        if key == 'pct':
            return lambda x: (x['pct'], x['name'])
        if key == 'last':
            return lambda x: (x['last'] or '', x['name'])
        return lambda x: (x['no'] if x['no'] else 9999, x['name'])

    # ---------- 统计 ----------
    def stats(self, sort_key='no', reverse=False):
        """汇总：钱全都算（含期初），但「笔数」只数真正的充值（不含期初）

        sort_key / reverse 只影响 rows 的先后顺序，不影响任何数字。
        """
        self._ensure_member_ids()
        total = 0.0
        initial_total = 0.0
        agg = {}
        for r in self.records:
            total += r['amount']
            k = r['member'] or '(未填写)'
            a = agg.setdefault(k, {'amount': 0.0, 'count': 0, 'initial': 0,
                                   'initial_amount': 0.0, 'last': ''})
            a['amount'] += r['amount']
            if r.get('initial'):
                a['initial'] += 1
                a['initial_amount'] += r['amount']
                initial_total += r['amount']
            else:
                a['count'] += 1
                if r['date'] > a['last']:
                    a['last'] = r['date']
        names = []
        for m in list(self.members) + list(agg.keys()):
            if m and m not in names:
                names.append(m)
        rows = []
        for n in names:
            a = agg.get(n, {'amount': 0.0, 'count': 0, 'initial': 0,
                            'initial_amount': 0.0, 'last': ''})
            rows.append({
                'no': None if n == '(未填写)' else self.member_no(n),
                'name': n,
                'amount': a['amount'],
                'count': a['count'],
                'initial': a['initial'],
                'initial_amount': a['initial_amount'],
                'pct': (a['amount'] / total * 100.0) if total > 0 else 0.0,
                'last': a['last'],
            })
        rows.sort(key=self._sum_sort_key(sort_key), reverse=reverse)
        all_rows = [r for r in rows if r['count'] or r['initial']]
        initial_count = sum(r['initial'] for r in rows)
        return {
            'total': total,
            'count': sum(r['count'] for r in rows),
            'initial_count': initial_count,
            'initial_total': initial_total,
            'people': len(all_rows),
            'rows': rows,
            'latest': self._latest(),
            'trash': len(self.deleted),
        }

    def years(self):
        """数据里出现过的年份，供下拉筛选"""
        return sorted({r['date'][:4] for r in self.records if len(r['date']) >= 4})

    def _latest(self):
        """最近一次「真正的充值」（期初那条不算，除非账本里只有期初）"""
        def better(a, b):
            return a is None or b['date'] > a['date'] or (
                b['date'] == a['date'] and b['createdAt'] > a['createdAt'])
        best = None
        for r in self.records:
            if r.get('initial'):
                continue
            if better(best, r):
                best = r
        if best is not None:
            return best
        for r in self.records:            # 只有期初记录时的兜底
            if better(best, r):
                best = r
        return best

    def query(self, keyword='', member='', year='', month='', sort_key='date',
              reverse=True, show_initial=True):
        """筛选 + 排序，返回记录列表（year / month 为空表示不限）"""
        kw = (keyword or '').strip().lower()
        y = (year or '').strip()
        m = (month or '').strip()
        out = []
        for r in self.records:
            if not show_initial and r.get('initial'):
                continue
            if kw and kw not in (r['member'] + ' ' + r['note'] + ' ' + r['method']).lower():
                continue
            if member:
                if member == '(未填写)':
                    if r['member']:
                        continue
                elif r['member'] != member:
                    continue
            if y and r['date'][:4] != y:
                continue
            if m and r['date'][5:7] != '%02d' % int(m):
                continue
            out.append(r)
        if sort_key == 'amount':
            out.sort(key=lambda r: (r['amount'], r['date']), reverse=reverse)
        elif sort_key == 'member':
            # 按人分组，组内还是按时间走（期初那条排最前）
            out.sort(key=lambda r: (r['member'],
                                    0 if r.get('initial') else 1,
                                    r['date'], r['createdAt']),
                     reverse=reverse)
        elif sort_key == 'method':
            out.sort(key=lambda r: (r['method'], r['date']), reverse=reverse)
        elif sort_key == 'note':
            out.sort(key=lambda r: (r['note'], r['date']), reverse=reverse)
        else:
            out.sort(key=lambda r: (r['date'], r['createdAt']), reverse=reverse)
        return out

    # ---------- 导出 ----------
    def csv_text(self):
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator='\r\n')
        w.writerow(['电费充值明细'])
        w.writerow(['宿舍/房间', self.room or ''])
        w.writerow(['导出时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        w.writerow([])
        w.writerow(['日期', '充值人', '金额(元)', '支付方式', '备注'])
        for r in sorted(self.records, key=lambda x: (x['date'], x['createdAt'])):
            w.writerow([r['date'], r['member'],
                        '%.2f' % r['amount'], r['method'], r['note']])
        s = self.stats()
        w.writerow([])
        w.writerow(['合计', '', '%.2f' % s['total'], '', '%d 笔' % s['count']])
        w.writerow([])
        w.writerow(['成员汇总'])
        w.writerow(['序号', '成员', '笔数', '累计充值(元)', '占比', '最近充值'])
        for row in s['rows']:
            if not (row['count'] or row['initial']):
                continue
            w.writerow([row['no'] if row['no'] else '—', row['name'], row['count'],
                        '%.2f' % row['amount'],
                        '%.1f%%' % row['pct'], row['last'] or '—'])
        return buf.getvalue()

    def report_text(self):
        # 结算单是发给室友看的：只说每个人实实在在充了多少、算了几笔，
        # 期初那几条只留在明细账单里，不在这里露面。
        s = self.stats()
        lines = ['【电费充值汇总】' + (self.room or '未命名')]
        lines.append('总充值 ¥%s（%d 笔，%d 人）'
                     % (money(s['total']), s['count'], s['people']))
        lines.append('—————————————')
        shown = [r for r in s['rows'] if (r['count'] or r['initial'])]
        if not shown:
            lines.append('（暂无记录）')
        for row in shown:
            lines.append('%s：已充 ¥%s，%d 笔'
                         % (row['name'], money(row['amount']), row['count']))
        lt = s['latest']
        if lt:
            lines.append('—————————————')
            lines.append('最近一次：%s　%s　¥%s'
                         % (lt['date'], lt['member'] or '—', money(lt['amount'])))
        lines.append('生成时间：' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        return '\n'.join(lines)

    # ---------- 导出：纯文本 / Excel ----------
    def _sorted_records(self):
        return sorted(self.records, key=lambda x: (x['date'], x['createdAt']))

    def _shown_rows(self, s=None):
        """汇总表里要展示的人（有真充值或期初的都算）"""
        s = s or self.stats()
        return [r for r in s['rows'] if (r['count'] or r['initial'])]

    def txt_text(self):
        """导出成纯文本账本（总览 + 成员汇总 + 充值明细），记事本直接能看

        期初只出现在**明细**里（备注前加「期初」），总览和汇总都不提，
        但钱照算 —— 跟界面上的口径完全一致。
        """
        s = self.stats()
        rule = '=' * 48
        thin = '-' * 48
        out = [rule,
               '  电费充值账本',
               '  宿舍/房间：' + (self.room or '未命名'),
               '  导出时间：' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
               rule, '']

        out.append('【总览】')
        out.append('  总充值：¥%s' % money(s['total']))
        out.append('  充值笔数：%d 笔' % s['count'])
        out.append('  参与人数：%d 人' % s['people'])
        lt = s['latest']
        if lt:
            out.append('  最近一次：%s　%s　¥%s'
                       % (lt['date'], lt['member'] or '—', money(lt['amount'])))
        out.append('')

        shown = self._shown_rows(s)
        out.append('【成员汇总】')
        if not shown:
            out.append('  （暂无记录）')
        else:
            w = [6, 10, 6, 14, 7, 12]
            a = ['l', 'l', 'r', 'r', 'r', 'l']
            out.append('  ' + row_cells(['序号', '成员', '笔数', '累计充值', '占比', '最近充值'], w, a))
            out.append('  ' + thin)
            for row in shown:
                out.append('  ' + row_cells(
                    [row['no'] or '—', row['name'], row['count'],
                     '¥' + money(row['amount']), '%.1f%%' % row['pct'],
                     row['last'] or '—'], w, a))
        out.append('')

        recs = self._sorted_records()
        out.append('【充值明细】')
        if not recs:
            out.append('  （暂无记录）')
        else:
            w = [12, 10, 12, 10]
            a = ['l', 'l', 'r', 'l']
            out.append('  ' + row_cells(['日期', '充值人', '金额(元)', '支付方式'], w, a)
                       + '  备注')
            out.append('  ' + thin)
            for r in recs:
                note = r['note'] or ''
                if r.get('initial'):
                    note = (INITIAL_TAG + '　' + note).strip()
                out.append('  ' + row_cells(
                    [r['date'], r['member'] or '—', money(r['amount']), r['method']],
                    w, a) + '  ' + note)
            out.append('  ' + thin)
            out.append('  合计：¥%s（%d 笔）' % (money(s['total']), s['count']))
        out.append('')
        out.append(rule)
        out.append('  由「电费记账本 v%s」导出' % APP_VERSION)
        return '\r\n'.join(out)

    def xlsx_bytes(self):
        """导出成 Excel（.xlsx）的字节串：充值明细 / 成员汇总 / 总览 三张表

        金额列是真数字（带千分位两位小数格式），打开就能直接求和，
        不是「看起来像数字的文本」。
        """
        s = self.stats()

        detail = [['日期', '充值人', '金额(元)', '支付方式', '备注']]
        for r in self._sorted_records():
            note = r['note'] or ''
            if r.get('initial'):
                note = (INITIAL_TAG + '　' + note).strip()
            detail.append([r['date'], r['member'] or '—', float(r['amount']),
                           r['method'], note])
        detail.append([('合计', 'bold'), ('', 'bold'),
                       (float(s['total']), 'boldmoney'), ('', 'bold'),
                       ('%d 笔' % s['count'], 'bold')])

        summary = [['序号', '成员', '笔数', '累计充值(元)', '占比', '最近充值']]
        for row in self._shown_rows(s):
            summary.append([('—' if not row['no'] else int(row['no']), 'center'),
                            row['name'], int(row['count']),
                            float(row['amount']), '%.1f%%' % row['pct'],
                            row['last'] or '—'])
        summary.append([('合计', 'bold'), ('', 'bold'),
                        (int(s['count']), 'boldint'),
                        (float(s['total']), 'boldmoney'), ('', 'bold'), ('', 'bold')])

        info = [['项目', '内容'],
                ['宿舍/房间', self.room or '未命名'],
                ['总充值(元)', float(s['total'])],
                ['充值笔数', int(s['count'])],
                ['参与人数', int(s['people'])],
                ['导出时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]]
        lt = s['latest']
        if lt:
            info.append(['最近一次充值', '%s　%s　¥%s'
                         % (lt['date'], lt['member'] or '—', money(lt['amount']))])
        return build_xlsx([('充值明细', detail),
                           ('成员汇总', summary),
                           ('总览', info)])


# ============================================================
# 局域网同步：手机连同一个 WiFi，直接跟电脑上的账本对账
# ============================================================
LAN_PORT = 8686          # 默认端口，被占了会自动往后找


def lan_ip():
    """猜本机在局域网里的地址

    招数：往一个外网地址建一个 UDP socket，内核选完出口网卡后把本机地址
    读回来 —— 全程不发包，所以断网也不会卡住。失败再退回主机名解析。
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 53))
        ip = s.getsockname()[0]
        if ip and not ip.startswith('127.'):
            return ip
    except Exception:
        pass
    finally:
        s.close()
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith('127.'):
            return ip
    except Exception:
        pass
    return '127.0.0.1'


class SyncServer(object):
    """把账本暴露成一个极小的 HTTP 服务，只给同一个 WiFi 里的手机用

    三个接口（配对码都对不上就直接 403）：
        GET  /ping?pair=xxxx    探活，顺便报一下账本有多少条
        GET  /export?pair=xxxx  按桌面版 JSON 格式把整本账本吐出去
        POST /import?pair=xxxx  收下手机传来的账本，按 id 去重合并进来

    配对码是开服务时随机生成的 4 位数。同一 WiFi 下别人即使扫到端口，
    没有这个码也读不到、更写不进。
    """

    def __init__(self, store):
        self.store = store
        self.httpd = None
        self.thread = None
        self.pair = ''
        self.port = LAN_PORT
        self.last = ''            # 最近一次同步的结果，显示在界面上
        self.lock = threading.Lock()
        self.ui_root = None       # 由 App 填上：Tk 主窗口，用来把动作投回主线程
        self.on_applied = None    # 由 App 填上：同步完刷新界面
        self.on_start = None      # 由 App 填上：服务起来了就开始取活儿的定时器
        self._jobs = queue.Queue()   # 后台线程排的活儿，等主线程来取

    # ---------- 生命周期 ----------
    def running(self):
        return self.httpd is not None

    def new_pair(self):
        # 自动回归测试的口子：`FEENOTE_SYNC_PAIR=4321` 时配对码固定，
        # 否则每次开机随机 —— 平时用不到这个环境变量。
        forced = (os.environ.get('FEENOTE_SYNC_PAIR') or '').strip()
        if len(forced) == 4 and forced.isdigit():
            self.pair = forced
        else:
            self.pair = '%04d' % random.randint(0, 9999)
        return self.pair

    def start(self, port=None):
        """返回 (是否成功, 说明文字)"""
        if self.httpd is not None:
            return True, '服务已经在跑了'
        if not self.pair:
            self.new_pair()
        want = int(port or self.port)
        handler = self._make_handler()
        httpd = None
        last_err = None
        # 端口被占用就往后试几个，省得让人自己去改配置。
        # 传 0 表示「随便给个空闲端口」，此时要从 socket 上把真实端口读回来。
        for p in range(want, want + 10):
            try:
                httpd = http.server.ThreadingHTTPServer(('0.0.0.0', p), handler)
                self.port = httpd.server_address[1]
                break
            except OSError as e:
                last_err = e
        if httpd is None:
            return False, '端口 %d~%d 都被占用了：%s' % (want, want + 9, last_err)
        self.httpd = httpd
        self.thread = threading.Thread(target=httpd.serve_forever,
                                       kwargs={'poll_interval': 0.3},
                                       name='fee-lan-sync', daemon=True)
        self.thread.start()
        if self.on_start:
            self.on_start()          # 让界面把「取活儿」的定时器挂上
        return True, '已启动，端口 %d' % self.port

    def stop(self):
        if self.httpd is None:
            return
        httpd = self.httpd
        self.httpd = None
        try:
            httpd.shutdown()
            httpd.server_close()
        except Exception:
            traceback.print_exc()
        self.thread = None

    def url(self):
        return 'http://%s:%d' % (lan_ip(), self.port)

    # ---------- 请求处理 ----------
    def _make_handler(self):
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            server_version = 'FeeBookSync/1.0'
            protocol_version = 'HTTP/1.1'

            def log_message(self, fmt, *args):
                pass                      # 别往控制台刷访问日志

            # -- 小工具 --
            def _send(self, code, body, ctype):
                if isinstance(body, str):
                    body = body.encode('utf-8')
                self.send_response(code)
                self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)

            def _json(self, code, obj):
                self._send(code, json.dumps(obj, ensure_ascii=False),
                           'application/json; charset=utf-8')

            def _fail(self, code, msg):
                self._json(code, {'ok': False, 'error': msg})

            def _query(self):
                return dict(urllib.parse.parse_qsl(
                    urllib.parse.urlparse(self.path).query))

            def _pair_ok(self):
                given = (self._query().get('pair')
                         or self.headers.get('X-Pair', '')).strip()
                return bool(outer.pair) and given == outer.pair

            def _body_json(self):
                n = int(self.headers.get('Content-Length') or 0)
                if n <= 0 or n > 8 * 1024 * 1024:      # 超过 8MB 直接当异常
                    raise ValueError('请求体大小异常（%d 字节）' % n)
                raw = self.rfile.read(n)
                return json.loads(raw.decode('utf-8'))

            # -- 路由 --
            def do_GET(self):
                if not self._pair_ok():
                    return self._fail(403, '配对码不对')
                path = urllib.parse.urlparse(self.path).path.rstrip('/') or '/'
                if path == '/ping':
                    s = outer.store
                    return self._json(200, {
                        'ok': True, 'app': APP_NAME, 'version': APP_VERSION,
                        'room': s.room, 'records': len(s.records),
                        'trash': len(s.deleted), 'members': len(s.members),
                    })
                if path == '/export':
                    return self._send(
                        200, json.dumps(outer.store.payload(),
                                        ensure_ascii=False, indent=2),
                        'application/json; charset=utf-8')
                return self._fail(404, '没有这个接口')

            def do_POST(self):
                if not self._pair_ok():
                    return self._fail(403, '配对码不对')
                path = urllib.parse.urlparse(self.path).path.rstrip('/') or '/'
                if path != '/import':
                    return self._fail(404, '没有这个接口')
                try:
                    data = self._body_json()
                    if not isinstance(data, dict):
                        raise ValueError('传来的不是账本对象')
                    if not isinstance(data.get('records'), list):
                        raise ValueError('账本里没有 records 列表')
                except Exception as e:
                    return self._fail(400, '数据读不出来：%s' % e)
                # 真正的落盘动作必须回主线程做：Store 会被界面同时读写。
                # _run_on_ui 会把活儿投回主线程、等它做完，并把结果带回来。
                try:
                    result = outer._run_on_ui(
                        lambda: outer.apply_remote(data))
                except Exception as e:
                    traceback.print_exc()
                    return self._fail(500, '合并失败：%s' % e)
                return self._json(200, result)

        return Handler

    def _run_on_ui(self, fn):
        """在 Tk 主线程里执行 fn，把它的返回值原样带回来

        界面和后台线程都在碰同一份 Store，改数据只能在主线程做，
        否则两边同时写会丢记录。

        做法是「队列 + 主线程来取」而不是 `root.after()`：
        Tkinter 只认创建它的那个线程，从别的线程调 after() 会直接抛异常
        （报在 createcommand 那层），所以后台线程只能老老实实排队。
        """
        if self.ui_root is None:
            # 没挂界面（单测、或把同步服务单独拿去用）：直接就地执行
            return fn()
        if threading.current_thread() is threading.main_thread():
            # 已经在主线程里（例如用户点按钮触发）就别绕圈，直接跑
            return fn()
        done = threading.Event()
        box = {}
        self._jobs.put((fn, done, box))
        if not done.wait(60):
            raise RuntimeError('主界面 60 秒没有响应，同步放弃')
        if 'err' in box:
            raise box['err']
        return box['ok']

    def pump(self):
        """主线程定时调用：把后台线程排队的活儿挨个做掉（必须在主线程跑）"""
        n = 0
        while True:
            try:
                fn, done, box = self._jobs.get_nowait()
            except queue.Empty:
                return n
            n += 1
            try:
                box['ok'] = fn()
            except Exception as e:        # noqa: BLE001
                box['err'] = e
            finally:
                done.set()

    def apply_remote(self, data):
        """把手机传来的账本合并进本地（只在主线程调用）"""
        # 用 id 集合算差集，而不是「前后条数相减」——
        # 同一次同步里可能既新增又删除，净增减互相抵消，报出来的数是错的。
        before_live = {r['id'] for r in self.store.records}
        before_dead = {r['id'] for r in self.store.deleted}
        self.store.snapshot('手机同步')
        try:
            self.store.apply(data, replace=False)
        except Exception:
            self.store.discard_snapshot()
            raise
        ok, err = self.store.save()
        after_live = {r['id'] for r in self.store.records}
        after_dead = {r['id'] for r in self.store.deleted}
        added = len(after_live - before_live)
        trashed = len(after_dead - before_dead)
        self.last = ('手机同步：新增 %d 条 / 删除 %d 条%s'
                     % (added, trashed, '' if ok else '（保存失败：%s）' % err))
        if self.on_applied:
            self.on_applied(self.last)
        return {
            'ok': True, 'added': added, 'trashed': trashed,
            'records': len(after_live), 'trash': len(after_dead),
            'saved': bool(ok), 'note': '' if ok else str(err),
        }


# ============================================================
# 界面层
# ============================================================
class CalendarPicker(tk.Frame):
    """日期选择器：点一下弹出**一整月的大日期表**（日历下拉），不用手打日期

    日历里可以直接点某一天；顶部还能换月、直接跳年份/月份，
    补录 2025 年的历史数据也很快。
    """

    WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日']

    def __init__(self, master, bg=C_CARD, font=None, cell_w=5, btn_width=17,
                 cal_font=None, **kw):
        tk.Frame.__init__(self, master, bg=bg, **kw)
        self.font = font or ('Microsoft YaHei UI', 10)
        # 日历里的字号比输入框稍大，点起来更清楚
        self.cal_font = cal_font or (self.font[0], max(self.font[1] + 1, 11))
        self.cell_w = cell_w
        self.var_date = tk.StringVar(value=today_str())
        self.var_display = tk.StringVar()
        self.popup = None
        self._cells = {}
        self._cell_day = {}
        now = datetime.now()
        self._y, self._m = now.year, now.month

        self.btn = tk.Button(self, textvariable=self.var_display, font=self.font,
                             width=btn_width, bg=C_INPUT_BG, fg=C_TEXT,
                             activebackground=C_PRIMARY_L, activeforeground=C_TEXT,
                             relief='solid', bd=1, highlightthickness=0,
                             anchor='w', cursor='hand2', padx=6, pady=2,
                             command=self.toggle)
        self.btn.pack(fill='x', expand=True)
        self._refresh_display()

    # ---------------- 对外接口 ----------------
    def get(self):
        return self.var_date.get() or today_str()

    def set(self, value):
        try:
            y, m, d = [int(x) for x in str(value)[:10].split('-')]
            datetime(y, m, d)          # 顺便校验，4 月 31 日这种会被挡下
        except Exception:
            now = datetime.now()
            y, m, d = now.year, now.month, now.day
        self.var_date.set('%04d-%02d-%02d' % (y, m, d))
        self._y, self._m = y, m
        self._refresh_display()
        if self._alive():
            self._sync_head()
            self._render_days()

    def set_today(self):
        self.set(today_str())

    def toggle(self):
        if self._alive():
            self.close_popup()
        else:
            self.open_popup()

    def goto(self, year, month):
        """跳到某年某月（月份允许越界，会自动进位）"""
        y, m = year + (month - 1) // 12, (month - 1) % 12 + 1
        self._y, self._m = y, m
        self._sync_head()
        self._render_days()

    def pick(self, day):
        """选中当前所显示月份的某一天，并收起日历"""
        try:
            datetime(self._y, self._m, int(day))
        except Exception:
            return
        self.set('%04d-%02d-%02d' % (self._y, self._m, int(day)))
        self.close_popup()

    def open_popup(self):
        if not self._alive():
            self._build_popup()
        try:
            y, m, _ = [int(x) for x in self.get().split('-')]
            self._y, self._m = y, m
        except Exception:
            pass
        self._sync_head()
        self._render_days()

        p = self.popup
        self.update_idletasks()
        pw, ph = p.winfo_reqwidth(), p.winfo_reqheight()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2
        sw, sh = p.winfo_screenwidth(), p.winfo_screenheight()
        if x + pw > sw - 8:
            x = max(8, sw - pw - 8)
        if y + ph > sh - 48:               # 下面放不下就改成往上弹
            y = max(8, self.winfo_rooty() - ph - 2)
        p.geometry('%dx%d+%d+%d' % (pw, ph, x, y))
        p.deiconify()
        p.lift()
        try:
            p.grab_set()
        except Exception:
            pass
        try:
            p.focus_force()
        except Exception:
            pass

    def close_popup(self):
        p, self.popup = self.popup, None
        if p is None:
            return
        try:
            p.grab_release()
        except Exception:
            pass
        try:
            if p.winfo_exists():
                p.destroy()
        except Exception:
            pass

    def _alive(self):
        try:
            return self.popup is not None and bool(self.popup.winfo_exists())
        except Exception:
            return False

    # ---------------- 内部 ----------------
    def _refresh_display(self):
        iso = self.get()
        try:
            d = datetime.strptime(iso, DATE_FMT)
            self.var_display.set('%s  周%s  ▾' % (iso, self.WEEKDAYS[d.weekday()]))
        except Exception:
            self.var_display.set(iso + '  ▾')

    def _build_popup(self):
        p = tk.Toplevel(self)
        p.withdraw()
        p.overrideredirect(True)
        p.configure(bg=C_PRIMARY)          # 只露 1px，当边框用
        self.popup = p

        outer = tk.Frame(p, bg=C_CARD)
        outer.pack(fill='both', expand=True, padx=1, pady=1)

        # —— 顶部：换月 / 直接跳年、月 ——
        head = tk.Frame(outer, bg=C_PRIMARY)
        head.pack(fill='x')

        prev = tk.Label(head, text='‹', bg=C_PRIMARY, fg='#ffffff',
                        font=(self.cal_font[0], 14, 'bold'), width=2, cursor='hand2')
        prev.pack(side='left')
        prev.bind('<Button-1>', lambda e: self.goto(self._y, self._m - 1))

        years = [str(y) for y in range(2020, datetime.now().year + 6)]
        self.cb_y = ttk.Combobox(head, width=6, state='readonly', font=self.cal_font, values=years)
        self.cb_y.pack(side='left', pady=5)
        tk.Label(head, text='年', bg=C_PRIMARY, fg='#cfe2fc', font=self.cal_font).pack(side='left')
        self.cb_m = ttk.Combobox(head, width=3, state='readonly', font=self.cal_font,
                                 values=[str(i) for i in range(1, 13)])
        self.cb_m.pack(side='left', padx=(4, 0), pady=5)
        tk.Label(head, text='月', bg=C_PRIMARY, fg='#cfe2fc', font=self.cal_font).pack(side='left')

        nxt = tk.Label(head, text='›', bg=C_PRIMARY, fg='#ffffff',
                       font=(self.cal_font[0], 14, 'bold'), width=2, cursor='hand2')
        nxt.pack(side='right')
        nxt.bind('<Button-1>', lambda e: self.goto(self._y, self._m + 1))

        self.cb_y.bind('<<ComboboxSelected>>',
                       lambda e: self.goto(int(self.cb_y.get()), self._m))
        self.cb_m.bind('<<ComboboxSelected>>',
                       lambda e: self.goto(self._y, int(self.cb_m.get())))

        # —— 星期表头 ——
        wk = tk.Frame(outer, bg=C_CARD)
        wk.pack(fill='x', padx=6, pady=(4, 2))
        for i, t in enumerate(self.WEEKDAYS):
            tk.Label(wk, text=t, bg=C_CARD, fg=(C_RED if i >= 5 else C_MUTED),
                     font=(self.cal_font[0], self.cal_font[1], 'bold'),
                     width=self.cell_w).grid(row=0, column=i, padx=1)

        # —— 日期网格：固定 6 行 × 7 列，切换月份时大小不会跳 ——
        gf = tk.Frame(outer, bg=C_CARD)
        gf.pack(fill='both', expand=True, padx=6)
        for r in range(6):
            for c in range(7):
                b = tk.Button(gf, text='', width=self.cell_w, height=1, font=self.cal_font,
                              relief='flat', bd=0, highlightthickness=0, bg=C_CARD,
                              activebackground=C_PRIMARY_L, cursor='hand2',
                              command=lambda rr=r, cc=c: self._click_cell(rr, cc))
                b.grid(row=r, column=c, padx=1, pady=1)
                self._cells[(r, c)] = b
                self._cell_day[(r, c)] = None

        # —— 底部 ——
        foot = tk.Frame(outer, bg=C_CARD)
        foot.pack(fill='x', padx=6, pady=(2, 6))
        tk.Button(foot, text='今天', font=self.cal_font,
                  bg=C_PRIMARY_L, fg=C_PRIMARY_D,
                  activebackground=C_PRIMARY_HOVER, activeforeground=C_PRIMARY_D,
                  relief='flat', bd=0, highlightthickness=0,
                  cursor='hand2', padx=14, pady=3,
                  command=lambda: (self.set_today(), self.close_popup())).pack(side='left')
        tk.Label(foot, text='点日期即选中', bg=C_CARD, fg=C_MUTED,
                 font=(self.cal_font[0], max(7, self.cal_font[1] - 2))).pack(side='right')

        p.bind('<Escape>', lambda e: self.close_popup())
        p.bind('<Button-1>', self._maybe_close)

    def _sync_head(self):
        if not self._alive():
            return
        vals = [str(v) for v in self.cb_y.cget('values')]
        if str(self._y) not in vals:
            self.cb_y.configure(values=sorted(set(vals + [str(self._y)])))
        if self.cb_y.get() != str(self._y):
            self.cb_y.set(str(self._y))
        if self.cb_m.get() != str(self._m):
            self.cb_m.set(str(self._m))

    def _render_days(self):
        if not self._alive():
            return
        try:
            first = datetime(self._y, self._m, 1)
        except Exception:
            return
        lead = first.weekday()                 # 周一排在第一列
        days = calendar.monthrange(self._y, self._m)[1]
        cur = self.get()
        today = today_str()
        for (r, c), b in self._cells.items():
            day = r * 7 + c - lead + 1
            if 1 <= day <= days:
                iso = '%04d-%02d-%02d' % (self._y, self._m, day)
                self._cell_day[(r, c)] = day
                if iso == cur:                                     # 已选中
                    b.configure(text=str(day), state='normal', bg=C_PRIMARY, fg='#ffffff',
                                relief='flat', bd=0)
                elif iso == today:                                 # 今天带个框
                    b.configure(text=str(day), state='normal', bg=C_PRIMARY_L,
                                fg=C_PRIMARY_D, relief='solid', bd=1)
                else:
                    b.configure(text=str(day), state='normal', bg=C_CARD, fg=C_TEXT,
                                relief='flat', bd=0)
            else:
                self._cell_day[(r, c)] = None
                b.configure(text='', state='disabled', bg=C_CARD, relief='flat', bd=0)

    def _click_cell(self, r, c):
        day = self._cell_day.get((r, c))
        if day:
            self.pick(day)

    def _maybe_close(self, e):
        """带 grab 时，点窗口外面的事件也会送到这里，按坐标判断是否点在日历外"""
        p = self.popup
        if p is None:
            return
        try:
            if not p.winfo_exists():
                return
            x, y = e.x_root, e.y_root
            rx, ry = p.winfo_rootx(), p.winfo_rooty()
            inside = (rx <= x < rx + p.winfo_width()) and (ry <= y < ry + p.winfo_height())
        except Exception:
            return
        if not inside:
            self.close_popup()


# 兼容旧名字，避免别处引用失效
DatePicker = CalendarPicker


class App(object):
    def __init__(self, root, store):
        self.root = root
        self.store = store
        self.sort_key = 'date'
        self.sort_reverse = True
        # 「每个人分别充了多少」那张表自己的排序（默认按固定序号从小到大）
        self.sum_sort_key = 'no'
        self.sum_sort_reverse = False
        self._saved_after = None

        self.ui_font = 'Microsoft YaHei UI'
        self.ui_scale = self._detect_scale()
        self._init_fonts()
        self._init_style()
        self._build()
        self.refresh_all()

        self._bind_keys()
        # 局域网同步服务：默认不启动，主人在「局域网同步」里点开才跑
        self._pump_on = False
        self.sync = SyncServer(store)
        self.sync.ui_root = root
        self.sync.on_applied = self._on_sync_applied
        self.sync.on_start = self._ensure_sync_pump
        if store.load_error:
            self.root.after(300, lambda: messagebox.showwarning('提示', store.load_error))
        root.protocol('WM_DELETE_WINDOW', self.on_close)

    def _ensure_sync_pump(self):
        """服务一开就把「取活儿」的定时器挂上；已经挂着的就别重复挂"""
        if not self._pump_on:
            self._sync_pump()

    def _sync_pump(self):
        """主线程上定时取活儿的循环

        只在同步服务开着的时候排下一拍 —— 服务一停就彻底停掉，
        不在后台留常驻定时器白耗电。
        """
        self._pump_on = False
        try:
            self.sync.pump()
        except Exception:
            traceback.print_exc()
        if self.sync.running():
            self._pump_on = True
            try:
                self.root.after(150, self._sync_pump)
            except Exception:
                self._pump_on = False

    def _on_sync_applied(self, text):
        """后台同步把数据改完了 → 刷新界面（此刻已经在主线程上）"""
        try:
            self.var_room.set(self.store.room)
            self.refresh_all()
            self.lbl_saved.configure(text=text)
        except Exception:
            traceback.print_exc()

    def _detect_scale(self):
        """当前屏幕的文字缩放（相对 96 DPI）。

        这台机器就是 150%（tk scaling ≈ 2.0）—— 字号放大了 1.5 倍，
        窗口要是还按 1180 的物理像素开，整个界面就会挤成一团。
        这里量出缩放比，窗口、行高、列宽统统跟着放大。
        """
        try:
            s = float(self.root.winfo_fpixels('1i')) / 96.0
        except Exception:
            s = 1.0
        return min(max(s, 1.0), 2.0)

    def _bind_keys(self):
        """快捷键：Ctrl+Z 撤销、Ctrl+Y / Ctrl+Shift+Z 重做"""
        self.root.bind('<Control-z>', lambda e: self.do_undo())
        self.root.bind('<Control-Z>', lambda e: self.do_undo())
        self.root.bind('<Control-y>', lambda e: self.do_redo())
        self.root.bind('<Control-Y>', lambda e: self.do_redo())
        self.root.bind('<Control-Shift-Z>', lambda e: self.do_redo())
        self.root.bind('<Control-Shift-z>', lambda e: self.do_redo())

    # ---------- 字体 / 样式 ----------
    def _init_fonts(self):
        try:
            import tkinter.font as tkfont
            fams = set(tkfont.families())
            for f in ('Microsoft YaHei UI', 'Microsoft YaHei', 'SimHei', 'SimSun'):
                if f in fams:
                    self.ui_font = f
                    break
        except Exception:
            pass
        self.F = (self.ui_font, 9)
        self.FB = (self.ui_font, 9, 'bold')
        self.F_TITLE = (self.ui_font, 14, 'bold')
        self.F_BIG = (self.ui_font, 15, 'bold')
        self.F_SMALL = (self.ui_font, 8)
        self.F_SECTION = (self.ui_font, 10, 'bold')

    def _init_style(self):
        st = ttk.Style()
        try:
            if 'vista' in st.theme_names():
                st.theme_use('vista')
        except Exception:
            pass
        # 行高要跟着真实字号走：系统缩放 150% 时 9 号字就占 24px，
        # 写死 27 会让行里文字贴边、挤成一团。
        try:
            import tkinter.font as tkfont
            row_h = max(27, tkfont.Font(font=self.F).metrics('linespace') + 8)
        except Exception:
            row_h = 27
        st.configure('Treeview', rowheight=row_h, font=self.F, background=C_CARD,
                     fieldbackground=C_CARD, borderwidth=0)
        st.configure('Treeview.Heading', font=self.FB)
        st.map('Treeview', background=[('selected', C_PRIMARY_L)],
               foreground=[('selected', C_PRIMARY_D)])
        st.configure('TCombobox', padding=2)

    def mkbtn(self, parent, text, command, kind='plain', width=None, font=None):
        colors = {
            'primary': (C_PRIMARY, '#ffffff', C_PRIMARY_D, '#ffffff'),
            'plain': (C_CARD, C_TEXT, '#eef4fb', C_PRIMARY_D),
            'soft': (C_PRIMARY_L, C_PRIMARY_D, C_PRIMARY_HOVER, C_PRIMARY_D),
            # 顶栏是浅色的，ghost 就贴底色走「纯文字」风格，别再加色块
            'ghost': (C_HEADER, C_HEADER_TITLE, C_PRIMARY_L, C_PRIMARY_D),
            # 顶栏底色淡，主按钮得自己撑起实心色才跳得出来
            'cta': (C_PRIMARY, '#ffffff', C_PRIMARY_D, '#ffffff'),
            'danger': ('#fdecef', C_RED, '#f9dbe0', C_RED),
        }
        bg, fg, abg, afg = colors.get(kind, colors['plain'])
        b = tk.Button(parent, text=text, command=command, font=font or self.F,
                      bg=bg, fg=fg, activebackground=abg, activeforeground=afg,
                      disabledforeground='#98a5b5',   # 禁用时明确变灰，别让人以为能点
                      relief='flat', bd=0, highlightthickness=0, cursor='hand2',
                      padx=11, pady=5)
        if width:
            b.configure(width=width)
        return b

    def mkentry(self, parent, textvariable=None, width=22, big=False, **extra):
        """统一的输入框样式：白底 + 明显边框（默认边框太浅会像没有输入框）"""
        kw = dict(font=(self.ui_font, 12, 'bold') if big else self.F,
                  width=width, relief='flat', bd=0,
                  bg=C_INPUT_BG, fg=C_TEXT, insertbackground=C_TEXT,
                  highlightthickness=1, highlightbackground=C_INPUT_LINE,
                  highlightcolor=C_PRIMARY)
        if textvariable is not None:
            kw['textvariable'] = textvariable
        kw.update(extra)
        return tk.Entry(parent, **kw)

    def text_w(self, font, *cands):
        """用**真实字体**量出最宽的那段文字有多少像素

        坑：列宽千万别写死。同样写 `width=104`，在 100% 缩放下放得下
        `2026-09-18`，到 125% 缩放就被截成 `2026-09-1`。这里按当前 DPI
        的真实字体量，量出来多少就是多少。
        """
        try:
            import tkinter.font as tkfont
            f = tkfont.Font(font=font)
            return max(f.measure(str(t)) for t in cands)
        except Exception:
            return max(len(str(t)) for t in cands) * 8

    def col_w(self, font, cands, extra=26, minimum=44):
        """列宽 = 最宽文字 + 单元格留白（倍率已由字体自己带上）"""
        return max(minimum, self.text_w(font, *cands) + extra)

    def fit_columns(self, tv, spec, arrow=True):
        """按 spec 设置列宽；spec = [(列名, 表头, 锚点, 候选文字, 是否伸展)]

        两个必须一起量的东西：
        1. **排序箭头**：表头点一下会变成「日期 ▼」，量宽度时得把带箭头的
           那份也算进去，否则一点排序标题就被截掉半个字。
        2. 不伸展的列 minwidth 给到自然宽的 75%，窗口被拉小时还能让一点，
           而不是硬撑到把最后一列挤出可视区（那才是「列不见了」的元凶）。
        """
        for col, head, anchor, cands, stretch in spec:
            heads = [head]
            if arrow:
                heads += [head + ' ▲', head + ' ▼']
            w = self.col_w(self.FB, heads + list(cands))
            tv.heading(col, text=head, anchor=anchor)
            tv.column(col, width=w,
                      minwidth=60 if stretch else max(44, int(w * 0.75)),
                      anchor=anchor, stretch=stretch)

    # ---------- 布局 ----------
    def _build(self):
        self.root.title('%s v%s' % (APP_NAME, APP_VERSION))
        self.root.configure(bg=C_BG)
        # 按屏幕尺寸 + 文字缩放自适应：界面本身是按 100% 缩放设计的，
        # 缩放 150% 时窗口也要跟着放大，不然控件全被挤扁。
        sc = self.ui_scale
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w = int(min(1180 * sc, sw - 40))
        h = int(min(880 * sc, sh - int(110 * sc)))       # 留出任务栏，别被挡住
        self.root.geometry('%dx%d+%d+%d' % (w, h, max(0, (sw - w) // 2), max(0, (sh - h) // 4)))
        self.root.minsize(int(min(980 * sc, w)), int(min(650 * sc, h)))
        try:
            ico = resource_path('app.ico')
            if os.path.exists(ico):
                self.root.iconbitmap(ico)
        except Exception:
            pass

        outer = tk.Frame(self.root, bg=C_BG)
        outer.pack(fill='both', expand=True, padx=12, pady=10)
        outer.rowconfigure(2, weight=0)                  # 录入/汇总区：高度跟着内容走，防止被裁剪
        outer.rowconfigure(3, weight=1, minsize=int(170 * self.ui_scale))   # 明细区：吃掉剩余空间
        outer.columnconfigure(0, weight=1)

        self._build_header(outer)
        self._build_stats(outer)
        self._build_middle(outer)
        self._build_records(outer)
        self._build_status(outer)

    def _build_header(self, parent):
        bar = tk.Frame(parent, bg=C_HEADER)
        bar.grid(row=0, column=0, sticky='ew')
        self.bar_header = bar
        # 下沿 1px 细线：顶栏是浅色的，跟正文之间要有条分界，不然糊成一片
        tk.Frame(bar, bg=C_HEADER_LINE, height=1).pack(side='bottom', fill='x')
        inner = tk.Frame(bar, bg=C_HEADER)
        inner.pack(fill='x', padx=14, pady=10)
        self.hdr_inner = inner          # 布局体检要量它的所需宽度

        left = tk.Frame(inner, bg=C_HEADER)
        left.pack(side='left')
        tk.Label(left, text='⚡ 电费记账本', bg=C_HEADER, fg=C_HEADER_TITLE,
                 font=self.F_TITLE).pack(side='left')
        tk.Label(left, text='  宿舍/房间', bg=C_HEADER, fg=C_HEADER_SUB,
                 font=self.F).pack(side='left', padx=(12, 4))
        self.var_room = tk.StringVar(value=self.store.room)
        e = tk.Entry(left, textvariable=self.var_room, font=self.F, width=16,
                     relief='flat', bd=0, bg=C_HEADER_INPUT, fg=C_TEXT,
                     insertbackground=C_TEXT,
                     highlightthickness=1, highlightbackground=C_INPUT_LINE,
                     highlightcolor=C_PRIMARY)
        e.pack(side='left', ipady=3)
        e.bind('<KeyRelease>', self.on_room_change)
        e.bind('<FocusOut>', self.on_room_change)

        right = tk.Frame(inner, bg=C_HEADER)
        right.pack(side='right')
        # 一键导出：不弹「另存为」，直接把 txt + xlsx 丢进程序旁的「导出」文件夹
        self.mkbtn(right, '⬇ 一键导出', self.export_all, 'cta').pack(side='left', padx=(0, 3))
        # 其余导出方式收进下拉，省得顶栏排一长串按钮
        mb = tk.Menubutton(right, text='更多导出 ▾', font=self.F,
                           bg=C_HEADER, fg=C_HEADER_TITLE,
                           activebackground=C_PRIMARY_L, activeforeground=C_PRIMARY_D,
                           relief='flat', bd=0,
                           highlightthickness=0, cursor='hand2', padx=11, pady=5)
        menu = tk.Menu(mb, tearoff=0, font=self.F)
        menu.add_command(label='导出 TXT 文本账本', command=self.export_txt)
        menu.add_command(label='导出 Excel（.xlsx）', command=self.export_xlsx)
        menu.add_separator()
        menu.add_command(label='导出 CSV 表格', command=self.export_csv)
        menu.add_command(label='导出 JSON 备份', command=self.export_json)
        mb.configure(menu=menu)
        mb.pack(side='left', padx=3)
        # 手机同步：跟安卓版对账的入口，单独用软底按钮，别埋进灰按钮堆里
        self.btn_sync = self.mkbtn(right, '手机同步', self.open_lan_sync, 'soft')
        self.btn_sync.pack(side='left', padx=(3, 3))
        for text, cmd in (
            ('成员管理', self.open_members),
            ('复制结算单', self.copy_report),
            ('打开数据文件夹', self.open_folder),
            ('导入 JSON', self.import_json),
        ):
            self.mkbtn(right, text, cmd, 'ghost').pack(side='left', padx=3)

    def _build_stats(self, parent):
        wrap = tk.Frame(parent, bg=C_BG)
        wrap.grid(row=1, column=0, sticky='ew', pady=(10, 0))
        for i in range(4):
            wrap.columnconfigure(i, weight=1, uniform='s')
        self.stat_labels = {}
        defs = [
            ('total', '总充值', C_PRIMARY),
            ('count', '充值笔数', C_TEXT),
            ('people', '参与人数', C_TEXT),
            ('latest', '最近充值', C_TEXT),
        ]
        for i, (key, title, color) in enumerate(defs):
            card = tk.Frame(wrap, bg=C_CARD, highlightbackground=C_LINE, highlightthickness=1)
            card.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 5, 0))
            tk.Label(card, text=title, bg=C_CARD, fg=C_MUTED, font=self.F_SMALL,
                     anchor='w').pack(fill='x', padx=12, pady=(8, 0))
            big = key == 'latest'
            lab = tk.Label(card, text='—', bg=C_CARD, fg=color,
                           font=self.F_SMALL if big else self.F_BIG, anchor='w')
            lab.pack(fill='x', padx=12, pady=(1, 9))
            self.stat_labels[key] = lab

    def _build_middle(self, parent):
        mid = tk.Frame(parent, bg=C_BG)
        mid.grid(row=2, column=0, sticky='nsew', pady=(10, 0))
        mid.columnconfigure(1, weight=1)
        mid.rowconfigure(0, weight=1)

        # --- 左：录入 ---
        card = tk.Frame(mid, bg=C_CARD, highlightbackground=C_LINE, highlightthickness=1)
        card.grid(row=0, column=0, sticky='nsw', padx=(0, 10))
        box = tk.Frame(card, bg=C_CARD)
        box.pack(fill='both', expand=True, padx=14, pady=11)
        trow = tk.Frame(box, bg=C_CARD)
        trow.pack(fill='x', pady=(0, 7))
        tk.Label(trow, text='记一笔充值', bg=C_CARD, fg=C_TEXT, font=self.F_SECTION).pack(side='left')
        tk.Label(trow, text='填好按回车即可提交', bg=C_CARD, fg=C_MUTED,
                 font=self.F_SMALL).pack(side='right')

        def field(label, w):
            row = tk.Frame(box, bg=C_CARD)
            row.pack(fill='x', pady=2)
            tk.Label(row, text=label, bg=C_CARD, fg=C_MUTED, font=self.F_SMALL,
                     width=8, anchor='w').pack(side='left')
            return row, w(row)

        row = tk.Frame(box, bg=C_CARD)
        row.pack(fill='x', pady=2)
        tk.Label(row, text='日期', bg=C_CARD, fg=C_MUTED, font=self.F_SMALL,
                 width=8, anchor='w').pack(side='left')
        self.dp_date = CalendarPicker(row, bg=C_CARD, font=self.F)
        self.dp_date.pack(side='left')
        self.mkbtn(row, '今天', self.set_today_t, 'plain',
                   font=self.F_SMALL).pack(side='left', padx=(6, 0))

        row, self.cb_member = field('谁充的', lambda p: ttk.Combobox(p, font=self.F, width=20))
        self.cb_member.pack(side='left', fill='x', expand=True)

        row, self.e_amount = field('充多少', lambda p: self.mkentry(p, width=22, big=True))
        self.e_amount.pack(side='left', ipady=4, fill='x', expand=True)
        self.e_amount.bind('<Return>', lambda ev: self.add_record())
        self.e_amount.bind('<KP_Enter>', lambda ev: self.add_record())

        qrow = tk.Frame(box, bg=C_CARD)
        qrow.pack(fill='x', pady=(3, 5))
        tk.Label(qrow, text='', bg=C_CARD, width=8).pack(side='left')
        for q in (10, 20, 50, 100, 200):
            self.mkbtn(qrow, '+%d' % q, lambda v=q: self.quick_add(v), 'plain',
                       font=self.F_SMALL).pack(side='left', padx=2, expand=True, fill='x')

        row, self.cb_method = field('支付方式', lambda p: ttk.Combobox(p, font=self.F, width=20,
                                                                     values=METHODS, state='readonly'))
        self.cb_method.current(0)
        self.cb_method.pack(side='left', fill='x', expand=True)

        row, self.e_note = field('备注', lambda p: self.mkentry(p, width=22))
        self.e_note.pack(side='left', ipady=4, fill='x', expand=True)
        self.e_note.bind('<Return>', lambda ev: self.add_record())

        act = tk.Frame(box, bg=C_CARD)
        act.pack(fill='x', pady=(10, 0))
        self.mkbtn(act, '＋ 添加记录', self.add_record, 'primary', font=self.FB).pack(
            side='left', fill='x', expand=True, ipady=3)
        self.mkbtn(act, '清空', self.clear_form, 'plain').pack(side='left', padx=(6, 0), ipady=3)

        # --- 右：汇总 ---
        card2 = tk.Frame(mid, bg=C_CARD, highlightbackground=C_LINE, highlightthickness=1)
        card2.grid(row=0, column=1, sticky='nsew')
        head = tk.Frame(card2, bg=C_CARD)
        head.pack(fill='x', padx=14, pady=(12, 6))
        tk.Label(head, text='每个人分别充了多少', bg=C_CARD, fg=C_TEXT,
                 font=self.F_SECTION, anchor='w').pack(side='left')
        self.lbl_sum_sub = tk.Label(head, text='', bg=C_CARD, fg=C_MUTED, font=self.F_SMALL)
        self.lbl_sum_sub.pack(side='right')
        # 这张表自己的排序（点下面的表头也能排）
        self.var_sum_sort = tk.StringVar(value=SUM_SORT_OPTIONS[0][0])
        self.cb_sum_sort = ttk.Combobox(head, textvariable=self.var_sum_sort, font=self.F,
                                        width=13, state='readonly',
                                        values=[o[0] for o in SUM_SORT_OPTIONS])
        self.cb_sum_sort.pack(side='right', padx=(0, 8))
        self.cb_sum_sort.bind('<<ComboboxSelected>>', lambda e: self.on_sum_sort_change())
        tk.Label(head, text='排序', bg=C_CARD, fg=C_MUTED,
                 font=self.F_SMALL).pack(side='right', padx=(0, 4))

        # 「期初」只出现在下面的明细账单里，汇总表不显示这一维
        cols = ('no', 'name', 'count', 'amount', 'pct', 'last')
        sumwrap = tk.Frame(card2, bg=C_CARD)
        sumwrap.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        self.tv_sum = ttk.Treeview(sumwrap, columns=cols, show='headings', height=6,
                                   selectmode='browse')
        names = [m for m in self.store.members if m] or ['成员']
        blank = any(not r['member'] for r in self.store.records)
        self.fit_columns(self.tv_sum, [
            ('no', '序号', 'center', ['888'], False),
            ('name', '成员', 'w', [max(names, key=len)] + (['(未填写)'] if blank else []), False),
            ('count', '笔数', 'center', ['888'], False),
            ('amount', '累计充值', 'e', ['¥1,234.00'], False),
            # pct 这一列候选里放块字符，只是当「宽度尺子」用：
            # 柱子本身由 Canvas 画（见 draw_pct_bars），但列宽得照
            # 「一根柱子 + 百分号」留够，否则 Canvas 会被判定太窄而让位。
            ('pct', '占比', 'w', ['██████ 100.0%', '░░░░░░ 0.0%'], True),
            ('last', '最近充值', 'center', ['2026-09-18'], False),
        ])
        for c in cols:                       # 表头也能点着排序
            self.tv_sum.heading(c, command=lambda k=c: self.sum_sort_by(k))
        sumsb = ttk.Scrollbar(sumwrap, orient='vertical', command=self.tv_sum.yview)
        # 滚动时占比条得跟着挪，所以在 yscrollcommand 里顺手排队重画一次
        self.tv_sum.configure(
            yscrollcommand=lambda *a: (sumsb.set(*a), self._queue_bar_redraw()))
        self.tv_sum.pack(side='left', fill='both', expand=True)
        sumsb.pack(side='right', fill='y')
        self.tv_sum.tag_configure('empty', foreground=C_MUTED)
        # 占比条：ttk.Treeview 不能给「单个格子」上色（tag 只能整行变色），
        # 所以直接在 Treeview 内部叠一层 Canvas 自己画。
        # 它是 Treeview 的子控件 → bbox() 给的坐标能直接拿来用，不用做坐标换算。
        self.bar_canvas = tk.Canvas(self.tv_sum, bg=C_CARD, highlightthickness=0, bd=0)
        self.bar_canvas.bind('<Button-1>', self._on_bar_click)
        self.tv_sum.bind('<<TreeviewSelect>>', lambda e: self._queue_bar_redraw())
        self._sum_pct = {}
        self._bar_font = None
        # 柱子长度按列宽自适应：窗口一变大/缩放一变，重新算一次
        self.tv_sum.bind('<Configure>', self._on_sum_resize)
        self._sum_w = 0

    def _build_records(self, parent):
        card = tk.Frame(parent, bg=C_CARD, highlightbackground=C_LINE, highlightthickness=1)
        card.grid(row=3, column=0, sticky='nsew', pady=(10, 0))

        head = tk.Frame(card, bg=C_CARD)
        head.pack(fill='x', padx=14, pady=(12, 6))
        tk.Label(head, text='明细记录', bg=C_CARD, fg=C_TEXT, font=self.F_SECTION).pack(side='left')
        self.lbl_rec_sub = tk.Label(head, text='', bg=C_CARD, fg=C_MUTED, font=self.F_SMALL)
        self.lbl_rec_sub.pack(side='left', padx=(10, 0))

        # 撤销 / 重做 / 回收站 —— 防误删三件套，放在最顺手的位置
        # 注意：Tk 里 emoji（🗑 之类）会渲染成方块，这里一律用纯文字
        self.btn_trash = self.mkbtn(head, '回收站', self.open_trash, 'plain', font=self.F_SMALL)
        self.btn_trash.pack(side='right')
        self.btn_redo = self.mkbtn(head, '重做', self.do_redo, 'plain', font=self.F_SMALL)
        self.btn_redo.pack(side='right', padx=(0, 6))
        self.btn_undo = self.mkbtn(head, '撤销', self.do_undo, 'soft', font=self.F_SMALL)
        self.btn_undo.pack(side='right', padx=(0, 6))

        tools = tk.Frame(card, bg=C_CARD)
        tools.pack(fill='x', padx=14, pady=(0, 8))
        tk.Label(tools, text='搜索', bg=C_CARD, fg=C_MUTED, font=self.F_SMALL).pack(side='left')
        self.var_kw = tk.StringVar()
        ent = self.mkentry(tools, textvariable=self.var_kw, width=12)
        ent.pack(side='left', ipady=3, padx=(4, 10))
        self.var_kw.trace_add('write', lambda *a: self.refresh_records())

        tk.Label(tools, text='成员', bg=C_CARD, fg=C_MUTED, font=self.F_SMALL).pack(side='left')
        self.var_fmember = tk.StringVar()
        self.cb_filter = ttk.Combobox(tools, textvariable=self.var_fmember, font=self.F,
                                      width=8, state='readonly')
        self.cb_filter.pack(side='left', padx=(4, 10))
        self.cb_filter.bind('<<ComboboxSelected>>', lambda e: self.refresh_records())

        tk.Label(tools, text='年份', bg=C_CARD, fg=C_MUTED, font=self.F_SMALL).pack(side='left')
        self.var_fyear = tk.StringVar()
        self.cb_fyear = ttk.Combobox(tools, textvariable=self.var_fyear, font=self.F,
                                     width=8, state='readonly')
        self.cb_fyear.pack(side='left', padx=(4, 8))
        self.cb_fyear.bind('<<ComboboxSelected>>', lambda e: self.refresh_records())

        tk.Label(tools, text='月份', bg=C_CARD, fg=C_MUTED, font=self.F_SMALL).pack(side='left')
        self.var_fmonth = tk.StringVar()
        self.cb_fmonth = ttk.Combobox(tools, textvariable=self.var_fmonth, font=self.F,
                                      width=6, state='readonly')
        self.cb_fmonth.pack(side='left', padx=(4, 8))
        self.cb_fmonth.bind('<<ComboboxSelected>>', lambda e: self.refresh_records())

        tk.Label(tools, text='排序', bg=C_CARD, fg=C_MUTED, font=self.F_SMALL).pack(side='left')
        self.var_sort = tk.StringVar(value=SORT_OPTIONS[0][0])
        self.cb_sort = ttk.Combobox(tools, textvariable=self.var_sort, font=self.F,
                                    width=13, state='readonly',
                                    values=[o[0] for o in SORT_OPTIONS])
        self.cb_sort.pack(side='left', padx=(4, 8))
        self.cb_sort.bind('<<ComboboxSelected>>', lambda e: self.on_sort_change())

        self.mkbtn(tools, '重置筛选', self.reset_filter, 'plain',
                   font=self.F_SMALL).pack(side='left', padx=4)
        self.mkbtn(tools, '移入回收站', self.delete_selected, 'danger',
                   font=self.F_SMALL).pack(side='right')
        self.mkbtn(tools, '编辑选中', self.edit_selected, 'soft',
                   font=self.F_SMALL).pack(side='right', padx=(0, 6))

        wrap = tk.Frame(card, bg=C_CARD)
        wrap.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        cols = ('date', 'member', 'amount', 'method', 'note')
        self.tv_rec = ttk.Treeview(wrap, columns=cols, show='headings', selectmode='extended')
        names = [m for m in self.store.members if m] or ['充值人']
        blank = any(not r['member'] for r in self.store.records)
        self.fit_columns(self.tv_rec, [
            ('date', '日期 ▼', 'w', ['2026-09-18'], False),
            ('member', '充值人', 'w', [max(names, key=len)] + (['(未填写)'] if blank else []), False),
            ('amount', '金额(元) ▼', 'e', ['1,234.00'], False),
            ('method', '方式', 'w', [max(METHODS, key=len)], False),
            ('note', '备注', 'w', ['备注'], True),
        ])
        for c in cols:                       # 表头可点击排序
            self.tv_rec.heading(c, command=lambda k=c: self.sort_by(k))
        vsb = ttk.Scrollbar(wrap, orient='vertical', command=self.tv_rec.yview)
        self.tv_rec.configure(yscrollcommand=vsb.set)
        self.tv_rec.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tv_rec.tag_configure('odd', background=C_ROW_ALT)
        # 期初那条用浅黄底 + 斜体感区分，一眼看出「不算笔数」
        self.tv_rec.tag_configure('initial', background='#fdf6e3', foreground=C_AMBER)
        self.tv_rec.bind('<Double-1>', lambda e: self.edit_selected())
        self.tv_rec.bind('<Delete>', lambda e: self.delete_selected())

    def _build_status(self, parent):
        bar = tk.Frame(parent, bg=C_BG)
        bar.grid(row=4, column=0, sticky='ew', pady=(8, 0))
        self.lbl_status = tk.Label(bar, text='', bg=C_BG, fg=C_MUTED, font=self.F_SMALL, anchor='w')
        self.lbl_status.pack(side='left')
        self.lbl_saved = tk.Label(bar, text='', bg=C_BG, fg=C_PRIMARY, font=self.F_SMALL, anchor='e')
        self.lbl_saved.pack(side='right')

    # ============ 数据刷新 ============
    def refresh_all(self):
        self.refresh_stats()
        self.refresh_summary()
        self.refresh_members_box()
        self.refresh_records()
        self.refresh_status()
        self.refresh_history_buttons()

    def refresh_status(self):
        t = self.store.stats()['trash']
        extra = '　·　回收站 %d 条' % t if t else ''
        self.lbl_status.configure(text='数据文件：%s%s' % (self.store.path, extra))

    def refresh_history_buttons(self):
        """撤销 / 重做按钮的可用状态与提示文字"""
        def short(s, n=8):
            s = s or ''
            return s if len(s) <= n else s[:n] + '…'

        u, r = self.store.can_undo(), self.store.can_redo()
        self.btn_undo.configure(
            text=('撤销' if not u else '撤销 · %s' % short(self.store.undo_label())),
            state=('normal' if u else 'disabled'))
        self.btn_redo.configure(
            text=('重做' if not r else '重做 · %s' % short(self.store.redo_label())),
            state=('normal' if r else 'disabled'))
        n = len(self.store.deleted)
        # 回收站永远可点（哪怕是空的）—— 空的时候也让人看到这个入口在哪儿
        self.btn_trash.configure(
            text=('回收站' if not n else '回收站 (%d)' % n),
            state='normal')

    def refresh_stats(self):
        s = self.store.stats()
        self.stat_labels['total'].configure(text='¥' + money(s['total']))
        self.stat_labels['count'].configure(text='%d 笔' % s['count'])
        self.stat_labels['people'].configure(text='%d 人' % s['people'])
        lt = s['latest']
        self.stat_labels['latest'].configure(
            text='还没有记录' if not lt else '%s  %s ¥%s' % (
                lt['date'], lt['member'] or '—', money(lt['amount'])))

    def refresh_summary(self):
        s = self.store.stats(self.sum_sort_key, self.sum_sort_reverse)
        sub = ('%d 人 · 共 %d 笔' % (s['people'], s['count'])) if s['people'] else ''
        self.lbl_sum_sub.configure(text=sub)
        self.tv_sum.delete(*self.tv_sum.get_children())
        pcts = self._sum_pct = {}
        for row in s['rows']:
            if not (row['count'] or row['initial']):
                continue
            # 占比格子先写上纯文字：正常情况会被 Canvas 画的柱子盖住，
            # 万一列被挤得太窄、Canvas 没铺上，也还有数字可看，不至于开天窗。
            iid = self.tv_sum.insert('', 'end', values=(
                ('%d' % row['no']) if row['no'] else '—',
                row['name'], row['count'],
                '¥' + money(row['amount']),
                '%.1f%%' % row['pct'],
                row['last'] or '—'),
                tags=('empty',) if not row['count'] else ())
            pcts[iid] = float(row['pct'])
        # 表头箭头 + 右上角下拉，两边互相同步
        arrow = lambda k: (' ▼' if self.sum_sort_reverse else ' ▲') if self.sum_sort_key == k else ''
        for c, t, anc in (('no', '序号', 'center'), ('name', '成员', 'w'),
                          ('count', '笔数', 'center'),
                          ('amount', '累计充值', 'e'), ('pct', '占比', 'w'),
                          ('last', '最近充值', 'center')):
            txt = t + arrow(c)
            if str(self.tv_sum.heading(c, 'text')) != txt:
                self.tv_sum.heading(c, text=txt, anchor=anc)
        lab = sort_label_of(self.sum_sort_key, self.sum_sort_reverse, SUM_SORT_OPTIONS)
        if self.var_sum_sort.get() != lab:
            self.var_sum_sort.set(lab)
        # 行内容变了 → 柱子重画。用 after_idle 是因为此刻 ttk 还没完成布局，
        # 马上问 bbox() 拿到的还是上一轮的坐标。
        self._queue_bar_redraw()

    def _queue_bar_redraw(self):
        """排队重画占比条：同一轮里的多次请求合并成一次，滚动时别反复重画"""
        if getattr(self, '_bar_pending', False):
            return
        self._bar_pending = True

        def _run():
            self._bar_pending = False
            self.draw_pct_bars()

        try:
            self.root.after_idle(_run)
        except Exception:
            _run()

    def _on_bar_click(self, event):
        """Canvas 盖在占比格上，会拦掉 Treeview 自己的命中判定。
        这里手动把「点到了哪一行」补回去，不然点这一列选不中行。"""
        try:
            for item in self.tv_sum.get_children(''):
                bb = self.tv_sum.bbox(item, 'pct')
                if bb and bb[1] <= event.y <= bb[1] + bb[3]:
                    self.tv_sum.selection_set(item)
                    self.tv_sum.focus(item)
                    return
        except Exception:
            pass

    def draw_pct_bars(self):
        """把「占比」列画成圆角药丸条

        为什么不用字符块（原先那套 ██░░）：
        1. 块字符只能整行共用一个前景色，画出来是一排死黑的实心方块，又重又脏；
        2. `░` 比 `█` 还宽（字体回退到别的字体），按 `█` 估格子数会把末尾的
           百分号挤出列外。
        Canvas 版颜色 / 圆角 / 长度全都可控，还能跟着列宽实时伸缩。
        """
        cv = getattr(self, 'bar_canvas', None)
        if cv is None:
            return
        cv.delete('all')
        try:
            if not self.tv_sum.winfo_ismapped():
                cv.place_forget()
                return
            items = self.tv_sum.get_children('')
            rh = int(float(ttk.Style().lookup('Treeview', 'rowheight') or 27))
        except Exception:
            cv.place_forget()
            return
        if not items:
            cv.place_forget()
            return

        import tkinter.font as tkfont
        if self._bar_font is None:
            self._bar_font = tkfont.Font(font=self.F)
        tw = self._bar_font.measure('100.0%')

        boxes = []
        for item in items:
            bb = self.tv_sum.bbox(item, 'pct')
            # bbox 返回 '' = 这一行滚出可视区了；
            # 高度不足 = 被上下边缘切了一半，跳过，免得 Canvas 越过表头；
            # 列被挤得太窄也跳过 —— 格子里那行纯文字会兜底，不至于开天窗。
            if bb and bb[3] >= rh - 1 and bb[2] >= tw + 46:
                boxes.append((item, bb))
        if not boxes:
            cv.place_forget()
            return

        x0 = min(b[1][0] for b in boxes)
        y0 = min(b[1][1] for b in boxes)
        x1 = max(b[1][0] + b[1][2] for b in boxes)
        y1 = max(b[1][1] + b[1][3] for b in boxes)
        cv.place(x=x0, y=y0, width=x1 - x0, height=y1 - y0)

        pad_l, pad_r, gap = 10, 6, 10
        for n, (item, (bx, by, bw, bh)) in enumerate(boxes):
            sel = item in self.tv_sum.selection()
            lx, cy = bx - x0, by - y0 + bh // 2
            bar_h = float(max(7, min(11, bh // 3)))
            half = bar_h / 2.0
            right = lx + bw - pad_r - tw - gap      # 柱子右端（给百分号留位）
            pct = self._sum_pct.get(item, 0.0)
            if right - (lx + pad_l) >= bar_h * 2:
                # capstyle='round' 让两端自己变成半圆，药丸条不用手拼
                cv.create_line(lx + pad_l + half, cy, right - half, cy,
                               width=bar_h, capstyle='round',
                               fill=C_BAR_TRACK_SEL if sel else C_BAR_TRACK)
                reach = (right - lx - pad_l - bar_h) * pct / 100.0
                if reach > 0.5:
                    cv.create_line(lx + pad_l + half, cy, lx + pad_l + half + reach, cy,
                                   width=bar_h, capstyle='round',
                                   fill=BAR_COLORS[n % len(BAR_COLORS)])
            cv.create_text(lx + bw - pad_r, cy, text='%.1f%%' % pct, anchor='e',
                           font=self.F, fill=C_PRIMARY_D if sel else C_TEXT)

    def _on_sum_resize(self, event=None):
        """汇总表宽度变了 → 柱子长度重新算

        坑：ttk 的列宽不是立刻更新的（要过几拍布局才稳）。窗口缩小时如果
        拿「缩小前」的旧宽度去算柱子，柱子会多出小半格，末尾的百分号被切掉。
        所以这里反复算几拍，直到列宽不再变化为止。
        """
        try:
            w = self.tv_sum.winfo_width()
        except Exception:
            return
        if event is not None and abs(w - self._sum_w) < 6:
            return
        self._sum_w = w
        if getattr(self, '_sum_pending', False):
            return
        self._sum_pending = True
        self._sum_tries = 0

        def _tick():
            try:
                self.refresh_summary()
                cw = self.tv_sum.column('pct')['width']
            except Exception:
                self._sum_pending = False
                return
            self._sum_tries += 1
            last = getattr(self, '_sum_last_cw', -1)
            self._sum_last_cw = cw
            if self._sum_tries < 6 and abs(cw - last) > 3:
                try:
                    self.root.after(60, _tick)
                    return
                except Exception:
                    pass
            self._sum_pending = False

        try:
            self.root.after(60, _tick)
        except Exception:
            _tick()

    def refresh_members_box(self):
        names = list(self.store.members)
        for r in self.store.records:
            if r['member'] and r['member'] not in names:
                names.append(r['member'])
        cur = self.cb_member.get()
        self.cb_member.configure(values=names)
        if cur:
            self.cb_member.set(cur)

        opts = ['全部成员'] + [n for n in names if n] + (['(未填写)'] if any(not r['member'] for r in self.store.records) else [])
        self.cb_filter.configure(values=opts)
        if self.var_fmember.get() not in opts:
            self.var_fmember.set('全部成员')

        years = ['全部年份'] + self.store.years()
        self.cb_fyear.configure(values=years)
        if self.var_fyear.get() not in years:
            self.var_fyear.set('全部年份')
        months = ['全部月份'] + ['%d' % m for m in range(1, 13)]
        self.cb_fmonth.configure(values=months)
        if self.var_fmonth.get() not in months:
            self.var_fmonth.set('全部月份')

    def refresh_records(self):
        f = self.var_fmember.get()
        member = '' if f in ('', '全部成员') else f
        y = self.var_fyear.get()
        m = self.var_fmonth.get()
        rows = self.store.query(
            keyword=self.var_kw.get(),
            member=member,
            year='' if y in ('', '全部年份') else y,
            month='' if m in ('', '全部月份') else m,
            sort_key=self.sort_key,
            reverse=self.sort_reverse,
        )
        self.tv_rec.delete(*self.tv_rec.get_children())
        total = 0.0
        n_initial = 0
        for i, r in enumerate(rows):
            total += r['amount']
            if r.get('initial'):
                n_initial += 1
                tags = ('initial',)
            else:
                tags = ('odd',) if i % 2 else ()
            self.tv_rec.insert('', 'end', iid=r['id'],
                               values=(r['date'], r['member'] or '—',
                                       money(r['amount']), r['method'], r['note']),
                               tags=tags)
        arrow = lambda k: (' ▼' if self.sort_reverse else ' ▲') if self.sort_key == k else ''
        for c, t, anc in (('date', '日期', 'w'), ('member', '充值人', 'w'),
                          ('amount', '金额(元)', 'e'), ('method', '方式', 'w'),
                          ('note', '备注', 'w')):
            txt = t + arrow(c)
            if str(self.tv_rec.heading(c, 'text')) != txt:
                self.tv_rec.heading(c, text=txt, anchor=anc)
        if not self.store.records:
            sub = '账本是空的，先在左边记一笔吧'
        else:
            # 期初那几条只在下面的账单里露面，这里的说明就不再提它了
            sub = '当前 %d / %d 笔 · 合计 ¥%s' % (
                len(rows) - n_initial, self.store.stats()['count'], money(total))
        self.lbl_rec_sub.configure(text=sub)
        # 排序下拉跟着表格一起同步（点表头排序时也会更新）
        lab = sort_label_of(self.sort_key, self.sort_reverse)
        if self.var_sort.get() != lab:
            self.var_sort.set(lab)

    # ============ 事件 ============
    def set_today_t(self):
        self.dp_date.set_today()

    def quick_add(self, v):
        cur = num(self.e_amount.get())
        self.e_amount.delete(0, 'end')
        self.e_amount.insert(0, ('%.2f' % (cur + v)).rstrip('0').rstrip('.'))
        self.e_amount.focus_set()

    def clear_form(self):
        self.e_amount.delete(0, 'end')
        self.e_note.delete(0, 'end')
        self.cb_member.set('')
        self.set_today_t()
        self.e_member_focus()

    def e_member_focus(self):
        try:
            self.cb_member.focus_set()
        except Exception:
            pass

    def on_room_change(self, event=None):
        if self.var_room.get() != self.store.room:
            self.store.room = self.var_room.get()
            self.save_now(quiet=True)

    def add_record(self):
        member = (self.cb_member.get() or '').strip()
        amount = num(self.e_amount.get())
        date = self.dp_date.get()
        if not member:
            messagebox.showwarning('还差一步', '先写一下是谁充的喵～')
            self.e_member_focus()
            return
        if amount <= 0:
            messagebox.showwarning('还差一步', '金额要大于 0 哦～')
            self.e_amount.focus_set()
            return
        self.store.snapshot('添加记录')
        self.store.add(date, member, amount, self.cb_method.get() or '校园卡', self.e_note.get().strip())
        self.save_now()
        self.refresh_all()
        self.e_amount.delete(0, 'end')
        self.e_note.delete(0, 'end')
        self.e_amount.focus_set()
        self.lbl_saved.configure(text='已记下：%s 充了 ¥%s（Ctrl+Z 可撤销）' % (member, money(amount)))

    # ---------- 撤销 / 重做 ----------
    def do_undo(self):
        if not self.store.can_undo():
            self.lbl_saved.configure(text='没有可以撤销的操作了')
            return
        label = self.store.undo()
        self.save_now(quiet=True)
        self.refresh_all()
        self.lbl_saved.configure(text='已撤销：%s' % label)

    def do_redo(self):
        if not self.store.can_redo():
            self.lbl_saved.configure(text='没有可以重做的操作了')
            return
        label = self.store.redo()
        self.save_now(quiet=True)
        self.refresh_all()
        self.lbl_saved.configure(text='已重做：%s' % label)

    # ---------- 排序 ----------
    def on_sort_change(self):
        key, rev = SORT_MAP.get(self.var_sort.get(), ('date', True))
        self.sort_key, self.sort_reverse = key, rev
        self.refresh_records()

    def sort_by(self, key):
        if self.sort_key == key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_key = key
            self.sort_reverse = (key != 'member')
        self.refresh_records()

    def on_sum_sort_change(self):
        key, rev = SUM_SORT_MAP.get(self.var_sum_sort.get(), ('no', False))
        self.sum_sort_key, self.sum_sort_reverse = key, rev
        self.refresh_summary()

    def sum_sort_by(self, key):
        """点「每个人分别充了多少」的表头排序；再点一次换方向

        编号是每人固定的，排序只挪行的先后 —— 所以按笔数排完，
        序号那一列就是乱序的，这正说明它是固定 id。
        """
        if self.sum_sort_key == key:
            self.sum_sort_reverse = not self.sum_sort_reverse
        else:
            self.sum_sort_key = key
            self.sum_sort_reverse = key in ('count', 'amount', 'last')
        self.refresh_summary()

    def reset_filter(self):
        self.var_kw.set('')
        self.var_fmember.set('全部成员')
        self.var_fyear.set('全部年份')
        self.var_fmonth.set('全部月份')
        self.refresh_records()

    def selected_ids(self):
        return list(self.tv_rec.selection())

    def edit_selected(self):
        ids = self.selected_ids()
        if not ids:
            messagebox.showinfo('提示', '先在下面的明细里选一行，再点「编辑选中」')
            return
        self.open_edit(ids[0])

    def delete_selected(self):
        ids = self.selected_ids()
        if not ids:
            messagebox.showinfo('提示', '先选中要删的记录（可按 Ctrl / Shift 多选）')
            return
        has_initial = any((self.store.get(i) or {}).get('initial') for i in ids)
        if len(ids) == 1:
            r = self.store.get(ids[0])
            msg = '要把这条记录移入回收站吗？\n\n%s  %s  ¥%s%s\n\n' % (
                r['date'], r['member'] or '—', money(r['amount']),
                ('  （%s）' % r['note']) if r['note'] else '')
            msg += '放心，只是挪到回收站，随时能恢复，Ctrl+Z 也能撤销。'
        else:
            msg = '要把选中的 %d 条记录移入回收站吗？\n\n' % len(ids)
            msg += '放心，只是挪到回收站，随时能恢复。'
        if has_initial:
            msg += '\n\n⚠️ 里面有「期初」记录，它虽然不算笔数，但金额是算进总账的。'
        if not messagebox.askyesno('移入回收站', msg):
            return
        self.store.snapshot('移入回收站 %d 条' % len(ids))
        n = self.store.delete_many(ids)
        self.save_now(quiet=True)
        self.refresh_all()
        self.lbl_saved.configure(text='已移入回收站 %d 条（可恢复 / Ctrl+Z 撤销）' % n)

    # ---------- 回收站 ----------
    def open_trash(self):
        win = tk.Toplevel(self.root)
        win.title('回收站')
        win.configure(bg=C_CARD)
        win.geometry('%dx%d' % (int(760 * self.ui_scale), int(430 * self.ui_scale)))
        win.transient(self.root)

        body = tk.Frame(win, bg=C_CARD)
        body.pack(fill='both', expand=True, padx=16, pady=14)
        tk.Label(body, text='删掉的记录都先放这儿，可以随时恢复；彻底删除才真的没了。',
                 bg=C_CARD, fg=C_MUTED, font=self.F_SMALL).pack(anchor='w')
        lbl_cnt = tk.Label(body, text='', bg=C_CARD, fg=C_TEXT, font=self.FB)
        lbl_cnt.pack(anchor='w', pady=(6, 6))

        wrap = tk.Frame(body, bg=C_CARD)
        wrap.pack(fill='both', expand=True)
        cols = ('dt', 'date', 'member', 'amount', 'method', 'note')
        tv = ttk.Treeview(wrap, columns=cols, show='headings', selectmode='extended')
        names = [m for m in self.store.members if m] or ['充值人']
        self.fit_columns(tv, [
            ('dt', '删除时间', 'center', ['2026-09-23 22:01'], False),
            ('date', '日期', 'w', ['2026-09-18'], False),
            ('member', '充值人', 'w', [max(names, key=len), '(未填写)'], False),
            ('amount', '金额(元)', 'e', ['1,234.00'], False),
            ('method', '方式', 'w', [max(METHODS, key=len)], False),
            ('note', '备注', 'w', ['备注'], True),
        ], arrow=False)          # 回收站这张表不能点排序，不用给箭头留位置
        sb = ttk.Scrollbar(wrap, orient='vertical', command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        def reload():
            tv.delete(*tv.get_children())
            items = self.store.trash()
            lbl_cnt.configure(text='回收站里共 %d 条' % len(items))
            for i, r in enumerate(items):
                dt = r.get('deletedAt')
                dts = datetime.fromtimestamp(dt / 1000.0).strftime('%Y-%m-%d %H:%M') if dt else ''
                tv.insert('', 'end', iid=r['id'],
                          values=(dts, r['date'], r['member'] or '—', money(r['amount']),
                                  r['method'], r['note']),
                          tags=('odd',) if i % 2 else ())
            tv.tag_configure('odd', background=C_ROW_ALT)

        def sel():
            return list(tv.selection())

        def do_restore():
            ids = sel()
            if not ids:
                messagebox.showinfo('提示', '先选中要恢复的记录', parent=win)
                return
            self.store.snapshot('恢复 %d 条' % len(ids))
            n = self.store.restore(ids)
            self.save_now(quiet=True)
            self.refresh_all()
            reload()
            self.lbl_saved.configure(text='已从回收站恢复 %d 条' % n)

        def do_purge():
            ids = sel()
            if not ids:
                messagebox.showinfo('提示', '先选中要彻底删除的记录', parent=win)
                return
            if not messagebox.askyesno(
                    '彻底删除',
                    '这 %d 条将被永久删除，之后没法恢复（Ctrl+Z 也救不回来了）。\n\n确定吗？'
                    % len(ids), parent=win):
                return
            self.store.snapshot('彻底删除 %d 条' % len(ids))
            n = self.store.purge(ids)
            self.save_now(quiet=True)
            self.refresh_all()
            reload()
            self.lbl_saved.configure(text='已彻底删除 %d 条' % n)

        def do_empty():
            if not self.store.deleted:
                return
            if not messagebox.askyesno(
                    '清空回收站',
                    '要把回收站里的 %d 条全部永久删除吗？之后没法恢复。' % len(self.store.deleted),
                    parent=win):
                return
            self.store.snapshot('清空回收站')
            n = self.store.purge_all()
            self.save_now(quiet=True)
            self.refresh_all()
            reload()
            self.lbl_saved.configure(text='已清空回收站（%d 条）' % n)

        btns = tk.Frame(body, bg=C_CARD)
        btns.pack(fill='x', pady=(10, 0))
        self.mkbtn(btns, '恢复选中', do_restore, 'primary').pack(side='left', ipady=2)
        self.mkbtn(btns, '彻底删除', do_purge, 'danger').pack(side='left', padx=6, ipady=2)
        self.mkbtn(btns, '清空回收站', do_empty, 'plain').pack(side='left', ipady=2)
        self.mkbtn(btns, '关闭', win.destroy, 'plain').pack(side='right', ipady=2)
        tv.bind('<Double-1>', lambda e: do_restore())

        reload()
        self._center(win)
        win.grab_set()

    # ---------- 编辑弹窗 ----------
    def open_edit(self, rid):
        r = self.store.get(rid)
        if not r:
            return
        win = tk.Toplevel(self.root)
        win.title('编辑记录')
        win.configure(bg=C_CARD)
        win.resizable(False, False)
        win.transient(self.root)

        body = tk.Frame(win, bg=C_CARD)
        body.pack(fill='both', expand=True, padx=18, pady=16)

        vars_ = {
            'member': tk.StringVar(value=r['member']),
            'amount': tk.StringVar(value=('%.2f' % r['amount']).rstrip('0').rstrip('.')),
            'method': tk.StringVar(value=r['method']),
            'note': tk.StringVar(value=r['note']),
        }
        var_initial = tk.BooleanVar(value=bool(r.get('initial')))
        drow = tk.Frame(body, bg=C_CARD)
        drow.pack(fill='x', pady=4)
        tk.Label(drow, text='日期', bg=C_CARD, fg=C_MUTED, font=self.F_SMALL,
                 width=8, anchor='w').pack(side='left')
        dp = DatePicker(drow, bg=C_CARD, font=self.F)
        dp.pack(side='left')
        dp.set(r['date'])

        rows = [
            ('谁充的', 'member', 'combo'),
            ('金额(元)', 'amount', 'entry'),
            ('支付方式', 'method', 'combo_method'),
            ('备注', 'note', 'entry'),
        ]
        for label, key, kind in rows:
            row = tk.Frame(body, bg=C_CARD)
            row.pack(fill='x', pady=4)
            tk.Label(row, text=label, bg=C_CARD, fg=C_MUTED, font=self.F_SMALL,
                     width=8, anchor='w').pack(side='left')
            if kind == 'combo':
                w = ttk.Combobox(row, textvariable=vars_[key], font=self.F, width=26,
                                 values=list(self.cb_member.cget('values')))
            elif kind == 'combo_method':
                w = ttk.Combobox(row, textvariable=vars_[key], font=self.F, width=26,
                                 values=METHODS, state='readonly')
            else:
                w = self.mkentry(row, textvariable=vars_[key], width=28)
            w.pack(side='left', fill='x', expand=True, ipady=3)

        irow = tk.Frame(body, bg=C_CARD)
        irow.pack(fill='x', pady=(6, 0))
        tk.Label(irow, text='', bg=C_CARD, width=8).pack(side='left')
        tk.Checkbutton(irow, text='这条是「期初」（金额照算，但不计入充值笔数）',
                       variable=var_initial, bg=C_CARD, fg=C_TEXT, font=self.F_SMALL,
                       activebackground=C_CARD, selectcolor=C_CARD,
                       highlightthickness=0, cursor='hand2',
                       anchor='w').pack(side='left')

        def do_save(event=None):
            m = vars_['member'].get().strip()
            a = num(vars_['amount'].get())
            d = dp.get()
            if not m:
                messagebox.showwarning('提示', '谁充的不能空着喵', parent=win)
                return
            if a <= 0:
                messagebox.showwarning('提示', '金额要大于 0 哦', parent=win)
                return
            self.store.snapshot('修改记录')
            self.store.update(rid, date=d, member=m, amount=a,
                              method=vars_['method'].get() or '校园卡',
                              note=vars_['note'].get().strip(),
                              initial=bool(var_initial.get()))
            self.save_now()
            self.refresh_all()
            win.destroy()
            self.lbl_saved.configure(text='已保存修改（Ctrl+Z 可撤销）')

        btns = tk.Frame(body, bg=C_CARD)
        btns.pack(fill='x', pady=(14, 0))
        self.mkbtn(btns, '保存修改', do_save, 'primary').pack(side='right', ipady=2)
        self.mkbtn(btns, '取消', win.destroy, 'plain').pack(side='right', padx=(0, 8), ipady=2)
        win.bind('<Return>', do_save)
        win.bind('<Escape>', lambda e: win.destroy())
        self._center(win)
        win.grab_set()

    # ---------- 成员管理 ----------
    def open_members(self):
        win = tk.Toplevel(self.root)
        win.title('成员管理')
        win.configure(bg=C_CARD)
        win.geometry('%dx%d' % (int(420 * self.ui_scale), int(430 * self.ui_scale)))
        win.transient(self.root)

        body = tk.Frame(win, bg=C_CARD)
        body.pack(fill='both', expand=True, padx=18, pady=16)

        add = tk.Frame(body, bg=C_CARD)
        add.pack(fill='x')
        tk.Label(add, text='新增成员', bg=C_CARD, fg=C_MUTED, font=self.F_SMALL).pack(anchor='w')
        row = tk.Frame(add, bg=C_CARD)
        row.pack(fill='x', pady=(4, 10))
        var_new = tk.StringVar()
        ent = self.mkentry(row, textvariable=var_new, width=20)
        ent.pack(side='left', fill='x', expand=True, ipady=4)
        ent.focus_set()

        tk.Label(body, text='成员列表（前面的数字是固定编号，双击改名）', bg=C_CARD, fg=C_MUTED,
                 font=self.F_SMALL).pack(anchor='w')
        listwrap = tk.Frame(body, bg=C_CARD)
        listwrap.pack(fill='both', expand=True, pady=(4, 10))
        lb = tk.Listbox(listwrap, font=self.F, relief='flat', bg='#f7f9fb',
                        highlightthickness=1, highlightbackground=C_LINE,
                        selectbackground=C_PRIMARY_L, selectforeground=C_PRIMARY_D,
                        activestyle='none')
        sb = ttk.Scrollbar(listwrap, orient='vertical', command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        def reload_list():
            lb.delete(0, 'end')
            for m in self.store.members:
                no = self.store.member_no(m)
                lb.insert('end', '%s. %s    （%d 笔）'
                          % (('%d' % no) if no else '—', m, self.store.count_of(m)))

        def do_add(event=None):
            v = var_new.get().strip()
            if not v:
                return
            if v in self.store.members:
                messagebox.showwarning('提示', '这个成员已经有啦', parent=win)
                return
            self.store.snapshot('新增成员')
            self.store.members.append(v)
            self.save_now()
            var_new.set('')
            reload_list()
            self.refresh_all()

        def do_rename(event=None):
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            old = self.store.members[idx]
            dlg = tk.Toplevel(win)
            dlg.title('改名')
            dlg.configure(bg=C_CARD)
            dlg.transient(win)
            dlg.resizable(False, False)
            f = tk.Frame(dlg, bg=C_CARD)
            f.pack(padx=16, pady=14)
            tk.Label(f, text='把「%s」改成：' % old, bg=C_CARD, fg=C_TEXT,
                     font=self.F).pack(anchor='w')
            v = tk.StringVar(value=old)
            e = self.mkentry(f, textvariable=v, width=24)
            e.pack(fill='x', pady=8, ipady=4)
            e.focus_set()
            e.select_range(0, 'end')

            def ok(ev=None):
                new = v.get().strip()
                if not new or new == old:
                    dlg.destroy()
                    return
                if new in self.store.members:
                    messagebox.showwarning('提示', '已经有一个叫「%s」的成员了' % new, parent=dlg)
                    return
                self.store.snapshot('成员改名')
                try:
                    n = self.store.rename_member(old, new)
                except ValueError as ex:
                    self.store.discard_snapshot()
                    messagebox.showwarning('提示', str(ex), parent=dlg)
                    return
                self.save_now()
                reload_list()
                self.refresh_all()
                dlg.destroy()
                self.lbl_saved.configure(text='「%s」→「%s」，同步 %d 条记录' % (old, new, n))

            e.bind('<Return>', ok)
            dlg.bind('<Escape>', lambda ev: dlg.destroy())
            self.mkbtn(f, '确定', ok, 'primary').pack(side='right', ipady=2)
            self.mkbtn(f, '取消', dlg.destroy, 'plain').pack(side='right', padx=(0, 8), ipady=2)
            self._center(dlg, win)
            dlg.grab_set()

        def do_del(event=None):
            sel = lb.curselection()
            if not sel:
                return
            name = self.store.members[sel[0]]
            cnt = self.store.count_of(name)
            msg = '确定删除成员「%s」吗？' % name
            if cnt:
                msg += '\n\nTA 的 %d 条充值记录会一起移入回收站（可以恢复 / Ctrl+Z 撤销）。' % cnt
            if not messagebox.askyesno('删除确认', msg, parent=win):
                return
            self.store.snapshot('删除成员')
            n = self.store.remove_member(name, with_records=True)
            self.save_now(quiet=True)
            reload_list()
            self.refresh_all()
            self.lbl_saved.configure(
                text='已删除成员「%s」%s' % (name, '，其 %d 条记录已入回收站' % n if n else ''))

        lb.bind('<Double-1>', do_rename)
        ent.bind('<Return>', do_add)

        btns = tk.Frame(body, bg=C_CARD)
        btns.pack(fill='x')
        self.mkbtn(btns, '添加', do_add, 'primary').pack(side='left', ipady=2)
        self.mkbtn(btns, '改名', do_rename, 'soft').pack(side='left', padx=6, ipady=2)
        self.mkbtn(btns, '删除', do_del, 'danger').pack(side='left', ipady=2)
        self.mkbtn(btns, '完成', win.destroy, 'plain').pack(side='right', ipady=2)

        reload_list()
        self._center(win)

    # ---------- 导入导出 ----------
    def export_csv(self):
        if not self.store.records:
            messagebox.showinfo('提示', '账本还是空的，没有可导出的内容喵')
            return
        name = (self.store.room or '电费记账').replace('/', '_') + '_' + now_stamp() + '.csv'
        path = filedialog.asksaveasfilename(
            parent=self.root, title='导出 CSV', defaultextension='.csv',
            initialfile=name, initialdir=app_dir(),
            filetypes=[('CSV 表格', '*.csv'), ('所有文件', '*.*')])
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                f.write(self.store.csv_text())
        except Exception as e:
            messagebox.showerror('导出失败', str(e))
            return
        self.lbl_saved.configure(text='CSV 已导出')
        if messagebox.askyesno('导出成功', 'CSV 已保存到：\n%s\n\n现在用 Excel 打开看看吗？' % path):
            self._open_path(path)

    def export_json(self):
        name = (self.store.room or '电费记账').replace('/', '_') + '_' + now_stamp() + '.json'
        path = filedialog.asksaveasfilename(
            parent=self.root, title='导出账本备份', defaultextension='.json',
            initialfile=name, initialdir=app_dir(),
            filetypes=[('JSON 数据', '*.json'), ('所有文件', '*.*')])
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.store.payload(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror('导出失败', str(e))
            return
        self.lbl_saved.configure(text='JSON 备份已导出')
        messagebox.showinfo('导出成功', '备份已保存到：\n%s' % path)

    # ---------- 导出：txt / xlsx ----------
    def export_dir(self):
        """一键导出落盘的目录（程序旁边的「导出」文件夹）"""
        return os.path.join(app_dir(), EXPORT_DIR)

    def _export_stem(self):
        base = (self.store.room or '电费记账')
        for ch in '/\\:*?"<>|':
            base = base.replace(ch, '_')
        return '%s_%s' % (base.strip() or '电费记账', now_stamp())

    def _export_one(self, ext, writer, title, filetypes):
        """另存为单个文件；writer(path) 负责真正写盘"""
        if not self.store.records:
            messagebox.showinfo('提示', '账本还是空的，没有可导出的内容喵')
            return
        d = self.export_dir()
        path = filedialog.asksaveasfilename(
            parent=self.root, title=title, defaultextension=ext,
            initialfile=self._export_stem() + ext,
            initialdir=d if os.path.isdir(d) else app_dir(),
            filetypes=filetypes)
        if not path:
            return
        try:
            writer(path)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror('导出失败', str(e))
            return
        self.lbl_saved.configure(text='%s 已导出' % ext.lstrip('.').upper())
        if messagebox.askyesno('导出成功', '已保存到：\n%s\n\n现在打开看看吗？' % path):
            self._open_path(path)

    def export_txt(self):
        def write(path):
            with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                f.write(self.store.txt_text())
        self._export_one('.txt', write, '导出文本账本',
                         [('文本文件', '*.txt'), ('所有文件', '*.*')])

    def export_xlsx(self):
        def write(path):
            with open(path, 'wb') as f:
                f.write(self.store.xlsx_bytes())
        self._export_one('.xlsx', write, '导出 Excel 表格',
                         [('Excel 工作簿', '*.xlsx'), ('所有文件', '*.*')])

    def export_all(self):
        """一键导出：txt + xlsx 一起落到程序旁的「导出」文件夹，不弹另存为"""
        if not self.store.records:
            messagebox.showinfo('提示', '账本还是空的，没有可导出的内容喵')
            return
        d = self.export_dir()
        stem = self._export_stem()
        made = []
        try:
            os.makedirs(d, exist_ok=True)
            p_txt = os.path.join(d, stem + '.txt')
            with open(p_txt, 'w', encoding='utf-8-sig', newline='') as f:
                f.write(self.store.txt_text())
            made.append(p_txt)
            p_xlsx = os.path.join(d, stem + '.xlsx')
            with open(p_xlsx, 'wb') as f:
                f.write(self.store.xlsx_bytes())
            made.append(p_xlsx)
        except Exception as e:
            traceback.print_exc()
            left = '\n'.join(os.path.basename(x) for x in made) or '（无）'
            messagebox.showerror('导出失败', '%s\n\n已经写出来的文件：%s' % (e, left))
            return
        self.lbl_saved.configure(text='已导出 2 个文件')
        names = '\n'.join('  · ' + os.path.basename(x) for x in made)
        if messagebox.askyesno(
                '一键导出完成',
                '已导出 2 个文件到：\n%s\n\n%s\n\n现在打开 Excel 表格吗？'
                % (d, names)):
            self._open_path(made[1])

    def import_json(self):
        path = filedialog.askopenfilename(
            parent=self.root, title='选择要导入的账本文件',
            filetypes=[('JSON 数据', '*.json'), ('所有文件', '*.*')])
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror('导入失败', '文件读取失败：%s' % e)
            return
        recs = data.get('records') if isinstance(data, dict) else None
        if recs is None:
            messagebox.showerror('导入失败', '这个文件里没有找到记录数据（records）')
            return
        if not self.store.records and not self.store.members:
            replace = True
        else:
            ans = messagebox.askyesnocancel(
                '导入方式',
                '文件里有 %d 条记录，当前账本有 %d 条记录。\n\n'
                '「是」= 合并（两边都保留，按 id 去重）\n'
                '「否」= 覆盖（用文件内容替换当前账本）\n'
                '「取消」= 不导入' % (len(recs), len(self.store.records)))
            if ans is None:
                return
            replace = not ans
        try:
            self.store.snapshot('导入账本')
            self.store.apply(data, replace=replace)
        except Exception as e:
            self.store.discard_snapshot()
            messagebox.showerror('导入失败', str(e))
            return
        ok, err = self.store.save()
        self.var_room.set(self.store.room)
        self.refresh_all()
        self.lbl_saved.configure(text='已导入 %d 条记录' % len(recs))
        if not ok:
            messagebox.showwarning('提示', '数据已载入，但保存到文件失败：%s' % err)

    # ---------- 局域网同步 ----------
    def open_lan_sync(self):
        """手机同步面板：开关服务、看地址和配对码、看上次同步结果"""
        win = tk.Toplevel(self.root)
        win.title('手机同步 · 局域网')
        win.configure(bg=C_BG)
        win.transient(self.root)
        win.resizable(False, False)

        card = tk.Frame(win, bg=C_CARD, highlightbackground=C_LINE, highlightthickness=1)
        card.pack(fill='both', expand=True, padx=14, pady=14)

        tk.Label(card, text='让手机跟这台电脑对账', bg=C_CARD, fg=C_TEXT,
                 font=self.F_SECTION, anchor='w').pack(fill='x', padx=16, pady=(14, 6))
        tk.Label(card, justify='left', anchor='w', bg=C_CARD, fg=C_MUTED,
                 font=self.F_SMALL,
                 text=('1. 手机和电脑连同一个 WiFi\n'
                       '2. 点下面「启动服务」\n'
                       '3. 手机上进「设置 → 电脑同步」，填这里的地址和配对码\n\n'
                       '数据只在局域网里跑，不上传任何服务器；关掉窗口就断。\n'
                       '第一次启动若弹出 Windows 防火墙提示，请选「允许访问」，\n'
                       '否则手机会连不上（专用网络打勾即可）。')
                 ).pack(fill='x', padx=16, pady=(0, 12))

        # —— 地址 / 配对码 ——
        box = tk.Frame(card, bg=C_PRIMARY_L)
        box.pack(fill='x', padx=16, pady=(0, 10))
        tk.Label(box, text='服务地址', bg=C_PRIMARY_L, fg=C_MUTED,
                 font=self.F_SMALL, anchor='w').pack(fill='x', padx=14, pady=(10, 0))
        lbl_addr = tk.Label(box, text='（未启动）', bg=C_PRIMARY_L, fg=C_PRIMARY_D,
                            font=self.F_BIG, anchor='w')
        lbl_addr.pack(fill='x', padx=14)
        tk.Label(box, text='配对码', bg=C_PRIMARY_L, fg=C_MUTED,
                 font=self.F_SMALL, anchor='w').pack(fill='x', padx=14, pady=(8, 0))
        lbl_pair = tk.Label(box, text='————', bg=C_PRIMARY_L, fg=C_PRIMARY_D,
                            font=self.F_BIG, anchor='w')
        lbl_pair.pack(fill='x', padx=14, pady=(0, 10))

        lbl_hint = tk.Label(card, text='', bg=C_CARD, fg=C_MUTED, font=self.F_SMALL,
                            anchor='w', justify='left', wraplength=380)
        lbl_hint.pack(fill='x', padx=16, pady=(0, 8))

        btns = tk.Frame(card, bg=C_CARD)
        btns.pack(fill='x', padx=16, pady=(0, 14))
        btn_toggle = self.mkbtn(btns, '启动服务', None, 'primary', font=self.FB)

        def refresh():
            running = self.sync.running()
            if running:
                lbl_addr.configure(text=self.sync.url())
                lbl_pair.configure(text=self.sync.pair)
                btn_toggle.configure(text='停止服务')
            else:
                lbl_addr.configure(text='（未启动）')
                lbl_pair.configure(text=self.sync.pair or '————')
                btn_toggle.configure(text='启动服务')
            note = self.sync.last
            if note:
                lbl_hint.configure(text='最近一次：' + note)

        def toggle():
            if self.sync.running():
                self.sync.stop()
                self.sync.last = '服务已停止'
            else:
                ok, msg = self.sync.start()
                self.sync.last = msg if ok else ('启动失败：%s' % msg)
            refresh()

        btn_toggle.configure(command=toggle)
        btn_toggle.pack(side='left', ipady=2)
        self.mkbtn(btns, '换个配对码', lambda: (self.sync.new_pair(), refresh()),
                   'soft').pack(side='left', padx=6, ipady=2)
        self.mkbtn(btns, '复制地址',
                   lambda: self._copy(self.sync.url() if self.sync.running() else ''),
                   'plain').pack(side='left', ipady=2)
        self.mkbtn(btns, '关闭', win.destroy, 'plain').pack(side='right', ipady=2)

        refresh()
        self._center(win, self.root)
        win.grab_set()

    def _copy(self, text):
        if not text or text == '（未启动）':
            messagebox.showinfo('提示', '服务还没启动，没有可复制的地址')
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.lbl_saved.configure(text='地址已复制到剪贴板')

    def copy_report(self):
        if not self.store.records:
            messagebox.showinfo('提示', '还没有记录，没什么好结算的喵')
            return
        text = self.store.report_text()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.lbl_saved.configure(text='结算单已复制，去群里粘贴吧')
        messagebox.showinfo('已复制', '结算单已复制到剪贴板，直接粘贴到群里就行：\n\n' + text)

    def open_folder(self):
        d = os.path.dirname(self.store.path)
        self._open_path(d)

    def open_data_file(self):
        self._open_path(self.store.path)

    def _open_path(self, p):
        try:
            if os.name == 'nt':
                os.startfile(p)  # noqa
            else:
                import subprocess
                subprocess.Popen(['xdg-open', p])
        except Exception as e:
            messagebox.showerror('打不开', str(e))

    # ---------- 保存 ----------
    def save_now(self, quiet=False):
        ok, err = self.store.save()
        if ok:
            self.lbl_saved.configure(text='已保存 ' + datetime.now().strftime('%H:%M:%S'))
            if quiet:
                self.root.after(1500, lambda: self.lbl_saved.configure(text=''))
        else:
            self.lbl_saved.configure(text='保存失败')
            messagebox.showerror('保存失败', '数据没能写入文件：\n%s' % err)

    # ---------- 通用 ----------
    def _center(self, win, parent=None):
        parent = parent or self.root
        win.update_idletasks()
        w, h = win.winfo_width(), win.winfo_height()
        if w <= 1 or h <= 1:
            w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 3
        win.geometry('+%d+%d' % (max(0, x), max(0, y)))

    def on_close(self):
        self.on_room_change()
        try:
            self.sync.stop()
        except Exception:
            traceback.print_exc()
        ok, err = self.store.save()
        if not ok:
            if not messagebox.askyesno(
                    '没能保存',
                    '数据没能写入文件：\n%s\n\n还想关闭吗？\n'
                    '选「否」可以留在窗口里，先把数据导出/另存一份。' % err):
                return
        self.root.destroy()


# ============================================================
# 入口
# ============================================================
def enable_dpi():
    try:
        from ctypes import windll
        try:
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def run_gui():
    enable_dpi()
    path = resolve_data_path()
    store = Store(path)
    root = tk.Tk()

    def report_callback(exc_type, exc, tb):
        msg = ''.join(traceback.format_exception(exc_type, exc, tb))
        try:
            with open(os.path.join(app_dir(), '运行错误日志.txt'), 'a', encoding='utf-8') as f:
                f.write('[%s]\n%s\n' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg))
        except Exception:
            pass
        try:
            messagebox.showerror('出错了', msg[-1200:])
        except Exception:
            pass

    root.report_callback_exception = report_callback
    sys.excepthook = report_callback
    App(root, store)
    root.mainloop()


if __name__ == '__main__':
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')
    run_gui()
