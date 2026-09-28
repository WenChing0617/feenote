# -*- coding: utf-8 -*-
"""电费记账本 · 桌面版 测试（数据层 + 真实 Tk 界面冒烟）"""
import os
import io
import sys
import json
import shutil
import zipfile
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import 电费记账本 as app  # noqa: E402

PASS = [0]
FAIL = [0]


def t(name, cond, extra=''):
    if cond:
        PASS[0] += 1
        print('  PASS  ' + name)
    else:
        FAIL[0] += 1
        print('  FAIL  ' + name + ('  → %s' % extra if extra else ''))


def close(a, b, eps=1e-9):
    return abs(a - b) < eps


def _money_of(v):
    """把界面上的 '¥1,234.50' 还原成数字，方便比较大小"""
    return float(str(v).replace('¥', '').replace(',', '').strip())


tmp = tempfile.mkdtemp(prefix='dianfei_test_')
DATA = os.path.join(tmp, '电费记账数据.json')

# 屏蔽弹窗，避免测试被阻塞
app.messagebox.showinfo = lambda *a, **k: 'ok'
app.messagebox.showwarning = lambda *a, **k: 'ok'
app.messagebox.showerror = lambda *a, **k: print('    [errorbox]', a)
app.messagebox.askyesno = lambda *a, **k: True
app.messagebox.askyesnocancel = lambda *a, **k: True

print('=== 0. 原始表解析（累计总额 → 每次充值）===')
import 导入初始数据 as imp  # noqa: E402

SAMPLE = '''9.9
350
350
250
200（已注销）
350
350

9.19
350
350
300 *
200（已注销）
350
400*
'''
g, _w = imp.parse_groups(SAMPLE)
t('解析出 2 组', len(g) == 2, len(g))
t('每组 6 个床铺各一个值', all(len(x['vals']) == 6 for x in g))
t('日期正确', [x['date'] for x in g] == ['2025-09-09', '2025-09-19'], [x['date'] for x in g])
t('星号识别正确', g[1]['stars'] == [False, False, True, False, False, True], g[1]['stars'])
recs0, _n = imp.build(g)
t('首组也算一笔（5 人各一条）',
  len([r for r in recs0 if r['date'] == '2025-09-09']) == 5, len(recs0))
t('首组被标成「期初」',
  all(r['initial'] is True for r in recs0 if r['date'] == '2025-09-09'))
t('后面的组不是「期初」',
  all(r['initial'] is False for r in recs0 if r['date'] != '2025-09-09'))
t('4 号床从不出现', all(r['member'] != '4号床' for r in recs0))
_per0 = {}
for _r in recs0:
    _per0[_r['member']] = _per0.get(_r['member'], 0) + _r['amount']
_last0 = g[-1]['vals']
t('每人累计 == 原始表末行',
  all(abs(_per0.get('%d号床' % (b + 1), 0) - _last0[b]) < 1e-9 for b in (0, 1, 2, 4, 5)),
  (_per0, _last0))
t('合计 == 末行合计（不含 4 号床）',
  abs(sum(_per0.values()) - sum(v for b, v in enumerate(_last0) if b != 3)) < 1e-9,
  (sum(_per0.values()), sum(v for b, v in enumerate(_last0) if b != 3)))

if os.path.exists(imp.SRC):
    with open(imp.SRC, encoding='utf-8') as _f:
        _g2, _ = imp.parse_groups(_f.read())
    _r2, _ = imp.build(_g2)
    _per2 = {}
    for _r in _r2:
        _per2[_r['member']] = _per2.get(_r['member'], 0) + _r['amount']
    _last2 = _g2[-1]['vals']
    t('真实数据：每人累计 == 末行',
      all(abs(_per2.get('%d号床' % (b + 1), 0) - _last2[b]) < 1e-9 for b in (0, 1, 2, 4, 5)), _per2)
    t('真实数据：2号床 800 / 1号床 750 / 3号床 650 / 6号床 750 / 5号床 500',
      _per2.get('2号床') == 800 and _per2.get('1号床') == 750 and _per2.get('3号床') == 650
      and _per2.get('6号床') == 750 and _per2.get('5号床') == 500, _per2)
    t('真实数据：合计 3450', abs(sum(_per2.values()) - 3450) < 1e-9, sum(_per2.values()))
    t('真实数据：38 条明细', len(_r2) == 38, len(_r2))
    t('真实数据：其中 5 条期初（各人一条）',
      len([r for r in _r2 if r.get('initial')]) == 5,
      len([r for r in _r2 if r.get('initial')]))
    t('真实数据：28 组（2025-09-09 ~ 2026-09-18）',
      len(_g2) == 28 and _g2[0]['date'] == '2025-09-09' and _g2[-1]['date'] == '2026-09-18',
      (len(_g2), _g2[0]['date'], _g2[-1]['date']))
else:
    print('  （这台机器上没有 %s，跳过真实数据核对）' % imp.SRC)

print('=== 1. 数据层：新增 / 保存 / 重新加载 ===')
st = app.Store(DATA)
t('初始为空账本', st.records == [] and st.members == [])
st.room = 'A-302'
st.add('2026-09-01', '张三', 100, '微信', '9月电费')
st.add('2026-09-05', '李四', 200, '支付宝', '')
st.add('2026-09-12', '张三', 50, '微信', '补交')
ok, err = st.save()
t('保存成功', ok, err)
t('数据文件已生成', os.path.exists(DATA))
t('成员自动登记', st.members == ['张三', '李四'], st.members)

st2 = app.Store(DATA)
t('重新打开读回 3 条', len(st2.records) == 3, len(st2.records))
t('房间名保留', st2.room == 'A-302')
t('金额正确', close(sum(r['amount'] for r in st2.records), 350))

print('=== 2. 数据层：统计与对账 ===')
s = st2.stats()
t('总充值 350.00', close(s['total'], 350))
t('笔数 3', s['count'] == 3)
t('人数 2', s['people'] == 2)
t('统计结果不含人均应摊', 'per_head' not in s, list(s.keys()))
rows = {r['name']: r for r in s['rows']}
t('张三累计 150.00', close(rows['张三']['amount'], 150))
t('张三笔数 2', rows['张三']['count'] == 2)
t('张三最近充值 2026-09-12', rows['张三']['last'] == '2026-09-12', rows['张三']['last'])
t('李四最近充值 2026-09-05', rows['李四']['last'] == '2026-09-05', rows['李四']['last'])
t('汇总行不含差额字段', 'diff' not in rows['张三'], list(rows['张三'].keys()))
t('占比正确（张三 42.86%）', close(rows['张三']['pct'], 150 / 350 * 100, 0.01))
t('汇总默认按固定编号排（张三=1、李四=2）', [r['no'] for r in s['rows']] == [1, 2],
  [(r['name'], r['no']) for r in s['rows']])
t('汇总可以按金额降序',
  st2.stats(sort_key='amount', reverse=True)['rows'][0]['name'] == '李四',
  [r['name'] for r in st2.stats(sort_key='amount', reverse=True)['rows']])
t('最近一笔日期正确', s['latest']['date'] == '2026-09-12', s['latest']['date'])

print('=== 3. 数据层：改 / 删 / 筛选排序 ===')
rid = st2.records[0]['id']
st2.update(rid, amount=400, method='现金', note='改成400')
t('编辑生效', close(st2.get(rid)['amount'], 400))
t('编辑后总额 650.00', close(st2.stats()['total'], 650))

t('按备注搜索命中 1 条', len(st2.query(keyword='改成400')) == 1)
t('按成员筛选命中 2 条（张三）', len(st2.query(member='张三')) == 2)
t('按年份筛选命中 3 条（2026）', len(st2.query(year='2026')) == 3, len(st2.query(year='2026')))
t('按月份筛选命中 3 条（9月）', len(st2.query(month='9')) == 3, len(st2.query(month='9')))
t('年+月组合筛选', len(st2.query(year='2026', month='9')) == 3)
t('筛选 2025 年无结果', len(st2.query(year='2025')) == 0)
t('年份下拉取自数据', st2.years() == ['2026'], st2.years())
t('金额降序第一是 400', st2.query(sort_key='amount', reverse=True)[0]['amount'] == 400)
t('日期升序第一是 09-01', st2.query(sort_key='date', reverse=False)[0]['date'] == '2026-09-01')

st2.delete(st2.records[-1]['id'])
t('删除后 2 条', len(st2.records) == 2)
t('删掉的进了回收站（不是销毁）', len(st2.deleted) == 1, len(st2.deleted))
st2.save()

print('=== 3b. 期初不算笔数 / 每人固定编号 / 回收站 / 撤销重做 ===')
pb = os.path.join(tmp, 'seq.json')
stb = app.Store(pb)
stb.room = 'C-303'
# 1 号床：期初 350 + 三次充值；2 号床：两次充值
stb.add('2025-09-09', '1号床', 350, '校园卡', '期初首笔（原始表首行，无 * 标记）')
stb.add('2025-09-19', '1号床', 50)
stb.add('2025-10-20', '1号床', 100)
stb.add('2026-03-01', '1号床', 80)
stb.add('2025-09-20', '2号床', 200)
stb.add('2026-03-05', '2号床', 120)

sb = stb.stats()
t('期初的钱照样进总账（¥900）', close(sb['total'], 900), sb['total'])
t('总笔数不含期初（5 笔）', sb['count'] == 5, sb['count'])
t('期初条数单独统计（1 条）', sb['initial_count'] == 1, sb['initial_count'])
t('期初金额单独统计（¥350）', close(sb['initial_total'], 350), sb['initial_total'])
rb = {r['name']: r for r in sb['rows']}
t('1 号床：金额算到期初（¥580），笔数只有 3', close(rb['1号床']['amount'], 580)
  and rb['1号床']['count'] == 3, (rb['1号床']['amount'], rb['1号床']['count']))
t('1 号床：期初 1 条 / ¥350', rb['1号床']['initial'] == 1
  and close(rb['1号床']['initial_amount'], 350), rb['1号床'])
t('2 号床：2 笔无期初', rb['2号床']['count'] == 2 and rb['2号床']['initial'] == 0)
t('「最近充值」跳过期初', sb['latest']['date'] == '2026-03-05', sb['latest']['date'])
t('count_of 默认不算期初', stb.count_of('1号床') == 3, stb.count_of('1号床'))
t('count_of 可以含着期初数', stb.count_of('1号床', include_initial=True) == 4)

# 每个人的固定编号（相当于身份证号：发出去就不改、不回收）
t('成员编号按登记顺序发：1 号床=1、2 号床=2',
  stb.member_no('1号床') == 1 and stb.member_no('2号床') == 2, dict(stb.member_ids))
t('编号是幂等的（反复问都是同一个）', stb.member_no('1号床') == 1)
t('汇总表每一行都带着编号', sorted(r['no'] for r in sb['rows']) == [1, 2],
  [(r['name'], r['no']) for r in sb['rows']])
t('默认按编号从小到大排', [r['no'] for r in stb.stats()['rows']] == [1, 2],
  [r['name'] for r in stb.stats()['rows']])
t('按累计充值降序：1 号床(¥580) 在前',
  [r['name'] for r in stb.stats(sort_key='amount', reverse=True)['rows']]
  == ['1号床', '2号床'],
  [r['amount'] for r in stb.stats(sort_key='amount', reverse=True)['rows']])
t('按累计充值升序：2 号床(¥320) 在前',
  [r['name'] for r in stb.stats(sort_key='amount', reverse=False)['rows']]
  == ['2号床', '1号床'])
t('按笔数降序：1 号床(3 笔) 在前',
  [r['no'] for r in stb.stats(sort_key='count', reverse=True)['rows']] == [1, 2],
  [r['count'] for r in stb.stats(sort_key='count', reverse=True)['rows']])
t('排序只挪行，编号一个都不变',
  sorted(r['no'] for r in stb.stats(sort_key='count', reverse=True)['rows']) == [1, 2])
t('按最近充值排可用', len(stb.stats(sort_key='last', reverse=True)['rows']) == 2)
t('按成员名排也带着编号', all(r['no'] for r in stb.stats(sort_key='name')['rows']))

# 编号的稳定性：改名 / 新人 / 老人去而复返
stn = app.Store(os.path.join(tmp, 'no.json'))
for m in ('1号床', '2号床', '3号床'):
    stn.members.append(m)
stn._ensure_member_ids()
t('按成员列表顺序发号：1/2/3', [stn.member_no(m) for m in ('1号床', '2号床', '3号床')] == [1, 2, 3], dict(stn.member_ids))
stn.rename_member('2号床', '2号床(老王)')
t('改名 → 编号跟着搬过去，号不变', stn.member_no('2号床(老王)') == 2, dict(stn.member_ids))
t('改名后老名字不再占号', '2号床' not in stn.member_ids, dict(stn.member_ids))
stn.members.append('6号床')
t('新成员拿最大的号 +1（4）', stn.member_no('6号床') == 4, dict(stn.member_ids))
stn.members.remove('6号床')               # 人退宿了，号留着不回收
stn.members.append('9号床')
t('后来的人不会捡走老人留下的号（9 号床拿 5）',
  stn.member_no('9号床') == 5, dict(stn.member_ids))
stn.members.append('6号床')
t('老人回来还是原来的号（4）', stn.member_no('6号床') == 4, dict(stn.member_ids))
stn.save()
stn2 = app.Store(os.path.join(tmp, 'no.json'))
t('存盘 → 读回来，编号一字不差', stn2.member_ids == stn.member_ids,
  (stn2.member_ids, stn.member_ids))

t('按支付方式排序可用', len(stb.query(sort_key='method')) == 6)
t('按备注排序可用', len(stb.query(sort_key='note')) == 6)
t('可以不显示期初', len(stb.query(show_initial=False)) == 5,
  len(stb.query(show_initial=False)))

# 期初只在「明细账单」里露面，结算单 / CSV 汇总 / 各处小字都不提它
_rep_b = stb.report_text()
t('结算单里完全不出现「期初」', '期初' not in _rep_b, _rep_b)
t('结算单每人一行只说笔数和金额',
  '1号床：已充 ¥580.00，3 笔' in _rep_b, _rep_b.split('\n')[3])
_csv_b = stb.csv_text()
t('CSV 汇总段没有「其中期初」列', '其中期初' not in _csv_b)
t('CSV 合计行不再提期初', '另有' not in _csv_b, _csv_b)
t('CSV 明细账单里照样留着期初（该显示的地方保留）', '期初' in _csv_b)

# 回收站：软删除 → 恢复 → 彻底删除
before_n = len(stb.records)
victim = [r['id'] for r in stb.records if r['member'] == '2号床']
stb.delete_many(victim)
t('软删除：账本里少了 2 条', len(stb.records) == before_n - 2, len(stb.records))
t('软删除：回收站里多了 2 条', len(stb.deleted) == 2, len(stb.deleted))
t('回收站记录带删除时间', all('deletedAt' in r for r in stb.deleted))
t('软删除后总额少了（总账跟着变）', close(stb.stats()['total'], 580), stb.stats()['total'])
t('回收站按最近删除排前', stb.trash()[0]['id'] in victim)
t('恢复 1 条', stb.restore(victim[:1]) == 1)
t('恢复后总数回来 1 条', len(stb.records) == before_n - 1, len(stb.records))
t('恢复后不再带 deletedAt',
  all('deletedAt' not in r for r in stb.records), stb.records[0].keys())
n_purge = stb.purge(victim[1:])
t('彻底删除剩下的 1 条', n_purge == 1 and len(stb.deleted) == 0, (n_purge, len(stb.deleted)))

# 撤销 / 重做
stb.clear_history()
t('一开始没得撤销', not stb.can_undo() and not stb.can_redo())
t('撤销空栈返回 None', stb.undo() is None)

base = len(stb.records)
stb.snapshot('添加记录')
stb.add('2026-04-01', '1号床', 60)
t('撤销前的动作名是「添加记录」', stb.undo_label() == '添加记录', stb.undo_label())
after_add = len(stb.records)
t('添加后多了 1 条', after_add == base + 1)
t('撤销 → 回到添加前', stb.undo() == '添加记录' and len(stb.records) == base, len(stb.records))
t('撤销后可以重做', stb.can_redo() and stb.redo() == '添加记录')
t('重做 → 又回到添加后', len(stb.records) == after_add, len(stb.records))

# 撤销要能连「金额」一起还原（全量快照）
amt_before = stb.stats()['total']
stb.snapshot('修改记录')
stb.update(stb.records[-1]['id'], amount=99999)
t('改金额后总额变了', not close(stb.stats()['total'], amt_before))
stb.undo()
t('撤销修改 → 金额原样回来', close(stb.stats()['total'], amt_before), stb.stats()['total'])

# 撤销「删除」要把记录从回收站拿回来
tgt = stb.records[-1]['id']
stb.snapshot('移入回收站 1 条')
stb.delete_many([tgt])
t('删除后可撤销', stb.can_undo())
stb.undo()
t('撤销删除 → 记录回到账本', stb.get(tgt) is not None and len(stb.deleted) == 0,
  (stb.get(tgt) is not None, len(stb.deleted)))

# 新动过一笔之后，重做分支作废
stb.snapshot('A')
stb.add('2026-04-02', '2号床', 10)
stb.undo()
t('撤销后可以重做', stb.can_redo())
stb.snapshot('B')
stb.add('2026-04-03', '2号床', 20)
t('有了新动作后，重做栈清空', not stb.can_redo())

# 撤销栈有上限，不会无限膨胀
for i in range(app.UNDO_LIMIT + 20):
    stb.snapshot('压栈 %d' % i)
    stb.add('2026-05-01', '2号床', 1)
t('撤销栈不超过上限', len(stb._undo) <= app.UNDO_LIMIT, len(stb._undo))

# 期初标记能落盘 + 读回
stb.save()
stb2 = app.Store(pb)
t('重新加载后：期初标记还在',
  sum(1 for r in stb2.records if r.get('initial')) == sb['initial_count'],
  sum(1 for r in stb2.records if r.get('initial')))
t('重新加载后：回收站清空（已彻底删掉）', stb2.deleted == [])

# 回收站也要能落盘
tr = os.path.join(tmp, 'trash.json')
str_ = app.Store(tr)
str_.add('2026-01-01', '甲', 10)
str_.delete_many([str_.records[0]['id']])
t('回收站能存下', str_.save()[0] and len(app.Store(tr).deleted) == 1,
  len(app.Store(tr).deleted))
t('只有回收站内容也不算「空账本」', not str_.is_empty())

print('=== 4. 数据层：成员改名 / 删除 ===')
n = st2.rename_member('张三', '张三丰')
t('改名同步 1 条记录', n == 1, n)
t('改名后成员列表更新', '张三丰' in st2.members and '张三' not in st2.members, st2.members)
t('改名后记录同步', all(r['member'] != '张三' for r in st2.records))
try:
    st2.rename_member('张三丰', '李四')
    t('重名被拦截', False)
except ValueError:
    t('重名被拦截', True)
st2.members.append('王五')
n = st2.remove_member('王五', with_records=True)
t('删除无记录成员，影响 0 条', n == 0)
st2.add('2026-09-15', '王五', 30)
n = st2.remove_member('王五', with_records=True)
t('删除成员同时删记录', n == 1, n)
st2.save()

print('=== 5. 数据层：CSV / 结算单 / 备份 ===')
st3 = app.Store(DATA)
st3.room = 'A-302'
csv_txt = st3.csv_text()
t('CSV 明细表头（不带序号列）', '日期,充值人,金额(元),支付方式,备注' in csv_txt)
t('CSV 含明细行', '2026-09-01,张三丰,400.00,现金,改成400' in csv_txt, csv_txt[:400])
t('CSV 汇总表头（序号在最前）',
  '序号,成员,笔数,累计充值(元),占比,最近充值' in csv_txt, csv_txt)
t('CSV 汇总段没有「其中期初」列', '其中期初' not in csv_txt)
t('CSV 合计行不再提期初', '另有' not in csv_txt)
t('CSV 不含人均应摊列', '人均' not in csv_txt and '差额' not in csv_txt)
t('CSV 换行为 CRLF', '\r\n' in csv_txt)
rep = st3.report_text()
t('结算单含总充值', '总充值 ¥600.00（2 笔，2 人）' in rep, rep.split('\n')[1])
t('结算单每人一行', '张三丰：已充 ¥400.00，1 笔' in rep, rep.split('\n')[3])
t('结算单李四一行', '李四：已充 ¥200.00，1 笔' in rep, rep.split('\n')[4])
t('结算单已去掉人均/多垫/待补', ('人均' not in rep) and ('多垫' not in rep) and ('待补' not in rep), rep)
t('自动备份目录已生成', os.path.isdir(os.path.join(tmp, app.BACKUP_DIR)),
  os.listdir(tmp))

print('=== 6. 数据层：导入合并 / 覆盖 ===')
other = {
    'app': '电费记账本', 'room': 'B-101', 'members': ['赵六'],
    'records': [{'id': 'zzz1', 'date': '2026-09-20', 'member': '赵六', 'amount': 80,
                 'method': '微信', 'note': '', 'createdAt': 1}],
}
before = len(st3.records)
st3.apply(other, replace=False)
t('合并导入：记录累加', len(st3.records) == before + 1, len(st3.records))
t('合并导入：成员取并集', '赵六' in st3.members, st3.members)
t('合并导入：房间名不被覆盖', st3.room == 'A-302')
st3.apply(other, replace=False)
t('重复导入按 id 去重', len(st3.records) == before + 1, len(st3.records))
st3.apply(other, replace=True)
t('覆盖导入：只剩 1 条', len(st3.records) == 1)
t('覆盖导入：房间名被替换', st3.room == 'B-101')

# 「删除」必须能跨设备传播：对端回收站里的记录，本地还留着就跟着进回收站
# （手机删了一条，电脑上不能又冒出来，否则两边永远对不上）
st6 = app.Store(os.path.join(tmp, 'proc.json'))
st6.add('2026-05-01', '甲', 10)
st6.add('2026-05-02', '乙', 20)
st6.save()
keep_id, del_id = st6.records[0]['id'], st6.records[1]['id']
st6.apply({'records': [], 'deleted': [
    {'id': del_id, 'date': '2026-05-02', 'member': '乙', 'amount': 20,
     'method': '微信', 'note': '', 'createdAt': 9, 'deletedAt': 1767000000000},
]}, replace=False)
t('合并时删除会传播：本地那条被移走',
  all(r['id'] != del_id for r in st6.records), [r['id'] for r in st6.records])
t('合并时删除会传播：进了回收站',
  any(r['id'] == del_id for r in st6.deleted), [r['id'] for r in st6.deleted])
t('合并时删除会传播：没被误伤的那条还在',
  any(r['id'] == keep_id for r in st6.records))
t('删除传播是软删除（能恢复）', st6.restore([del_id]) == 1 and st6.get(del_id) is not None)
st6.apply({'records': [], 'deleted': [
    {'id': 'neverseen000', 'date': '2026-01-01', 'member': '丙', 'amount': 5,
     'method': '现金', 'note': '', 'createdAt': 1, 'deletedAt': 1}]}, replace=False)
t('对端回收站里的 id 本地从没记录过 → 只进回收站，不报错',
  any(r['id'] == 'neverseen000' for r in st6.deleted))

print('=== 7. 容错 ===')
bad = os.path.join(tmp, 'bad.json')
with open(bad, 'w', encoding='utf-8') as f:
    f.write('{ 这不是 json')
st4 = app.Store(bad)
t('坏文件不崩溃，给出提示', st4.records == [] and st4.load_error is not None, st4.load_error)
st5 = app.Store(os.path.join(tmp, '不存在.json'))
t('文件不存在时正常新建', st5.records == [] and st5.load_error is None)
weird = {'records': [{'date': '乱七八糟', 'member': None, 'amount': 'abc'}]}
st5.apply(weird, replace=True)
t('脏数据被清洗成合法记录',
  len(st5.records) == 1 and len(st5.records[0]['date']) == 10 and st5.records[0]['amount'] == 0.0,
  st5.records)

print('=== 7b. 防清空安全阀（重点）===')
prot = os.path.join(tmp, 'protect.json')
good = app.Store(prot)
good.room = 'C-101'
good.add('2026-09-01', '阿明', 100, '微信', '')
okp, errp = good.save()
t('正常保存成功', okp and len(app.Store(prot).records) == 1, errp)

blank = app.Store(prot)
blank.records, blank.members, blank.room = [], [], ''
okb, errb = blank.save()
t('空账本拒绝覆盖有内容的文件', (not okb) and '取消这次保存' in errb, errb)
t('原文件确实没被动过', len(app.Store(prot).records) == 1)

miss = os.path.join(tmp, '首次使用.json')
okm, errm = app.Store(miss).save()
t('文件不存在时允许新建', okm and os.path.exists(miss), errm)

bad2 = os.path.join(tmp, 'corrupt2.json')
with open(bad2, 'w', encoding='utf-8') as f:
    f.write('{ 这回是真坏了')
st6 = app.Store(bad2)
t('坏文件被隔离留底', bool(st6.quarantine_path) and os.path.exists(st6.quarantine_path or ''),
  st6.quarantine_path)
t('隔离副本名带「损坏_」', os.path.basename(st6.quarantine_path or '').startswith('损坏_'))
t('提示里写明了留底位置', '留了一份' in (st6.load_error or ''), st6.load_error)
okc, errc = st6.save()
t('坏文件不会被空账本覆盖', not okc, errc)
t('坏文件内容原样还在', open(bad2, encoding='utf-8').read() == '{ 这回是真坏了')

bdir = os.path.join(tmp, '数据备份')
t('备份目录已生成', os.path.isdir(bdir))
day_files = [f for f in os.listdir(bdir) if f.startswith('电费记账数据_')]
t('每日备份不是空壳', any(app.Store._read_has_data(os.path.join(bdir, f)) for f in day_files),
  day_files)

print('=== 8. 界面冒烟（真实 Tk 窗口）===')
GUI_DATA = os.path.join(tmp, 'gui.json')
gui_store = app.Store(GUI_DATA)
gui_store.room = 'B-208'
gui_store.add('2026-09-01', '小明', 100, '微信', '')
gui_store.add('2026-09-03', '小红', 200, '支付宝', '')
gui_store.save()

root = app.tk.Tk()
a = app.App(root, gui_store)
root.update()
root.update_idletasks()
t('主窗口构建成功', root.winfo_exists() == 1)
t('标题含程序名', app.APP_NAME in root.title(), root.title())
t('窗口未超出屏幕', root.winfo_width() <= root.winfo_screenwidth()
  and root.winfo_height() <= root.winfo_screenheight(),
  '%dx%d / 屏幕 %dx%d' % (root.winfo_width(), root.winfo_height(),
                          root.winfo_screenwidth(), root.winfo_screenheight()))


def descendants(w):
    out = []
    for c in w.winfo_children():
        out.append(c)
        out.extend(descendants(c))
    return out


# 关键回归：录入表单里的输入框/按钮不能被布局裁剪掉
widgets = [('日期选择器', a.dp_date), ('日期按钮', a.dp_date.btn),
           ('谁充的', a.cb_member), ('充多少', a.e_amount),
           ('支付方式', a.cb_method), ('备注', a.e_note)]
missing = [n for n, w in widgets if not w.winfo_ismapped() or w.winfo_height() < 10]
t('录入表单 6 个控件全部可见', not missing, missing)
box = a.cb_member.master.master
clipped = [c for c in descendants(box) if not c.winfo_ismapped()]
t('录入卡片没有被裁剪的控件', not clipped,
  [(c.winfo_class(), c.cget('text') if 'text' in c.keys() else '') for c in clipped])
t('录入卡片高度足够', box.winfo_height() >= box.winfo_reqheight() - 2,
  '%d / 需要 %d' % (box.winfo_height(), box.winfo_reqheight()))
sum_card = a.tv_sum.master
_sum_cols = ('no', 'name', 'count', 'amount', 'pct', 'last')
t('汇总表列未被挤压', sum(a.tv_sum.column(c)['width'] for c in _sum_cols)
  <= sum_card.winfo_width(), '列总宽 %d / 容器宽 %d' % (
      sum(a.tv_sum.column(c)['width'] for c in _sum_cols),
      sum_card.winfo_width()))
t('统计卡显示总充值 ¥300.00', a.stat_labels['total'].cget('text') == '¥300.00',
  a.stat_labels['total'].cget('text'))
t('统计卡人数 2 人', a.stat_labels['people'].cget('text') == '2 人')
import tkinter.font as _tkfont  # noqa: E402
_f = _tkfont.Font(font=('Microsoft YaHei UI', 9))
_need = _f.measure('2026-09-12') + 24
t('「最近充值」列宽放得下完整日期', a.tv_sum.column('last')['width'] >= _need,
  '列宽 %d / 需要 %d' % (a.tv_sum.column('last')['width'], _need))
t('统计卡只剩 4 张（无「人均应摊」）', len(a.stat_labels) == 4, list(a.stat_labels.keys()))
t('最近充值显示完整日期', a.stat_labels['latest'].cget('text').startswith('2026-09-03'),
  a.stat_labels['latest'].cget('text'))
t('支付方式默认校园卡', a.cb_method.get() == '校园卡', a.cb_method.get())
t('下拉里都能用（readonly）', 'readonly' in str(a.cb_method.cget('state')), a.cb_method.cget('state'))
t('明细表 2 行', len(a.tv_rec.get_children()) == 2, len(a.tv_rec.get_children()))
t('汇总表 2 行', len(a.tv_sum.get_children()) == 2)
sum_vals = [a.tv_sum.item(i)['values'] for i in a.tv_sum.get_children()]
t('汇总表第一列是每个人的固定编号', all(str(v[0]).isdigit() for v in sum_vals), sum_vals)
t('汇总表的编号互不重复', len({v[0] for v in sum_vals}) == len(sum_vals), sum_vals)
t('汇总表占比列是纯百分比文字（柱子改由 Canvas 画）',
  all(str(v[4]).endswith('%') and '█' not in str(v[4]) for v in sum_vals), sum_vals)
root.update()
a.draw_pct_bars()
t('占比条真的画到 Canvas 上了', len(a.bar_canvas.find_all()) > 0,
  'items=%d' % len(a.bar_canvas.find_all()))
t('汇总表末列是最近充值日期', all(len(str(v[5])) == 10 for v in sum_vals), sum_vals)
t('汇总表不再有「期初」列（期初只在明细账单里）',
  'initial' not in a.tv_sum.cget('columns'), a.tv_sum.cget('columns'))
t('汇总表小字不提期初', '期初' not in a.lbl_sum_sub.cget('text'), a.lbl_sum_sub.cget('text'))

print('=== 8a. 汇总表：每人固定编号 + 排序（明细表不再有序号列）===')
t('明细表已去掉「序号」列', 'seq' not in a.tv_rec.cget('columns'),
  a.tv_rec.cget('columns'))
t('汇总表有「序号」列', 'no' in a.tv_sum.cget('columns'), a.tv_sum.cget('columns'))
t('汇总表列顺序：序号在最前', list(a.tv_sum.cget('columns'))[0] == 'no',
  a.tv_sum.cget('columns'))
t('汇总表排序下拉可用（readonly）', 'readonly' in str(a.cb_sum_sort.cget('state')))
t('汇总表排序下拉共 9 种方式', len(a.cb_sum_sort.cget('values')) == 9,
  a.cb_sum_sort.cget('values'))
t('汇总表排序下拉里没有期初了',
  all('期初' not in str(v) for v in a.cb_sum_sort.cget('values')),
  a.cb_sum_sort.cget('values'))
t('汇总表默认按序号从小到大', a.var_sum_sort.get() == '序号（小→大）', a.var_sum_sort.get())


def width_problems(tv, head_font, cell_font):
    """回归：每一列的宽度都要放得下「表头」和「该列最长的内容」

    这类 bug 只在别的 DPI 缩放（125% / 150%）下才现形，肉眼很难发现，
    所以用「真实字体量出来的宽度」当尺子，直接把被截断的列揪出来。
    """
    import tkinter.font as _f
    fh = _f.Font(font=head_font)
    fc = _f.Font(font=cell_font)
    pad = 8                      # Treeview 单元格左右内边距
    bad = []
    for c in tv.cget('columns'):
        need = fh.measure(str(tv.heading(c)['text'])) + pad
        for iid in tv.get_children():
            v = tv.item(iid)['values']
            idx = list(tv.cget('columns')).index(c)
            need = max(need, fc.measure(str(v[idx])) + pad)
        if tv.column(c)['width'] < need:
            bad.append((c, tv.column(c)['width'], need))
    return bad


_p1 = width_problems(a.tv_rec, a.FB, a.F)
t('明细表每列都放得下表头和内容', not _p1, _p1)
_p2 = width_problems(a.tv_sum, a.FB, a.F)
t('汇总表每列都放得下表头和内容', not _p2, _p2)

_rec_vals = [a.tv_rec.item(i)['values'] for i in a.tv_rec.get_children()]
t('明细表首列是日期', all(len(str(v[0])) == 10 for v in _rec_vals), _rec_vals)
t('明细表里没有序号列（序号属于汇总表）',
  all(not str(v[0]).isdigit() for v in _rec_vals), _rec_vals)
t('明细表排序下拉有 7 种方式', len(a.cb_sort.cget('values')) == 7, a.cb_sort.cget('values'))
t('排序下拉用于排序（readonly）', 'readonly' in str(a.cb_sort.cget('state')))
t('默认排序是「日期（新→旧）」', a.var_sort.get() == '日期（新→旧）', a.var_sort.get())

a.var_sort.set('金额（高→低）')
a.on_sort_change()
root.update()
_first = a.tv_rec.item(a.tv_rec.get_children()[0])['values']
t('选「金额高→低」后首行是 200', '200.00' in str(_first[2]), _first)
a.var_sort.set('金额（低→高）')
a.on_sort_change()
root.update()
_first = a.tv_rec.item(a.tv_rec.get_children()[0])['values']
t('选「金额低→高」后首行是 100', '100.00' in str(_first[2]), _first)

# 汇总表排序：点表头 / 用下拉都行；编号永远钉在人身上，不跟着排
_sum_before = {a.tv_sum.item(i)['values'][0]: a.tv_sum.item(i)['values'][1]
               for i in a.tv_sum.get_children()}
a.var_sum_sort.set('累计充值（低→高）')
a.on_sum_sort_change()
root.update()
_sum_rows = [a.tv_sum.item(i)['values'] for i in a.tv_sum.get_children()]
t('汇总表能按累计充值排序（升序首行金额最小）',
  _money_of(_sum_rows[0][3]) <= _money_of(_sum_rows[-1][3]), _sum_rows)
t('排完序编号还是钉在原来那个人身上',
  {r[0]: r[1] for r in _sum_rows} == _sum_before, (_sum_before, _sum_rows))
a.sum_sort_by('no')                      # 点一下表头 → 回到按序号
root.update()
_sum_rows = [a.tv_sum.item(i)['values'] for i in a.tv_sum.get_children()]
t('点汇总表表头就能切回按序号排',
  [r[0] for r in _sum_rows] == sorted(r[0] for r in _sum_rows), _sum_rows)
t('汇总表表头带排序箭头', ('▲' in str(a.tv_sum.heading('no')['text'])
  or '▼' in str(a.tv_sum.heading('no')['text'])), a.tv_sum.heading('no')['text'])
t('汇总表下拉跟着表头同步', a.var_sum_sort.get() == '序号（小→大）', a.var_sum_sort.get())
a.sum_sort_by('amount')                  # 再点一次别的列，确认能来回切
root.update()
t('再点累计充值表头也能排', a.sum_sort_key == 'amount', a.sum_sort_key)
a.sum_sort_by('no')
root.update()

a.var_sort.set('日期（新→旧）')
a.on_sort_change()
root.update()

print('=== 8c. 界面：撤销 / 重做 / 回收站 ===')
_base = len(a.tv_rec.get_children())
t('撤销按钮初始不可用', str(a.btn_undo.cget('state')) == 'disabled', a.btn_undo.cget('state'))
t('回收站按钮常亮（空的时候也能看见入口）', str(a.btn_trash.cget('state')) == 'normal',
  a.btn_trash.cget('state'))

a.cb_member.set('小刚')
a.e_amount.delete(0, 'end')
a.e_amount.insert(0, '88')
a.add_record()
root.update()
t('新增后明细多 1 行', len(a.tv_rec.get_children()) == _base + 1,
  len(a.tv_rec.get_children()))
t('新增后撤销按钮可用', str(a.btn_undo.cget('state')) == 'normal', a.btn_undo.cget('state'))
t('撤销按钮上写了动作名', '添加记录' in a.btn_undo.cget('text'), a.btn_undo.cget('text'))
a.do_undo()
root.update()
t('撤销后明细回到原样', len(a.tv_rec.get_children()) == _base, len(a.tv_rec.get_children()))
t('撤销后重做按钮可用', str(a.btn_redo.cget('state')) == 'normal', a.btn_redo.cget('state'))
t('重做按钮上写了动作名', '添加记录' in a.btn_redo.cget('text'), a.btn_redo.cget('text'))
a.do_redo()
root.update()
t('重做后明细又多 1 行', len(a.tv_rec.get_children()) == _base + 1,
  len(a.tv_rec.get_children()))
a.do_undo()
root.update()
t('Ctrl+Z 撤销 → 又回到原样', len(a.tv_rec.get_children()) == _base, len(a.tv_rec.get_children()))

# 删除 → 进回收站 → 撤销
_sel = a.tv_rec.get_children()[0]
a.tv_rec.selection_set(_sel)
a.delete_selected()
root.update()
t('界面删除后少 1 行', len(a.tv_rec.get_children()) == _base - 1,
  len(a.tv_rec.get_children()))
t('界面删除后进回收站', len(a.store.deleted) == 1, len(a.store.deleted))
t('回收站按钮显示条数', '(1)' in a.btn_trash.cget('text'), a.btn_trash.cget('text'))
t('状态栏提示回收站条数', '回收站 1 条' in a.lbl_status.cget('text'), a.lbl_status.cget('text'))
a.do_undo()
root.update()
t('撤销删除 → 记录回到账本', len(a.tv_rec.get_children()) == _base
  and len(a.store.deleted) == 0, (len(a.tv_rec.get_children()), len(a.store.deleted)))

# 再次删除，这次从回收站窗口里恢复
_sel = a.tv_rec.get_children()[0]
a.tv_rec.selection_set(_sel)
a.delete_selected()
root.update()
a.open_trash()
root.update()
_twins = [w for w in a.root.winfo_children()
          if isinstance(w, app.tk.Toplevel) and w.title() == '回收站']
t('回收站窗口能打开', bool(_twins), [w.title() for w in a.root.winfo_children()
                                if isinstance(w, app.tk.Toplevel)])


def _walk(w, kinds, out):
    for c in w.winfo_children():
        if isinstance(c, kinds):
            out.append(c)
        _walk(c, kinds, out)
    return out


if _twins:
    _tw = _twins[0]
    root.update_idletasks()
    root.update()
    _tvs = _walk(_tw, app.ttk.Treeview, [])
    t('回收站窗口里有列表', bool(_tvs))
    if _tvs:
        _tv = _tvs[0]
        t('回收站列表显示 1 条', len(_tv.get_children()) == 1, len(_tv.get_children()))
        _pt = width_problems(_tv, a.FB, a.F)
        t('回收站列表没有列被截断', not _pt, _pt)
        _btns = _walk(_tw, app.tk.Button, [])
        _restore_btn = [b for b in _btns if '恢复' in str(b.cget('text'))]
        t('回收站有「恢复选中」按钮', bool(_restore_btn), [b.cget('text') for b in _btns])
        if _restore_btn and _tv.get_children():
            _tv.selection_set(_tv.get_children()[0])
            _restore_btn[0].invoke()
            root.update()
            t('点恢复后记录回到账本', len(a.store.deleted) == 0, len(a.store.deleted))
            t('恢复后明细行数复原', len(a.tv_rec.get_children()) == _base,
              len(a.tv_rec.get_children()))
    _tw.destroy()
    root.update()

print('=== 8b. 日历下拉（弹出一整月的日期表）===')
t('日期默认今天', a.dp_date.get() == app.today_str(), a.dp_date.get())
t('平时不占额外窗口', a.dp_date.popup is None)
a.dp_date.open_popup()
root.update()
t('日历能弹出来', a.dp_date._alive())
t('日期格子是 7 列 × 6 行', len(a.dp_date._cells) == 42, len(a.dp_date._cells))
t('星期表头是「一」到「日」', a.dp_date.WEEKDAYS == ['一', '二', '三', '四', '五', '六', '日'],
  a.dp_date.WEEKDAYS)


def shown_days(p):
    return sorted(d for d in p._cell_day.values() if d)


a.dp_date.goto(2026, 9)
root.update()
t('2026 年 9 月表里是 1~30 号', shown_days(a.dp_date) == list(range(1, 31)), len(shown_days(a.dp_date)))
a.dp_date.goto(2025, 2)
root.update()
t('2025 年 2 月表里是 1~28 号', shown_days(a.dp_date) == list(range(1, 29)), len(shown_days(a.dp_date)))
a.dp_date.goto(2024, 2)
root.update()
t('闰年 2024 年 2 月表里是 1~29 号', shown_days(a.dp_date) == list(range(1, 30)),
  len(shown_days(a.dp_date)))

_w, _h = a.dp_date.popup.winfo_reqwidth(), a.dp_date.popup.winfo_reqheight()
t('日历是一张「大表」（宽高都够大）', _w >= 240 and _h >= 220, '%dx%d' % (_w, _h))
a.dp_date.goto(2026, 9)
a.dp_date.pick(15)
root.update()
t('点 15 号就选到 9 月 15 日', a.dp_date.get() == '2026-09-15', a.dp_date.get())
t('选完自动收起', not a.dp_date._alive())

a.dp_date.open_popup()
root.update()
a.dp_date.goto(2026, 12)
a.dp_date.goto(a.dp_date._y, a.dp_date._m + 1)
t('12 月往后翻 → 2027 年 1 月', (a.dp_date._y, a.dp_date._m) == (2027, 1),
  (a.dp_date._y, a.dp_date._m))
a.dp_date.goto(2026, 1)
a.dp_date.goto(a.dp_date._y, 0)
t('1 月往前翻 → 2025 年 12 月', (a.dp_date._y, a.dp_date._m) == (2025, 12),
  (a.dp_date._y, a.dp_date._m))
t('年份下拉含历史年份', '2025' in [str(v) for v in a.dp_date.cb_y.cget('values')],
  [str(v) for v in a.dp_date.cb_y.cget('values')])
a.dp_date.close_popup()
root.update()
t('能主动收起', not a.dp_date._alive())

a.dp_date.set('2025-04-31')
t('非法日期（4 月 31 日）被挡下 → 回退今天', a.dp_date.get() == app.today_str(), a.dp_date.get())
a.dp_date.set('2026-09-18')
t('日期可精确设置', a.dp_date.get() == '2026-09-18', a.dp_date.get())
t('显示文字带星期', '周' in a.dp_date.var_display.get(), a.dp_date.var_display.get())
a.dp_date.set_today()
t('「今天」按钮生效', a.dp_date.get() == app.today_str())

# 通过界面录入一笔（日期走下拉）
a.dp_date.set('2026-09-10')
a.cb_member.set('小明')
a.e_amount.delete(0, 'end')
a.e_amount.insert(0, '50')
a.e_note.insert(0, '界面录入')
a.add_record()
root.update()
newest = sorted(a.store.records, key=lambda r: r['createdAt'])[-1]
t('界面录入后 3 行', len(a.tv_rec.get_children()) == 3, len(a.tv_rec.get_children()))
t('录入日期取自下拉选择', newest['date'] == '2026-09-10', newest['date'])
t('录入支付方式默认校园卡', newest['method'] == '校园卡', newest['method'])
t('界面录入后总额 ¥350.00', a.stat_labels['total'].cget('text') == '¥350.00',
  a.stat_labels['total'].cget('text'))
t('录入后金额框已清空', a.e_amount.get() == '')
t('录入后成员框保留', a.cb_member.get() == '小明')
t('成员下拉含新成员', '小明' in list(a.cb_member.cget('values')))
t('数据已自动落盘', len(app.Store(GUI_DATA).records) == 3)

# 快捷金额
a.quick_add(100)
t('快捷 +100 生效', a.e_amount.get() == '100', a.e_amount.get())
a.quick_add(50)
t('再 +50 = 150', a.e_amount.get() == '150', a.e_amount.get())
a.clear_form()
t('清空按钮生效', a.e_amount.get() == '' and a.e_note.get() == '')

# 筛选 & 排序
a.var_kw.set('界面录入')
root.update()
t('搜索筛选命中 1 行', len(a.tv_rec.get_children()) == 1, len(a.tv_rec.get_children()))
a.reset_filter()
root.update()
t('重置筛选恢复 3 行', len(a.tv_rec.get_children()) == 3)
t('年份下拉已填充', '全部年份' in list(a.cb_fyear.cget('values')),
  list(a.cb_fyear.cget('values')))
t('月份下拉共 13 项', len(a.cb_fmonth.cget('values')) == 13,
  len(a.cb_fmonth.cget('values')))
a.var_fyear.set('2026')
a.refresh_records()
root.update()
t('按年筛选：2026 年 3 行', len(a.tv_rec.get_children()) == 3, len(a.tv_rec.get_children()))
a.var_fyear.set('2025')
a.refresh_records()
root.update()
t('按年筛选：2025 年 0 行', len(a.tv_rec.get_children()) == 0)
a.reset_filter()
a.var_fmonth.set('1')
a.refresh_records()
root.update()
t('按月筛选：1 月 0 行', len(a.tv_rec.get_children()) == 0)
a.reset_filter()
root.update()
t('重置筛选恢复 3 行', len(a.tv_rec.get_children()) == 3)
a.sort_by('amount')
root.update()
first = a.tv_rec.item(a.tv_rec.get_children()[0])['values']
t('按金额排序首行为 200（金额在第 3 列）', '200.00' in str(first[2]), first)
t('排序箭头已更新', '▼' in a.tv_rec.heading('amount')['text'] or '▲' in a.tv_rec.heading('amount')['text'],
  a.tv_rec.heading('amount')['text'])
t('点表头排序时，排序下拉跟着同步', '金额' in a.var_sort.get(), a.var_sort.get())
t('明细表已经没有序号列了', 'seq' not in a.tv_rec.cget('columns'),
  a.tv_rec.cget('columns'))
t('汇总表序号列表头带箭头时也不会丢字',
  '序号' in str(a.tv_sum.heading('no')['text']), a.tv_sum.heading('no')['text'])
_a2 = a.var_sort.get()
a.sort_by('amount')
root.update()
t('再点一次表头 → 换成相反方向', a.var_sort.get() != _a2, (_a2, a.var_sort.get()))
a.sort_by('date')
root.update()

# 选中删除
target = a.tv_rec.get_children()[0]
a.tv_rec.selection_set(target)
a.delete_selected()
root.update()
t('界面删除后 2 行', len(a.tv_rec.get_children()) == 2, len(a.tv_rec.get_children()))

# 结算单复制
a.copy_report()
t('结算单进入剪贴板', '电费充值汇总' in root.clipboard_get(), root.clipboard_get()[:40])

# 导出 CSV / JSON（拦截文件对话框）
a._open_path = lambda p: None  # 避免测试时真的调用系统程序打开文件
csv_out = os.path.join(tmp, 'out.csv')
json_out = os.path.join(tmp, 'out.json')
app.filedialog.asksaveasfilename = lambda *a2, **k: csv_out
a.export_csv()
t('CSV 文件已写出', os.path.exists(csv_out))
with open(csv_out, 'rb') as f:
    head = f.read(3)
t('CSV 带 UTF-8 BOM（Excel 中文不乱码）', head == b'\xef\xbb\xbf', head)
app.filedialog.asksaveasfilename = lambda *a2, **k: json_out
a.export_json()
t('JSON 文件已写出', os.path.exists(json_out))
with open(json_out, 'r', encoding='utf-8') as f:
    dumped = json.load(f)
t('JSON 内容完整', dumped['room'] == 'B-208' and len(dumped['records']) == 2, dumped.get('room'))

# 导入
imp = os.path.join(tmp, 'imp.json')
with open(imp, 'w', encoding='utf-8') as f:
    json.dump({'room': 'C-1', 'members': ['小天'],
               'records': [{'id': 'q1', 'date': '2026-09-10', 'member': '小天', 'amount': 60,
                            'method': '现金', 'note': ''}]}, f, ensure_ascii=False)
app.filedialog.askopenfilename = lambda *a2, **k: imp
a.import_json()
root.update()
t('导入后 3 行', len(a.tv_rec.get_children()) == 3, len(a.tv_rec.get_children()))
t('导入后含新成员', '小天' in list(a.cb_member.cget('values')))

# 期初只在「明细账单」里显示 —— 塞一条进去，看看别的地方有没有露馅
a.store.add('2025-09-09', '小明', 350, '校园卡', '期初首笔（原始表首行，无 * 标记）')
a.refresh_all()
root.update()
t('加了期初后，汇总表依然没有「期初」列',
  'initial' not in a.tv_sum.cget('columns'), a.tv_sum.cget('columns'))
t('加了期初后，汇总表小字不提期初',
  '期初' not in a.lbl_sum_sub.cget('text'), a.lbl_sum_sub.cget('text'))
t('加了期初后，明细表小字也不提期初',
  '期初' not in a.lbl_rec_sub.cget('text'), a.lbl_rec_sub.cget('text'))
t('加了期初后，账单里能看见它（带 initial 标记）',
  any('initial' in a.tv_rec.item(i)['tags'] for i in a.tv_rec.get_children()),
  [a.tv_rec.item(i)['tags'] for i in a.tv_rec.get_children()])
t('加了期初后，统计卡笔数不把它算进去',
  a.stat_labels['count'].cget('text') == '3 笔', a.stat_labels['count'].cget('text'))
t('加了期初后，结算单里还是不提期初', '期初' not in a.store.report_text())

# ---------------- 导出 txt / xlsx ----------------
print()
print('=== 导出 txt / xlsx ===')
XLNS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def _cell_texts(sheet_xml):
    """把一张工作表里所有内联文本单元格抠出来"""
    out = []
    for c in ET.fromstring(sheet_xml).iter(XLNS + 'c'):
        is_el = c.find(XLNS + 'is')
        if is_el is not None:
            t_el = is_el.find(XLNS + 't')
            out.append((t_el.text or '') if t_el is not None else '')
    return out


def _cell_nums(sheet_xml):
    """所有「真数字」单元格的 (引用, 字面量)"""
    out = []
    for c in ET.fromstring(sheet_xml).iter(XLNS + 'c'):
        if c.get('t') is None:
            v = c.find(XLNS + 'v')
            if v is not None:
                out.append((c.get('r'), v.text))
    return out


xp = os.path.join(tmp, 'x.xlsx')
with open(xp, 'wb') as f:
    f.write(a.store.xlsx_bytes())
t('xlsx 是合法 zip', zipfile.is_zipfile(xp))
z = zipfile.ZipFile(xp)
NEED = ['[Content_Types].xml', '_rels/.rels', 'xl/workbook.xml',
        'xl/_rels/workbook.xml.rels', 'xl/styles.xml',
        'xl/worksheets/sheet1.xml', 'xl/worksheets/sheet2.xml',
        'xl/worksheets/sheet3.xml']
t('xlsx 部件齐全', all(n in z.namelist() for n in NEED), z.namelist())
t('xlsx 无坏成员', z.testzip() is None)
bad_xml = []
for n in z.namelist():
    if n.endswith(('.xml', '.rels')):
        try:
            ET.fromstring(z.read(n))
        except Exception as e:
            bad_xml.append('%s: %s' % (n, e))
t('xlsx 里每个 XML 都良构', not bad_xml, bad_xml)

sheets = [(s.get('name'), s.get('sheetId'))
          for s in ET.fromstring(z.read('xl/workbook.xml')).iter(XLNS + 'sheet')]
t('三张工作表且顺序正确', sheets == [('充值明细', '1'), ('成员汇总', '2'), ('总览', '3')], sheets)

s1 = z.read('xl/worksheets/sheet1.xml').decode('utf-8')
t('明细表第一行是表头',
  _cell_texts(s1)[:5] == ['日期', '充值人', '金额(元)', '支付方式', '备注'],
  _cell_texts(s1)[:6])
nums1 = _cell_nums(s1)
t('金额写成了真数字（不是文本）', any(r == 'C3' for r, _ in nums1), nums1[:6])
t('整数不带小数点尾巴', any(v == '350' for _, v in nums1), nums1[:6])
t('明细表冻结首行', 'state="frozen"' in s1)
t('明细表带自动筛选', '<autoFilter' in s1)
t('明细表里能看到期初', '期初' in s1)

s2 = z.read('xl/worksheets/sheet2.xml').decode('utf-8')
t('汇总表没有「期初」字样', '期初' not in s2)
t('汇总表表头就是 6 列', _cell_texts(s2)[:6] ==
  ['序号', '成员', '笔数', '累计充值(元)', '占比', '最近充值'], _cell_texts(s2)[:6])

# 备注里的 XML 特殊字符必须转义对了，不能被吃掉或撑坏文件
a.store.add('2026-09-21', '小明', 12.5, '现金', '带&和<尖括号>的备注')
zx = zipfile.ZipFile(io.BytesIO(a.store.xlsx_bytes()))
zx1 = zx.read('xl/worksheets/sheet1.xml').decode('utf-8')
t('特殊字符备注转义正确（读回来还是原文）',
  '带&和<尖括号>的备注' in _cell_texts(zx1), [v for v in _cell_texts(zx1) if '带' in v])

txt = a.store.txt_text()
t('txt 有总览 / 成员汇总 / 充值明细三段',
  all(k in txt for k in ('【总览】', '【成员汇总】', '【充值明细】')))
t('txt 期初只出现在明细段（前面两段都没有）',
  '期初' not in txt.split('【充值明细】')[0])
t('txt 明细段里有期初标记', '期初' in txt.split('【充值明细】')[1])
t('txt 是 CRLF 换行（记事本友好）', '\r\n' in txt)
t('txt 金额格式是 ¥ + 两位小数', '¥' in txt and '12.50' in txt,
  [l for l in txt.splitlines() if '¥' in l][:4])
_big = app.Store(os.path.join(tmp, 'big.json'))
_big.room = 'X'
_big.add('2026-01-01', '甲', 1234.56, '微信', '')
_big.add('2026-01-02', '乙', 1234567.8, '校园卡', '')
_btxt = _big.txt_text()
t('txt 大金额带千分位', '¥1,234.56' in _btxt and '¥1,234,567.80' in _btxt,
  [l for l in _btxt.splitlines() if '¥1' in l])

emp = app.Store(os.path.join(tmp, 'empty.json'))
t('空账本 txt 不崩', '（暂无记录）' in emp.txt_text())
t('空账本 xlsx 也生成得出', len(emp.xlsx_bytes()) > 400
  and zipfile.ZipFile(io.BytesIO(emp.xlsx_bytes())).testzip() is None)

# 一键导出：不弹「另存为」，直接落到程序旁的「导出」文件夹
# 这里把 app_dir 指到临时目录，免得往真的程序目录里写测试垃圾
_real_app_dir = app.app_dir
app.app_dir = lambda: tmp
edir = a.export_dir()
before = set(os.listdir(edir)) if os.path.isdir(edir) else set()
a.export_all()
after = set(os.listdir(edir)) if os.path.isdir(edir) else set()
app.app_dir = _real_app_dir
fresh = after - before
t('一键导出写出 2 个文件', len(fresh) == 2, fresh)
t('一键导出的是一份 txt + 一份 xlsx',
  any(n.endswith('.txt') for n in fresh) and any(n.endswith('.xlsx') for n in fresh), fresh)
t('一键导出的 xlsx 也能被解析',
  all(zipfile.ZipFile(os.path.join(edir, n)).testzip() is None
      for n in fresh if n.endswith('.xlsx')))
t('一键导出的文件名带房间 + 时间戳',
  all(n.startswith((a.store.room or '电费记账') + '_') and len(n.split('_')[-1]) > 8
      for n in fresh), (a.store.room, fresh))
for n in fresh:                      # 别把测试产物留在临时目录里
    os.remove(os.path.join(edir, n))
if os.path.isdir(edir) and not os.listdir(edir):
    os.rmdir(edir)

# 顶栏入口
allw = descendants(root)
btn_texts = [w.cget('text') for w in allw if isinstance(w, app.tk.Button)]
t('顶栏有「一键导出」按钮', any('一键导出' in s for s in btn_texts), btn_texts)
t('顶栏有「手机同步」按钮', any('手机同步' in s for s in btn_texts), btn_texts)
t('同步服务已挂到主窗口（改数据回主线程 / 同步完刷界面）',
  a.sync.ui_root is root and a.sync.on_applied is not None)
menus = [w for w in allw if isinstance(w, app.tk.Menubutton)]
t('顶栏有「更多导出」下拉', any('更多导出' in w.cget('text') for w in menus),
  [w.cget('text') for w in menus])
labels = []
if menus:
    m = menus[0].nametowidget(menus[0].cget('menu'))
    end = m.index('end')
    for i in range((end or 0) + 1):
        try:
            if m.type(i) == 'command':
                labels.append(m.entrycget(i, 'label'))
        except Exception:
            pass
t('下拉里有 TXT / Excel / CSV / JSON 四项',
  sum(1 for s in ('TXT', 'Excel', 'CSV', 'JSON') if any(s in x for x in labels)) == 4, labels)

# 另存为路径版本（TXT / xlsx 各走一次）
txt_out = os.path.join(tmp, 'o.txt')
app.filedialog.asksaveasfilename = lambda *a2, **k: txt_out
a.export_txt()
t('导出 TXT 文件已写出', os.path.exists(txt_out))
t('导出的 TXT 带 BOM（记事本不乱码）',
  open(txt_out, 'rb').read(3) == b'\xef\xbb\xbf')
xls_out = os.path.join(tmp, 'o.xlsx')
app.filedialog.asksaveasfilename = lambda *a2, **k: xls_out
a.export_xlsx()
t('导出 xlsx 文件已写出', os.path.exists(xls_out))
t('另存为的 xlsx 也是合法工作簿', zipfile.ZipFile(xls_out).testzip() is None)

# 崩溃兜底
def boom(*_a):
    raise RuntimeError('测试异常')
try:
    root.report_callback_exception(*[RuntimeError, RuntimeError('x'), None])
    t('异常兜底可调用', True)
except Exception as e:
    t('异常兜底可调用', False, e)

print('=== 9. 局域网同步（起真服务，用真 HTTP 打接口）===')
import urllib.request                                                    # noqa: E402
import urllib.error                                                      # noqa: E402
import threading                                                         # noqa: E402
import time                                                              # noqa: E402


def _http(url, obj=None, timeout=10):
    """返回 (状态码, 文本)；HTTP 错误也当正常结果返回，方便断言"""
    data = None if obj is None else json.dumps(obj, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        url, data=data, method='POST' if data else 'GET',
        headers={'Content-Type': 'application/json'} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')


# —— 9a. 数据层直连（不挂界面）——
sst = app.Store(os.path.join(tmp, 'sync.json'))
sst.room = '302'
sst.add('2026-09-01', '甲', 100, '校园卡', '')
sst.add('2026-09-02', '乙', 200, '校园卡', '')
sst.save()
sst.clear_history()

srv = app.SyncServer(sst)
srv.new_pair()
okstart, startmsg = srv.start(0)          # 端口给 0 = 随便挑个空闲的
t('同步服务能启动', okstart, startmsg)
t('启动后拿到的端口是个真端口', srv.port > 0, srv.port)
t('配对码是 4 位数字', len(srv.pair) == 4 and srv.pair.isdigit(), srv.pair)
sbase = 'http://127.0.0.1:%d' % srv.port

code, body = _http(sbase + '/ping?pair=' + srv.pair)
pj = json.loads(body)
t('ping 返回 200 且带应用名', code == 200 and pj.get('app') == app.APP_NAME, (code, body))
t('ping 报对条数 / 房间', pj.get('records') == 2 and pj.get('room') == '302', pj)
wrong = '0000' if srv.pair != '0000' else '1111'
code, _b = _http(sbase + '/ping?pair=' + wrong)
t('配对码不对 → 403', code == 403, code)
code, _b = _http(sbase + '/ping?pair=')
t('不带配对码 → 403', code == 403, code)
code, _b = _http(sbase + '/nope?pair=' + srv.pair)
t('不存在的接口 → 404', code == 404, code)

code, body = _http(sbase + '/export?pair=' + srv.pair)
book = json.loads(body)
t('export 是桌面版 JSON 格式', code == 200 and book.get('app') == app.APP_NAME
  and len(book.get('records') or []) == 2, (code, list(book)))
t('export 出来的记录都带 id', all(r.get('id') for r in book['records']))

victim = sst.records[0]['id']
phone = {
    'app': app.APP_NAME, 'version': '1.1', 'room': '302',
    'members': ['甲', '乙', '丙'], 'memberIds': {'甲': 1, '乙': 2, '丙': 3},
    'records': [{'id': 'aa11bb22cc33', 'date': '2026-09-10', 'member': '丙',
                 'amount': 300, 'method': '微信', 'note': '手机加的',
                 'createdAt': 1767000000001}],
    'deleted': [dict(sst.get(victim), deletedAt=1767000000002)],
}
code, body = _http(sbase + '/import?pair=' + srv.pair, phone)
rj = json.loads(body)
t('import 返回 200', code == 200, (code, body))
t('import 报「新增 1 / 删除 1」', rj.get('added') == 1 and rj.get('trashed') == 1, rj)
t('手机新记录进来了', any(r['id'] == 'aa11bb22cc33' for r in sst.records))
t('手机删的那条在电脑上进回收站了',
  any(r['id'] == victim for r in sst.deleted)
  and all(r['id'] != victim for r in sst.records))
t('新成员丙也并进来了', '丙' in sst.members, sst.members)

code, body = _http(sbase + '/import?pair=' + srv.pair, phone)
rj = json.loads(body)
t('再同步一次是幂等的（不再重复加）',
  rj.get('added') == 0 and rj.get('trashed') == 0, rj)

code, _b = _http(sbase + '/import?pair=' + srv.pair, {'app': 'x'})
t('缺 records 的包 → 400', code == 400, code)
code, _b = _http(sbase + '/import?pair=' + srv.pair, [])
t('传数组 → 400', code == 400, code)

sst2 = app.Store(os.path.join(tmp, 'sync.json'))
t('同步结果真的落盘了', len(sst2.records) == 2 and len(sst2.deleted) == 1,
  (len(sst2.records), len(sst2.deleted)))
srv.stop()
t('stop() 之后 running() 为假', srv.running() is False)
code, _b = _http(sbase + '/ping?pair=' + srv.pair, timeout=3)
t('停止后 ping 不再返回 200', code != 200, code)

# —— 9b. 挂在界面上：请求从后台线程来，改数据要回主线程 ——
okstart, startmsg = a.sync.start(0)
t('界面上的同步服务能启动', okstart, startmsg)
ui_res = {}


def _post_from_thread():
    try:
        ui_res['code'], ui_res['body'] = _http(
            'http://127.0.0.1:%d/import?pair=%s' % (a.sync.port, a.sync.pair),
            {'app': app.APP_NAME, 'room': 'B-208', 'members': ['小明', '小红', '小刚'],
             'memberIds': {'小明': 1, '小红': 2, '小刚': 3},
             'records': [{'id': 'ui1112223334', 'date': '2026-09-30', 'member': '小刚',
                          'amount': 66, 'method': '微信', 'note': '线程来的',
                          'createdAt': 1767000000003}],
             'deleted': []})
    except Exception as e:                        # noqa: BLE001
        ui_res['err'] = e


th = threading.Thread(target=_post_from_thread, daemon=True)
th.start()
t0 = time.time()
while th.is_alive() and time.time() - t0 < 20:
    root.update()          # 泵主线程事件循环，_run_on_ui 的 after(0) 才会被执行
    time.sleep(0.02)
th.join(3)
t('后台线程的请求拿到了 200', ui_res.get('code') == 200, ui_res)
t('后台线程收到的是 ok:true', json.loads(ui_res.get('body') or '{}').get('ok') is True,
  ui_res.get('body'))
t('数据真的并进了界面用的那份 Store',
  any(r.get('id') == 'ui1112223334' for r in a.store.records))
t('界面也刷新了（明细表出现了新记录）',
  any('小刚' in str(a.tv_rec.item(i)['values']) for i in a.tv_rec.get_children()))
t('状态栏提示了同步结果', '手机同步' in a.lbl_saved.cget('text'), a.lbl_saved.cget('text'))
a.sync.stop()
t('界面上的服务也停得掉', a.sync.running() is False)

# 面板能打开（只冒烟：建出来再关掉）
tops_before = [w for w in root.winfo_children() if isinstance(w, app.tk.Toplevel)]
try:
    a.open_lan_sync()
    root.update()
    tops = [w for w in root.winfo_children() if isinstance(w, app.tk.Toplevel)]
    t('「手机同步」面板打得开', len(tops) > len(tops_before), len(tops))
    for w in tops:
        if w not in tops_before:
            w.destroy()
except Exception as e:                            # noqa: BLE001
    t('「手机同步」面板打得开', False, e)
root.update()

a.on_close()
t('关闭窗口正常退出', True)

shutil.rmtree(tmp, ignore_errors=True)
print('\n结果：%d 通过 / %d 失败' % (PASS[0], FAIL[0]))
sys.exit(1 if FAIL[0] else 0)
