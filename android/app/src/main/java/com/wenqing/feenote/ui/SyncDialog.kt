package com.wenqing.feenote.ui

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Handler
import android.os.Looper
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.wenqing.feenote.data.Repository
import com.wenqing.feenote.data.SyncPlan
import com.wenqing.feenote.net.LanSync
import com.wenqing.feenote.net.SyncTarget
import com.wenqing.feenote.util.SyncPrefs
import com.wenqing.feenote.util.money2

/**
 * 「电脑同步」面板。
 *
 * 两个方向**分开**，不再一次双向全同步 ——
 * 用户能明确知道这一下是把手机的东西送出去，还是把电脑的东西拿回来：
 *   - 同步到手机（电脑 → 手机）：只读电脑，把电脑有、手机没有的补进手机
 *   - 同步到电脑（手机 → 电脑）：只推手机，电脑按 uid 去重合并
 *
 * 两个方向在动手之前都会先做一次**预演**（`Repository.planSync`），
 * 找出「uid 不同但人 + 日期 + 金额一样」的疑似重复，弹框让用户确认。
 * 不这么做的话，两边各自手输过的同一笔账会各拿一个 uid，同步完就变成两份。
 *
 * 网络动作全在后台线程，结果用 Handler 抛回主线程 ——
 * 本机 Maven Central 不通，不想为一个请求引 coroutines / OkHttp。
 */
@Composable
fun SyncDialog(
    repo: Repository,
    onDismiss: () -> Unit,
    onChanged: () -> Unit,
) {
    val context = LocalContext.current
    val saved = remember { SyncPrefs.load(context) }

    var host by remember { mutableStateOf(saved.host) }
    var portText by remember { mutableStateOf(saved.port.toString()) }
    var pair by remember { mutableStateOf(saved.pair) }
    var busy by remember { mutableStateOf(false) }
    var result by remember { mutableStateOf<String?>(null) }
    var resultOk by remember { mutableStateOf(true) }
    var pending by remember { mutableStateOf<PendingSync?>(null) }

    val onWifi = remember { isOnWifi(context) }

    fun currentTarget(): SyncTarget =
        SyncTarget.parse(host, pair, portText.trim().toIntOrNull() ?: SyncTarget.DEFAULT_PORT)

    /** 先把活儿丢到后台线程，回来再看是「直接给结论」还是「要先问一句」 */
    fun run(block: () -> Step) {
        val target = currentTarget()
        // problem = 格式不对，发也白发；hint = 格式没错但一定连不通（比如填了 127.0.0.1）
        val blocked = target.problem() ?: target.hint()
        if (blocked != null) {
            result = blocked
            resultOk = false
            return
        }
        busy = true
        result = null
        Thread {
            val step = try {
                block()
            } catch (e: Exception) {
                Step.Say(e.message ?: "同步失败（${e.javaClass.simpleName}）", ok = false)
            }
            if (step is Step.Say && step.ok) SyncPrefs.save(context, target)
            Handler(Looper.getMainLooper()).post {
                busy = false
                when (step) {
                    is Step.Say -> {
                        resultOk = step.ok
                        result = step.text
                        if (step.ok) onChanged()
                    }
                    is Step.Need -> {
                        resultOk = true
                        result = step.hint
                        pending = step.pending
                    }
                }
            }
        }.start()
    }

    Dialog(onDismissRequest = { if (!busy) onDismiss() }) {
        Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surface) {
            Column(
                Modifier
                    .padding(20.dp)
                    .heightIn(max = 600.dp)
                    .verticalScroll(rememberScrollState()),
            ) {
                Text(
                    "电脑同步",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    "电脑上打开桌面版 → 点顶栏「手机同步」→ 启动服务，\n" +
                        "把那里的地址和 4 位配对码抄到这里。两台要连同一个 WiFi。",
                    fontSize = 12.sp,
                    lineHeight = 18.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (!onWifi) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "当前好像没连 WiFi —— 手机和电脑不在同一个网里是同步不了的。",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.error,
                    )
                }

                Spacer(Modifier.height(14.dp))
                OutlinedTextField(
                    value = host,
                    onValueChange = { host = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    enabled = !busy,
                    label = { Text("电脑地址") },
                    placeholder = { Text("192.168.1.5") },
                )
                Spacer(Modifier.height(10.dp))
                Row {
                    OutlinedTextField(
                        value = portText,
                        onValueChange = { portText = it.filter { c -> c.isDigit() } },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        enabled = !busy,
                        label = { Text("端口") },
                    )
                    Spacer(Modifier.width(10.dp))
                    OutlinedTextField(
                        value = pair,
                        onValueChange = { pair = it.filter { c -> c.isDigit() }.take(4) },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        enabled = !busy,
                        label = { Text("配对码") },
                        placeholder = { Text("4 位") },
                    )
                }

                Spacer(Modifier.height(10.dp))
                OutlinedButton(
                    enabled = !busy,
                    modifier = Modifier.fillMaxWidth(),
                    onClick = {
                        // 「测试连接」只探活，不动任何数据 —— 先确认地址对了再同步
                        run {
                            val info = LanSync.ping(currentTarget())
                            Step.Say(
                                "连上了：${info.app} v${info.version}\n" +
                                    "电脑上房间「${info.room.ifBlank { "未设置" }}」，" +
                                    "记录 ${info.records} 条、回收站 ${info.trash} 条、" +
                                    "成员 ${info.members} 人。"
                            )
                        }
                    },
                ) { Text("测试连接") }

                Spacer(Modifier.height(16.dp))
                Box(
                    Modifier
                        .fillMaxWidth()
                        .height(1.dp)
                        .background(MaterialTheme.colorScheme.outlineVariant)
                )
                Spacer(Modifier.height(14.dp))

                // ---------------- 方向一：电脑 → 手机 ----------------
                DirectionBlock(
                    title = "同步到手机",
                    subtitle = "把电脑上有、手机上没有的取回来。\n只读电脑，不会改动电脑上的账。",
                    buttonText = "同步到手机",
                    enabled = !busy,
                    onClick = {
                        run {
                            val target = currentTarget()
                            val remote = LanSync.pull(target)
                            val plan = repo.planSync(remote)
                            if (plan.pullDup.isEmpty()) {
                                Step.Say(applyPull(repo, remote, plan, skip = true))
                            } else {
                                Step.Need(
                                    PendingSync(toPhone = true, plan = plan, remote = remote),
                                    "电脑上有 ${plan.pullDup.size} 条和手机疑似是同一笔，\n" +
                                        "先确认一下再取回。",
                                )
                            }
                        }
                    },
                )

                Spacer(Modifier.height(12.dp))

                // ---------------- 方向二：手机 → 电脑 ----------------
                DirectionBlock(
                    title = "同步到电脑",
                    subtitle = "把手机上有、电脑上没有的推过去。\n电脑按 uid 合并，不会覆盖它原有的记录。",
                    buttonText = "同步到电脑",
                    enabled = !busy,
                    onClick = {
                        run {
                            val target = currentTarget()
                            // 先读一遍电脑那份（只读），才知道有哪些是疑似重复
                            val remote = LanSync.pull(target)
                            val plan = repo.planSync(remote)
                            if (plan.pushDup.isEmpty()) {
                                Step.Say(applyPush(repo, target, plan, skip = true))
                            } else {
                                Step.Need(
                                    PendingSync(toPhone = false, plan = plan, remote = remote),
                                    "手机上有 ${plan.pushDup.size} 条和电脑疑似是同一笔，\n" +
                                        "先确认一下再推送。",
                                )
                            }
                        }
                    },
                )

                if (busy) {
                    Spacer(Modifier.height(14.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            "正在跟电脑说话…",
                            fontSize = 13.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }

                result?.let { text ->
                    Spacer(Modifier.height(14.dp))
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .background(
                                if (resultOk) {
                                    MaterialTheme.colorScheme.primaryContainer
                                } else {
                                    MaterialTheme.colorScheme.errorContainer
                                },
                                RoundedCornerShape(12.dp),
                            )
                            .padding(horizontal = 12.dp, vertical = 10.dp),
                    ) {
                        Text(
                            text,
                            fontSize = 13.sp,
                            lineHeight = 19.sp,
                            color = if (resultOk) {
                                MaterialTheme.colorScheme.onPrimaryContainer
                            } else {
                                MaterialTheme.colorScheme.onErrorContainer
                            },
                        )
                    }
                }

                Spacer(Modifier.height(14.dp))
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                ) {
                    TextButton(onClick = { if (!busy) onDismiss() }) { Text("关闭") }
                }
            }
        }
    }

    // ---------------- 疑似重复确认 ----------------
    pending?.let { p ->
        DupConfirmDialog(
            pending = p,
            onSkipAndGo = {
                pending = null
                if (p.toPhone) {
                    run { Step.Say(applyPull(repo, p.remote, p.plan, skip = true)) }
                } else {
                    run { Step.Say(applyPush(repo, currentTarget(), p.plan, skip = true)) }
                }
            },
            onTakeAll = {
                pending = null
                if (p.toPhone) {
                    run { Step.Say(applyPull(repo, p.remote, p.plan, skip = false)) }
                } else {
                    run { Step.Say(applyPush(repo, currentTarget(), p.plan, skip = false)) }
                }
            },
            onCancel = { pending = null },
        )
    }
}

// ---------------------------------------------------------------------- 方向块

@Composable
private fun DirectionBlock(
    title: String,
    subtitle: String,
    buttonText: String,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    Column(Modifier.fillMaxWidth()) {
        Text(
            title,
            fontSize = 15.sp,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.onSurface,
        )
        Spacer(Modifier.height(2.dp))
        Text(
            subtitle,
            fontSize = 12.sp,
            lineHeight = 17.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(8.dp))
        Button(
            enabled = enabled,
            modifier = Modifier.fillMaxWidth(),
            onClick = onClick,
        ) { Text(buttonText, fontWeight = FontWeight.SemiBold) }
    }
}

// ---------------------------------------------------------------------- 重复确认

@Composable
private fun DupConfirmDialog(
    pending: PendingSync,
    onSkipAndGo: () -> Unit,
    onTakeAll: () -> Unit,
    onCancel: () -> Unit,
) {
    val dups = if (pending.toPhone) pending.plan.pullDup else pending.plan.pushDup
    val from = if (pending.toPhone) "电脑" else "手机"
    val to = if (pending.toPhone) "手机" else "电脑"

    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text("发现 ${dups.size} 条疑似重复") },
        text = {
            Column(Modifier.heightIn(max = 380.dp).verticalScroll(rememberScrollState())) {
                Text(
                    "下面这些在${from}和${to}上各有一条，人和日期、金额都一样，" +
                        "多半是同一笔账在两边各记了一次。\n" +
                        "建议跳过 —— 否则两边会各留一份。",
                    fontSize = 13.sp,
                    lineHeight = 19.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(10.dp))
                dups.take(8).forEach { d ->
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .background(
                                MaterialTheme.colorScheme.surfaceVariant,
                                RoundedCornerShape(10.dp),
                            )
                            .padding(horizontal = 10.dp, vertical = 8.dp),
                    ) {
                        Text(
                            "${d.date}  ${d.member}  ${money2(d.amount)}",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                        Text(
                            "手机备注：${d.phoneNote.ifBlank { "（空）" }}\n" +
                                "电脑备注：${d.pcNote.ifBlank { "（空）" }}",
                            fontSize = 11.sp,
                            lineHeight = 16.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Spacer(Modifier.height(6.dp))
                }
                if (dups.size > 8) {
                    Text(
                        "…… 还有 ${dups.size - 8} 条",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onSkipAndGo) {
                Text("跳过这些，同步其它的", fontWeight = FontWeight.SemiBold)
            }
        },
        dismissButton = {
            Row {
                TextButton(onClick = onCancel) { Text("取消") }
                TextButton(onClick = onTakeAll) { Text("全都同步") }
            }
        },
    )
}

// ---------------------------------------------------------------------- 实际动作

/** 电脑 → 手机。skip = true 时跳过疑似重复的那几条 */
private fun applyPull(
    repo: Repository,
    remote: String,
    plan: SyncPlan,
    skip: Boolean,
): String {
    val got = repo.importJson(
        remote,
        merge = true,
        skipUids = if (skip) plan.pullDupUids else emptySet(),
        label = "从电脑同步到手机",
    )
    if (got.added == 0 && got.trashed == 0 && got.skippedDup == 0) {
        return "手机这边已经是最新的了，没有需要取回的记录。\n手机现有 ${got.total} 条。"
    }
    return "已同步到手机。\n" +
        "新增 ${got.added} 条、删除 ${got.trashed} 条" +
        (if (got.skippedDup > 0) "、跳过疑似重复 ${got.skippedDup} 条" else "") +
        "，\n手机现在共 ${got.total} 条。"
}

/** 手机 → 电脑。skip = true 时把疑似重复的那几条剔出去再推 */
private fun applyPush(
    repo: Repository,
    target: SyncTarget,
    plan: SyncPlan,
    skip: Boolean,
): String {
    val skipUids = if (skip) plan.pushDupUids else emptySet()
    val book = if (skipUids.isEmpty()) {
        repo.exportJson()
    } else {
        repo.exportJson(
            records = plan.pushRecords.filter { it.uid !in skipUids },
            deleted = plan.pushTrash.filter { it.uid !in skipUids },
        )
    }
    val res = LanSync.push(target, book)
    if (res.added == 0 && res.trashed == 0) {
        return "电脑那边已经是最新的了，没有需要推过去的记录。\n电脑现有 ${res.records} 条。"
    }
    return "已同步到电脑。\n" +
        "电脑新增 ${res.added} 条、删除 ${res.trashed} 条" +
        (if (skipUids.isNotEmpty()) "、跳过疑似重复 ${skipUids.size} 条" else "") +
        "，\n电脑现在共 ${res.records} 条。"
}

// ---------------------------------------------------------------------- 小结构

/** 正在等用户确认的同步 */
private data class PendingSync(
    /** true = 电脑 → 手机；false = 手机 → 电脑 */
    val toPhone: Boolean,
    val plan: SyncPlan,
    /** 从电脑取回的那份原文，确认之后再拿它导入 */
    val remote: String,
)

private sealed interface Step {
    data class Say(val text: String, val ok: Boolean = true) : Step
    data class Need(val pending: PendingSync, val hint: String) : Step
}

/** 当前是不是连在 WiFi 上（读不到状态就当 true，别乱报错吓人） */
private fun isOnWifi(context: Context): Boolean {
    return try {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val caps = cm.getNetworkCapabilities(cm.activeNetwork) ?: return false
        caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
    } catch (e: Exception) {
        true
    }
}
