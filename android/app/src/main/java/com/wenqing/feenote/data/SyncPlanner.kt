package com.wenqing.feenote.data

import com.wenqing.feenote.util.JsonCodec

/** 一对疑似重复：手机一条、电脑一条 */
data class DupPair(
    val date: String,
    val member: String,
    val amount: Double,
    val phoneNote: String,
    val pcNote: String,
    /** 手机那条的 uid */
    val phoneUid: String,
    /** 电脑那条的 uid */
    val pcUid: String,
)

/**
 * 一次同步的预演结果 —— 先算清楚「会推什么、会取什么、哪些疑似重复」，
 * 让用户确认之后再真的动数据。
 */
data class SyncPlan(
    /** 打算推给电脑的（电脑还没有这个 uid 的） */
    val pushRecords: List<Record>,
    val pushTrash: List<Record>,
    /** 上面这些里，和电脑某条疑似同一条的 */
    val pushDup: List<DupPair>,
    /** 打算从电脑取回的条数（手机还没有这个 uid 的） */
    val pullNew: Int,
    val pullTrashNew: Int,
    /** 取回的里面，和手机某条疑似同一条的 */
    val pullDup: List<DupPair>,
    val phoneTotal: Int,
    val pcTotal: Int,
) {
    /** 真正要推的条数（扣掉疑似重复） */
    val pushNew: Int get() = pushRecords.size - pushDup.size
    val pullTotal: Int get() = pullNew + pullTrashNew

    /** 取回时该跳过的 uid */
    val pullDupUids: Set<String> get() = pullDup.map { it.pcUid }.toSet()

    /** 推送时该剔掉的 uid */
    val pushDupUids: Set<String> get() = pushDup.map { it.phoneUid }.toSet()
}

/** 手机本地自己的一堆疑似重复（同一人 + 同一天 + 同金额出现两次以上） */
data class DupGroup(
    val date: String,
    val member: String,
    val amount: Double,
    val items: List<Record>,
)

/**
 * 同步计划的**纯逻辑**。
 *
 * 特意抽成一个不碰数据库的对象：`Repository` 依赖 Android 的 `SQLiteDatabase`，
 * 在 JVM 单元测试里跑不起来（没引 Robolectric）；把这段算法搬出来就能直接测。
 * `Repository.planSync()` 只负责查库、然后调这里。
 */
object SyncPlanner {

    /**
     * 「弱去重键」：同一个人、同一天、同一个金额。
     *
     * uid 是强身份 —— 同一个 uid 一定是同一条。但两边**各自手输**的同一笔账会各拿一个 uid，
     * 光靠 uid 去重拦不住，同步完就会变成两边各存一份。
     * 这份弱键就是拿来抓这种「内容一样、身份不同」的疑似重复，抓到了交给用户决定。
     */
    fun weakKey(date: String, member: String, amount: Double): String =
        "$date|$member|${Math.round(amount * 100)}"

    fun weakKey(r: Record): String = weakKey(r.date, r.member, r.amount)
    fun weakKey(r: JsonCodec.Row): String = weakKey(r.date, r.member, r.amount)

    /**
     * 预演一次同步。
     *
     * @param phoneLive 手机上的活跃记录
     * @param phoneDead 手机上回收站里的记录
     * @param remote    电脑那边账本（已经解析好的）
     */
    fun plan(
        phoneLive: List<Record>,
        phoneDead: List<Record>,
        remote: JsonCodec.Book,
    ): SyncPlan {
        val pcRows = ArrayList<JsonCodec.Row>(remote.records.size + remote.deleted.size)
        pcRows.addAll(remote.records)
        pcRows.addAll(remote.deleted)

        // 电脑上已有哪些 uid / 哪些弱键
        val pcUids = HashSet<String>()
        val pcWeak = HashMap<String, JsonCodec.Row>()
        pcRows.forEach { row ->
            if (row.uid.isEmpty()) return@forEach
            pcUids.add(row.uid)
            pcWeak.putIfAbsent(weakKey(row), row)
        }

        // 手机上已有哪些 uid / 哪些弱键
        val phoneUids = HashSet<String>()
        val phoneWeak = HashMap<String, Record>()
        (phoneLive + phoneDead).forEach { r ->
            if (r.uid.isEmpty()) return@forEach
            phoneUids.add(r.uid)
            phoneWeak.putIfAbsent(weakKey(r), r)
        }

        val pushRecords = ArrayList<Record>()
        val pushTrash = ArrayList<Record>()
        val pushDup = ArrayList<DupPair>()

        fun considerForPush(list: List<Record>, into: ArrayList<Record>) {
            list.forEach { r ->
                if (r.uid.isEmpty() || pcUids.contains(r.uid)) return@forEach
                into.add(r)
                pcWeak[weakKey(r)]?.let { hit ->
                    pushDup.add(
                        DupPair(
                            date = r.date, member = r.member, amount = r.amount,
                            phoneNote = r.note, pcNote = hit.note,
                            phoneUid = r.uid, pcUid = hit.uid,
                        )
                    )
                }
            }
        }
        considerForPush(phoneLive, pushRecords)
        considerForPush(phoneDead, pushTrash)

        var pullNew = 0
        var pullTrashNew = 0
        val pullDup = ArrayList<DupPair>()
        remote.records.forEach { row ->
            if (row.uid.isEmpty() || phoneUids.contains(row.uid)) return@forEach
            pullNew++
            phoneWeak[weakKey(row)]?.let { hit ->
                pullDup.add(
                    DupPair(
                        date = row.date, member = row.member, amount = row.amount,
                        phoneNote = hit.note, pcNote = row.note,
                        phoneUid = hit.uid, pcUid = row.uid,
                    )
                )
            }
        }
        remote.deleted.forEach { row ->
            if (row.uid.isEmpty() || phoneUids.contains(row.uid)) return@forEach
            pullTrashNew++
        }

        return SyncPlan(
            pushRecords = pushRecords,
            pushTrash = pushTrash,
            pushDup = pushDup,
            pullNew = pullNew,
            pullTrashNew = pullTrashNew,
            pullDup = pullDup,
            phoneTotal = phoneLive.size,
            pcTotal = remote.records.size,
        )
    }

    /** 手机本地自己的一堆疑似重复 */
    fun duplicateGroups(records: List<Record>): List<DupGroup> = records
        .filter { it.uid.isNotEmpty() }
        .groupBy { weakKey(it) }
        .filter { it.value.size > 1 }
        .map { (_, v) ->
            val first = v.first()
            DupGroup(first.date, first.member, first.amount, v.sortedBy { it.createdAt })
        }
        .sortedWith(compareByDescending<DupGroup> { it.date }.thenBy { it.member })
}
