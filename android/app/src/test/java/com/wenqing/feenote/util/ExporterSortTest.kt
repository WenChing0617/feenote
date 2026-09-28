package com.wenqing.feenote.util

import com.wenqing.feenote.data.Record
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 导出排序的单元测试。
 *
 * 为什么值得单独测：**顺序反了是肉眼扫代码看不出来的**。
 * 导出的 TXT / CSV 是发给室友看的，第一眼应该看到最近交的那笔，
 * 而不是开学第一天那笔 —— 这条规则很容易在某次重构里被顺手改回去。
 */
class ExporterSortTest {

    private fun rec(date: String, member: String = "甲", amount: Double = 50.0, at: Long = 0L) =
        Record(date = date, member = member, amount = amount, createdAt = at)

    @Test
    fun `最新的日期排在最上面`() {
        val sorted = Exporter.newestFirst(
            listOf(
                rec("2026-07-07"),
                rec("2026-09-27"),
                rec("2026-08-14"),
            )
        )
        assertEquals(
            listOf("2026-09-27", "2026-08-14", "2026-07-07"),
            sorted.map { it.date },
        )
    }

    @Test
    fun `同一天的多笔按创建时间倒序——最后记的排最上`() {
        val sorted = Exporter.newestFirst(
            listOf(
                rec("2026-09-27", at = 100L),
                rec("2026-09-27", at = 300L),
                rec("2026-09-27", at = 200L),
            )
        )
        assertEquals(listOf(300L, 200L, 100L), sorted.map { it.createdAt })
    }

    @Test
    fun `日期和创建时间都相同时不会乱序（用 id 兜底，保证导出结果稳定）`() {
        val sorted = Exporter.newestFirst(
            listOf(
                rec("2026-09-27", at = 100L).copy(id = 1L),
                rec("2026-09-27", at = 100L).copy(id = 9L),
                rec("2026-09-27", at = 100L).copy(id = 5L),
            )
        )
        assertEquals(listOf(9L, 5L, 1L), sorted.map { it.id })
    }

    @Test
    fun `期初首笔日期最早，所以会沉到最底下`() {
        val sorted = Exporter.newestFirst(
            listOf(
                rec("2025-09-09").copy(initial = true),
                rec("2026-09-27"),
                rec("2026-01-01"),
            )
        )
        assertEquals("2025-09-09", sorted.last().date)
        assertTrue("期初标记本身不能丢", sorted.last().initial)
    }

    @Test
    fun `空列表不会炸`() {
        assertEquals(emptyList<Record>(), Exporter.newestFirst(emptyList()))
    }

    @Test
    fun `只有一条时原样返回`() {
        val one = rec("2026-09-27")
        assertEquals(listOf(one), Exporter.newestFirst(listOf(one)))
    }

    @Test
    fun `排序不改变条数——不会漏记录也不会变出记录`() {
        val input = List(7) { rec("2026-09-${"%02d".format(it + 1)}") }
        assertEquals(input.size, Exporter.newestFirst(input).size)
        assertEquals(input.map { it.date }.toSet(), Exporter.newestFirst(input).map { it.date }.toSet())
    }

    @Test
    fun `不修改传进来的那个列表`() {
        val input = listOf(rec("2026-07-07"), rec("2026-09-27"))
        val before = input.map { it.date }
        Exporter.newestFirst(input)
        assertEquals("原列表不能被就地改掉", before, input.map { it.date })
    }
}
