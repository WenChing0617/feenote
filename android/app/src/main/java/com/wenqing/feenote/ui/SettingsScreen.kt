package com.wenqing.feenote.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.net.Uri
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.RestoreFromTrash
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.wenqing.feenote.BuildConfig
import com.wenqing.feenote.data.Member
import com.wenqing.feenote.data.Record
import com.wenqing.feenote.data.Repository
import com.wenqing.feenote.ui.theme.memberColor
import com.wenqing.feenote.util.Dates
import com.wenqing.feenote.util.Exporter
import com.wenqing.feenote.util.JsonCodec
import com.wenqing.feenote.util.Sharer
import com.wenqing.feenote.util.money2

/** 设置页：房间号、成员管理、导出、回收站 */
@Composable
fun SettingsScreen(
    repo: Repository,
    dataVersion: Int,
    onChanged: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val room = remember(dataVersion) { repo.room() }
    val members = remember(dataVersion) { repo.members() }
    val recordCount = remember(dataVersion) { repo.records().size }
    val trashCount = remember(dataVersion) { repo.trash().size }
    val total = remember(dataVersion) { repo.grandTotal() }
    val firstDate = remember(dataVersion) { repo.firstDate() }
    val lastDate = remember(dataVersion) { repo.lastDate() }

    var showRoomEditor by remember { mutableStateOf(false) }
    var showMembers by remember { mutableStateOf(false) }
    var showTrash by remember { mutableStateOf(false) }
    var showSync by remember { mutableStateOf(false) }
    var showDup by remember { mutableStateOf(false) }
    var showOnboarding by remember { mutableStateOf(false) }
    var showShare by remember { mutableStateOf(false) }

    // 撤销 / 恢复：每改一笔就记一个快照，这里读栈顶看还能撤什么
    val undoLabel = remember(dataVersion) { repo.undoLabel }
    val redoLabel = remember(dataVersion) { repo.redoLabel }
    val dupGroups = remember(dataVersion) { repo.duplicateGroups() }

    var pendingExport by remember { mutableStateOf<Pair<String, String>?>(null) }

    val exportTxt = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("text/plain")
    ) { uri ->
        pendingExport?.let { (name, content) ->
            if (uri != null) {
                writeText(context, uri, content, withBom = false)
                toast(context, "已导出 $name")
            }
        }
        pendingExport = null
    }

    val exportCsv = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("text/csv")
    ) { uri ->
        pendingExport?.let { (name, content) ->
            if (uri != null) {
                writeText(context, uri, content, withBom = true)
                toast(context, "已导出 $name")
            }
        }
        pendingExport = null
    }

    // 与电脑互通：导出一份桌面版能直接「导入账本」的 JSON
    val exportBook = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/json")
    ) { uri ->
        pendingExport?.let { (name, content) ->
            if (uri != null) {
                writeText(context, uri, content, withBom = false)
                toast(context, "已导出 $name")
            }
        }
        pendingExport = null
    }

    // 导入：先从系统文件选择器读到内容，再问是合并还是覆盖
    var importText by remember { mutableStateOf<String?>(null) }
    val pickBook = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri != null) {
            val text = readText(context, uri)
            if (text == null) {
                toast(context, "这个文件读不出来")
            } else {
                importText = text
            }
        }
    }

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 28.dp),
    ) {
        item { SectionTitle("房间") }
        item {
            SettingRow(
                title = "房间号",
                subtitle = if (room.isBlank()) "未设置" else room,
                onClick = { showRoomEditor = true },
            )
        }
        item {
            SettingRow(
                title = "首次设置引导",
                subtitle = "一次填好房间号和成员，也可随时重来",
                onClick = { showOnboarding = true },
            )
        }

        item { SectionTitle("成员（${members.size} 人）") }
        item {
            SettingRow(
                title = "成员管理",
                subtitle = if (members.isEmpty()) {
                    "还没有成员，点这里添加"
                } else {
                    members.joinToString("、") { "${it.orderNo}.${it.name}" }
                },
                onClick = { showMembers = true },
            )
        }

        item { SectionTitle("操作历史") }
        item {
            SettingRow(
                title = "撤销上一步",
                subtitle = undoLabel?.let { "会撤掉「$it」" } ?: "暂时没有可以撤销的操作",
                enabled = undoLabel != null,
                onClick = {
                    val done = repo.undo()
                    onChanged()
                    if (done != null) toast(context, "已撤销：$done")
                },
            )
        }
        item {
            SettingRow(
                title = "恢复（重做）",
                subtitle = redoLabel?.let { "会恢复「$it」" } ?: "没有刚撤销掉的操作",
                enabled = redoLabel != null,
                onClick = {
                    val done = repo.redo()
                    onChanged()
                    if (done != null) toast(context, "已恢复：$done")
                },
            )
        }

        item { SectionTitle("与电脑互通") }
        item {
            SettingRow(
                title = "电脑同步（局域网）",
                subtitle = "两台连同一个 WiFi，可选「同步到手机」或「同步到电脑」。不用数据线、不经过服务器",
                onClick = { showSync = true },
            )
        }
        item {
            SettingRow(
                title = "查重（同一笔记了两份）",
                subtitle = if (dupGroups.isEmpty()) {
                    "没有发现重复记录"
                } else {
                    "发现 ${dupGroups.size} 组疑似重复，共 ${dupGroups.sumOf { it.items.size }} 条"
                },
                onClick = { if (dupGroups.isEmpty()) toast(context, "没有发现重复记录") else showDup = true },
            )
        }
        item {
            SettingRow(
                title = "导出账本 JSON",
                subtitle = "不用局域网时的老办法：导成文件，再到电脑上「导入账本」",
                onClick = {
                    val name = Exporter.fileName(repo, "json")
                    pendingExport = name to repo.exportJson()
                    exportBook.launch(name)
                },
            )
        }
        item {
            SettingRow(
                title = "导入账本 JSON",
                subtitle = "读电脑上导出的账本，可选合并或覆盖",
                onClick = { pickBook.launch(arrayOf("*/*")) },
            )
        }

        item { SectionTitle("导出") }
        item {
            SettingRow(
                title = "分享给微信 / QQ",
                subtitle = "把账本发到群里：直接弹系统分享面板，挑一个应用就发出去了",
                onClick = { showShare = true },
            )
        }
        item {
            SettingRow(
                title = "导出 TXT（文本报告）",
                subtitle = "适合直接看或发群里",
                onClick = {
                    val name = Exporter.fileName(repo, "txt")
                    pendingExport = name to Exporter.buildTxt(repo)
                    exportTxt.launch(name)
                },
            )
        }
        item {
            SettingRow(
                title = "导出 CSV（表格）",
                subtitle = "可用 Excel / WPS 打开",
                onClick = {
                    val name = Exporter.fileName(repo, "csv")
                    pendingExport = name to Exporter.buildCsv(repo)
                    exportCsv.launch(name)
                },
            )
        }
        item {
            SettingRow(
                title = "复制文本报告到剪贴板",
                subtitle = "粘贴到微信、备忘录都很方便",
                onClick = {
                    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                    cm.setPrimaryClip(ClipData.newPlainText("电费记账", Exporter.buildTxt(repo)))
                    toast(context, "已复制到剪贴板")
                },
            )
        }

        item { SectionTitle("回收站") }
        item {
            SettingRow(
                title = "回收站",
                subtitle = if (trashCount == 0) "空" else "$trashCount 条已删除记录",
                onClick = { showTrash = true },
            )
        }

        item { SectionTitle("数据概览") }
        item {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 14.dp, vertical = 4.dp),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
            ) {
                Column(Modifier.padding(16.dp)) {
                    InfoLine("记录条数", "$recordCount 条")
                    InfoLine("累计金额", money2(total))
                    if (firstDate.isNotEmpty()) {
                        InfoLine("数据范围", "${Dates.full(firstDate)} ~ ${Dates.full(lastDate)}")
                    }
                    InfoLine("数据存放", "手机本地数据库，卸载应用才会清除")
                }
            }
        }

        item {
            Text(
                text = "电费记账本 · Android 版 v${BuildConfig.VERSION_NAME}\n" +
                    "数据存在手机本地数据库，不经过任何服务器。\n" +
                    "「电脑同步」只在同一个 WiFi 里直连你自己那台电脑，配上 4 位配对码才能读写。\n" +
                    "「分享」由系统分享面板完成，文件不经过本应用之外的任何服务器。",
                fontSize = 12.sp,
                lineHeight = 18.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 20.dp),
            )
        }
    }

    if (showRoomEditor) {
        RoomEditorDialog(
            current = room,
            onDismiss = { showRoomEditor = false },
            onSave = {
                repo.setRoom(it)
                showRoomEditor = false
                onChanged()
            },
        )
    }

    if (showOnboarding) {
        OnboardingDialog(
            repo = repo,
            firstRun = false,
            onDismiss = { showOnboarding = false },
            onDone = {
                showOnboarding = false
                onChanged()
            },
        )
    }

    if (showMembers) {
        MemberManagerDialog(
            repo = repo,
            onDismiss = { showMembers = false },
            onChanged = onChanged,
        )
    }

    if (showTrash) {
        TrashDialog(
            repo = repo,
            onDismiss = { showTrash = false },
            onChanged = onChanged,
        )
    }

    if (showSync) {
        SyncDialog(
            repo = repo,
            onDismiss = { showSync = false },
            onChanged = onChanged,
        )
    }

    if (showDup) {
        DupDialog(
            repo = repo,
            onDismiss = { showDup = false },
            onChanged = onChanged,
        )
    }

    if (showShare) {
        ShareDialog(
            repo = repo,
            onDismiss = { showShare = false },
        )
    }

    importText?.let { text ->
        val book = runCatching { JsonCodec.parse(text) }.getOrNull()
        if (book == null) {
            AlertDialog(
                onDismissRequest = { importText = null },
                title = { Text("导入失败") },
                text = {
                    Text("这个文件不是账本 JSON，或者内容已经损坏。\n\n请确认选的是桌面版「导出账本备份」生成的那个 .json。")
                },
                confirmButton = {
                    TextButton(onClick = { importText = null }) { Text("知道了") }
                },
            )
        } else {
            // 先算一下这个文件里有多少条和手机上的疑似是同一笔（同人 + 同日期 + 同金额）
            val dupCount = remember(text) {
                runCatching { repo.planSync(text).pullDup.size }.getOrDefault(0)
            }
            AlertDialog(
                onDismissRequest = { importText = null },
                title = { Text("导入账本") },
                text = {
                    Column {
                        Text(
                            "文件里有 ${book.records.size} 条记录" +
                                if (book.deleted.isEmpty()) "" else "、回收站 ${book.deleted.size} 条",
                            fontSize = 15.sp,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                        Spacer(Modifier.height(10.dp))
                        Text(
                            "合并：两边记录都保留，同一条只留一份（推荐）\n" +
                                "覆盖：用文件内容整个替换手机账本，手机上多出来的记录会没有",
                            fontSize = 13.sp,
                            lineHeight = 20.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        if (dupCount > 0) {
                            Spacer(Modifier.height(10.dp))
                            Text(
                                "⚠ 文件里有 $dupCount 条和手机上的记录「同人、同日期、同金额」，" +
                                    "多半是同一笔账在两边各记了一次。\n" +
                                    "合并后会变成两份，导完请到「查重」里删掉多余的那条。",
                                fontSize = 12.sp,
                                lineHeight = 18.sp,
                                color = MaterialTheme.colorScheme.error,
                            )
                        }
                    }
                },
                confirmButton = {
                    TextButton(onClick = {
                        val r = runCatching { repo.importJson(text, merge = true) }.getOrNull()
                        importText = null
                        onChanged()
                        toast(
                            context,
                            if (r == null) "导入失败"
                            else "合并完成：新增 ${r.added} 条，回收站 ${r.trashed} 条，现有 ${r.total} 条",
                        )
                    }) { Text("合并") }
                },
                dismissButton = {
                    Row {
                        TextButton(onClick = {
                            val r = runCatching { repo.importJson(text, merge = false) }.getOrNull()
                            importText = null
                            onChanged()
                            toast(
                                context,
                                if (r == null) "导入失败" else "已覆盖：账本现有 ${r.total} 条记录",
                            )
                        }) { Text("覆盖", color = MaterialTheme.colorScheme.error) }
                        TextButton(onClick = { importText = null }) { Text("取消") }
                    }
                },
            )
        }
    }
}

// ------------------------------------------------------------------ 小组件

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        fontSize = 13.sp,
        fontWeight = FontWeight.SemiBold,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(start = 20.dp, top = 20.dp, bottom = 6.dp),
    )
}

@Composable
private fun SettingRow(
    title: String,
    subtitle: String,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 14.dp, vertical = 4.dp)
            .clickable(enabled = enabled, onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 14.dp)) {
            Text(
                title,
                fontSize = 16.sp,
                color = if (enabled) {
                    MaterialTheme.colorScheme.onSurface
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
            )
            if (subtitle.isNotEmpty()) {
                Spacer(Modifier.height(3.dp))
                Text(
                    subtitle,
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                )
            }
        }
    }
}

@Composable
private fun InfoLine(label: String, value: String) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 5.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurface)
    }
}

// ------------------------------------------------------------------ 房间号

@Composable
private fun RoomEditorDialog(current: String, onDismiss: () -> Unit, onSave: (String) -> Unit) {
    var text by remember { mutableStateOf(current) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("房间号") },
        text = {
            OutlinedTextField(
                value = text,
                onValueChange = { text = it },
                singleLine = true,
                placeholder = { Text("例如 302") },
            )
        },
        confirmButton = { TextButton(onClick = { onSave(text.trim()) }) { Text("保存") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

// ------------------------------------------------------------------ 成员管理

@Composable
private fun MemberManagerDialog(
    repo: Repository,
    onDismiss: () -> Unit,
    onChanged: () -> Unit,
) {
    var list by remember { mutableStateOf(repo.members()) }
    var newName by remember { mutableStateOf("") }
    var renameTarget by remember { mutableStateOf<Member?>(null) }
    var deleteTarget by remember { mutableStateOf<Member?>(null) }

    fun reload() {
        list = repo.members()
        onChanged()
    }

    Dialog(onDismissRequest = onDismiss) {
        Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surface) {
            Column(Modifier.padding(20.dp)) {
                Text(
                    "成员管理",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    "编号固定，改名后历史记录一起跟着变",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(14.dp))

                Column(Modifier.verticalScroll(rememberScrollState())) {
                    list.forEach { m ->
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .padding(vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(32.dp)
                                    .background(memberColor(m.orderNo), CircleShape),
                                contentAlignment = Alignment.Center,
                            ) {
                                Text(
                                    m.orderNo.toString(),
                                    color = Color.White,
                                    fontSize = 14.sp,
                                    fontWeight = FontWeight.Bold,
                                )
                            }
                            Spacer(Modifier.width(10.dp))
                            Text(
                                m.name,
                                fontSize = 16.sp,
                                color = MaterialTheme.colorScheme.onSurface,
                                modifier = Modifier.weight(1f),
                            )
                            IconButton(onClick = { renameTarget = m }) {
                                Icon(Icons.Filled.Edit, contentDescription = "改名")
                            }
                            IconButton(onClick = { deleteTarget = m }) {
                                Icon(
                                    Icons.Filled.DeleteOutline,
                                    contentDescription = "删除",
                                    tint = MaterialTheme.colorScheme.error,
                                )
                            }
                        }
                    }
                }

                Spacer(Modifier.height(10.dp))
                HorizontalDivider()
                Spacer(Modifier.height(12.dp))

                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = newName,
                        onValueChange = { newName = it },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        label = { Text("新成员姓名") },
                    )
                    Spacer(Modifier.width(8.dp))
                    IconButton(
                        onClick = {
                            if (repo.addMember(newName)) {
                                newName = ""
                                reload()
                            }
                        },
                    ) {
                        Icon(Icons.Filled.Add, contentDescription = "添加")
                    }
                }

                Spacer(Modifier.height(14.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = onDismiss) { Text("完成") }
                }
            }
        }
    }

    renameTarget?.let { target ->
        var input by remember(target) { mutableStateOf(target.name) }
        AlertDialog(
            onDismissRequest = { renameTarget = null },
            title = { Text("把「${target.name}」改成") },
            text = {
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it },
                    singleLine = true,
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    repo.renameMember(target.name, input)
                    renameTarget = null
                    reload()
                }) { Text("保存") }
            },
            dismissButton = { TextButton(onClick = { renameTarget = null }) { Text("取消") } },
        )
    }

    deleteTarget?.let { target ->
        AlertDialog(
            onDismissRequest = { deleteTarget = null },
            title = { Text("删除成员「${target.name}」？") },
            text = { Text("TA 的所有记录会一起移入回收站，之后仍可恢复。") },
            confirmButton = {
                TextButton(onClick = {
                    repo.deleteMember(target.name)
                    deleteTarget = null
                    reload()
                }) { Text("删除") }
            },
            dismissButton = { TextButton(onClick = { deleteTarget = null }) { Text("取消") } },
        )
    }
}

// ------------------------------------------------------------------ 回收站

@Composable
private fun TrashDialog(
    repo: Repository,
    onDismiss: () -> Unit,
    onChanged: () -> Unit,
) {
    var list by remember { mutableStateOf(repo.trash()) }
    var confirmEmpty by remember { mutableStateOf(false) }

    fun reload() {
        list = repo.trash()
        onChanged()
    }

    Dialog(onDismissRequest = onDismiss) {
        Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surface) {
            Column(Modifier.padding(20.dp)) {
                Text(
                    "回收站",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    if (list.isEmpty()) "没有已删除的记录" else "${list.size} 条已删除记录",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(12.dp))

                Column(
                    Modifier
                        .heightIn(max = 320.dp)
                        .verticalScroll(rememberScrollState()),
                ) {
                    list.forEach { r: Record ->
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .padding(vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(
                                    "${r.member}  ${money2(r.amount)}",
                                    fontSize = 15.sp,
                                    color = MaterialTheme.colorScheme.onSurface,
                                )
                                Text(
                                    "${Dates.full(r.date)}${if (r.note.isBlank()) "" else " · ${r.note}"}",
                                    fontSize = 12.sp,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            IconButton(onClick = {
                                repo.restore(r.id)
                                reload()
                            }) {
                                Icon(Icons.Filled.RestoreFromTrash, contentDescription = "恢复")
                            }
                            IconButton(onClick = {
                                repo.purge(r.id)
                                reload()
                            }) {
                                Icon(
                                    Icons.Filled.DeleteOutline,
                                    contentDescription = "彻底删除",
                                    tint = MaterialTheme.colorScheme.error,
                                )
                            }
                        }
                    }
                }

                Spacer(Modifier.height(10.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    if (list.isNotEmpty()) {
                        TextButton(onClick = { confirmEmpty = true }) {
                            Text("清空回收站", color = MaterialTheme.colorScheme.error)
                        }
                    }
                    TextButton(onClick = onDismiss) { Text("关闭") }
                }
            }
        }
    }

    if (confirmEmpty) {
        AlertDialog(
            onDismissRequest = { confirmEmpty = false },
            title = { Text("清空回收站？") },
            text = { Text("这 ${list.size} 条记录将被彻底删除，无法恢复。") },
            confirmButton = {
                TextButton(onClick = {
                    repo.purgeTrash()
                    confirmEmpty = false
                    reload()
                }) { Text("彻底删除") }
            },
            dismissButton = {
                TextButton(onClick = { confirmEmpty = false }) { Text("取消") }
            },
        )
    }
}

// ------------------------------------------------------------------ 查重

/**
 * 查重面板：列出手机本地「同一人 + 同一天 + 同金额」出现了两次以上的记录。
 *
 * 这类重复多半是两边各自手输过同一笔账（uid 不同，光靠 uid 去重拦不住），
 * 也可能是真的交了两次。程序不替用户下判断，只把可疑的摆出来，让用户点着删。
 */
@Composable
private fun DupDialog(
    repo: Repository,
    onDismiss: () -> Unit,
    onChanged: () -> Unit,
) {
    var version by remember { mutableStateOf(0) }
    val groups = remember(version) { repo.duplicateGroups() }

    Dialog(onDismissRequest = onDismiss) {
        Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surface) {
            Column(Modifier.padding(20.dp).heightIn(max = 600.dp)) {
                Text(
                    "查重",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    "下面这些是「同一个人、同一天、同一个金额」出现了两次以上的记录。\n" +
                        "如果确认是同一笔，删掉多余的那条就行（会进回收站，还能恢复）。",
                    fontSize = 12.sp,
                    lineHeight = 18.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(12.dp))

                if (groups.isEmpty()) {
                    Text(
                        "没有发现重复记录 👍",
                        fontSize = 14.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                } else {
                    LazyColumn(
                        Modifier.weight(1f, fill = false),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        items(groups, key = { "${it.date}|${it.member}|${it.amount}" }) { g ->
                            Column(
                                Modifier
                                    .fillMaxWidth()
                                    .background(
                                        MaterialTheme.colorScheme.surfaceVariant,
                                        RoundedCornerShape(12.dp),
                                    )
                                    .padding(12.dp),
                            ) {
                                Text(
                                    "${Dates.full(g.date)}  ${g.member}  ${money2(g.amount)}",
                                    fontSize = 14.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    color = MaterialTheme.colorScheme.onSurface,
                                )
                                Spacer(Modifier.height(6.dp))
                                g.items.forEach { r ->
                                    Row(
                                        Modifier.fillMaxWidth(),
                                        verticalAlignment = Alignment.CenterVertically,
                                    ) {
                                        Column(Modifier.weight(1f)) {
                                            Text(
                                                "${r.method}${if (r.note.isBlank()) "" else " · ${r.note}"}",
                                                fontSize = 13.sp,
                                                color = MaterialTheme.colorScheme.onSurface,
                                            )
                                            Text(
                                                "uid ${r.uid}",
                                                fontSize = 11.sp,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            )
                                        }
                                        TextButton(onClick = {
                                            repo.moveToTrash(r.id, "查重删掉多余的那条")
                                            version++
                                            onChanged()
                                        }) {
                                            Text("删这条", color = MaterialTheme.colorScheme.error)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Spacer(Modifier.height(12.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = onDismiss) { Text("关闭") }
                }
            }
        }
    }
}

// ------------------------------------------------------------------ 分享

/**
 * 分享面板：先挑一个格式，再点「分享」调起系统分享面板。
 *
 * 为什么不点一下就直接分享：导出是有副作用的动作（会生成文件、会跳出应用），
 * 而「发到群里」这件事又很难撤回，所以中间加一步让用户看清楚要发哪个格式。
 */
@Composable
private fun ShareDialog(repo: Repository, onDismiss: () -> Unit) {
    val context = LocalContext.current
    var kind by remember { mutableStateOf(Sharer.Kind.TXT) }
    val room = remember { repo.room() }
    val title = if (room.isBlank()) "电费记账本" else "电费记账本 · $room 室"
    val recordCount = remember { repo.records().size }

    Dialog(onDismissRequest = onDismiss) {
        Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surface) {
            Column(Modifier.padding(20.dp).heightIn(max = 560.dp)) {
                Text(
                    "分享账本",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    "选一个格式，点「分享」会弹出系统面板，再挑微信、QQ 或别的应用发出去。",
                    fontSize = 12.sp,
                    lineHeight = 18.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(14.dp))

                Column(
                    Modifier.weight(1f, fill = false).verticalScroll(rememberScrollState()),
                ) {
                    Sharer.Kind.entries.forEach { k ->
                        FormatOption(
                            name = k.label,
                            desc = when (k) {
                                Sharer.Kind.TXT -> "一段排好版文字，微信聊天里能直接看（推荐）"
                                Sharer.Kind.CSV -> "表格文件，对方用 Excel / WPS 打开"
                                Sharer.Kind.JSON -> "完整账本备份，用于在电脑版「导入账本」恢复"
                            },
                            selected = kind == k,
                            onClick = { kind = k },
                        )
                        Spacer(Modifier.height(8.dp))
                    }

                    Spacer(Modifier.height(6.dp))
                    Text(
                        "当前账本共 $recordCount 条记录" +
                            (if (room.isBlank()) "" else "，房间 $room") + "。\n" +
                            "文件只在你点「分享」时生成，发出去之后能不能撤回由对方那个应用决定。",
                        fontSize = 11.sp,
                        lineHeight = 17.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }

                Spacer(Modifier.height(14.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = onDismiss) { Text("取消") }
                    Spacer(Modifier.width(4.dp))
                    Button(
                        onClick = {
                            val name = Exporter.shareFileName(repo, kind.ext)
                            val body = when (kind) {
                                Sharer.Kind.TXT -> Exporter.buildTxt(repo)
                                Sharer.Kind.CSV -> Exporter.buildCsv(repo)
                                Sharer.Kind.JSON -> repo.exportJson()
                            }
                            val ok = Sharer.shareText(
                                context = context,
                                fileName = name,
                                content = body,
                                kind = kind,
                                title = title,
                                // CSV 要带 BOM，Excel / WPS 打开才不乱码
                                withBom = kind == Sharer.Kind.CSV,
                            )
                            // 分享面板弹出来了就关掉自己的弹窗，免得两层叠着
                            if (ok) onDismiss()
                        },
                        modifier = Modifier.height(38.dp),
                        contentPadding = PaddingValues(horizontal = 18.dp, vertical = 0.dp),
                    ) {
                        Text("分享", fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                    }
                }
            }
        }
    }
}

@Composable
private fun FormatOption(
    name: String,
    desc: String,
    selected: Boolean,
    onClick: () -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .background(
                if (selected) {
                    MaterialTheme.colorScheme.primaryContainer
                } else {
                    MaterialTheme.colorScheme.surfaceVariant
                },
                RoundedCornerShape(12.dp),
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(
            selected = selected,
            onClick = onClick,
            colors = RadioButtonDefaults.colors(
                selectedColor = MaterialTheme.colorScheme.primary,
            ),
        )
        Spacer(Modifier.width(6.dp))
        Column(Modifier.weight(1f)) {
            Text(
                name,
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Spacer(Modifier.height(1.dp))
            Text(
                desc,
                fontSize = 11.sp,
                lineHeight = 15.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

// ------------------------------------------------------------------ 工具

private fun writeText(context: Context, uri: Uri, text: String, withBom: Boolean) {
    try {
        context.contentResolver.openOutputStream(uri)?.use { os ->
            if (withBom) {
                os.write(byteArrayOf(0xEF.toByte(), 0xBB.toByte(), 0xBF.toByte()))
            }
            os.write(text.toByteArray(Charsets.UTF_8))
        }
    } catch (e: Exception) {
        toast(context, "导出失败：${e.message}")
    }
}

/** 读文件内容；读不到返回 null */
private fun readText(context: Context, uri: Uri): String? = try {
    context.contentResolver.openInputStream(uri)?.use {
        it.readBytes().toString(Charsets.UTF_8).removePrefix("\uFEFF")
    }
} catch (e: Exception) {
    null
}

private fun toast(context: Context, message: String) {
    Toast.makeText(context, message, Toast.LENGTH_SHORT).show()
}
