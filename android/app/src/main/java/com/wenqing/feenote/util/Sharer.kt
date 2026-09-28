package com.wenqing.feenote.util

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.core.content.FileProvider
import java.io.File

/**
 * 系统分享：把导出好的文件丢给微信 / QQ / 邮件 / 网盘等等。
 *
 * 为什么不直接 `Intent` 塞 `File`：
 * Android 7.0（API 24）起禁止把 `file://` URI 交给别的应用，会抛
 * `FileUriExposedException`。所以文件必须先落到自己的目录，再用 [FileProvider]
 * 换成 `content://` URI，并带上 `FLAG_GRANT_READ_URI_PERMISSION`
 * 临时把「读这一个文件」的权限授给接收方。
 *
 * 这一整套**不需要任何权限**（不碰 `WRITE_EXTERNAL_STORAGE`）——
 * 应用专属目录本来就归自己管，授权也只针对被分享的这一个文件。
 */
object Sharer {

    /** 分享文件放在这个子目录下，与 `res/xml/file_paths.xml` 里声明的路径对应 */
    private const val DIR = "share"

    /** 支持的分享类型；也决定 MIME 和文件后缀 */
    enum class Kind(val ext: String, val mime: String, val label: String) {
        TXT("txt", "text/plain", "文本报告"),
        CSV("csv", "text/csv", "表格"),
        JSON("json", "application/json", "账本备份"),
    }

    /**
     * 把 [content] 写进分享目录，然后调起系统分享面板。
     *
     * @param title 分享面板顶部的说明，例如「电费记账本 · 302 室」
     * @return `true` 表示面板已经弹出来了；`false` 表示中途失败（已经 Toast 过原因）
     */
    fun shareText(
        context: Context,
        fileName: String,
        content: String,
        kind: Kind,
        title: String,
        withBom: Boolean = false,
    ): Boolean {
        val file = runCatching { write(context, fileName, content, withBom) }
            .getOrElse {
                toast(context, "分享失败：写文件出错（${it.message}）")
                return false
            }

        val uri = runCatching { uriFor(context, file) }.getOrElse {
            toast(context, "分享失败：拿不到文件地址（${it.message}）")
            return false
        }

        // 分享面板本身要经 `Intent.createChooser` 才会出现「可以用哪些应用发」这一步；
        // 直接 startActivity 的话部分机型会弹「没有应用可执行此操作」。
        val send = Intent(Intent.ACTION_SEND).apply {
            type = kind.mime
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_SUBJECT, title)
            putExtra(Intent.EXTRA_TITLE, fileName)
            // 微信、QQ 在部分版本上不认 EXTRA_STREAM，得再给一份 ClipData 才肯收
            clipData = android.content.ClipData.newRawUri(fileName, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }

        val chooser = Intent.createChooser(send, "分享「$fileName」").apply {
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            // 从非 Activity 上下文启动时要这个标志，否则会抛 AndroidRuntimeException
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        return runCatching {
            context.startActivity(chooser)
            true
        }.getOrElse {
            toast(context, "分享失败：没有能接收的应用（${it.message}）")
            false
        }
    }

    /** 只写文件、不分享；成功返回文件，失败抛异常 */
    private fun write(
        context: Context,
        fileName: String,
        content: String,
        withBom: Boolean,
    ): File {
        val dir = File(shareDir(context), DIR).apply { mkdirs() }
        val file = File(dir, fileName)
        file.outputStream().use { os ->
            // CSV 加 UTF-8 BOM，Excel / WPS 打开才不乱码
            if (withBom) os.write(byteArrayOf(0xEF.toByte(), 0xBB.toByte(), 0xBF.toByte()))
            os.write(content.toByteArray(Charsets.UTF_8))
        }
        return file
    }

    /**
     * 应用专属外部目录；`null`（极少数机型外部存储没挂载）时退回内部目录 ——
     * 两条路径在 `file_paths.xml` 里都声明了。
     */
    private fun shareDir(context: Context): File =
        context.getExternalFilesDir(null) ?: context.filesDir

    private fun uriFor(context: Context, file: File): Uri =
        FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)

    private fun toast(context: Context, message: String) {
        Toast.makeText(context, message, Toast.LENGTH_LONG).show()
    }
}
