package com.wenqing.feenote.util

import android.content.Context
import com.wenqing.feenote.net.SyncTarget

/** 记住电脑地址，免得每次同步都要从电脑上重新抄一遍 */
object SyncPrefs {
    private const val FILE = "feenote_sync"
    private const val KEY_HOST = "host"
    private const val KEY_PORT = "port"
    private const val KEY_PAIR = "pair"

    fun load(context: Context): SyncTarget {
        val sp = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
        return SyncTarget(
            host = sp.getString(KEY_HOST, "").orEmpty(),
            port = sp.getInt(KEY_PORT, SyncTarget.DEFAULT_PORT),
            pair = sp.getString(KEY_PAIR, "").orEmpty(),
        )
    }

    fun save(context: Context, target: SyncTarget) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit()
            .putString(KEY_HOST, target.host)
            .putInt(KEY_PORT, target.port)
            .putString(KEY_PAIR, target.pair)
            .apply()
    }
}
