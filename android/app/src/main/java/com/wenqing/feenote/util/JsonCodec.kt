package com.wenqing.feenote.util

import com.wenqing.feenote.data.Member
import com.wenqing.feenote.data.Record
import org.json.JSONArray
import org.json.JSONObject

/**
 * 账本 JSON 交换格式 —— 手机版与桌面版互通的唯一契约。
 *
 * 字段与桌面版 `Store.payload()` / `Store.apply()` 逐一对齐，也就是说：
 * - 这里导出的文件，桌面版「导入账本」能直接吃；
 * - 桌面版导出的文件，这里也能读。
 *
 * ```
 * {
 *   "app": "电费记账本", "version": "1.4", "room": "302",
 *   "members": ["甲","乙",...],
 *   "memberIds": { "甲": 1, ... },
 *   "records":  [ { "id","date","member","amount","method","note","createdAt","initial" } ],
 *   "deleted":  [ 同上结构 ],
 *   "savedAt": "2026-09-28 11:30:00"
 * }
 * ```
 *
 * 关键点：`records[].id` 存的是 [Record.uid]（12 位十六进制），**不是** SQLite 自增主键。
 * 两边都靠这个字段做去重合并。
 *
 * 解析用 Android 自带的 `org.json`，不引入任何第三方依赖。
 */
object JsonCodec {

    const val APP_NAME = "电费记账本"

    /** 与桌面版 `APP_VERSION` 对齐，方便人眼比对文件 */
    const val FORMAT_VERSION = "1.4"

    // ------------------------------------------------------------------ 写

    fun build(
        room: String,
        members: List<Member>,
        records: List<Record>,
        deleted: List<Record>,
        savedAt: String,
    ): String {
        val root = JSONObject()
        root.put("app", APP_NAME)
        root.put("version", FORMAT_VERSION)
        root.put("room", room)
        root.put("members", JSONArray(members.map { it.name }))

        val ids = JSONObject()
        members.forEach { ids.put(it.name, it.orderNo) }
        root.put("memberIds", ids)

        root.put("records", JSONArray(records.map { recordJson(it) }))
        root.put("deleted", JSONArray(deleted.map { recordJson(it) }))
        root.put("savedAt", savedAt)
        return root.toString(2)
    }

    private fun recordJson(r: Record): JSONObject = JSONObject().apply {
        put("id", r.uid)
        put("date", r.date)
        put("member", r.member)
        put("amount", r.amount)
        put("method", r.method)
        put("note", r.note)
        put("createdAt", r.createdAt)
        put("initial", r.initial)
    }

    // ------------------------------------------------------------------ 读

    /** 从文件里读出来的一条记录（尚未进数据库） */
    data class Row(
        val uid: String,
        val date: String,
        val member: String,
        val amount: Double,
        val method: String,
        val note: String,
        val createdAt: Long,
        val initial: Boolean,
    )

    /** 一个完整的账本文件 */
    data class Book(
        val room: String,
        val members: List<String>,
        val memberIds: Map<String, Int>,
        val records: List<Row>,
        val deleted: List<Row>,
    )

    /** 解析失败会抛异常，调用方负责兜住并提示 */
    fun parse(text: String): Book {
        val root = JSONObject(text.removePrefix("\uFEFF"))

        val members = LinkedHashSet<String>()
        root.optJSONArray("members")?.let { arr ->
            for (i in 0 until arr.length()) {
                val name = arr.optString(i, "").trim()
                if (name.isNotEmpty()) members.add(name)
            }
        }

        val memberIds = LinkedHashMap<String, Int>()
        root.optJSONObject("memberIds")?.let { obj ->
            obj.keys().forEach { key ->
                val name = key.trim()
                val no = obj.optInt(key, -1)
                if (name.isNotEmpty() && no > 0) memberIds[name] = no
            }
        }

        return Book(
            room = root.optString("room", "").trim(),
            members = members.toList(),
            memberIds = memberIds,
            records = parseRows(root.optJSONArray("records")),
            deleted = parseRows(root.optJSONArray("deleted")),
        )
    }

    private fun parseRows(arr: JSONArray?): List<Row> {
        if (arr == null) return emptyList()
        val list = ArrayList<Row>(arr.length())
        for (i in 0 until arr.length()) {
            val o = arr.optJSONObject(i) ?: continue
            val date = o.optString("date", "").trim()
            val member = o.optString("member", "").trim()
            // 日期或成员缺一个就没法进账本，直接跳过
            if (date.isEmpty() || member.isEmpty()) continue
            list.add(
                Row(
                    uid = o.optString("id", "").trim(),
                    date = date,
                    member = member,
                    amount = o.optDouble("amount", 0.0),
                    method = o.optString("method", "").trim(),
                    note = o.optString("note", ""),
                    createdAt = o.optLong("createdAt", 0L),
                    initial = o.optBoolean("initial", false),
                )
            )
        }
        return list
    }
}
