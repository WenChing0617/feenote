package com.wenqing.feenote.util

import com.wenqing.feenote.data.Member
import com.wenqing.feenote.data.Record
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * 手机版与桌面版 JSON 互通的契约测试。
 *
 * 要证明的只有两件事：
 * 1. **手机读得懂电脑导出的文件** —— 拿桌面版真实导出的 `电费记账数据.json` 直接喂给解析器；
 * 2. **电脑读得懂手机导出的文件** —— 检查 [JsonCodec.build] 的产物字段与桌面版
 *    `Store.payload()` 完全同构（测试会把产物落盘，交给外部脚本用桌面版的口径再验一遍）。
 *
 * 只要这两条成立，两端的「导入账本」就能互相吃对方的文件。
 */
class JsonCodecTest {

    // ---------------------------------------------------------------- 手机 ← 电脑

    @Test
    fun `能解析桌面版真实导出的账本`() {
        val book = JsonCodec.parse(desktopSample())

        assertEquals("302", book.room)
        assertEquals(listOf("甲", "乙", "丙", "丁", "戊"), book.members)
        assertEquals(5, book.memberIds.size)
        assertEquals(1, book.memberIds["甲"])
        assertEquals(5, book.memberIds["戊"])

        assertEquals(40, book.records.size)
        assertEquals(0, book.deleted.size)
    }

    @Test
    fun `桌面版文件的 40 条记录逐条对得上`() {
        val book = JsonCodec.parse(desktopSample())

        // 首条：期初首笔
        val first = book.records.first()
        assertEquals("ce3f1890bccc", first.uid)
        assertEquals("2025-09-09", first.date)
        assertEquals("甲", first.member)
        assertEquals(30.0, first.amount, 0.0001)
        assertEquals("校园卡", first.method)
        assertTrue("首条应为期初", first.initial)

        // 末条：2026-09-24 丁
        val last = book.records.last()
        assertEquals("7e02804a9407", last.uid)
        assertEquals("2026-09-24", last.date)
        assertEquals("丁", last.member)
        assertEquals(70.0, last.amount, 0.0001)
        assertTrue("末条不是期初", !last.initial)

        // 累计金额必须等于 2000（与桌面版对账口径一致）
        assertEquals(2000.0, book.records.sumOf { it.amount }, 0.0001)

        // uid 不能有重复，否则合并去重会出错
        assertEquals(40, book.records.map { it.uid }.toSet().size)
    }

    // ---------------------------------------------------------------- 电脑 ← 手机

    @Test
    fun `导出的 JSON 与桌面版 payload 字段同构`() {
        val json = JsonCodec.build(
            room = "302",
            members = listOf(Member(1, "甲", 1), Member(2, "乙", 2)),
            records = listOf(
                Record(
                    id = 7, uid = "aaaa11112222", date = "2026-10-01", member = "甲",
                    amount = 88.5, method = "校园卡", note = "备注里有,逗号和\"引号\"",
                    initial = false, createdAt = 1767000000001L,
                )
            ),
            deleted = listOf(
                Record(
                    id = 9, uid = "bbbb33334444", date = "2026-10-02", member = "乙",
                    amount = 5.0, method = "微信", note = "", initial = false,
                    createdAt = 1767000000002L, deleted = true,
                )
            ),
            savedAt = "2026-09-28 11:30:00",
        )

        val root = JSONObject(json)

        // 桌面版 Store.payload() 的八个字段，一个都不能少
        assertEquals(
            listOf("app", "deleted", "memberIds", "members", "records", "room", "savedAt", "version"),
            root.keys().asSequence().sorted().toList(),
        )
        assertEquals("电费记账本", root.getString("app"))
        assertEquals("302", root.getString("room"))

        // records[].id 必须是 uid，不是自增主键（写错的话桌面版会当成新记录重复插入）
        val rec = root.getJSONArray("records").getJSONObject(0)
        assertEquals("aaaa11112222", rec.getString("id"))
        assertEquals("2026-10-01", rec.getString("date"))
        assertEquals(88.5, rec.getDouble("amount"), 0.0001)
        assertEquals(1767000000001L, rec.getLong("createdAt"))
        assertEquals(false, rec.getBoolean("initial"))
        // 备注里的逗号引号必须被正确转义
        assertEquals("备注里有,逗号和\"引号\"", rec.getString("note"))

        // 回收站是独立数组
        assertEquals(1, root.getJSONArray("deleted").length())
        assertEquals("bbbb33334444", root.getJSONArray("deleted").getJSONObject(0).getString("id"))

        // 成员编号表
        assertEquals(1, root.getJSONObject("memberIds").getInt("甲"))
        assertEquals(2, root.getJSONObject("memberIds").getInt("乙"))
    }

    @Test
    fun `导出再解析能原样还原`() {
        val members = listOf(Member(1, "甲", 1), Member(2, "乙", 2))
        val records = listOf(
            Record(1, "aaaa11112222", "2026-10-01", "甲", 88.5, "校园卡", "测试", false, 111L),
            Record(2, "bbbb33334444", "2026-10-02", "乙", 5.0, "微信", "", false, 222L),
        )
        val deleted = listOf(
            Record(3, "cccc55556666", "2026-10-03", "甲", 1.0, "现金", "删掉的", true, 333L, true),
        )

        val json = JsonCodec.build("302", members, records, deleted, "2026-09-28 11:30:00")
        val book = JsonCodec.parse(json)

        assertEquals("302", book.room)
        assertEquals(listOf("甲", "乙"), book.members)
        assertEquals(2, book.records.size)
        assertEquals(1, book.deleted.size)

        assertEquals("aaaa11112222", book.records[0].uid)
        assertEquals(88.5, book.records[0].amount, 0.0001)
        assertEquals(111L, book.records[0].createdAt)
        assertEquals("cccc55556666", book.deleted[0].uid)
        assertTrue("期初标记要能还原", book.deleted[0].initial)
    }

    // ---------------------------------------------------------------- 容错

    @Test
    fun `缺可选字段时不炸，用默认值兜住`() {
        val minimal = """
            { "records": [ { "date": "2026-10-01", "member": "甲", "amount": 10 } ] }
        """.trimIndent()

        val book = JsonCodec.parse(minimal)
        assertEquals(1, book.records.size)
        assertEquals("", book.records[0].uid)
        // 支付方式缺省留空，由数据层落库时补「校园卡」
        assertEquals("", book.records[0].method)
        assertEquals(false, book.records[0].initial)
        assertEquals(10.0, book.records[0].amount, 0.0001)
    }

    @Test
    fun `日期或成员缺失的记录会被跳过`() {
        val messy = """
            { "records": [
                { "date": "2026-10-01", "member": "甲", "amount": 10 },
                { "date": "", "member": "甲", "amount": 10 },
                { "date": "2026-10-02", "member": "", "amount": 10 }
            ] }
        """.trimIndent()

        assertEquals(1, JsonCodec.parse(messy).records.size)
    }

    @Test
    fun `带 BOM 的文件也能读`() {
        assertEquals(1, JsonCodec.parse("\uFEFF" + """{"records":[{"date":"2026-10-01","member":"甲","amount":1}]}""").records.size)
    }

    // ---------------------------------------------------------------- 给外部脚本的产物

    /**
     * 把一份「手机导出」的样本落盘，交给 Python 侧用桌面版 `Store.apply()` 的口径再验一遍，
     * 确认不存在重复插入。产物路径：`app/build/exchange-test/phone_export.json`
     */
    @Test
    fun `生成给桌面版校验用的样本文件`() {
        val records = listOf(
            Record(1, "ce3f1890bccc", "2025-09-09", "甲", 350.0, "校园卡", "期初首笔（原始表首行，无 * 标记）", true, 1767000000001L),
            Record(2, "b2a25b5d39b9", "2025-09-09", "乙", 350.0, "校园卡", "期初首笔（原始表首行，无 * 标记）", true, 1767000000002L),
            // 手机上新记的两条，桌面版没有
            Record(3, "111122223333", "2026-10-05", "戊", 60.0, "校园卡", "手机记的", false, 1791000000001L),
            Record(4, "444455556666", "2026-10-06", "丙", 40.0, "微信", "手机记的", false, 1791000000002L),
        )
        val deleted = listOf(
            Record(5, "deadbeef0001", "2026-09-30", "丁", 20.0, "校园卡", "手机删掉的", false, 1790000000001L, true),
        )

        val json = JsonCodec.build(
            room = "302",
            members = listOf(
                Member(1, "甲", 1), Member(2, "乙", 2), Member(3, "丙", 3),
                Member(4, "丁", 4), Member(5, "戊", 5),
            ),
            records = records,
            deleted = deleted,
            savedAt = "2026-09-28 11:30:00",
        )

        val out = File("build/exchange-test/phone_export.json")
        out.parentFile?.mkdirs()
        out.writeText(json, Charsets.UTF_8)

        assertTrue("样本文件应已写出", out.exists() && out.length() > 0)
    }

    private fun desktopSample(): String =
        javaClass.classLoader!!.getResourceAsStream("desktop_sample.json")!!
            .readBytes().toString(Charsets.UTF_8)
}
