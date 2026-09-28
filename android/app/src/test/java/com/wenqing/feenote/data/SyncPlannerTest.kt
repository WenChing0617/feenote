package com.wenqing.feenote.data

import com.wenqing.feenote.util.JsonCodec
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 同步预演 + 弱去重的单元测试。
 *
 * 这块逻辑是这一版的重点：uid 只能拦「同一条被同步两次」，
 * 拦不住「两边各自手输了同一笔账」—— 后者会让两边各留一份。
 * 所以 [SyncPlanner.weakKey] 抓「人 + 日期 + 金额」都一样的，
 * 抓到就交给用户确认。这些用例就是把边界钉死。
 *
 * 纯逻辑，不碰数据库，可以在 JVM 里直接跑。
 */
class SyncPlannerTest {

    // ---------------------------------------------------------------- 造数据

    private fun rec(
        uid: String,
        date: String = "2026-09-01",
        member: String = "甲",
        amount: Double = 100.0,
        note: String = "",
        createdAt: Long = 1_800_000_000_000,
    ) = Record(
        id = 0L, uid = uid, date = date, member = member, amount = amount,
        method = "校园卡", note = note, initial = false, createdAt = createdAt,
    )

    private fun row(
        uid: String,
        date: String = "2026-09-01",
        member: String = "甲",
        amount: Double = 100.0,
        note: String = "",
    ) = JsonCodec.Row(
        uid = uid, date = date, member = member, amount = amount,
        method = "校园卡", note = note, createdAt = 1_800_000_000_000L, initial = false,
    )

    private fun book(
        records: List<JsonCodec.Row> = emptyList(),
        deleted: List<JsonCodec.Row> = emptyList(),
    ) = JsonCodec.Book(
        room = "302",
        members = listOf("甲", "乙"),
        memberIds = mapOf("甲" to 1, "乙" to 2),
        records = records,
        deleted = deleted,
    )

    // ---------------------------------------------------------------- 弱去重键

    @Test
    fun `弱键把金额换算成分，浮点误差不影响判断`() {
        assertEquals(
            SyncPlanner.weakKey("2026-09-01", "甲", 100.0),
            SyncPlanner.weakKey("2026-09-01", "甲", 100.0),
        )
        // 0.1 + 0.2 那种经典误差不该把同一条判成两条
        assertEquals(
            SyncPlanner.weakKey("2026-09-01", "甲", 0.3),
            SyncPlanner.weakKey("2026-09-01", "甲", 0.1 + 0.2),
        )
    }

    @Test
    fun `差一分钱就不是重复`() {
        assertTrue(
            SyncPlanner.weakKey("2026-09-01", "甲", 100.0) !=
                SyncPlanner.weakKey("2026-09-01", "甲", 100.01),
        )
    }

    @Test
    fun `人不同或日期不同都不是重复`() {
        val base = SyncPlanner.weakKey("2026-09-01", "甲", 100.0)
        assertTrue(base != SyncPlanner.weakKey("2026-09-01", "乙", 100.0))
        assertTrue(base != SyncPlanner.weakKey("2026-09-02", "甲", 100.0))
    }

    // ---------------------------------------------------------------- 推送侧

    @Test
    fun `电脑没有的记录全都要推过去`() {
        val plan = SyncPlanner.plan(
            phoneLive = listOf(rec("aaa"), rec("bbb", date = "2026-09-02")),
            phoneDead = emptyList(),
            remote = book(),
        )
        assertEquals(2, plan.pushRecords.size)
        assertEquals(2, plan.pushNew)
        assertEquals(0, plan.pushDup.size)
        assertEquals(0, plan.pcTotal)
    }

    @Test
    fun `电脑已经有同一个 uid 的，不用再推`() {
        val plan = SyncPlanner.plan(
            phoneLive = listOf(rec("aaa"), rec("bbb")),
            phoneDead = emptyList(),
            remote = book(records = listOf(row("aaa"))),
        )
        assertEquals(listOf("bbb"), plan.pushRecords.map { it.uid })
    }

    @Test
    fun `uid 不同但人日期金额一样，判为疑似重复并给出要剔掉的 uid`() {
        val plan = SyncPlanner.plan(
            phoneLive = listOf(rec("phone0000001", note = "手机记的")),
            phoneDead = emptyList(),
            remote = book(records = listOf(row("pc0000000001", note = "电脑记的"))),
        )
        assertEquals(1, plan.pushRecords.size)
        assertEquals(1, plan.pushDup.size)
        assertEquals(setOf("phone0000001"), plan.pushDupUids)
        // 推的时候要扣掉疑似重复的那条
        assertEquals(0, plan.pushNew)

        val dup = plan.pushDup[0]
        assertEquals("2026-09-01", dup.date)
        assertEquals("甲", dup.member)
        assertEquals(100.0, dup.amount, 0.0)
        assertEquals("手机记的", dup.phoneNote)
        assertEquals("电脑记的", dup.pcNote)
        assertEquals("phone0000001", dup.phoneUid)
        assertEquals("pc0000000001", dup.pcUid)
    }

    @Test
    fun `回收站里的记录也会参与弱去重`() {
        val plan = SyncPlanner.plan(
            phoneLive = emptyList(),
            phoneDead = listOf(rec("phone0000002")),
            remote = book(records = listOf(row("pc0000000002"))),
        )
        assertEquals(1, plan.pushTrash.size)
        assertEquals(1, plan.pushDup.size)
        assertEquals(setOf("phone0000002"), plan.pushDupUids)
    }

    @Test
    fun `uid 为空的记录不参与同步（两边都没法认它）`() {
        val plan = SyncPlanner.plan(
            phoneLive = listOf(rec("")),
            phoneDead = emptyList(),
            remote = book(records = listOf(row(""))),
        )
        assertEquals(0, plan.pushRecords.size)
        assertEquals(0, plan.pushDup.size)
        assertEquals(0, plan.pullNew)
    }

    // ---------------------------------------------------------------- 取回侧

    @Test
    fun `电脑上手机没有的才算要取回`() {
        val plan = SyncPlanner.plan(
            phoneLive = listOf(rec("aaa")),
            phoneDead = emptyList(),
            remote = book(records = listOf(row("aaa"), row("bbb", date = "2026-09-05"))),
        )
        assertEquals(1, plan.pullNew)
        assertEquals(0, plan.pullDup.size)
        assertEquals(2, plan.pcTotal)
        assertEquals(1, plan.phoneTotal)
    }

    @Test
    fun `取回侧的弱重复也认得出来`() {
        val plan = SyncPlanner.plan(
            phoneLive = listOf(rec("phone0000003", note = "手机备注")),
            phoneDead = emptyList(),
            remote = book(records = listOf(row("pc0000000003", note = "电脑备注"))),
        )
        assertEquals(1, plan.pullNew)
        assertEquals(1, plan.pullDup.size)
        assertEquals(setOf("pc0000000003"), plan.pullDupUids)
        assertEquals("手机备注", plan.pullDup[0].phoneNote)
        assertEquals("电脑备注", plan.pullDup[0].pcNote)
    }

    @Test
    fun `电脑回收站里手机还没有的，计入取回`() {
        val plan = SyncPlanner.plan(
            phoneLive = emptyList(),
            phoneDead = emptyList(),
            remote = book(deleted = listOf(row("gone00000001"))),
        )
        assertEquals(0, plan.pullNew)
        assertEquals(1, plan.pullTrashNew)
        assertEquals(1, plan.pullTotal)
    }

    @Test
    fun `同名同日同金额但 uid 相同时，不算重复只算已同步`() {
        val plan = SyncPlanner.plan(
            phoneLive = listOf(rec("same00000001")),
            phoneDead = emptyList(),
            remote = book(records = listOf(row("same00000001"))),
        )
        assertEquals(0, plan.pushRecords.size)
        assertEquals(0, plan.pushDup.size)
        assertEquals(0, plan.pullNew)
        assertEquals(0, plan.pullDup.size)
    }

    // ---------------------------------------------------------------- 本地查重

    @Test
    fun `本地同人同日同金额两条，算一组重复`() {
        val groups = SyncPlanner.duplicateGroups(
            listOf(rec("a00000000001"), rec("b00000000001")),
        )
        assertEquals(1, groups.size)
        assertEquals(2, groups[0].items.size)
        assertEquals("2026-09-01", groups[0].date)
        assertEquals("甲", groups[0].member)
        assertEquals(100.0, groups[0].amount, 0.0)
    }

    @Test
    fun `三条一样的会归到同一组里`() {
        val groups = SyncPlanner.duplicateGroups(
            listOf(rec("a00000000001"), rec("b00000000001"), rec("c00000000001")),
        )
        assertEquals(1, groups.size)
        assertEquals(3, groups[0].items.size)
    }

    @Test
    fun `明细按创建时间排，方便认出哪条是后加的`() {
        val groups = SyncPlanner.duplicateGroups(
            listOf(
                rec("late00000001", createdAt = 2000),
                rec("early0000001", createdAt = 1000),
            ),
        )
        assertEquals(listOf("early0000001", "late00000001"), groups[0].items.map { it.uid })
    }

    @Test
    fun `uid 为空的重复不算（种子数据那种没有身份的）`() {
        val groups = SyncPlanner.duplicateGroups(listOf(rec(""), rec("")))
        assertTrue(groups.isEmpty())
    }

    @Test
    fun `组之间按日期倒序`() {
        val groups = SyncPlanner.duplicateGroups(
            listOf(
                rec("a00000000001", date = "2026-09-01"),
                rec("b00000000001", date = "2026-09-01"),
                rec("c00000000001", date = "2026-10-01"),
                rec("d00000000001", date = "2026-10-01"),
            ),
        )
        assertEquals(listOf("2026-10-01", "2026-09-01"), groups.map { it.date })
    }
}
