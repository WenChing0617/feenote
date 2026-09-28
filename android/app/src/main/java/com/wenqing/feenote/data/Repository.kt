package com.wenqing.feenote.data

import android.content.ContentValues
import android.database.sqlite.SQLiteDatabase
import com.wenqing.feenote.util.Dates
import com.wenqing.feenote.util.JsonCodec
import com.wenqing.feenote.util.Onboarding
import com.wenqing.feenote.util.SnapshotStack
import com.wenqing.feenote.util.Uids
import java.util.Locale

/** 所有数据库读写都走这里，界面层只跟它打交道 */
class Repository(private val helper: DbHelper) {

    private val db: SQLiteDatabase get() = helper.writableDatabase

    companion object {
        /** 最多记住多少步可撤销的操作 */
        const val MAX_UNDO = 30

        /** meta 表里的键：首次引导是否已经走过（或已被跳过） */
        private const val KEY_ONBOARDED = "onboarded"
    }

    // ------------------------------------------------------------------ 撤销 / 恢复

    /**
     * 撤销栈。存的是**整份账本的 JSON 快照**，不是逐条 diff ——
     * 账本本身很小（40 条 ≈ 10 KB），快照式不用为每种操作各写一遍反向逻辑，
     * 也就不会出现"某个新加的操作忘了写反向"的漏网。
     *
     * 这份 JSON 和导入导出用的是同一个格式，撤销时直接走 [replaceBook] 换回去。
     * 栈本身（含边界行为）在 [SnapshotStack] 里，那部分能跑 JVM 单测。
     */
    private val history = SnapshotStack<String>(MAX_UNDO)

    /** 撤销 / 恢复 自己回滚数据时不要再拍快照，否则栈会被自己塞满 */
    private var capturing = true

    private fun capture(label: String) {
        if (!capturing) return
        history.push(label, exportJson())
    }

    val canUndo: Boolean get() = history.canUndo
    val canRedo: Boolean get() = history.canRedo

    /** 撤销栈深度。界面靠它判断"刚才那一下是不是真的改了数据"，好决定要不要弹撤销提示 */
    val undoCount: Int get() = history.size

    /** 下一步撤销会撤掉什么，用于界面提示 */
    val undoLabel: String? get() = history.undoLabel
    val redoLabel: String? get() = history.redoLabel

    fun clearHistory() = history.clear()

    /** 撤销上一步；返回被撤掉那一步的描述，没得撤返回 null */
    fun undo(): String? {
        val r = history.undo(exportJson()) ?: return null
        restoreBook(r.value)
        return r.label
    }

    /** 恢复（重做）刚被撤销的那一步 */
    fun redo(): String? {
        val r = history.redo(exportJson()) ?: return null
        restoreBook(r.value)
        return r.label
    }

    private fun restoreBook(book: String) {
        val parsed = JsonCodec.parse(book)
        val wasCapturing = capturing
        capturing = false
        try {
            db.beginTransaction()
            try {
                replaceBook(parsed)
                db.setTransactionSuccessful()
            } finally {
                db.endTransaction()
            }
        } finally {
            capturing = wasCapturing
        }
    }

    // ------------------------------------------------------------------ 房间号

    fun room(): String {
        db.rawQuery("SELECT value FROM meta WHERE key='room'", null).use { c ->
            if (c.moveToFirst()) return c.getString(0) ?: ""
        }
        return ""
    }

    fun setRoom(value: String, label: String = "改房间号") {
        capture(label)
        setRoomRaw(value)
    }

    /** 内部用：不拍快照。导入 / 撤销 自己已经在外面拍过了，再来一次会多垫一步 */
    private fun setRoomRaw(value: String) {
        db.execSQL(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('room', ?)",
            arrayOf<Any?>(value.trim()),
        )
    }

    // ------------------------------------------------------------------ 首次使用引导

    /** 是否已经走过（或者跳过）首次引导 */
    fun isOnboarded(): Boolean {
        db.rawQuery("SELECT value FROM meta WHERE key='$KEY_ONBOARDED'", null).use { c ->
            if (c.moveToFirst()) return (c.getString(0) ?: "") == "1"
        }
        return false
    }

    private fun markOnboarded() {
        db.execSQL(
            "INSERT OR REPLACE INTO meta(key, value) VALUES(?, '1')",
            arrayOf<Any?>(KEY_ONBOARDED),
        )
    }

    /**
     * 要不要弹首次引导。判断规则在 [Onboarding.needed] 里（那边能跑单测）。
     */
    fun needsOnboarding(): Boolean = Onboarding.needed(
        onboarded = isOnboarded(),
        memberCount = members().size,
        recordCount = records().size,
        trashCount = trash().size,
    )

    /** 用户点了「以后再说」—— 记一笔，别再弹了 */
    fun skipOnboarding() = markOnboarded()

    /**
     * 首次引导一次性写入：房间号 + 成员名单（顺序即编号）。
     *
     * 全程只拍 **一次** 快照 —— 否则填一次引导会往撤销栈里垫进好几步垃圾。
     * 已经存在的成员会被跳过（设置页里可以随时重开这个引导，不该加出重复的人）；
     * 要删人请到「成员管理」，那里会把 TA 的记录一起妥善处理。
     */
    fun applyOnboarding(roomValue: String, names: List<String>) {
        val clean = Onboarding.normalize(names)
        val existing = memberNames().toSet()
        capture("首次设置")
        db.beginTransaction()
        try {
            setRoomRaw(roomValue)
            var seq = db.rawQuery("SELECT IFNULL(MAX(order_no), 0) FROM members", null).use { c ->
                if (c.moveToFirst()) c.getInt(0) else 0
            }
            clean.filter { it !in existing }.forEach { name ->
                seq += 1
                db.execSQL(
                    "INSERT INTO members(name, order_no) VALUES(?, ?)",
                    arrayOf<Any?>(name, seq),
                )
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
        markOnboarded()
    }

    // ------------------------------------------------------------------ 成员

    fun members(): List<Member> {
        val list = ArrayList<Member>()
        db.rawQuery("SELECT id, name, order_no FROM members ORDER BY order_no, id", null).use { c ->
            while (c.moveToNext()) {
                list.add(Member(c.getLong(0), c.getString(1) ?: "", c.getInt(2)))
            }
        }
        return list
    }

    fun memberNames(): List<String> = members().map { it.name }

    /** 新增成员。返回 false 表示名字为空或已存在 */
    fun addMember(name: String, label: String = "加成员"): Boolean {
        val n = name.trim()
        if (n.isEmpty() || memberNames().contains(n)) return false
        val next = db.rawQuery("SELECT IFNULL(MAX(order_no), 0) FROM members", null).use { c ->
            if (c.moveToFirst()) c.getInt(0) else 0
        } + 1
        capture("$label「$n」")
        db.execSQL("INSERT INTO members(name, order_no) VALUES(?, ?)", arrayOf<Any?>(n, next))
        return true
    }

    /** 改名：成员表和所有记录一起改，保证历史数据跟着走 */
    fun renameMember(oldName: String, newName: String, label: String = "成员改名"): Boolean {
        val n = newName.trim()
        if (n.isEmpty() || n == oldName || memberNames().contains(n)) return false
        capture("$label「$oldName」→「$n」")
        db.beginTransaction()
        return try {
            db.execSQL("UPDATE members SET name=? WHERE name=?", arrayOf<Any?>(n, oldName))
            db.execSQL("UPDATE records SET member=? WHERE member=?", arrayOf<Any?>(n, oldName))
            db.setTransactionSuccessful()
            true
        } finally {
            db.endTransaction()
        }
    }

    /** 删除成员：TA 的记录一并移入回收站，可随时恢复 */
    fun deleteMember(name: String, label: String = "删成员") {
        capture("$label「$name」")
        db.beginTransaction()
        try {
            db.execSQL("DELETE FROM members WHERE name=?", arrayOf<Any?>(name))
            db.execSQL("UPDATE records SET deleted=1 WHERE member=?", arrayOf<Any?>(name))
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    // ------------------------------------------------------------------ 记录

    fun records(): List<Record> = queryRecords("deleted=0")

    fun trash(): List<Record> = queryRecords("deleted=1")

    private fun queryRecords(where: String, args: Array<String>? = null): List<Record> {
        val list = ArrayList<Record>()
        db.rawQuery(
            "SELECT id, uid, date, member, amount, method, note, initial, created_at, deleted " +
                "FROM records WHERE $where ORDER BY date DESC, created_at DESC, id DESC",
            args,
        ).use { c ->
            while (c.moveToNext()) {
                list.add(
                    Record(
                        id = c.getLong(0),
                        uid = c.getString(1) ?: "",
                        date = c.getString(2) ?: "",
                        member = c.getString(3) ?: "",
                        amount = c.getDouble(4),
                        method = c.getString(5) ?: "校园卡",
                        note = c.getString(6) ?: "",
                        initial = c.getInt(7) == 1,
                        createdAt = c.getLong(8),
                        deleted = c.getInt(9) == 1,
                    )
                )
            }
        }
        return list
    }

    fun addRecord(record: Record, label: String = "记一笔"): Long {
        capture("$label ${record.member} ¥${trimMoney(record.amount)}")
        val values = ContentValues().apply {
            put("uid", record.uid.ifBlank { Uids.new() })
            put("date", record.date)
            put("member", record.member)
            put("amount", record.amount)
            put("method", record.method)
            put("note", record.note)
            put("initial", if (record.initial) 1 else 0)
            put("created_at", record.createdAt)
            put("deleted", if (record.deleted) 1 else 0)
        }
        return db.insert("records", null, values)
    }

    fun updateRecord(record: Record, label: String = "改一笔") {
        capture("$label ${record.member} ¥${trimMoney(record.amount)}")
        val values = ContentValues().apply {
            put("date", record.date)
            put("member", record.member)
            put("amount", record.amount)
            put("method", record.method)
            put("note", record.note)
            put("initial", if (record.initial) 1 else 0)
        }
        db.update("records", values, "id=?", arrayOf(record.id.toString()))
    }

    fun moveToTrash(id: Long, label: String = "删除") {
        capture("$label「${describe(id)}」")
        db.execSQL("UPDATE records SET deleted=1 WHERE id=?", arrayOf<Any?>(id))
    }

    fun restore(id: Long, label: String = "恢复") {
        capture("$label「${describe(id)}」")
        db.execSQL("UPDATE records SET deleted=0 WHERE id=?", arrayOf<Any?>(id))
    }

    /** 彻底删除（不可恢复） */
    fun purge(id: Long, label: String = "彻底删除") {
        capture("$label「${describe(id)}」")
        db.execSQL("DELETE FROM records WHERE id=?", arrayOf<Any?>(id))
    }

    fun purgeTrash(label: String = "清空回收站") {
        val n = trash().size
        if (n == 0) return
        capture("$label（$n 条）")
        db.execSQL("DELETE FROM records WHERE deleted=1")
    }

    /** 给撤销提示用的一句人话，如「甲 ¥100」 */
    private fun describe(id: Long): String {
        db.rawQuery("SELECT member, amount FROM records WHERE id=?", arrayOf(id.toString())).use { c ->
            if (c.moveToFirst()) return "${c.getString(0) ?: ""} ¥${trimMoney(c.getDouble(1))}"
        }
        return "这条"
    }

    // ------------------------------------------------------------------ 统计

    /** 每人累计；`count` 不含期初首笔（与桌面版口径一致） */
    fun totals(): List<MemberTotal> {
        val orderMap = members().associate { it.name to it.orderNo }
        val list = ArrayList<MemberTotal>()
        db.rawQuery(
            "SELECT member, SUM(amount), SUM(CASE WHEN initial=0 THEN 1 ELSE 0 END) " +
                "FROM records WHERE deleted=0 GROUP BY member",
            null,
        ).use { c ->
            while (c.moveToNext()) {
                val name = c.getString(0) ?: ""
                list.add(
                    MemberTotal(
                        member = name,
                        orderNo = orderMap[name] ?: 999,
                        total = c.getDouble(1),
                        count = c.getInt(2),
                    )
                )
            }
        }
        return list.sortedBy { it.orderNo }
    }

    fun grandTotal(): Double {
        db.rawQuery("SELECT IFNULL(SUM(amount), 0) FROM records WHERE deleted=0", null).use { c ->
            if (c.moveToFirst()) return c.getDouble(0)
        }
        return 0.0
    }

    /**
     * 某位成员的全部充值记录（统计页点人看明细用）。
     *
     * 复用 [queryRecords] 的排序（date DESC, created_at DESC, id DESC），
     * 所以返回的已经是「最新的在最上面」，界面直接渲染即可。
     */
    fun recordsOf(member: String): List<Record> =
        queryRecords("deleted=0 AND member = ?", arrayOf(member))

    /**
     * 某位成员的累计情况；没记录时返回 null，由调用方决定怎么显示。
     * 走和 [totals] 一样的口径，避免两处算出来对不上。
     */
    fun totalOf(member: String): MemberTotal? = totals().firstOrNull { it.member == member }

    /** 非期初的记录笔数 */
    fun realCount(): Int {
        db.rawQuery("SELECT COUNT(*) FROM records WHERE deleted=0 AND initial=0", null).use { c ->
            if (c.moveToFirst()) return c.getInt(0)
        }
        return 0
    }

    fun firstDate(): String {
        db.rawQuery("SELECT MIN(date) FROM records WHERE deleted=0", null).use { c ->
            if (c.moveToFirst()) return c.getString(0) ?: ""
        }
        return ""
    }

    fun lastDate(): String {
        db.rawQuery("SELECT MAX(date) FROM records WHERE deleted=0", null).use { c ->
            if (c.moveToFirst()) return c.getString(0) ?: ""
        }
        return ""
    }

    // ------------------------------------------------------------------ 与桌面版互通

    /**
     * 导出成桌面版能直接「导入账本」的 JSON，格式完全对齐。
     *
     * [records] / [deleted] 可以传子集 —— 同步时用来把「疑似重复」的那几条剔出去再推给电脑。
     */
    fun exportJson(
        records: List<Record> = records(),
        deleted: List<Record> = trash(),
    ): String = JsonCodec.build(
        room = room(),
        members = members(),
        records = records,
        deleted = deleted,
        savedAt = Dates.now(),
    )

    /** 导入结果，供界面提示用 */
    data class ImportResult(
        /** 新增的活跃记录条数 */
        val added: Int,
        /** 新进回收站 / 被跟着删掉的条数 */
        val trashed: Int,
        /** 新增的成员数 */
        val membersAdded: Int,
        /** 因为「疑似和本地某条重复」而主动跳过的条数 */
        val skippedDup: Int,
        /** 导入后账本里的活跃记录总数 */
        val total: Int,
    )

    /**
     * 导入桌面版导出的账本 JSON。
     *
     * @param merge true = 合并（两边记录都保留，按 uid 去重）
     *              false = 覆盖（整个账本换成文件内容）
     * @param skipUids 这几条 uid 不要导入（用户在「发现疑似重复」时选了跳过）
     */
    fun importJson(
        text: String,
        merge: Boolean,
        skipUids: Set<String> = emptySet(),
        label: String = if (merge) "导入账本（合并）" else "导入账本（覆盖）",
    ): ImportResult {
        val book = JsonCodec.parse(text)
        capture(label)
        db.beginTransaction()
        return try {
            val result = if (merge) mergeBook(book, skipUids) else replaceBook(book)
            db.setTransactionSuccessful()
            result
        } finally {
            db.endTransaction()
        }
    }

    /** 覆盖：把整个账本换成文件里的内容 */
    private fun replaceBook(book: JsonCodec.Book): ImportResult {
        db.execSQL("DELETE FROM records")
        db.execSQL("DELETE FROM members")
        setRoomRaw(book.room)

        val names = LinkedHashSet<String>()
        names.addAll(book.members)
        book.records.forEach { names.add(it.member) }
        book.deleted.forEach { names.add(it.member) }
        insertMembers(names.toList(), book.memberIds)

        book.records.forEach { insertRow(it, deleted = false) }
        book.deleted.forEach { insertRow(it, deleted = true) }

        return ImportResult(
            added = book.records.size,
            trashed = book.deleted.size,
            membersAdded = names.size,
            skippedDup = 0,
            total = book.records.size,
        )
    }

    /**
     * 合并：本地已有的记录一律保留（本地优先，与桌面版 `Store.apply()` 的规则一致），
     * 只把文件里本地还没有的补进来。
     *
     * 回收站单独处理 —— 文件里标为已删除、而本地还在活跃列表里的，跟着删。
     * 少了这一步，手机上删掉的记录会被电脑上一份还留着它的文件反复「复活」。
     */
    private fun mergeBook(book: JsonCodec.Book, skipUids: Set<String> = emptySet()): ImportResult {
        if (room().isBlank()) setRoomRaw(book.room)

        val names = LinkedHashSet<String>()
        names.addAll(book.members)
        book.records.forEach { names.add(it.member) }
        book.deleted.forEach { names.add(it.member) }
        val membersAdded = insertMembers(names.toList(), book.memberIds)

        // uid -> (本地行 id, 是否已在回收站)
        val local = HashMap<String, Pair<Long, Boolean>>()
        db.rawQuery("SELECT id, uid, deleted FROM records", null).use { c ->
            while (c.moveToNext()) {
                val uid = c.getString(1) ?: ""
                if (uid.isNotEmpty()) local[uid] = c.getLong(0) to (c.getInt(2) == 1)
            }
        }

        var added = 0
        var skipped = 0
        book.records.forEach { row ->
            if (row.uid.isEmpty() || local.containsKey(row.uid)) return@forEach
            if (row.uid in skipUids) {
                skipped++
                return@forEach
            }
            // 顺手登记进 local，防止文件里同一条 uid 出现两次被插两遍
            local[row.uid] = insertRow(row, deleted = false) to false
            added++
        }

        var trashed = 0
        book.deleted.forEach { row ->
            if (row.uid.isEmpty()) return@forEach
            if (row.uid in skipUids && !local.containsKey(row.uid)) {
                skipped++
                return@forEach
            }
            when (val hit = local[row.uid]) {
                null -> {
                    local[row.uid] = insertRow(row, deleted = true) to true
                    trashed++
                }
                // 本地还在活跃列表 → 跟着进回收站（删除优先）
                else -> if (!hit.second) {
                    db.execSQL("UPDATE records SET deleted=1 WHERE id=?", arrayOf<Any?>(hit.first))
                    local[row.uid] = hit.first to true
                    trashed++
                }
            }
        }

        return ImportResult(added, trashed, membersAdded, skipped, records().size)
    }

    // ------------------------------------------------------------------ 同步预演
    //
    // 算法本身在 `SyncPlanner`（不碰数据库，可跑 JVM 单测）；
    // 这里只负责查库、把它喂进去。

    fun planSync(remoteJson: String): SyncPlan =
        SyncPlanner.plan(records(), trash(), JsonCodec.parse(remoteJson))

    fun duplicateGroups(): List<DupGroup> = SyncPlanner.duplicateGroups(records())


    /**
     * 把人写进成员表。已存在的保留原编号；新人优先用文件里的编号，
     * 撞号了就顺延到最大编号之后（与桌面版 `apply()` 的规则一致）。
     */
    private fun insertMembers(names: List<String>, preferred: Map<String, Int>): Int {
        val current = LinkedHashMap<String, Int>()
        db.rawQuery("SELECT name, order_no FROM members ORDER BY order_no, id", null).use { c ->
            while (c.moveToNext()) current[c.getString(0) ?: ""] = c.getInt(1)
        }
        val used = current.values.toMutableSet()
        var next = (used.maxOrNull() ?: 0) + 1
        var added = 0
        names.forEach { name ->
            if (name.isBlank() || current.containsKey(name)) return@forEach
            var no = preferred[name] ?: next
            while (no in used) no++
            db.execSQL("INSERT INTO members(name, order_no) VALUES(?, ?)", arrayOf<Any?>(name, no))
            current[name] = no
            used.add(no)
            if (no >= next) next = no + 1
            added++
        }
        return added
    }

    /** 往 records 插一行；uid 撞车就跳过，不炸整个导入 */
    private fun insertRow(row: JsonCodec.Row, deleted: Boolean): Long {
        val values = ContentValues().apply {
            put("uid", row.uid.ifBlank { Uids.new() })
            put("date", row.date)
            put("member", row.member)
            put("amount", row.amount)
            put("method", row.method.ifBlank { "校园卡" })
            put("note", row.note)
            put("initial", if (row.initial) 1 else 0)
            put("created_at", row.createdAt)
            put("deleted", if (deleted) 1 else 0)
        }
        return db.insertWithOnConflict(
            "records", null, values, SQLiteDatabase.CONFLICT_IGNORE,
        )
    }
}

/**
 * 金额去尾零，只用于提示文案：`50.0 → "50"`、`50.5 → "50.50"`。
 * 比较用的是「分」这个整数（见 `weakKey`），不走字符串格式化，免得受浮点误差影响。
 */
private fun trimMoney(value: Double): String {
    val cents = Math.round(value * 100)
    return if (cents % 100 == 0L) (cents / 100).toString()
    else String.format(Locale.US, "%.2f", cents / 100.0)
}
