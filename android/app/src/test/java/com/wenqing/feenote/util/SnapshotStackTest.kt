package com.wenqing.feenote.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * [SnapshotStack] 的单元测试。
 *
 * 撤销功能出 bug 的地方基本都在这几个边界上：
 * 撤销两步之后又做了新动作、栈满了丢哪个、空栈时按钮该不该亮。
 * 所以这些用例写得比"能跑通"要细一点。
 */
class SnapshotStackTest {

    @Test
    fun `空栈时撤销和恢复都不可用`() {
        val s = SnapshotStack<String>()
        assertFalse(s.canUndo)
        assertFalse(s.canRedo)
        assertNull(s.undoLabel)
        assertNull(s.redoLabel)
        assertNull(s.undo("now"))
        assertNull(s.redo("now"))
    }

    @Test
    fun `撤销交回来的是 push 那一刻的状态，不是当前状态`() {
        val s = SnapshotStack<String>()
        s.push("记一笔 甲 ¥100", "state-0")
        assertEquals(1, s.size)
        assertEquals("记一笔 甲 ¥100", s.undoLabel)

        val r = s.undo("state-1")
        assertEquals("记一笔 甲 ¥100", r!!.label)
        assertEquals("state-0", r.value)
    }

    @Test
    fun `撤销之后可以恢复，恢复交回来的是撤销时的当前状态`() {
        val s = SnapshotStack<String>()
        s.push("记一笔", "state-0")
        s.undo("state-1")

        assertTrue(s.canRedo)
        assertEquals("记一笔", s.redoLabel)

        val r = s.redo("state-0")
        assertEquals("记一笔", r!!.label)
        assertEquals("state-1", r.value)

        assertTrue(s.canUndo)
        assertFalse(s.canRedo)
    }

    @Test
    fun `多步撤销按后进先出`() {
        val s = SnapshotStack<String>()
        s.push("第一步", "s0")
        s.push("第二步", "s1")
        s.push("第三步", "s2")

        assertEquals("第三步", s.undo("s3")!!.label)
        assertEquals("第二步", s.undo("s2")!!.label)
        assertEquals("第一步", s.undo("s1")!!.label)
        assertFalse(s.canUndo)
        assertNull(s.undo("s0"))
    }

    @Test
    fun `做了新动作之后，redo 被清掉`() {
        val s = SnapshotStack<String>()
        s.push("A", "s0")
        s.push("B", "s1")
        s.undo("s2")
        assertTrue(s.canRedo)

        // 撤销之后又改了东西，那条被撤销的旧路就不该还能"重做"回来
        s.push("C", "s2")
        assertFalse(s.canRedo)
        assertNull(s.redo("s3"))
        assertEquals("C", s.undoLabel)
    }

    @Test
    fun `连续的撤销恢复可以反复来回`() {
        val s = SnapshotStack<String>()
        s.push("A", "s0")
        var cur = "s1"

        for (i in 0 until 5) {
            val u = s.undo(cur)!!
            cur = u.value
            assertEquals("s0", cur)
            val r = s.redo(cur)!!
            cur = r.value
            assertEquals("s1", cur)
        }
        assertTrue(s.canUndo)
        assertFalse(s.canRedo)
    }

    @Test
    fun `超过上限时丢掉最老的一步`() {
        val s = SnapshotStack<String>(limit = 3)
        s.push("1", "s0")
        s.push("2", "s1")
        s.push("3", "s2")
        s.push("4", "s3")

        assertEquals(3, s.size)
        assertEquals("4", s.undo("s4")!!.label)
        assertEquals("3", s.undo("s3")!!.label)
        assertEquals("2", s.undo("s2")!!.label)
        // 「1」已经因为超限被丢掉了
        assertFalse(s.canUndo)
    }

    @Test
    fun `clear 把两边都清空`() {
        val s = SnapshotStack<String>()
        s.push("A", "s0")
        s.push("B", "s1")
        s.undo("s2")
        s.clear()
        assertFalse(s.canUndo)
        assertFalse(s.canRedo)
        assertEquals(0, s.size)
    }

    @Test
    fun `装得下任意类型，不只是字符串`() {
        data class Book(val room: String, val count: Int)

        val s = SnapshotStack<Book>(limit = 2)
        s.push("记一笔", Book("302", 40))
        val r = s.undo(Book("302", 41))!!
        assertEquals(Book("302", 40), r.value)
        assertEquals("302", r.value.room)
        assertEquals(40, r.value.count)
    }

    @Test
    fun `撤销到中途再撤销一步，redo 栈按相反顺序排`() {
        val s = SnapshotStack<String>()
        s.push("A", "s0")
        s.push("B", "s1")

        // 当前是 s2：撤销 B → s1
        assertEquals("B", s.undo("s2")!!.label)
        // 再撤销 A → s0
        assertEquals("A", s.undo("s1")!!.label)

        // 恢复的应该是 A（最后被撤销的那个）
        assertEquals("A", s.redo("s0")!!.label)
        assertEquals("B", s.redo("s1")!!.label)
    }
}
