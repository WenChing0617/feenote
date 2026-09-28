# -*- coding: utf-8 -*-
"""把「电费.txt」（累计总额格式）解析成程序用的 电费记账数据.json

原始格式：每 7 行为一次记录
    第 1 行  ：日期（如 9.9 / 12.20；单独一行 "26年" 表示年份切到 2026）
    第 2~7 行：1~6 号床铺的【累计充值总额】，行尾带 * 表示本次是这个人充的

本次充值金额 = 本组数值 - 上一组数值
第一组（开学第一次，原始表首行）也算一笔，视作从 0 起算，
但它带上 initial=True —— 金额算进总账，但不占「充值笔数」。
"""
import json
import os
import re
import uuid
from datetime import datetime

SRC = r'D:\文件\文件\电费.txt'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'dist', '电费记账数据.json')

START_YEAR = 2025
SKIP_BEDS = {4}          # 4 号床已注销，不参与
MEMBER_FMT = '%d号床'
# 首组（2025-09-09 开学第一次）也算一笔充值，视作从 0 起算。
# 这样每人的累计充值 = 原始表最后一行的数值（已逐床铺核对一致）。
# 它会被标记成「期初」：钱算进总账，但不计入充值笔数。
COUNT_FIRST = True

DATE_RE = re.compile(r'^(\d{1,2})\s*[.．]\s*(\d{1,2})$')
YEAR_RE = re.compile(r'^(\d{2,4})\s*年$')
NUM_RE = re.compile(r'(\d+)')


def parse_groups(text):
    """按行解析成若干组：{'date': 'YYYY-MM-DD', 'vals': [6], 'stars': [6], 'raw': [...]}"""
    year = START_YEAR
    groups = []
    cur = None
    warnings = []

    for lineno, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue

        m = YEAR_RE.match(line)
        if m:
            y = int(m.group(1))
            year = y if y > 100 else 2000 + y
            continue

        m = DATE_RE.match(line)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            cur = {
                'date': '%04d-%02d-%02d' % (year, month, day),
                'vals': [],
                'stars': [],
                'raw': [],
                'line': lineno,
            }
            groups.append(cur)
            continue

        if cur is None:
            warnings.append('第 %d 行「%s」出现在任何日期之前，已忽略' % (lineno, line))
            continue

        num = NUM_RE.search(line)
        if not num:
            warnings.append('第 %d 行「%s」无法识别，已忽略' % (lineno, line))
            continue
        cur['vals'].append(int(num.group(1)))
        cur['stars'].append('*' in line)
        cur['raw'].append(line)

    for g in groups:
        if len(g['vals']) != 6:
            warnings.append('%s（第 %d 行起）只有 %d 个床铺数据，期望 6 个'
                            % (g['date'], g['line'], len(g['vals'])))
            while len(g['vals']) < 6:
                g['vals'].append(0)
                g['stars'].append(False)
    return groups, warnings


def build(groups):
    """逐组比较，生成充值记录

    第一组（9.9 开学第一次）也算一笔 —— 视作从 0 起算，
    金额同样入账，但会打上「期初」标记（不算充值笔数）。
    这样每人的累计充值才会正好等于原始表最后一行的数值。
    """
    records = []
    seq = 0
    notes = []
    for i in range(0 if COUNT_FIRST else 1, len(groups)):
        cur = groups[i]
        prev = groups[i - 1] if i > 0 else {'vals': [0] * 6, 'stars': [False] * 6}
        for bed in range(6):
            no = bed + 1
            if no in SKIP_BEDS:
                continue
            delta = cur['vals'][bed] - prev['vals'][bed]
            if delta <= 0:
                continue
            if i > 0 and not cur['stars'][bed]:
                notes.append('%s 的 %d 号床 +%d，原始数据里没有 * 标记（按数值变化推断为 TA 充入）'
                             % (cur['date'], no, delta))
            seq += 1
            records.append({
                'id': uuid.uuid4().hex[:12],
                'date': cur['date'],
                'member': MEMBER_FMT % no,
                'amount': float(delta),
                'method': '校园卡',
                'note': ('期初首笔（原始表首行，无 * 标记）' if i == 0 else ''),
                'createdAt': 1767000000000 + seq,
                'initial': (i == 0),
            })
    return records, notes


def main():
    with open(SRC, 'r', encoding='utf-8') as f:
        text = f.read()

    groups, warnings = parse_groups(text)
    records, notes = build(groups)

    members = [MEMBER_FMT % i for i in range(1, 7) if i not in SKIP_BEDS]
    # 每人一个固定编号（按床号顺序发：1 号床=1、2 号床=2、3 号床=3、5 号床=4、6 号床=5）
    member_ids = {m: idx + 1 for idx, m in enumerate(members)}

    data = {
        'app': '电费记账本',
        'version': '1.1',
        'room': '',
        'members': members,
        'memberIds': member_ids,
        'records': records,
        'deleted': [],
        'savedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # ---- 核对报告 ----
    n_init = sum(1 for r in records if r.get('initial'))
    print('解析到 %d 组数据（%s ~ %s）' % (len(groups), groups[0]['date'], groups[-1]['date']))
    print('生成充值记录 %d 笔（其中期初 %d 条，只入账不计笔数）\n' % (len(records), n_init))

    print('每次充值明细：')
    by_date = {}
    for r in records:
        by_date.setdefault(r['date'], []).append(r)
    for d in sorted(by_date):
        items = by_date[d]
        tot = sum(x['amount'] for x in items)
        tag = '  [期初]' if all(x.get('initial') for x in items) else ''
        print('  %s  共 ¥%-6.0f  %s%s' % (
            d, tot, '、'.join('%s ¥%.0f' % (x['member'], x['amount']) for x in items), tag))

    print('\n固定编号：' + '、'.join('%s = %d' % (m, member_ids[m]) for m in members))

    print('\n每人累计：')
    per = {}
    for r in records:
        per[r['member']] = per.get(r['member'], 0) + r['amount']
    total = sum(per.values())
    for m in sorted(per, key=lambda x: -per[x]):
        print('  %-8s ¥%8.2f' % (m, per[m]))
    print('  %-8s ¥%8.2f' % ('合计', total))

    # 核心对账：每人明细累计 是否等于 原始表最后一行的数值
    print('\n对账（程序算出的每人累计 ↔ 原始表最后一行）：')
    last = groups[-1]
    for bed in range(6):
        no = bed + 1
        if no in SKIP_BEDS:
            continue
        want = last['vals'][bed]
        got = per.get(MEMBER_FMT % no, 0)
        ok = abs(want - got) < 0.001
        print('  %-8s 程序合计 %-7.0f 原始表末行 %-5d  %s'
              % (MEMBER_FMT % no, got, want, '一致' if ok else '不一致!'))
    keep_total = sum(v for b, v in enumerate(last['vals']) if (b + 1) not in SKIP_BEDS)
    print('  %-8s 程序合计 %-7.0f 原始表末行 %-5d  %s'
          % ('合计', total, keep_total, '一致' if abs(total - keep_total) < 0.001 else '不一致!'))
    other = sum(v for b, v in enumerate(last['vals']) if (b + 1) in SKIP_BEDS)
    if other:
        print('  （另有已注销的 4 号床 %d，按约定不计入；如需计入，合计应为 %d）'
              % (other, keep_total + other))

    if warnings:
        print('\n注意：')
        for w in warnings:
            print('  ! ' + w)
    if notes:
        print('\n提示：')
        for n in notes:
            print('  · ' + n)
    print('\n已写入: %s' % OUT)


if __name__ == '__main__':
    main()
