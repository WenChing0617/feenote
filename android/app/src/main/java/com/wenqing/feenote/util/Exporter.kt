package com.wenqing.feenote.util

import com.wenqing.feenote.data.Repository

/**
 * 导出：把当前数据渲染成 TXT（人看的）和 CSV（Excel 能直接打开）。
 * 纯字符串生成，不碰文件系统；写文件由界面层通过系统文件选择器完成。
 */
object Exporter {

    /** 便于生成文件名，如 电费记账_302_20260928.txt */
    fun fileName(repo: Repository, ext: String): String {
        val room = repo.room().ifBlank { "电费" }
        val stamp = Dates.now().replace("-", "").replace(":", "").replace(" ", "_").take(15)
        return "电费记账_${room}_$stamp.$ext"
    }

    /** 文本报告 */
    fun buildTxt(repo: Repository): String {
        val sb = StringBuilder()
        // 房间号可能还没填（应用不再自带任何默认值），那就不要硬编一个出来
        val room = repo.room()
        val records = repo.records()
        val totals = repo.totals()
        val grand = repo.grandTotal()
        val initialCount = records.count { it.initial }
        val realCount = records.count { !it.initial }

        sb.appendLine(if (room.isBlank()) "电费记账本" else "电费记账本 · $room 室")
        sb.appendLine("导出时间：${Dates.now()}")
        if (records.isNotEmpty()) {
            sb.appendLine("数据范围：${Dates.full(records.last().date)} ~ ${Dates.full(records.first().date)}")
        }
        sb.appendLine()

        sb.appendLine("========== 每人累计 ==========")
        totals.forEach { t ->
            val pct = if (grand > 0) t.total / grand * 100 else 0.0
            sb.appendLine(
                "%d. %s  累计 %.2f 元  %d 笔  占 %.1f%%".format(
                    t.orderNo, t.member, t.total, t.count, pct,
                )
            )
        }
        sb.appendLine("合计：%.2f 元  充值 %d 笔%s".format(
            grand, realCount, if (initialCount > 0) "（另含期初 $initialCount 笔）" else "",
        ))
        sb.appendLine()

        sb.appendLine("========== 充值明细 ==========")
        records.sortedBy { it.date }.forEach { r ->
            val tail = buildString {
                if (r.note.isNotBlank()) append("  ").append(r.note)
                if (r.initial) append("  [期初]")
            }
            sb.appendLine(
                "%s %s  %s  +%.2f 元  %s%s".format(
                    r.date, Dates.weekday(r.date), r.member, r.amount, r.method, tail,
                )
            )
        }

        return sb.toString()
    }

    /** CSV（前端加 UTF-8 BOM，Excel 打开不乱码） */
    fun buildCsv(repo: Repository): String {
        val sb = StringBuilder()
        val orderMap = repo.members().associate { it.name to it.orderNo }

        sb.appendLine("日期,星期,成员,编号,金额,支付方式,备注,类型")
        repo.records().sortedBy { it.date }.forEach { r ->
            sb.appendLine(
                listOf(
                    r.date,
                    Dates.weekday(r.date),
                    escape(r.member),
                    (orderMap[r.member] ?: "").toString(),
                    "%.2f".format(r.amount),
                    escape(r.method),
                    escape(r.note),
                    if (r.initial) "期初" else "充值",
                ).joinToString(",")
            )
        }
        return sb.toString()
    }

    private fun escape(value: String): String {
        if (value.isEmpty()) return ""
        val needQuote = value.contains(',') || value.contains('"') || value.contains('\n')
        return if (needQuote) "\"" + value.replace("\"", "\"\"") + "\"" else value
    }
}
