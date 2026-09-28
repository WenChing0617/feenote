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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.wenqing.feenote.data.Record
import com.wenqing.feenote.data.Repository
import com.wenqing.feenote.ui.theme.memberColor
import com.wenqing.feenote.util.Dates
import com.wenqing.feenote.util.money
import com.wenqing.feenote.util.money2

/** 明细页：顶部总览 + 按日期分组的充值记录 */
@Composable
fun RecordListScreen(
    repo: Repository,
    dataVersion: Int,
    onChanged: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val records = remember(dataVersion) { repo.records() }
    val room = remember(dataVersion) { repo.room() }
    val total = remember(dataVersion) { repo.grandTotal() }
    val count = remember(dataVersion) { repo.realCount() }
    val members = remember(dataVersion) { repo.members() }
    val firstDate = remember(dataVersion) { repo.firstDate() }
    val lastDate = remember(dataVersion) { repo.lastDate() }
    val orderMap = remember(members) { members.associate { it.name to it.orderNo } }

    var showEditor by remember { mutableStateOf(false) }
    var editing by remember { mutableStateOf<Record?>(null) }
    var showOnboarding by remember { mutableStateOf(false) }

    val groups = remember(records) { records.groupBy { it.date } }

    Box(modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize()) {

            SummaryHeader(
                room = room,
                total = total,
                count = count,
                rangeText = if (firstDate.isEmpty()) "还没有记录"
                else "${Dates.friendly(firstDate)} ~ ${Dates.friendly(lastDate)}",
            )

            if (records.isEmpty()) {
                EmptyState(
                    hasMembers = members.isNotEmpty(),
                    onSetup = { showOnboarding = true },
                )
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(bottom = 96.dp),
                ) {
                    groups.forEach { (date, dayRecords) ->
                        item(key = "day_$date") {
                            DayHeader(date, dayRecords.sumOf { it.amount })
                        }
                        items(dayRecords, key = { it.id }) { record ->
                            RecordRow(
                                record = record,
                                color = memberColor(orderMap[record.member] ?: 0),
                                onClick = {
                                    editing = record
                                    showEditor = true
                                },
                            )
                        }
                    }
                }
            }
        }

        FloatingActionButton(
            onClick = {
                // 一个人都还没加就先引导去加人，否则记账时会选不出「谁充的」
                if (members.isEmpty()) {
                    showOnboarding = true
                } else {
                    editing = null
                    showEditor = true
                }
            },
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(20.dp),
        ) {
            Icon(Icons.Filled.Add, contentDescription = "记一笔")
        }
    }

    if (showEditor) {
        RecordEditorDialog(
            repo = repo,
            original = editing,
            onDismiss = { showEditor = false },
            onSaved = {
                showEditor = false
                onChanged()
            },
        )
    }

    if (showOnboarding) {
        OnboardingDialog(
            repo = repo,
            firstRun = false,
            onDismiss = { showOnboarding = false; onChanged() },
            onDone = {
                showOnboarding = false
                onChanged()
            },
        )
    }
}

/** 明细为空时的占位。没成员的话顺手给个入口，别让用户自己去设置里找 */
@Composable
private fun EmptyState(hasMembers: Boolean, onSetup: () -> Unit) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = if (hasMembers) {
                    "还没有记录\n点右下角 + 记第一笔"
                } else {
                    "还没有成员\n先加一下室友，才能记账"
                },
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                lineHeight = 26.sp,
            )
            if (!hasMembers) {
                Spacer(Modifier.height(16.dp))
                androidx.compose.material3.OutlinedButton(onClick = onSetup) {
                    Text("去添加成员")
                }
            }
        }
    }
}

@Composable
private fun SummaryHeader(
    room: String,
    total: Double,
    count: Int,
    rangeText: String,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.primary)
            .padding(horizontal = 20.dp, vertical = 18.dp),
    ) {
        Text(
            // 「302」补一个「室」，用户自己写了「B栋302室」就不重复加
            text = when {
                room.isBlank() -> "电费记账"
                room.endsWith("室") -> "$room · 电费记账"
                else -> "$room 室 · 电费记账"
            },
            color = MaterialTheme.colorScheme.onPrimary,
            fontSize = 16.sp,
            fontWeight = FontWeight.Medium,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            text = money2(total),
            color = MaterialTheme.colorScheme.onPrimary,
            fontSize = 36.sp,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.height(6.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = "共 $count 笔充值",
                color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.85f),
                fontSize = 13.sp,
            )
            Spacer(Modifier.width(14.dp))
            Text(
                text = rangeText,
                color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.85f),
                fontSize = 13.sp,
            )
        }
    }
}

@Composable
private fun DayHeader(date: String, amount: Double) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 20.dp, end = 20.dp, top = 18.dp, bottom = 6.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = "${Dates.friendly(date)} ${Dates.weekday(date)}",
            fontSize = 14.sp,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = "合计 ${money(amount)}",
            fontSize = 13.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun RecordRow(
    record: Record,
    color: Color,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 14.dp, vertical = 4.dp)
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // 成员色块
            Box(
                modifier = Modifier
                    .size(38.dp)
                    .background(color, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = record.member.take(1),
                    color = Color.White,
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Bold,
                )
            }

            Spacer(Modifier.width(12.dp))

            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = record.member,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Medium,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    if (record.initial) {
                        Spacer(Modifier.width(6.dp))
                        TagPill(text = "期初")
                    }
                }
                Spacer(Modifier.height(2.dp))
                val sub = if (record.note.isNotBlank()) {
                    "${record.method} · ${record.note}"
                } else {
                    record.method
                }
                Text(
                    text = sub,
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                )
            }

            Text(
                text = "+${money(record.amount)}",
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.tertiary,
            )
        }
    }
}

@Composable
private fun TagPill(text: String) {
    Box(
        modifier = Modifier
            .background(
                MaterialTheme.colorScheme.primaryContainer,
                RoundedCornerShape(6.dp),
            )
            .padding(horizontal = 6.dp, vertical = 1.dp),
    ) {
        Text(
            text = text,
            fontSize = 10.sp,
            color = MaterialTheme.colorScheme.onPrimaryContainer,
        )
    }
}
