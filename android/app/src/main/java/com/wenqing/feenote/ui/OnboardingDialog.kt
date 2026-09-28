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
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.InputChip
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.wenqing.feenote.data.Repository
import com.wenqing.feenote.util.Onboarding

/**
 * 首次使用引导（也可以在设置页里重新打开，那时 [firstRun] 传 false）。
 *
 * 应用本身**不带任何数据**，装完是个空账本。这个弹窗就是让新用户
 * 一分钟内把「房间号 + 室友」填好，之后就能直接记账 —— 不用先去设置里摸索。
 */
@Composable
fun OnboardingDialog(
    repo: Repository,
    firstRun: Boolean,
    onDismiss: () -> Unit,
    onDone: () -> Unit,
) {
    var room by remember { mutableStateOf(repo.room()) }
    var nameInput by remember { mutableStateOf("") }
    /** 重开时把已有成员带进来，免得又要手打一遍 */
    var names by remember { mutableStateOf(repo.memberNames()) }
    var error by remember { mutableStateOf("") }

    fun addName() {
        val err = Onboarding.validateName(nameInput, names)
        if (err != null) {
            error = err
            return
        }
        names = names + nameInput.trim()
        nameInput = ""
        error = ""
    }

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
                    text = if (firstRun) "欢迎使用电费记账本" else "房间与成员",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    text = if (firstRun) {
                        "应用里现在是空的，先填一下这两项，之后就能记账了。"
                    } else {
                        "改完点「保存」即可。要删人请用下面的「成员管理」，那里会一并处理 TA 的记录。"
                    },
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    lineHeight = 20.sp,
                )

                Spacer(Modifier.height(20.dp))

                // ---------------- 房间号 ----------------
                FieldLabel("房间号")
                OutlinedTextField(
                    value = room,
                    onValueChange = { room = it; error = "" },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    placeholder = { Text("比如 302") },
                )

                Spacer(Modifier.height(18.dp))

                // ---------------- 成员 ----------------
                FieldLabel("宿舍成员（谁交电费就填谁）")
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = nameInput,
                        onValueChange = { nameInput = it; error = "" },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        placeholder = { Text("名字或姓氏") },
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                        keyboardActions = KeyboardActions(onDone = { addName() }),
                    )
                    Spacer(Modifier.width(8.dp))
                    Button(onClick = { addName() }) { Text("添加") }
                }

                if (names.isNotEmpty()) {
                    Spacer(Modifier.height(10.dp))
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        names.forEachIndexed { index, n ->
                            InputChip(
                                selected = false,
                                onClick = { names = names.filterIndexed { i, _ -> i != index } },
                                label = { Text("${index + 1}. $n") },
                                trailingIcon = {
                                    Icon(
                                        Icons.Filled.Close,
                                        contentDescription = "移除 $n",
                                        modifier = Modifier.width(16.dp),
                                    )
                                },
                            )
                        }
                    }
                }

                Spacer(Modifier.height(10.dp))
                Text(
                    text = when {
                        error.isNotEmpty() -> error
                        names.isEmpty() -> "至少要加一个人，编号会按添加顺序排。"
                        else -> "编号：${Onboarding.preview(names)}"
                    },
                    fontSize = 12.sp,
                    color = if (error.isNotEmpty()) {
                        MaterialTheme.colorScheme.error
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                    lineHeight = 18.sp,
                )

                Spacer(Modifier.height(22.dp))

                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    TextButton(onClick = {
                        if (firstRun) repo.skipOnboarding()
                        onDismiss()
                    }) { Text(if (firstRun) "以后再说" else "取消") }

                    Spacer(Modifier.width(8.dp))

                    Button(
                        enabled = names.isNotEmpty(),
                        onClick = {
                            repo.applyOnboarding(room, names)
                            onDone()
                        },
                    ) { Text(if (firstRun) "开始使用" else "保存") }
                }

                Spacer(Modifier.height(4.dp))
                Text(
                    text = "这些随时都能在「设置」里改。",
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
