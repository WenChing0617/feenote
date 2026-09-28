package com.wenqing.feenote.net

/**
 * 电脑那一头的地址 / 端口 / 配对码。
 *
 * 故意不引用任何 Android 类 —— 这样这段解析逻辑能在普通的 JVM 单元测试里直接跑。
 */
data class SyncTarget(
    val host: String,
    val port: Int,
    val pair: String,
) {
    val baseUrl: String get() = "http://$host:$port"

    /** 出门前先自检；没问题返回 null，有问题返回给人看的一句话 */
    fun problem(): String? = when {
        host.isBlank() -> "还没填电脑地址"
        host.any { it.isWhitespace() } -> "地址里不能有空格"
        port !in 1..65535 -> "端口得是 1~65535"
        pair.length != 4 || !pair.all { it.isDigit() } -> "配对码是电脑上显示的 4 位数字"
        else -> null
    }

    /**
     * 格式没毛病、但一定连不通的写法。
     *
     * 特意跟 [problem] 分开：这里说的是「手机上」的语义，属于界面该拦的事，
     * 传输层不需要知道。测试里拿 127.0.0.1 连本机的假电脑时也不该被挡。
     */
    fun hint(): String? = when {
        host.startsWith("127.") || host.equals("localhost", ignoreCase = true) ->
            "手机上填 127.0.0.1 指的是手机自己，要填电脑在 WiFi 里的地址"
        host == "0.0.0.0" -> "不能填 0.0.0.0，要填电脑在 WiFi 里的地址"
        else -> null
    }

    companion object {
        const val DEFAULT_PORT = 8686

        /**
         * 宽容地认地址。下面几种写法都能用：
         *   `192.168.1.5`、`192.168.1.5:8686`、`http://192.168.1.5:8686`、末尾带 `/`
         * 用户从电脑上抄地址时多抄了 `http://` 是常事，别为这个让人卡住。
         */
        fun parse(text: String, pair: String, defaultPort: Int = DEFAULT_PORT): SyncTarget {
            var s = text.trim()
            for (prefix in listOf("http://", "https://")) {
                if (s.startsWith(prefix, ignoreCase = true)) s = s.substring(prefix.length)
            }
            s = s.trim().trimEnd('/')

            val host: String
            val port: Int
            val colon = s.lastIndexOf(':')
            if (colon >= 0) {
                host = s.substring(0, colon).trim()
                port = s.substring(colon + 1).trim().toIntOrNull() ?: defaultPort
            } else {
                host = s
                port = defaultPort
            }
            return SyncTarget(host, port, pair.trim())
        }
    }
}

/** `/ping` 回来的那点信息 */
data class PeerInfo(
    val app: String,
    val version: String,
    val room: String,
    val records: Int,
    val trash: Int,
    val members: Int,
)

/** 推给电脑之后，电脑报的账 */
data class PushResult(
    val added: Int,
    val trashed: Int,
    val records: Int,
    val trash: Int,
)

/** 同步过程中任何「能讲人话」的失败，都用它往外抛 */
class LanSyncException(message: String) : Exception(message)
