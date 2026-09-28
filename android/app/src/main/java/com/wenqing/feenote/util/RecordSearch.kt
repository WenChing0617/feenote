package com.wenqing.feenote.util

import com.wenqing.feenote.data.Record

/**
 * 记录搜索。
 *
 * 抽成纯函数（不碰数据库、不碰 Compose）是为了能写单测 ——
 * 「搜不到」和「搜出一堆不该有的」这两种错都很难靠肉眼发现。
 *
 * 匹配规则：
 * - 关键词按**空格拆成多个词**，必须**全部命中**才算匹配（与关系）。
 *   所以「微信 100」会精确圈出微信付的 100 元那几笔，而不是微信的**或**100 元的。
 * - 大小写不敏感（成员名、备注里可能有英文）。
 * - 一条记录有多个可搜字段：成员、日期（三种写法）、星期、金额（两种写法）、
 *   支付方式、备注、「期初」标记。搜「9月24」「周四」「¥50」「50.0」都能命中。
 */
object RecordSearch {

    /**
     * 按关键词过滤。关键词为空（或只有空格）时**原样返回**，
     * 让调用方不用再写一次 if —— 搜索框清空后自然就是全部。
     */
    fun filter(records: List<Record>, query: String): List<Record> {
        val terms = terms(query)
        if (terms.isEmpty()) return records
        return records.filter { record -> terms.all { hit(record, it) } }
    }

    /** 拆词：去首尾空格、按连续空白分、统一小写 */
    fun terms(query: String): List<String> =
        query.trim().lowercase().split(Regex("\\s+")).filter { it.isNotEmpty() }

    private fun hit(record: Record, term: String): Boolean = haystack(record).contains(term)

    /**
     * 把一条记录的所有可搜内容拼成一个小写字符串。
     *
     * 日期特意放了三种写法（`2026-09-24` / `2026年9月24日` / `9月24日`），
     * 用户想怎么打都能搜到；金额也放两种（`¥50` / `50.0`），
     * 这样搜「50」「¥50」「50.0」结果一致。
     */
    private fun haystack(r: Record): String = buildString {
        append(r.member.lowercase())
        append(' ')
        append(r.date)                       // 2026-09-24
        append(' ')
        append(Dates.full(r.date))           // 2026年9月24日
        append(' ')
        append(Dates.friendly(r.date))       // 9月24日
        append(' ')
        append(Dates.weekday(r.date))        // 周四
        append(' ')
        append(money(r.amount).lowercase())  // ¥50
        append(' ')
        append(r.amount.toString())          // 50.0
        append(' ')
        append(r.method.lowercase())
        append(' ')
        append(r.note.lowercase())
        if (r.initial) append(" 期初")
    }
}
