package com.wenqing.feenote.util

import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/** 日期小工具：统一用 yyyy-MM-dd 字符串在数据库里存 */
object Dates {

    private val fmt = SimpleDateFormat("yyyy-MM-dd", Locale.CHINA)

    fun today(): String = fmt.format(Date())

    fun now(): String =
        SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.CHINA).format(Date())

    /** 把 yyyy-MM-dd 拆成 (年, 月, 日)，用于日历控件初始定位 */
    fun parts(date: String): Triple<Int, Int, Int> {
        return try {
            val c = Calendar.getInstance()
            c.time = fmt.parse(date) ?: Date()
            Triple(c.get(Calendar.YEAR), c.get(Calendar.MONTH) + 1, c.get(Calendar.DAY_OF_MONTH))
        } catch (e: Exception) {
            val c = Calendar.getInstance()
            Triple(c.get(Calendar.YEAR), c.get(Calendar.MONTH) + 1, c.get(Calendar.DAY_OF_MONTH))
        }
    }

    /** 把 (年, 月, 日) 拼成 yyyy-MM-dd */
    fun of(year: Int, month: Int, day: Int): String =
        String.format(Locale.CHINA, "%04d-%02d-%02d", year, month, day)

    /** 该月有多少天 */
    fun daysInMonth(year: Int, month: Int): Int {
        val c = Calendar.getInstance()
        c.set(year, month - 1, 1)
        return c.getActualMaximum(Calendar.DAY_OF_MONTH)
    }

    /** 该月 1 号是星期几（1=周日 … 7=周六），用于日历排版 */
    fun firstDayOfWeek(year: Int, month: Int): Int {
        val c = Calendar.getInstance()
        c.set(year, month - 1, 1)
        return c.get(Calendar.DAY_OF_WEEK)
    }

    /** 星期几，如「周四」 */
    fun weekday(date: String): String {
        val (y, m, d) = parts(date)
        val c = Calendar.getInstance()
        c.set(y, m - 1, d)
        return when (c.get(Calendar.DAY_OF_WEEK)) {
            Calendar.MONDAY -> "周一"
            Calendar.TUESDAY -> "周二"
            Calendar.WEDNESDAY -> "周三"
            Calendar.THURSDAY -> "周四"
            Calendar.FRIDAY -> "周五"
            Calendar.SATURDAY -> "周六"
            else -> "周日"
        }
    }

    /** 友好显示：2026-09-24 → 9月24日 */
    fun friendly(date: String): String {
        val (y, m, d) = parts(date)
        return "${m}月${d}日"
    }

    /** 带年份显示：2026-09-24 → 2026年9月24日 */
    fun full(date: String): String {
        val (y, m, d) = parts(date)
        return "${y}年${m}月${d}日"
    }

    /** yyyy-MM-dd → 日历控件需要的 UTC 毫秒数 */
    fun toUtcMillis(date: String): Long {
        val (y, m, d) = parts(date)
        val c = Calendar.getInstance(TimeZone.getTimeZone("UTC"))
        c.set(y, m - 1, d, 0, 0, 0)
        c.set(Calendar.MILLISECOND, 0)
        return c.timeInMillis
    }

    /** 日历控件返回的 UTC 毫秒数 → yyyy-MM-dd */
    fun fromUtcMillis(millis: Long): String {
        val c = Calendar.getInstance(TimeZone.getTimeZone("UTC"))
        c.timeInMillis = millis
        return of(c.get(Calendar.YEAR), c.get(Calendar.MONTH) + 1, c.get(Calendar.DAY_OF_MONTH))
    }
}

/** 金额显示：350.0 → ¥350.00；整百时省略小数位更清爽 */
fun money(value: Double): String {
    return if (value == value.toLong().toDouble()) {
        "¥${value.toLong()}"
    } else {
        "¥" + String.format(Locale.CHINA, "%.2f", value)
    }
}

/** 始终保留两位小数 */
fun money2(value: Double): String = "¥" + String.format(Locale.CHINA, "%.2f", value)
