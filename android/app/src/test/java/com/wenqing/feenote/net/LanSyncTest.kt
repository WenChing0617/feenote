package com.wenqing.feenote.net

import com.sun.net.httpserver.HttpExchange
import com.sun.net.httpserver.HttpServer
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.net.InetSocketAddress
import java.nio.charset.StandardCharsets

/**
 * 电脑那一头的假实现：JDK 自带的 HttpServer，起来就是真 HTTP。
 *
 * 用真的 HTTP 而不是打桩，是为了把「配对码怎么传」「body 原样发过去没有」
 * 这类只有真跑一次才暴露的问题一起测掉。
 */
private class FakePc {
    private val server: HttpServer = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)

    val port: Int get() = server.address.port
    val target: SyncTarget get() = SyncTarget("127.0.0.1", port, pair)

    var pair = "1234"
    var lastPath = ""
    var lastQuery = ""
    var lastBody = ""

    /** 每个请求的回复：状态码 to 正文 */
    var reply: (String) -> Pair<Int, String> = { 200 to "{}" }

    init {
        server.createContext("/") { ex: HttpExchange ->
            lastPath = ex.requestURI.path
            lastQuery = ex.requestURI.query ?: ""
            lastBody = ex.requestBody.use { it.readBytes().toString(StandardCharsets.UTF_8) }
            val (code, text) = reply(lastPath)
            val bytes = text.toByteArray(StandardCharsets.UTF_8)
            ex.responseHeaders.add("Content-Type", "application/json; charset=utf-8")
            ex.sendResponseHeaders(code, bytes.size.toLong())
            ex.responseBody.use { it.write(bytes) }
        }
        server.executor = null
        server.start()
    }

    fun stop() = server.stop(0)

    fun gotPair(): String =
        lastQuery.split('&').firstOrNull { it.startsWith("pair=") }?.removePrefix("pair=").orEmpty()
}

class SyncTargetTest {

    @Test
    fun `光填 IP 用默认端口`() {
        val t = SyncTarget.parse("192.168.1.5", "1234")
        assertEquals("192.168.1.5", t.host)
        assertEquals(SyncTarget.DEFAULT_PORT, t.port)
        assertEquals("http://192.168.1.5:8686", t.baseUrl)
    }

    @Test
    fun `带端口就用填的端口`() {
        val t = SyncTarget.parse("192.168.1.5:9000", "1234")
        assertEquals("192.168.1.5", t.host)
        assertEquals(9000, t.port)
    }

    @Test
    fun `从电脑上抄地址时常把 http 和斜杠一起抄进来`() {
        listOf(
            "http://192.168.1.5:8686",
            "http://192.168.1.5:8686/",
            "  http://192.168.1.5:8686  ",
            "192.168.1.5:8686/",
        ).forEach { raw ->
            val t = SyncTarget.parse(raw, " 1234 ")
            assertEquals(raw, "192.168.1.5", t.host)
            assertEquals(raw, 8686, t.port)
            assertEquals(raw, "1234", t.pair)
        }
    }

    @Test
    fun `端口填成乱码就退回默认端口`() {
        assertEquals(SyncTarget.DEFAULT_PORT, SyncTarget.parse("192.168.1.5:abc", "1234").port)
    }

    @Test
    fun `填错的地方要能说出人话`() {
        assertTrue(SyncTarget("", 8686, "1234").problem()!!.contains("地址"))
        assertTrue(SyncTarget("192.168.1.5", 8686, "123").problem()!!.contains("配对码"))
        assertTrue(SyncTarget("192.168.1.5", 8686, "12ab").problem()!!.contains("配对码"))
        assertTrue(SyncTarget("192.168.1.5", 8686, "").problem()!!.contains("配对码"))
        assertTrue(SyncTarget("192.168.1.5", 0, "1234").problem()!!.contains("端口"))
    }

    @Test
    fun `填全了就没意见`() {
        assertNull(SyncTarget("192.168.1.5", 8686, "1234").problem())
        assertNull(SyncTarget("192.168.1.5", 8686, "1234").hint())
    }

    @Test
    fun `回环地址是界面层的提醒，不挡住传输层`() {
        // 手机上填 127.0.0.1 指的是手机自己，一定要提示
        val loop = SyncTarget("127.0.0.1", 8686, "1234")
        assertTrue(loop.hint()!!.contains("手机自己"))
        // 但它不是「格式错误」—— 单测要拿它连本机的假电脑，不能在这被拦
        assertNull(loop.problem())
        assertTrue(SyncTarget("localhost", 8686, "1234").hint()!!.contains("手机自己"))
        assertTrue(SyncTarget("0.0.0.0", 8686, "1234").hint()!!.contains("地址"))
    }
}

class LanSyncTest {

    private val fakes = ArrayList<FakePc>()

    private fun fake(): FakePc = FakePc().also { fakes.add(it) }

    @After
    fun tearDown() {
        fakes.forEach { it.stop() }
        fakes.clear()
    }

    @Test
    fun `ping 把电脑报的信息读出来`() {
        val pc = fake()
        pc.reply = {
            200 to """{"ok":true,"app":"电费记账本","version":"1.5","room":"302",
                      "records":40,"trash":2,"members":5}""".trimIndent()
        }
        val info = LanSync.ping(pc.target)
        assertEquals("/ping", pc.lastPath)
        assertEquals("电费记账本", info.app)
        assertEquals("1.5", info.version)
        assertEquals("302", info.room)
        assertEquals(40, info.records)
        assertEquals(2, info.trash)
        assertEquals(5, info.members)
    }

    @Test
    fun `配对码是按 query 参数传过去的`() {
        val pc = fake()
        pc.pair = "4321"
        pc.reply = { 200 to "{}" }
        LanSync.ping(pc.target)
        assertEquals("4321", pc.gotPair())
    }

    @Test
    fun `pull 原样把账本 JSON 拿回来`() {
        val pc = fake()
        val book = """{"app":"电费记账本","records":[{"id":"a1","amount":100}]}"""
        pc.reply = { 200 to book }
        assertEquals(book, LanSync.pull(pc.target))
        assertEquals("/export", pc.lastPath)
    }

    @Test
    fun `push 把手机账本原样发过去，再把电脑的账读回来`() {
        val pc = fake()
        pc.reply = { 200 to """{"ok":true,"added":2,"trashed":1,"records":42,"trash":3}""" }
        val sent = """{"app":"电费记账本","records":[{"id":"a1"}]}"""
        val r = LanSync.push(pc.target, sent)

        assertEquals("/import", pc.lastPath)
        assertEquals(sent, pc.lastBody)          // 一个字节都不能动，电脑那边按原文解析
        assertEquals(2, r.added)
        assertEquals(1, r.trashed)
        assertEquals(42, r.records)
        assertEquals(3, r.trash)
    }

    @Test
    fun `配对码不对时给的是人话，不是 403`() {
        val pc = fake()
        pc.reply = { 403 to """{"ok":false,"error":"配对码不对"}""" }
        try {
            LanSync.ping(pc.target)
            fail("应该抛异常")
        } catch (e: LanSyncException) {
            assertTrue(e.message!!, e.message!!.contains("配对码"))
        }
    }

    @Test
    fun `地址上没有同步服务时提示端口`() {
        val pc = fake()
        pc.reply = { 404 to """{"ok":false,"error":"没有这个接口"}""" }
        try {
            LanSync.pull(pc.target)
            fail("应该抛异常")
        } catch (e: LanSyncException) {
            assertTrue(e.message!!, e.message!!.contains("端口"))
        }
    }

    @Test
    fun `电脑 500 时把电脑的说法带出来`() {
        val pc = fake()
        pc.reply = { 500 to """{"ok":false,"error":"合并失败：磁盘满了"}""" }
        try {
            LanSync.push(pc.target, "{}")
            fail("应该抛异常")
        } catch (e: LanSyncException) {
            assertTrue(e.message!!, e.message!!.contains("磁盘满了"))
        }
    }

    @Test
    fun `地址没填就别出门发请求`() {
        var called = false
        val pc = fake()
        pc.reply = { called = true; 200 to "{}" }
        try {
            LanSync.ping(SyncTarget("", 8686, "1234"))
            fail("应该抛异常")
        } catch (e: LanSyncException) {
            assertTrue(e.message!!, e.message!!.contains("地址"))
        }
        assertTrue("不该真的发请求", !called)
    }

    @Test
    fun `端口没人听的时候给的是「连不上电脑」而不是英文报错`() {
        // 挑一个几乎不可能有人听的端口
        try {
            LanSync.ping(SyncTarget("127.0.0.1", 1, "1234"))
            fail("应该抛异常")
        } catch (e: LanSyncException) {
            assertNotNull(e.message)
            assertTrue(e.message!!, !e.message!!.contains("Exception"))
        }
    }

    @Test
    fun `ping 的返回被外部原样保留成 JSON 也能再解析（防字符串被二次转义）`() {
        val pc = fake()
        pc.reply = { 200 to JSONObject(mapOf("app" to "电费记账本", "records" to 7)).toString() }
        assertEquals(7, LanSync.ping(pc.target).records)
    }
}
