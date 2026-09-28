package com.wenqing.feenote.ui

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
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.wenqing.feenote.data.MemberTotal
import com.wenqing.feenote.data.Record
import com.wenqing.feenote.data.Repository
import com.wenqing.feenote.ui.theme.memberColor
import com.wenqing.feenote.util.Dates
import com.wenqing.feenote.util.RecordSearch
import com.wenqing.feenote.util.money
import com.wenqing.feenote.util.money2

/** 统计页：总账 + 每人累计（点某个人可以看他自己的全部充值记录） */
@Composable
fun StatsScreen(
    repo: Repository,
    dataVersion: Int,
    onChanged: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val totals = remember(dataVersion) { repo.totals() }
    val grand = remember(dataVersion) { repo.grandTotal() }
    val room = remember(dataVersion) { repo.room() }
    val records = remember(dataVersion) { repo.records() }
    val initialCount = remember(records) { records.count { it.initial } }
    val realCount = remember(records) { records.count { !it.initial } }

    var detailMember by remember { mutableStateOf<String?>(null) }

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 28.dp),
    ) {
        item {
            Column(
                Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.primary)
                    .padding(horizontal = 20.dp, vertical = 20.dp),
            ) {
                Text(
                    text = if (room.isBlank()) "总账" else "${room} 室 · 总账",
                    color = MaterialTheme.colorScheme.onPrimary,
                    fontSize = 16.sp,
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    text = money2(grand),
                    color = MaterialTheme.colorScheme.onPrimary,
                    fontSize = 38.sp,
                    fontWeight = FontWeight.Bold,
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    text = "充值 $realCount 笔" + if (initialCount > 0) "（另有期初 $initialCount 笔）" else "",
                    color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.85f),
                    fontSize = 13.sp,
                )
            }
        }

        item {
            Text(
                text = "每人累计",
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(start = 20.dp, top = 20.dp, bottom = 8.dp),
            )
        }

        items(totals, key = { it.member }) { item ->
            MemberStatCard(
                item = item,
                grand = grand,
                onClick = { detailMember = item.member },
            )
        }

        item {
            Text(
                text = "点某个人可以看 TA 的全部充值记录。\n" +
                    "说明：期初首笔（开学第一次充值）计入总金额，但不计入充值笔数。",
                fontSize = 12.sp,
                lineHeight = 18.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 18.dp),
            )
        }
    }

    detailMember?.let { name ->
        MemberDetailDialog(
            repo = repo,
            member = name,
            dataVersion = dataVersion,
            onDismiss = { detailMember = null },
            onChanged = onChanged,
        )
    }
}

@Composable
private fun MemberStatCard(item: MemberTotal, grand: Double, onClick: () -> Unit) {
    val ratio = if (grand > 0) (item.total / grand).toFloat() else 0f
    val color = memberColor(item.orderNo)

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 14.dp, vertical = 5.dp)
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(34.dp)
                        .background(color, CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = item.orderNo.toString(),
                        color = Color.White,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                    )
                }
                Spacer(Modifier.width(10.dp))
                Text(
                    text = item.member,
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Medium,
                    color = MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    text = money(item.total),
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.tertiary,
                )
            }

            Spacer(Modifier.height(12.dp))

            LinearProgressIndicator(
                progress = { ratio },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(7.dp),
                color = color,
                trackColor = MaterialTheme.colorScheme.surfaceVariant,
            )

            Spacer(Modifier.height(8.dp))

            Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = "${item.count} 笔充值",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = "占比 %.1f%%　›".format(ratio * 100),
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

// ------------------------------------------------------------------ 某人明细

/**
 * 某个成员的全部充值记录。
 *
 * 列表顺序直接用 [Repository.recordsOf] 给的（日期倒序）——
 * 也就是**最新的在最上面**，跟导出的 TXT / CSV 保持同一个顺序。
 *
 * 点任意一行进编辑 —— 编辑弹窗里同时带「删除」，删掉是移入回收站、之后能恢复。
 * 顶部搜索框按 [RecordSearch] 的规则过滤，但**不影响上面的累计小计**：
 * 小计始终是这个人的总账，搜索只收窄下面的列表。
 */
@Composable
private fun MemberDetailDialog(
    repo: Repository,
    member: String,
    dataVersion: Int,
    onDismiss: () -> Unit,
    onChanged: () -> Unit,
) {
    val list = remember(dataVersion, member) { repo.recordsOf(member) }
    val total = remember(dataVersion, member) { repo.totalOf(member) }
    val orderNo = total?.orderNo ?: 999
    val color = memberColor(orderNo)
    val grand = remember(dataVersion) { repo.grandTotal() }
    val maxHeight = (LocalConfiguration.current.screenHeightDp * 0.85f).dp

    var query by remember { mutableStateOf("") }
    var editing by remember { mutableStateOf<Record?>(null) }

    // 搜出来的子集。只有 list 或 query 变了才重算，不必每次重组都扫一遍
    val shown = remember(list, query) { RecordSearch.filter(list, query) }
    val searching = query.isNotBlank()

    // 期初和实际充值分开统计，跟统计页的口径对齐
    val initialRows = list.filter { it.initial }
    val realRows = list.filter { !it.initial }

    Dialog(onDismissRequest = onDismiss) {
        Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surface) {
            Column(
                Modifier
                    .padding(horizontal = 18.dp, vertical = 14.dp)
                    .heightIn(max = maxHeight),
            ) {
                // ---------------- 固定区（一）：标题
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(30.dp)
                            .background(color, CircleShape),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            text = orderNo.toString(),
                            color = Color.White,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = "$member 的充值记录",
                        modifier = Modifier.weight(1f),
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    TextButton(
                        onClick = onDismiss,
                        contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp),
                    ) { Text("关闭", fontSize = 13.sp) }
                }

                // ---------------- 固定区（二）：小计（不跟着滚）
                Spacer(Modifier.height(8.dp))
                Column(
                    Modifier
                        .fillMaxWidth()
                        .background(
                            MaterialTheme.colorScheme.primaryContainer,
                            RoundedCornerShape(12.dp),
                        )
                        .padding(horizontal = 12.dp, vertical = 9.dp),
                ) {
                    Row(verticalAlignment = Alignment.Bottom) {
                        Text(
                            text = money(total?.total ?: 0.0),
                            fontSize = 22.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onPrimaryContainer,
                        )
                        Spacer(Modifier.width(8.dp))
                        Text(
                            text = "累计充值" +
                                if (grand > 0) {
                                    "　占 %.1f%%".format((total?.total ?: 0.0) / grand * 100)
                                } else {
                                    ""
                                },
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onPrimaryContainer,
                            modifier = Modifier.padding(bottom = 3.dp),
                        )
                    }
                    Text(
                        text = "充值 ${realRows.size} 笔" +
                            if (initialRows.isNotEmpty()) "　·　期初 ${initialRows.size} 笔" else "",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                    )
                }

                // ---------------- 固定区（三）：搜索
                Spacer(Modifier.height(10.dp))
                SearchField(
                    value = query,
                    onValueChange = { query = it },
                    placeholder = "搜备注 / 方式 / 日期 / 金额",
                )

                // ---------------- 可滚动区：明细
                Spacer(Modifier.height(10.dp))
                when {
                    list.isEmpty() -> Text(
                        "还没有记录",
                        fontSize = 13.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(vertical = 20.dp),
                    )

                    // 搜崩了要明确说「是没匹配上」，不能跟「一条都没有」混为一谈
                    shown.isEmpty() -> Text(
                        "没有匹配「$query」的记录",
                        fontSize = 13.sp,
                        lineHeight = 19.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(vertical = 20.dp),
                    )

                    else -> Column(
                        Modifier.weight(1f, fill = false).verticalScroll(rememberScrollState())
                    ) {
                        Text(
                            // 搜索时把命中条数和金额合计说清楚，不然不知道筛掉了多少
                            text = if (searching) {
                                "命中 ${shown.size} 笔 · 合计 ${money(shown.sumOf { it.amount })}"
                            } else {
                                "从新到旧（最近的在最上面）"
                            },
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(bottom = 6.dp),
                        )
                        shown.forEach { r ->
                            DetailRow(r = r, color = color, onClick = { editing = r })
                            HorizontalDivider(
                                color = MaterialTheme.colorScheme.surfaceVariant,
                                thickness = 1.dp,
                            )
                        }
                    }
                }

                Spacer(Modifier.height(10.dp))
                Text(
                    text = if (searching) {
                        "点任意一条可以改金额、日期、备注，也能删掉（删了进回收站，可以恢复）。"
                    } else {
                        "点任意一条可以编辑或删除。这里只统计当前账本里的记录，回收站里的不算。"
                    },
                    fontSize = 11.sp,
                    lineHeight = 16.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }

    // 编辑 / 删除。保存或删除后 onChanged() 会让外层 dataVersion+1，
    // 于是上面那些 remember(dataVersion, ...) 重新查库 —— 列表和小计一起刷新。
    editing?.let { rec ->
        RecordEditorDialog(
            repo = repo,
            original = rec,
            onDismiss = { editing = null },
            onSaved = {
                editing = null
                onChanged()
            },
        )
    }
}

@Composable
private fun DetailRow(r: Record, color: Color, onClick: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            // clickable 放在 padding 前面，让整行的内边距也算点击区，手指更好点
            .clickable(onClick = onClick)
            .padding(vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = Dates.full(r.date),
                    fontSize = 14.sp,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Spacer(Modifier.width(6.dp))
                Text(
                    text = Dates.weekday(r.date),
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (r.initial) {
                    Spacer(Modifier.width(6.dp))
                    Text(
                        text = "期初",
                        fontSize = 10.sp,
                        color = MaterialTheme.colorScheme.onSecondaryContainer,
                        modifier = Modifier
                            .background(
                                MaterialTheme.colorScheme.secondaryContainer,
                                RoundedCornerShape(4.dp),
                            )
                            .padding(horizontal = 5.dp, vertical = 1.dp),
                    )
                }
            }
            Spacer(Modifier.height(2.dp))
            Text(
                text = r.method + if (r.note.isBlank()) "" else "　·　${r.note}",
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Spacer(Modifier.width(10.dp))
        Text(
            text = "+" + money2(r.amount),
            fontSize = 15.sp,
            fontWeight = FontWeight.SemiBold,
            color = color,
        )
        Spacer(Modifier.width(4.dp))
        Text(
            // 给个可点的暗示，不然用户不知道这行能按
            text = "›",
            fontSize = 16.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

