package com.wenqing.feenote.util

/**
 * 首次使用引导里的纯判断。
 *
 * 抽出来不是为了"好看"，而是因为 [com.wenqing.feenote.data.Repository] 依赖 SQLite，
 * 在 JVM 单元测试里跑不起来。这两个函数是引导逻辑里真正会出错的地方
 * （什么时候该弹、名字能不能用），放这儿就能被测到，界面层只负责渲染和收集输入。
 */
object Onboarding {

    /** 一次最多先加几个人，防止按住回车灌一长串 */
    const val MAX_MEMBERS = 12

    /**
     * 该不该弹首次引导。
     *
     * 条件卡得严：**没走过引导，而且账本里干干净净**。
     * 这样从旧版本升级上来的用户（已有成员或记录）绝不会被弹窗打扰，
     * 只有真正的新装用户才看得到 —— 应用本身不带任何数据。
     */
    fun needed(
        onboarded: Boolean,
        memberCount: Int,
        recordCount: Int,
        trashCount: Int,
    ): Boolean = !onboarded && memberCount == 0 && recordCount == 0 && trashCount == 0

    /**
     * 校验准备添加的成员名。
     *
     * @return 错误文案；`null` 表示这个名字可以用
     */
    fun validateName(
        raw: String,
        existing: List<String>,
        limit: Int = MAX_MEMBERS,
    ): String? {
        val n = raw.trim()
        return when {
            n.isEmpty() -> "请先写个名字"
            existing.size >= limit -> "最多先加 $limit 个人"
            n in existing -> "「$n」已经加过了"
            else -> null
        }
    }

    /**
     * 把用户填的一串名字整理成最终要入库的名单：
     * 去首尾空格、丢掉空串、按首次出现的顺序去重。
     */
    fun normalize(names: List<String>): List<String> =
        names.map { it.trim() }.filter { it.isNotEmpty() }.distinct()

    /** 编号预览文案，例如 `1.甲、2.乙` */
    fun preview(names: List<String>): String =
        names.mapIndexed { i, n -> "${i + 1}.$n" }.joinToString("、")
}
