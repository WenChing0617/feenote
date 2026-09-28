package com.wenqing.feenote.data

/** 一条充值记录 */
data class Record(
    /** SQLite 自增主键，只在手机本地有效 */
    val id: Long = 0L,
    /**
     * 跨设备唯一标识：12 位十六进制，与桌面版 JSON 里的 `id` 字段一一对应。
     * 手机和电脑之间靠它去重合并，导入导出走的都是它，不是上面那个自增主键。
     */
    val uid: String = "",
    /** 日期，格式 yyyy-MM-dd */
    val date: String,
    /** 成员姓名，如「甲」 */
    val member: String,
    /** 金额（元） */
    val amount: Double,
    /** 支付方式，默认「校园卡」 */
    val method: String = "校园卡",
    /** 备注 */
    val note: String = "",
    /** 是否为期初首笔：算进总额，但不计入充值笔数 */
    val initial: Boolean = false,
    /** 创建时间戳（用于同日期内的排序） */
    val createdAt: Long = System.currentTimeMillis(),
    /** 是否已移入回收站 */
    val deleted: Boolean = false,
)

/** 一位宿舍成员 */
data class Member(
    val id: Long = 0L,
    /** 姓名，如「甲」 */
    val name: String,
    /** 固定编号 1~5 */
    val orderNo: Int,
)

/** 统计结果：某人累计充值 */
data class MemberTotal(
    val member: String,
    val orderNo: Int,
    val total: Double,
    val count: Int,
)
