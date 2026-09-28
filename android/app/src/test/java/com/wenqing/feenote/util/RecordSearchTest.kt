package com.wenqing.feenote.util

import com.wenqing.feenote.data.Record
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 记录搜索的单元测试。
 *
 * 为什么值得单独测：搜索的两种错都很隐蔽 ——
 * **该命中的没命中**（用着用着就不信搜索了），
 * 和**不该命中的也命中了**（多词关键词一放宽就变成「或」，结果一屏噪音）。
 * 这两条靠肉眼扫代码基本看不出来，所以用例写得细一点。
 */
class RecordSearchTest {

    private fun rec(
        date: String = "2026-09-24",
        member: String = "甲",
        amount: Double = 50.0,
        method: String = "校园卡",
        note: String = "",
        initial: Boolean = false,
    ) = Record(
        date = date, member = member, amount = amount,
        method = method, note = note, initial = initial,
    )

    private val sample = listOf(
        rec(date = "2026-09-24", member = "甲", amount = 50.0, method = "校园卡", note = "开学第一次"),
        rec(date = "2026-09-27", member = "乙", amount = 100.0, method = "微信", note = "余额不足了"),
        rec(date = "2026-10-05", member = "甲", amount = 200.0, method = "支付宝", note = ""),
        rec(date = "2026-10-05", member = "丙", amount = 100.0, method = "校园卡", initial = true),
    )

    private fun datesOf(query: String) = RecordSearch.filter(sample, query).map { it.date }

    // ---------------------------------------------------------------- 基本

    @Test
    fun `空关键词原样返回全部`() {
        assertEquals(sample, RecordSearch.filter(sample, ""))
        assertEquals(sample, RecordSearch.filter(sample, "   "))
    }

    @Test
    fun `搜不到就返回空——不会兜底返回全部`() {
        assertTrue(RecordSearch.filter(sample, "不存在的词").isEmpty())
    }

    @Test
    fun `不会改动传进来的列表`() {
        val before = sample.toList()
        RecordSearch.filter(sample, "甲")
        assertEquals(before, sample)
    }

    // ---------------------------------------------------------------- 各字段

    @Test
    fun `按成员搜`() {
        assertEquals(listOf("2026-09-24", "2026-10-05"), datesOf("甲"))
    }

    @Test
    fun `按支付方式搜`() {
        assertEquals(listOf("2026-09-27"), datesOf("微信"))
    }

    @Test
    fun `按备注搜`() {
        assertEquals(listOf("2026-09-27"), datesOf("余额"))
    }

    @Test
    fun `按完整日期搜——2026-10-05 那两笔`() {
        assertEquals(listOf("2026-10-05", "2026-10-05"), datesOf("2026-10-05"))
    }

    @Test
    fun `按年月搜能圈出整月`() {
        assertEquals(listOf("2026-10-05", "2026-10-05"), datesOf("2026-10"))
    }

    @Test
    fun `按中文日期搜——9月24日`() {
        assertEquals(listOf("2026-09-24"), datesOf("9月24日"))
    }

    @Test
    fun `按星期搜——2026-09-24 是周四`() {
        assertEquals(listOf("2026-09-24"), datesOf("周四"))
    }

    @Test
    fun `按金额搜——50 命中 50 元那笔`() {
        assertEquals(listOf("2026-09-24"), datesOf("50"))
    }

    @Test
    fun `金额带货币符号也能搜`() {
        assertEquals(listOf("2026-09-24"), datesOf("¥50"))
    }

    @Test
    fun `金额小数写法能搜——100点0`() {
        assertEquals(listOf("2026-09-27", "2026-10-05"), datesOf("100.0"))
    }

    @Test
    fun `搜期初能找到标记了期初的那笔`() {
        assertEquals(listOf("2026-10-05"), datesOf("期初"))
    }

    // ---------------------------------------------------------------- 多词

    @Test
    fun `多词是「与」不是「或」——微信加100只出微信那笔`() {
        assertEquals(listOf("2026-09-27"), datesOf("微信 100"))
    }

    @Test
    fun `多词顺序无关`() {
        assertEquals(datesOf("微信 100"), datesOf("100 微信"))
    }

    @Test
    fun `多词里有一个搜不到就整条不匹配`() {
        assertTrue(RecordSearch.filter(sample, "微信 支付宝").isEmpty())
    }

    @Test
    fun `多余空格不会把词切空`() {
        assertEquals(RecordSearch.terms("  微信   100  "), listOf("微信", "100"))
        assertEquals(listOf("2026-09-27"), datesOf("  微信    100  "))
    }

    @Test
    fun `能收窄到具体某一条——成员加日期`() {
        assertEquals(listOf("2026-10-05"), datesOf("甲 10月"))
    }

    // ---------------------------------------------------------------- 边界

    @Test
    fun `空列表不会炸`() {
        assertTrue(RecordSearch.filter(emptyList(), "甲").isEmpty())
    }

    @Test
    fun `大小写不敏感`() {
        val upper = listOf(rec(member = "Amy", note = "WECHAT"))
        assertEquals(1, RecordSearch.filter(upper, "amy").size)
        assertEquals(1, RecordSearch.filter(upper, "wechat").size)
    }

    @Test
    fun `只搜成员时不会因为别人名字里含这个字而漏掉`() {
        // 「甲」不该匹配「甲甲」以外的其它人；这里确保结果是精确的 2 笔
        assertEquals(2, RecordSearch.filter(sample, "甲").size)
    }

    @Test
    fun `过滤不会改变条数以外的任何东西`() {
        val hit = RecordSearch.filter(sample, "校园卡")
        assertEquals(2, hit.size)
        assertEquals("校园卡", hit[0].method)
        assertEquals("校园卡", hit[1].method)
    }
}
