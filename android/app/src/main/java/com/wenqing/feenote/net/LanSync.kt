package com.wenqing.feenote.net

import org.json.JSONObject
import java.io.IOException
import java.net.ConnectException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL
import java.net.URLEncoder
import java.net.UnknownHostException
import java.nio.charset.StandardCharsets

/**
 * 跟电脑上的桌面版说话。
 *
 * 协议就三个接口（见桌面版 `SyncServer`）：
 *   GET  /ping?pair=xxxx    探活，顺便看看电脑那头有多少条记录
 *   GET  /export?pair=xxxx  把电脑上的整本账本取回来
 *   POST /import?pair=xxxx  把手机上的账本推过去，电脑按 uid 去重合并
 *
 * 只用 `HttpURLConnection` + `org.json`，不引第三方库 ——
 * 一来这机器上 Maven Central 不通、多一个依赖就多一分拉不到的风险，
 * 二来请求量极小（一次同步两三个请求），用不上 OkHttp 那种大件。
 *
 * 注意：所有方法都是**阻塞**的，必须在后台线程里调。
 */
object LanSync {

    private const val TIMEOUT_MS = 6000
    /** 电脑那边的账本撑死也就几百 KB，超过这个数多半是连错东西了 */
    private const val MAX_BODY = 8 * 1024 * 1024

    /** 探活。连不上/配对码不对都会抛 [LanSyncException]，消息是给人看的中文 */
    fun ping(target: SyncTarget): PeerInfo {
        val json = JSONObject(request(target, "/ping", "GET", null))
        return PeerInfo(
            app = json.optString("app"),
            version = json.optString("version"),
            room = json.optString("room"),
            records = json.optInt("records"),
            trash = json.optInt("trash"),
            members = json.optInt("members"),
        )
    }

    /** 把电脑上的账本原文取回来，交给 `Repository.importJson(text, merge = true)` 去合并 */
    fun pull(target: SyncTarget): String = request(target, "/export", "GET", null)

    /** 把手机上的账本推给电脑，返回电脑合并后的账 */
    fun push(target: SyncTarget, bookJson: String): PushResult {
        val json = JSONObject(request(target, "/import", "POST", bookJson))
        return PushResult(
            added = json.optInt("added"),
            trashed = json.optInt("trashed"),
            records = json.optInt("records"),
            trash = json.optInt("trash"),
        )
    }

    // ------------------------------------------------------------------ 底层

    private fun request(target: SyncTarget, path: String, method: String, body: String?): String {
        target.problem()?.let { throw LanSyncException(it) }
        val pair = URLEncoder.encode(target.pair, "UTF-8")
        var conn: HttpURLConnection? = null
        try {
            conn = (URL("${target.baseUrl}$path?pair=$pair").openConnection() as HttpURLConnection)
                .apply {
                    requestMethod = method
                    connectTimeout = TIMEOUT_MS
                    readTimeout = TIMEOUT_MS
                    useCaches = false
                    doInput = true
                    setRequestProperty("Accept", "application/json")
                    setRequestProperty("X-Pair", target.pair)
                    if (body != null) {
                        doOutput = true
                        setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    }
                }
            if (body != null) {
                conn.outputStream.use { it.write(body.toByteArray(StandardCharsets.UTF_8)) }
            }
            return readBody(conn)
        } catch (e: LanSyncException) {
            throw e
        } catch (e: UnknownHostException) {
            throw LanSyncException("找不到这个地址，检查一下电脑地址有没有抄错")
        } catch (e: ConnectException) {
            throw LanSyncException(
                "连不上电脑。检查：① 电脑上点过「启动服务」了吗 ② 两台在同一个 WiFi 吗 " +
                    "③ 电脑防火墙拦了吗",
            )
        } catch (e: SocketTimeoutException) {
            throw LanSyncException("电脑没反应（超时）。是不是两台不在同一个 WiFi？")
        } catch (e: IOException) {
            throw LanSyncException("网络出错：${e.message ?: e.javaClass.simpleName}")
        } finally {
            conn?.disconnect()
        }
    }

    private fun readBody(conn: HttpURLConnection): String {
        val code = conn.responseCode
        val stream = if (code in 200..299) conn.inputStream else conn.errorStream
        val bytes = stream?.use { it.readBytes() } ?: ByteArray(0)
        if (bytes.size > MAX_BODY) throw LanSyncException("电脑返回的数据太大了，先确认地址填的是电脑")
        val text = String(bytes, StandardCharsets.UTF_8)

        if (code in 200..299) return text
        val remote = runCatching { JSONObject(text).optString("error") }.getOrNull().orEmpty()
        throw LanSyncException(
            when (code) {
                400 -> "电脑说数据有问题：${remote.ifBlank { "格式不对" }}"
                403 -> "配对码不对。电脑上显示的 4 位数要跟这里填的一模一样"
                404 -> "这个地址上没有电费记账本的同步服务，确认端口填对了"
                405 -> "电脑上的版本太老，不支持这个操作"
                in 500..599 -> "电脑那边出错了：${remote.ifBlank { "看电脑上的提示" }}"
                else -> "电脑返回了 $code${if (remote.isBlank()) "" else "：$remote"}"
            }
        )
    }
}
