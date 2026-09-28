package com.wenqing.feenote.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 首次引导的判断逻辑。
 *
 * 这组测试真正要守住的是 [Onboarding.needed] 的**边界**：
 * 应用从此不带任何数据，但绝不能因为改动而给老用户弹出引导、
 * 也不能新装用户进来不弹。
 */
class OnboardingTest {

    // ---------------------------------------------------------------- needed

    @Test
    fun `全新安装（什么都没有、也没走过引导）要弹`() {
        assertTrue(Onboarding.needed(onboarded = false, memberCount = 0, recordCount = 0, trashCount = 0))
    }

    @Test
    fun `走过引导就不再弹`() {
        assertFalse(Onboarding.needed(onboarded = true, memberCount = 0, recordCount = 0, trashCount = 0))
    }

    @Test
    fun `老用户升级上来（已有成员）不弹`() {
        assertFalse(Onboarding.needed(onboarded = false, memberCount = 5, recordCount = 40, trashCount = 0))
    }

    @Test
    fun `只有成员没记录也不弹`() {
        assertFalse(Onboarding.needed(onboarded = false, memberCount = 3, recordCount = 0, trashCount = 0))
    }

    @Test
    fun `只有记录没成员也不弹`() {
        assertFalse(Onboarding.needed(onboarded = false, memberCount = 0, recordCount = 7, trashCount = 0))
    }

    @Test
    fun `成员和记录都删光、但回收站里还有东西也不弹`() {
        assertFalse(Onboarding.needed(onboarded = false, memberCount = 0, recordCount = 0, trashCount = 2))
    }

    @Test
    fun `跳过引导之后再清空账本也不会重新弹`() {
        // 用户点了「以后再说」→ onboarded 已置位；后来把人都删了
        assertFalse(Onboarding.needed(onboarded = true, memberCount = 0, recordCount = 0, trashCount = 0))
    }

    // ---------------------------------------------------------- validateName

    @Test
    fun `正常名字可以通过`() {
        assertNull(Onboarding.validateName("甲", listOf("乙")))
    }

    @Test
    fun `空名字被挡下`() {
        assertNotNull(Onboarding.validateName("", emptyList()))
        assertNotNull(Onboarding.validateName("   ", emptyList()))
    }

    @Test
    fun `重名被挡下（含前后空格视为同名）`() {
        assertNotNull(Onboarding.validateName("甲", listOf("甲")))
        assertNotNull(Onboarding.validateName("  甲  ", listOf("甲")))
    }

    @Test
    fun `名字前后空格会被裁掉再判断`() {
        assertEquals(1, Onboarding.normalize(listOf("  甲  ")).size)
        assertEquals("甲", Onboarding.normalize(listOf("  甲  ")).first())
    }

    @Test
    fun `超过上限被挡下`() {
        val full = (1..Onboarding.MAX_MEMBERS).map { "人$it" }
        assertNotNull(Onboarding.validateName("多出来的", full))
        // 正好卡在上限时也拦得住（不多不少）
        assertNull(Onboarding.validateName("再来一个", full.dropLast(1)))
    }

    // ------------------------------------------------------------- normalize

    @Test
    fun `normalize 丢掉空串并按首次出现去重`() {
        val out = Onboarding.normalize(listOf("甲", "", "  ", "乙", "甲", "丙"))
        assertEquals(listOf("甲", "乙", "丙"), out)
    }

    @Test
    fun `normalize 保持用户添加的顺序（编号按这个排）`() {
        assertEquals(listOf("丙", "甲", "乙"), Onboarding.normalize(listOf("丙", "甲", "乙")))
    }

    @Test
    fun `空输入得到空名单`() {
        assertTrue(Onboarding.normalize(listOf("", "   ")).isEmpty())
        assertTrue(Onboarding.normalize(emptyList()).isEmpty())
    }

    // ---------------------------------------------------------------- preview

    @Test
    fun `编号预览是从 1 开始的顿号分隔`() {
        assertEquals("1.甲、2.乙、3.丙", Onboarding.preview(listOf("甲", "乙", "丙")))
    }

    @Test
    fun `编号预览遇空名单是空串`() {
        assertEquals("", Onboarding.preview(emptyList()))
    }
}
