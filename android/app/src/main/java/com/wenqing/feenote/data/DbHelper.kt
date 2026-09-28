package com.wenqing.feenote.data

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import com.wenqing.feenote.util.Uids

/**
 * 本地 SQLite 数据库。数据文件位于应用私有目录 /data/data/com.wenqing.feenote/databases/feenote.db，
 * 卸载应用才会清除。
 *
 * 建库时**只建表、不塞任何数据** —— 账本是空的，装完由用户在首次引导里
 * 填自己的房间号和成员。老用户升级不会走到 onCreate，原有数据不受影响。
 */
class DbHelper(context: Context) : SQLiteOpenHelper(context, DB_NAME, null, DB_VERSION) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                order_no INTEGER NOT NULL
            )
            """.trimIndent()
        )

        db.execSQL(
            """
            CREATE TABLE records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT NOT NULL DEFAULT '',
                date TEXT NOT NULL,
                member TEXT NOT NULL,
                amount REAL NOT NULL,
                method TEXT NOT NULL DEFAULT '校园卡',
                note TEXT NOT NULL DEFAULT '',
                initial INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0
            )
            """.trimIndent()
        )
        db.execSQL("CREATE INDEX idx_records_date ON records(date)")
        db.execSQL("CREATE INDEX idx_records_member ON records(member)")
        // uid 是跨设备去重的依据，必须唯一
        db.execSQL("CREATE UNIQUE INDEX idx_records_uid ON records(uid)")

        db.execSQL(
            """
            CREATE TABLE meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """.trimIndent()
        )
    }

    /**
     * v1 → v2：给 records 补上 uid。
     *
     * uid 是手机与电脑之间合并去重的唯一依据（桌面版同一字段叫 `id`）。
     * 顺序很要紧：先加列 → 再回填 → 最后建唯一索引。
     * 反过来做的话，一堆默认空串会先撞上唯一索引，整个升级直接失败。
     * SQLite 的 ALTER TABLE 也不支持直接加 UNIQUE 列，所以只能这么两步走。
     */
    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 2) {
            db.execSQL("ALTER TABLE records ADD COLUMN uid TEXT NOT NULL DEFAULT ''")
            backfillUids(db)
            db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS idx_records_uid ON records(uid)")
        }
    }

    /** 给早先版本记下的、还没有 uid 的记录补一个（不动其它任何字段） */
    private fun backfillUids(db: SQLiteDatabase) {
        val rowIds = ArrayList<Long>()
        db.rawQuery("SELECT id FROM records WHERE uid IS NULL OR uid = ''", null).use { c ->
            while (c.moveToNext()) rowIds.add(c.getLong(0))
        }
        rowIds.forEach { rowId ->
            db.execSQL("UPDATE records SET uid=? WHERE id=?", arrayOf<Any?>(Uids.new(), rowId))
        }
    }

    override fun onConfigure(db: SQLiteDatabase) {
        super.onConfigure(db)
        db.setForeignKeyConstraintsEnabled(true)
    }

    companion object {
        const val DB_NAME = "feenote.db"

        /** v1：初版；v2：records 增加跨设备唯一标识 uid */
        const val DB_VERSION = 2
    }
}
