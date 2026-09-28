package com.wenqing.feenote

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ReceiptLong
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import com.wenqing.feenote.data.DbHelper
import com.wenqing.feenote.data.Repository
import com.wenqing.feenote.ui.OnboardingDialog
import com.wenqing.feenote.ui.RecordListScreen
import com.wenqing.feenote.ui.SettingsScreen
import com.wenqing.feenote.ui.StatsScreen
import com.wenqing.feenote.ui.theme.FeeNoteTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val repo = Repository(DbHelper(applicationContext))
        setContent {
            FeeNoteTheme {
                AppRoot(repo)
            }
        }
    }
}

/**
 * 应用根节点：底部三个页签 —— 明细 / 统计 / 设置。
 *
 * `dataVersion` 是一个"数据版本号"，任何增删改后 +1，
 * 各个页面用 remember(dataVersion) 重新查询数据库，实现刷新。
 *
 * 每次真的有改动时还会弹一条带「撤销」的提示（撤销完再给「恢复」），
 * 判断依据是 `repo.undoCount` 有没有变高 —— 没变高说明这次 onChanged
 * 只是刷新、没有实际改动（比如导入失败），就不弹。
 *
 * 首次打开（账本是空的、又没走过引导）会先弹 [OnboardingDialog]，
 * 让新用户填好自己的房间号和室友 —— 应用本身不带任何数据。
 */
@Composable
private fun AppRoot(repo: Repository) {
    var tab by remember { mutableIntStateOf(0) }
    var dataVersion by remember { mutableIntStateOf(0) }

    /** 首次引导只在冷启动时问一次，别每次重组都去查库 */
    var showOnboarding by remember { mutableStateOf(repo.needsOnboarding()) }

    val snackbar = remember { SnackbarHostState() }
    var seenUndoCount by remember { mutableIntStateOf(0) }
    /** 每次改动 +1，用来把「弹撤销提示」这件事推给 LaunchedEffect */
    var undoSignal by remember { mutableIntStateOf(0) }
    var undoSignalLabel by remember { mutableStateOf("") }

    val onChanged: () -> Unit = {
        dataVersion++
        val now = repo.undoCount
        if (now > seenUndoCount) {
            seenUndoCount = now
            repo.undoLabel?.let { label ->
                undoSignalLabel = label
                undoSignal++
            }
        } else {
            seenUndoCount = now
        }
    }

    LaunchedEffect(undoSignal) {
        if (undoSignal == 0) return@LaunchedEffect
        val r = snackbar.showSnackbar(
            message = "已${undoSignalLabel}",
            actionLabel = "撤销",
            duration = SnackbarDuration.Short,
        )
        if (r != SnackbarResult.ActionPerformed) return@LaunchedEffect

        val undone = repo.undo()
        dataVersion++
        seenUndoCount = repo.undoCount
        if (undone == null) return@LaunchedEffect

        val r2 = snackbar.showSnackbar(
            message = "已撤销：$undone",
            actionLabel = "恢复",
            duration = SnackbarDuration.Short,
        )
        if (r2 != SnackbarResult.ActionPerformed) return@LaunchedEffect

        val redone = repo.redo()
        dataVersion++
        seenUndoCount = repo.undoCount
        if (redone != null) {
            snackbar.showSnackbar("已恢复：$redone", duration = SnackbarDuration.Short)
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbar) },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(
                    selected = tab == 0,
                    onClick = { tab = 0 },
                    icon = { Icon(Icons.AutoMirrored.Filled.ReceiptLong, contentDescription = null) },
                    label = { Text("明细") },
                )
                NavigationBarItem(
                    selected = tab == 1,
                    onClick = { tab = 1 },
                    icon = { Icon(Icons.Filled.BarChart, contentDescription = null) },
                    label = { Text("统计") },
                )
                NavigationBarItem(
                    selected = tab == 2,
                    onClick = { tab = 2 },
                    icon = { Icon(Icons.Filled.Settings, contentDescription = null) },
                    label = { Text("设置") },
                )
            }
        },
    ) { inner ->
        val pageModifier = androidx.compose.ui.Modifier.padding(inner)
        when (tab) {
            0 -> RecordListScreen(repo, dataVersion, onChanged, pageModifier)
            1 -> StatsScreen(repo, dataVersion, pageModifier)
            else -> SettingsScreen(repo, dataVersion, onChanged, pageModifier)
        }
    }

    if (showOnboarding) {
        OnboardingDialog(
            repo = repo,
            firstRun = true,
            onDismiss = { showOnboarding = false; dataVersion++ },
            onDone = {
                showOnboarding = false
                onChanged()
            },
        )
    }
}
