package com.wenqing.feenote.ui.theme

import androidx.compose.ui.graphics.Color

// ------------------------------------------------------------------ 品牌色
// 清新通透的「清透天蓝」系。刻意避开绿色 —— 上一版是 #2E7D32 的深绿，
// 又沉又"土"，整个界面被那一片绿压住了。
val BrandBlue = Color(0xFF3A87F0)        // 主色：清透天蓝
val BrandBlueDeep = Color(0xFF2B6FD1)    // 按下态 / 需要更实的地方
val BrandBlueSoft = Color(0xFFDEEBFF)    // 极淡的蓝，用来托底

// 次色：淡紫蓝。给成员标签、图表副色用，和主色是邻居色相，搭起来很干净
val AccentViolet = Color(0xFF8B93F8)
val AccentVioletSoft = Color(0xFFE7E9FF)

// 强调色：珊瑚橘，专用于金额，一眼能从蓝色里跳出来
val AmountCoral = Color(0xFFFF8A5B)
val AmountCoralSoft = Color(0xFFFFE7DC)

// ------------------------------------------------------------------ 浅色主题
// 做法：底色用冷白、卡片纯白，层次靠「极淡的蓝」和发丝描边去分，
// 而不是靠重投影 —— 这样才通透，不会糊成一团灰。
val BgLight = Color(0xFFF6F9FD)
val SurfaceLight = Color(0xFFFFFFFF)
val ContainerLight = Color(0xFFEDF4FC)
val TextLight = Color(0xFF1B2733)
val TextMutedLight = Color(0xFF6B7C8C)
val OutlineLight = Color(0xFFD7E3F0)

// ------------------------------------------------------------------ 深色主题
val BrandBlueOnDark = Color(0xFF9CC7FF)
val AccentVioletOnDark = Color(0xFFB6BCFF)
val AmountCoralOnDark = Color(0xFFFFB59A)
val BgDark = Color(0xFF0E141B)
val SurfaceDark = Color(0xFF151C25)
val ContainerDark = Color(0xFF1E2733)
val TextDark = Color(0xFFE6EDF5)
val TextMutedDark = Color(0xFF9AABBD)
val OutlineDark = Color(0xFF3A4756)

/** 成员头像配色：按固定编号 1~5 取色，超出后循环。
 *  刻意选低饱和的清新色，配白字不刺眼。 */
private val MemberPalette = listOf(
    Color(0xFF3A87F0),   // 天蓝
    Color(0xFF8B7CF0),   // 淡紫
    Color(0xFFF2994A),   // 琥珀
    Color(0xFFEC6B8A),   // 玫粉
    Color(0xFF35B6C9),   // 湖青
    Color(0xFF7A8CA8),   // 灰蓝
)

fun memberColor(orderNo: Int): Color {
    val size = MemberPalette.size
    val index = ((orderNo - 1) % size + size) % size
    return MemberPalette[index]
}
