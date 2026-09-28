package com.wenqing.feenote.util

import java.util.UUID

/**
 * 记录的外部唯一标识（uid）。
 *
 * 桌面版用 `uuid.uuid4().hex[:12]` 生成 12 位十六进制串，作为跨设备去重的唯一依据
 * （见桌面版 `Store.apply()`：`exist = {r['id'] for r in self.records}`）。
 * 这里生成完全相同的形式，保证手机导出的文件能被桌面版正确去重，反之亦然。
 *
 * 注意：它和 SQLite 的自增主键 `records.id` 是两回事 —— 主键只在手机本地有意义，
 * 出了这台设备就必须靠 uid 认人。
 */
object Uids {
    /** 新的 12 位小写十六进制标识，如 `ce3f1890bccc` */
    fun new(): String = UUID.randomUUID().toString().replace("-", "").take(12)
}
