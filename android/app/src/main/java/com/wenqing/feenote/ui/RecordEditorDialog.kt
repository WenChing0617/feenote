package com.wenqing.feenote.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.wenqing.feenote.data.Record
import com.wenqing.feenote.data.Repository
import com.wenqing.feenote.util.Dates
import com.wenqing.feenote.util.money2

private val METHODS = listOf("校园卡", "微信", "支付宝", "现金")

/** 金额快捷填充：宿舍交电费基本都是这几个数 */
private val QUICK_AMOUNTS = listOf(50, 100, 200, 300, 500)

/** 记一笔 / 编辑一笔。original 为 null 表示新增 */
@Composable
fun RecordEditorDialog(
    repo: Repository,
    original: Record?,
    onDismiss: () -> Unit,
    onSaved: () -> Unit,
) {
    val members = remember { repo.members() }
    val isEdit = original != null

    var member by remember { mutableStateOf(original?.member ?: members.firstOrNull()?.name ?: "") }
    var amountText by remember {
        mutableStateOf(
            original?.let { if (it.amount == it.amount.toLong().toDouble()) it.amount.toLong().toString() else it.amount.toString() } ?: ""
        )
    }
    var date by remember { mutableStateOf(original?.date ?: Dates.today()) }
    var method by remember { mutableStateOf(original?.method ?: "校园卡") }
    var note by remember { mutableStateOf(original?.note ?: "") }

    var showDatePicker by remember { mutableStateOf(false) }
    var showDeleteConfirm by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }

    Dialog(onDismissRequest = onDismiss) {
        Surface(
            shape = RoundedCornerShape(22.dp),
            color = MaterialTheme.colorScheme.surface,
        ) {
            Column(
                Modifier
                    .padding(22.dp)
                    .verticalScroll(rememberScrollState()),
            ) {
                Text(
                    text = if (isEdit) "编辑记录" else "记一笔",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Spacer(Modifier.height(16.dp))

                // ---------------- 谁充的 ----------------
                FieldLabel("谁充的")
                Row(
                    Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    members.forEach { m ->
                        FilterChip(
                            selected = member == m.name,
                            onClick = { member = m.name },
                            label = { Text("${m.orderNo}. ${m.name}") },
                        )
                    }
                }

                Spacer(Modifier.height(14.dp))

                // ---------------- 金额 ----------------
                FieldLabel("充了多少钱")
                OutlinedTextField(
                    value = amountText,
                    onValueChange = { input ->
                        // 只允许数字和一个小数点
                        if (input.count { it == '.' } <= 1 &&
                            input.all { it.isDigit() || it == '.' }
                        ) {
                            amountText = input
                            error = ""
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    placeholder = { Text("例如 50") },
                    prefix = { Text("¥") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    isError = error.isNotEmpty(),
                    supportingText = if (error.isNotEmpty()) {
                        { Text(error) }
                    } else null,
                )

                // 快捷填充：点一下就填进上面的框，省得每次敲数字
                Row(
                    Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    QUICK_AMOUNTS.forEach { q ->
                        FilterChip(
                            selected = amountText.toDoubleOrNull() == q.toDouble(),
                            onClick = {
                                amountText = q.toString()
                                error = ""
                            },
                            label = { Text("¥$q") },
                        )
                    }
                    if (amountText.isNotEmpty()) {
                        TextButton(onClick = {
                            amountText = ""
                            error = ""
                        }) { Text("清空") }
                    }
                }

                Spacer(Modifier.height(6.dp))

                // ---------------- 日期 ----------------
                FieldLabel("日期")
                OutlinedButton(
                    onClick = { showDatePicker = true },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Filled.CalendarMonth, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(Dates.full(date))
                }

                Spacer(Modifier.height(14.dp))

                // ---------------- 支付方式 ----------------
                FieldLabel("支付方式")
                Row(
                    Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    METHODS.forEach { item ->
                        FilterChip(
                            selected = method == item,
                            onClick = { method = item },
                            label = { Text(item) },
                        )
                    }
                }

                Spacer(Modifier.height(14.dp))

                // ---------------- 备注 ----------------
                FieldLabel("备注（可留空）")
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    placeholder = { Text("例如 期末前最后一次") },
                )

                Spacer(Modifier.height(20.dp))

                // ---------------- 按钮 ----------------
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    if (isEdit) {
                        OutlinedButton(
                            onClick = { showDeleteConfirm = true },
                            modifier = Modifier.weight(1f),
                        ) {
                            Text("删除", color = MaterialTheme.colorScheme.error)
                        }
                    }
                    Button(
                        onClick = {
                            val amount = amountText.toDoubleOrNull()
                            when {
                                member.isBlank() -> error = "请先选一个人"
                                amount == null || amount <= 0 -> error = "请输入大于 0 的金额"
                                else -> {
                                    val saved = Record(
                                        id = original?.id ?: 0L,
                                        // 编辑时沿用原来的 uid；新增留空，由数据层生成
                                        uid = original?.uid ?: "",
                                        date = date,
                                        member = member,
                                        amount = amount,
                                        method = method,
                                        note = note.trim(),
                                        // 手机端不再提供「期初首笔」开关；
                                        // 编辑从电脑同步过来的期初记录时，原标记原样保留。
                                        initial = original?.initial ?: false,
                                        createdAt = original?.createdAt ?: System.currentTimeMillis(),
                                    )
                                    if (isEdit) repo.updateRecord(saved) else repo.addRecord(saved)
                                    onSaved()
                                }
                            }
                        },
                        modifier = Modifier.weight(1f),
                    ) {
                        Text(if (isEdit) "保存" else "记下")
                    }
                }
            }
        }
    }

    if (showDatePicker) {
        PickDateDialog(
            current = date,
            onPick = { date = it },
            onDismiss = { showDatePicker = false },
        )
    }

    if (showDeleteConfirm && original != null) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = false },
            title = { Text("删除这条记录？") },
            text = {
                Text("「${original.member} ${money2(original.amount)}」会移入回收站，之后仍可在设置里恢复。")
            },
            confirmButton = {
                TextButton(onClick = {
                    repo.moveToTrash(original.id)
                    showDeleteConfirm = false
                    onSaved()
                }) { Text("移入回收站") }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteConfirm = false }) { Text("取消") }
            },
        )
    }
}

/** 表单里的小标题（记账弹窗和首次引导共用，所以不是 private） */
@Composable
internal fun FieldLabel(text: String) {
    Text(
        text = text,
        fontSize = 13.sp,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(bottom = 6.dp),
    )
}

/** 月视图日历选日期 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PickDateDialog(
    current: String,
    onPick: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    val state = rememberDatePickerState(initialSelectedDateMillis = Dates.toUtcMillis(current))
    DatePickerDialog(
        onDismissRequest = onDismiss,
        confirmButton = {
            TextButton(onClick = {
                state.selectedDateMillis?.let { onPick(Dates.fromUtcMillis(it)) }
                onDismiss()
            }) { Text("确定") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        },
    ) {
        DatePicker(state = state)
    }
}
