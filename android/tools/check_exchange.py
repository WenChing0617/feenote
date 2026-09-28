# -*- coding: utf-8 -*-
"""校验手机版导出的账本 JSON 能不能被桌面版正确吸收。

关键点：这里**直接 import 桌面版自己的模块**、用它的 `Store.apply()` 来做合并，
而不是复刻一份逻辑 —— 否则就变成「自己证明自己」。

用法：
    python tools/check_exchange.py [手机导出的 json]
不带参数时，按顺序找这两个位置：
    1. app/build/exchange-test/phone_export.json  （跑过 testDebugUnitTest 后自动生成的）
    2. tools/sample_phone_export.json             （随工程附带的样本，由真实 Kotlin 代码生成）
"""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(HERE)
PHONE_EXPORT_CANDIDATES = [
    os.path.join(APP_DIR, 'app', 'build', 'exchange-test', 'phone_export.json'),
    os.path.join(HERE, 'sample_phone_export.json'),
]


def _find_desktop():
    """定位桌面版工程目录。不写死绝对路径，两种常见布局都能自动找到。

    也可以用环境变量覆盖：FEENOTE_DESKTOP=<桌面版目录>
    """
    env = os.environ.get('FEENOTE_DESKTOP')
    if env:
        return env
    parent = os.path.dirname(APP_DIR)
    for cand in (
        # 本仓库布局：android/ 和 desktop/ 是兄弟目录
        os.path.join(parent, 'desktop'),
        # 两个工程并排放的布局：…/电费记账本-安卓版 与 …/电费记账本-桌面版
        os.path.join(parent, '电费记账本-桌面版'),
    ):
        if os.path.exists(os.path.join(cand, '电费记账本.py')):
            return cand
    return None


_DESKTOP = _find_desktop()
DESKTOP_PY = os.path.join(_DESKTOP, '电费记账本.py') if _DESKTOP else ''
# 优先用桌面版当前的真实账本；本仓库里不带真实数据，就退回自带的空账本模板
_DESK_CANDIDATES = [
    os.path.join(_DESKTOP, 'dist', '电费记账数据.json') if _DESKTOP else '',
    os.path.join(_DESKTOP, '示例数据', '空账本模板.json') if _DESKTOP else '',
]
DESKTOP_DATA = next((p for p in _DESK_CANDIDATES if p and os.path.exists(p)), _DESK_CANDIDATES[0])


def using_empty_template():
    """当前用的是空账本模板而不是真实账本 —— 有几项断言在这种情形下不适用"""
    return os.path.basename(DESKTOP_DATA) == '空账本模板.json'

FAILED = []


def resolve_phone_export():
    if len(sys.argv) > 1:
        return sys.argv[1]
    for p in PHONE_EXPORT_CANDIDATES:
        if os.path.exists(p):
            return p
    return PHONE_EXPORT_CANDIDATES[0]


def check(name, cond, detail=''):
    print('  %s %s%s' % ('[OK]  ' if cond else '[FAIL]', name, ('  ' + detail) if detail else ''))
    if not cond:
        FAILED.append(name)


def load_desktop_module():
    """桌面版文件名叫「电费记账本.py」，中文名不能直接 import，用 importlib 走路径"""
    spec = importlib.util.spec_from_file_location('feenote_desktop', DESKTOP_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)   # 有 __main__ 保护，不会开窗口
    return mod


def blank_store(mod):
    """给一个不存在的路径 → 桌面版会以空账本启动"""
    return mod.Store(tempfile.mktemp(suffix='.json'))


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    phone_export = resolve_phone_export()
    for p in (phone_export, DESKTOP_PY, DESKTOP_DATA):
        if not os.path.exists(p):
            print('缺文件：%s' % p)
            return 2

    mod = load_desktop_module()
    phone = load_json(phone_export)
    desk_data = load_json(DESKTOP_DATA)

    print('=' * 66)
    print('手机导出文件：%s' % os.path.relpath(phone_export, APP_DIR))
    print('内容：%d 条活跃 + %d 条回收站' % (len(phone['records']), len(phone['deleted'])))
    print('电脑账本：%s（%d 条）' % (os.path.basename(DESKTOP_DATA), len(desk_data['records'])))
    if using_empty_template():
        print('       ^ 本仓库不带真实账本，用的是自带的空账本模板 —— 从空账本合并更严格')
    print('=' * 66)

    # ---------------------------------------------------------------- 场景 1
    print('\n场景 1 · 电脑(%d 条) 合并导入 手机导出文件' % len(desk_data['records']))
    desk = blank_store(mod)
    desk.apply(desk_data, replace=True)
    n0 = len(desk.records)
    desk.apply(phone, replace=False)          # 合并
    n1 = len(desk.records)

    phone_uids = {r['id'] for r in phone['records']}
    desk_uids_before = {r['id'] for r in desk_data['records']}
    expect_new = len(phone_uids - desk_uids_before)

    check('合并后条数 = %d + %d = %d' % (n0, expect_new, n0 + expect_new), n1 == n0 + expect_new,
          '实际 %d' % n1)
    ids = [r['id'] for r in desk.records]
    check('没有重复的 uid', len(ids) == len(set(ids)))
    check('回收站收下 1 条', len(desk.deleted) == 1, '实际 %d' % len(desk.deleted))
    # 房间号：本地已有值就不该被对端盖掉；本地是空的才采纳对端的
    if using_empty_template():
        check('房间号采用了对端的值', desk.room == phone['room'], '实际 %r' % desk.room)
    else:
        check('房间号没被对端盖掉', desk.room == desk_data['room'], '实际 %r' % desk.room)
    # 成员：合并语义是「并集」—— 本地原有的一个都不能丢，对端的也要并进来
    merged = set(desk.members)
    lost = set(desk_data['members']) - merged
    added = set(phone['members']) - merged
    check('本地成员一个都没丢', not lost, '丢了 %s' % '、'.join(sorted(lost)) if lost else '')
    check('对端成员也并进来了', not added, '少了 %s' % '、'.join(sorted(added)) if added else '')
    check('成员没有重复', len(desk.members) == len(merged), '实际 %d 项 / %d 个' % (len(desk.members), len(merged)))

    # ---------------------------------------------------------------- 场景 2
    print('\n场景 2 · 幂等性：同一份文件再合并一次，不应该有任何变化')
    desk.apply(phone, replace=False)
    check('条数不变', len(desk.records) == n1, '实际 %d' % len(desk.records))
    check('回收站不变', len(desk.deleted) == 1, '实际 %d' % len(desk.deleted))

    # ---------------------------------------------------------------- 场景 3
    print('\n场景 3 · 覆盖模式：整个账本换成文件内容')
    desk2 = blank_store(mod)
    desk2.apply(desk_data, replace=True)
    desk2.apply(phone, replace=True)          # 覆盖
    check('活跃记录 = 4', len(desk2.records) == 4, '实际 %d' % len(desk2.records))
    check('回收站 = 1', len(desk2.deleted) == 1, '实际 %d' % len(desk2.deleted))

    # ---------------------------------------------------------------- 场景 4
    print('\n场景 4 · 反向：手机的初始账本(=桌面版同一批 uid) 导入桌面版文件')
    phone_like = blank_store(mod)
    phone_like.apply(desk_data, replace=True)   # 手机首次启动后的状态
    before = len(phone_like.records)
    phone_like.apply(desk_data, replace=False)  # 导入电脑导出的同一份文件
    check('不产生任何重复（新增 0 条）', len(phone_like.records) == before,
          '%d → %d' % (before, len(phone_like.records)))

    # ---------------------------------------------------------------- 场景 5
    print('\n场景 5 · 删除传播（手机删掉 → 电脑也跟着进回收站）')
    target_id = phone['deleted'][0]['id'] if phone['deleted'] else None
    if target_id is None:
        print('  （手机的导出文件里没有回收站记录，跳过）')
    else:
        deleted_case = {
            'app': '电费记账本', 'version': '1.4', 'room': phone['room'],
            'members': desk_data['members'], 'memberIds': desk_data['memberIds'],
            'records': [], 'deleted': [r for r in phone['deleted'] if r['id'] == target_id],
            'savedAt': '2026-09-28 11:30:00',
        }
        desk3 = blank_store(mod)
        # 先让电脑上真的存在这条记录，再看对端把它标删后本地会不会跟着走
        seat = dict(deleted_case['deleted'][0])
        seat.pop('deleted', None)
        if desk_data['members']:
            seat['member'] = desk_data['members'][0]      # 挂到本地已有的成员上
        settled = dict(desk_data)
        settled['records'] = list(desk_data['records']) + [seat]
        desk3.apply(settled, replace=True)
        was_active = any(r['id'] == target_id for r in desk3.records)
        desk3.apply(deleted_case, replace=False)
        still_active = any(r['id'] == target_id for r in desk3.records)
        now_in_trash = any(r['id'] == target_id for r in desk3.deleted)
        check('删除前这条在电脑上是活跃的', was_active)
        check('对端标删后，本地不再活跃', not still_active)
        check('对端标删后，本地进了回收站', now_in_trash)

    print('\n' + '=' * 66)
    if FAILED:
        print('未通过 %d 项：%s' % (len(FAILED), '、'.join(FAILED)))
        return 1
    print('全部通过 ✅')
    return 0


if __name__ == '__main__':
    sys.exit(main())
