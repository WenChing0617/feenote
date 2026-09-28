package com.wenqing.feenote.ui

import androidx.compose.foundation.background
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
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.wenqing.feenote.data.MemberTotal
import com.wenqing.feenote.data.Repository
import com.wenqing.feenote.ui.theme.memberColor
import com.wenqing.feenote.util.money
import com.wenqing.feenote.util.money2

/** 统计页：总账 + 每人累计（带占比进度条） */
@Composable
fun StatsScreen(
    repo: Repository,
    dataVersion: Int,
    modifier: Modifier = Modifier,
) {
    val totals = remember(dataVersion) { repo.totals() }
    val grand = remember(dataVersion) { repo.grandTotal() }
    val room = remember(dataVersion) { repo.room() }
    val records = remember(dataVersion) { repo.records() }
    val initialCount = remember(records) { records.count { it.initial } }
    val realCount = remember(records) { records.count { !it.initial } }

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
            MemberStatCard(item = item, grand = grand)
        }

        item {
            Text(
                text = "说明：期初首笔（开学第一次充值）计入总金额，但不计入充值笔数。",
                fontSize = 12.sp,
                lineHeight = 18.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 18.dp),
            )
        }
    }
}

@Composable
private fun MemberStatCard(item: MemberTotal, grand: Double) {
    val ratio = if (grand > 0) (item.total / grand).toFloat() else 0f
    val color = memberColor(item.orderNo)

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 14.dp, vertical = 5.dp),
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
                    text = "占比 %.1f%%".format(ratio * 100),
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
