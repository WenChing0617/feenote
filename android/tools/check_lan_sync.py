# -*- coding: utf-8 -*-
"""局域网同步 · 端到端联调（真桌面服务 ⇄ 真安卓导出样本）

做的事情：
  1. 按路径 import 桌面版的 `电费记账本.py`（不复制代码，测的就是要上线的那个文件）
  2. 用「真实账本数据的副本」起一个真的 SyncServer（绝不动 dist 里的真数据）
  3. 拿 `tools/sample_phone_export.json`——这是安卓端 Kotlin 代码真跑出来的导出样本——
     推到电脑上，再取回来
  4. 逐项核对：期初不重复、手机新记录进来了、手机删的跟着删、幂等、格式能被安卓端解析

用法：
    python tools/check_lan_sync.py
（必须用带 tkinter 的 Python：桌面版模块 import 时会用到）
（桌面版工程的位置按下面的顺序找，找不到可以用环境变量 FEENOTE_DESKTOP 指定）
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ANDROID = os.path.dirname(HERE)
PHONE_SAMPLE = os.path.join(HERE, 'sample_phone_export.json')


def _find_desktop():
    """定位桌面版工程目录。不写死绝对路径，两种常见布局都能自动找到。"""
    env = os.environ.get('FEENOTE_DESKTOP')
    if env:
        return env
    parent = os.path.dirname(ANDROID)
    for cand in (
        # 本仓库布局：android/ 和 desktop/ 是兄弟目录
        os.path.join(parent, 'desktop'),
        # 两个工程并排放的布局：…/电费记账本-安卓版 与 …/电费记账本-桌面版
        os.path.join(parent, '电费记账本-桌面版'),
    ):
        if os.path.exists(os.path.join(cand, '电费记账本.py')):
            return cand
    return None


DESKTOP = _find_desktop()
if not DESKTOP:
    sys.exit('找不到桌面版工程。请把 desktop/ 放在本仓库里，'
             '或用环境变量指定：FEENOTE_DESKTOP=<桌面版目录>')

DESKTOP_PY = os.path.join(DESKTOP, '电费记账本.py')
DESKTOP_DATA = os.path.join(DESKTOP, 'dist', '电费记账数据.json')

OK = [0]
BAD = [0]


def t(name, cond, extra=''):
    if cond:
        OK[0] += 1
        print('  PASS  ' + name)
    else:
        BAD[0] += 1
        print('  FAIL  ' + name + ('  → %s' % (extra,)))


def load_desktop():
    if not os.path.exists(DESKTOP_PY):
        print('找不到桌面版：', DESKTOP_PY)
        sys.exit(2)
    spec = importlib.util.spec_from_file_location('feebook', DESKTOP_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def http(url, obj=None, timeout=8):
    data = None if obj is None else json.dumps(obj, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        url, data=data, method='POST' if data else 'GET',
        headers={'Content-Type': 'application/json'} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')


def main():
    app = load_desktop()
    print('桌面版模块已加载： %s' % DESKTOP_PY)

    tmp = tempfile.mkdtemp(prefix='lan_sync_e2e_')
    try:
        # 用真数据的副本，绝不碰 dist 里的原件
        if os.path.exists(DESKTOP_DATA):
            shutil.copy2(DESKTOP_DATA, os.path.join(tmp, '电费记账数据.json'))
            print('已把真实账本复制到临时目录（原件不动）')
        store = app.Store(os.path.join(tmp, app.DATA_FILE))
        before_live = {r['id'] for r in store.records}
        before_dead = {r['id'] for r in store.deleted}
        print('电脑上：%d 条活跃记录、%d 条回收站' % (len(before_live), len(before_dead)))

        phone = json.load(open(PHONE_SAMPLE, encoding='utf-8'))
        phone_ids = {r['id'] for r in phone['records']}
        phone_dead = {r['id'] for r in phone['deleted']}
        print('手机上：%d 条记录、%d 条已删除' % (len(phone_ids), len(phone_dead)))

        srv = app.SyncServer(store)
        srv.new_pair()
        ok, msg = srv.start(0)
        t('桌面同步服务能起来', ok, msg)
        base = 'http://127.0.0.1:%d' % srv.port
        q = '?pair=' + srv.pair
        print('  服务 %s   配对码 %s' % (srv.url(), srv.pair))

        # ---- 探活 ----
        code, body = http(base + '/ping' + q)
        info = json.loads(body)
        t('ping 通，报的是电脑上的账',
          code == 200 and info.get('app') == app.APP_NAME
          and info.get('records') == len(before_live), (code, body))

        wrong_pair = '0000' if srv.pair != '0000' else '1111'
        code, _b = http('%s/ping?pair=%s' % (base, wrong_pair))
        t('配对码不对进不来（403）', code == 403, code)

        # ---- 手机 → 电脑 ----
        code, body = http(base + '/import' + q, phone)
        res = json.loads(body)
        t('推手机账本返回 200', code == 200, (code, body))
        expect_new = len(phone_ids - before_live)
        t('新增数 = 手机上电脑没有的那几条（期初不重复算）',
          res.get('added') == expect_new,
          '期望 %d，实际 %s' % (expect_new, res.get('added')))

        after_live = {r['id'] for r in store.records}
        after_dead = {r['id'] for r in store.deleted}
        t('期初那两条没有变成两份', after_live >= before_live and
          len(after_live) == len(before_live) + expect_new,
          '电脑上 %d → %d' % (len(before_live), len(after_live)))
        t('手机新记的两条进来了', phone_ids - before_live <= after_live,
          sorted(phone_ids - before_live))
        if phone_dead & before_live:
            t('手机上删的那条，电脑跟着进了回收站',
              phone_dead <= after_dead and not (phone_dead & after_live))
        else:
            t('手机上删的那条（电脑原本没有）直接落进回收站', phone_dead <= after_dead)

        # ---- 电脑 → 手机 ----
        code, body = http(base + '/export' + q)
        book = json.loads(body)
        t('取回电脑账本返回 200', code == 200, code)
        t('取回的账本，记录数跟电脑上活跃记录一致',
          len(book['records']) == len(store.records),
          (len(book['records']), len(store.records)))
        t('取回的账本，回收站条数一致',
          len(book.get('deleted') or []) == len(store.deleted),
          (len(book.get('deleted') or []), len(store.deleted)))
        # 安卓端 JsonCodec.parse 要求的字段，一个都不能少
        need = {'app', 'version', 'room', 'members', 'memberIds', 'records', 'deleted', 'savedAt'}
        t('取回的账本字段齐（安卓端 JsonCodec 能直接解析）',
          need <= set(book), sorted(need - set(book)))
        t('取回的每条记录都带 id（安卓端靠它去重）',
          all(r.get('id') for r in book['records']))

        # ---- 幂等：手机再推一次不该翻倍 ----
        code, body = http(base + '/import' + q, phone)
        res2 = json.loads(body)
        t('手机再推一次是幂等的',
          res2.get('added') == 0 and res2.get('trashed') == 0, res2)
        t('电脑上条数没变',
          len({r['id'] for r in store.records}) == len(after_live))

        # ---- 落盘 ----
        reread = app.Store(os.path.join(tmp, app.DATA_FILE))
        t('同步结果真的写进了 json 文件',
          len(reread.records) == len(store.records)
          and len(reread.deleted) == len(store.deleted),
          (len(reread.records), len(reread.deleted)))
        t('同步产生的改动可以 Ctrl+Z 撤销（进了撤销栈）', store.can_undo())

        srv.stop()
        time.sleep(0.2)
        code, _b = http(base + '/ping' + q, timeout=3)
        t('服务停掉后接口不再可用', code != 200, code)

        print('\n电脑上最终：%d 条活跃、%d 条回收站' % (len(store.records), len(store.deleted)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print('\n结果：%d 通过 / %d 失败 %s' % (OK[0], BAD[0], '✅' if not BAD[0] else '❌'))
    return 1 if BAD[0] else 0


if __name__ == '__main__':
    sys.exit(main())
