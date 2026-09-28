package com.wenqing.feenote.util

import com.wenqing.feenote.data.Record
import com.wenqing.feenote.data.Repository

/**
 * 导出：把当前数据渲染成 TXT（人看的）和 CSV（Excel 能直接打开）。
 * 纯字符串生成，不碰文件系统；写文件由界面层通过系统文件选择器完成。
 */
object Exporter {

    /**
     * 明细的排列顺序：**最新的在最上面**。
     *
     * 单独抽出来是为了能写单测 —— 这条规则很容易在某次重构里被顺手改回去，
     * 而「顺序反了」这种问题肉眼扫代码是看不出来的。
     *
     * 同一天有多笔时按创建时间倒序（最后记的那笔排最上），
     * 再相同就按 id 倒序，保证顺序是稳定的、不会每次导出都变。
     */
    fun newestFirst(records: List<Record>): List<Record> =
        records.sortedWith(
            compareByDescending<Record> { it.date }
                .thenByDescending { it.createdAt }
                .thenByDescending { it.id },
        )

    /** 便于生成文件名，如 电费记账_302_20260928.txt */
    fun fileName(repo: Repository, ext: String): String {
        val room = repo.room().ifBlank { "电费" }
        val stamp = Dates.now().replace("-", "").replace(":", "").replace(" ", "_").take(15)
        return "电费记账_${room}_$stamp.$ext"
    }

    /**
     * 分享用的文件名。
     *
     * 与 [fileName] 分开，是因为分享出去的文件名会**原样显示在微信 / QQ 的聊天里**，
     * 冒号、斜杠这类字符在部分接收端会被替换或截断，所以这里只留汉字、数字、
     * 字母、下划线和短横线（房间号里若混进别的字符也一并过滤掉）。
     */
    fun shareFileName(repo: Repository, ext: String): String {
        val room = repo.room().filter { it.isLetterOrDigit() || it == '_' || it == '-' }
        val stamp = Dates.now().replace("-", "").replace(":", "").replace(" ", "").take(12)
        return if (room.isBlank()) "电费记账_$stamp.$ext" else "电费记账_${room}_$stamp.$ext"
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
        // 最新的排最上面：分享出去 / 发到群里，第一眼想看到的是最近交的那笔
        newestFirst(records).forEach { r ->
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
        // 同 TXT：最新的在最上面，打开就是最近几笔
        newestFirst(repo.records()).forEach { r ->
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
