package com.wenqing.feenote.ui

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * 搜索输入框：明细页和统计页的个人明细弹窗共用。
 *
 * 单独抽出来是为了两处的尺寸、图标、清空按钮、提示语保持一致 ——
 * 同一个控件抄两遍，改一处忘一处是迟早的事。
 *
 * 高度压到 52dp：Material3 的 `OutlinedTextField` 默认要 56dp 以上，
 * 塞进弹窗后会明显挤到下面的列表（弹窗高度只有屏高的 85%）。
 */
@Composable
internal fun SearchField(
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String,
    modifier: Modifier = Modifier,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = modifier
            .fillMaxWidth()
            .height(52.dp),
        singleLine = true,
        textStyle = MaterialTheme.typography.bodyMedium,
        placeholder = { Text(placeholder, fontSize = 13.sp) },
        leadingIcon = {
            Icon(
                Icons.Filled.Search,
                contentDescription = null,
                modifier = Modifier.size(18.dp),
            )
        },
        trailingIcon = {
            // 没输入时不显示清空按钮 —— 空框旁边挂个叉会让人以为有内容
            if (value.isNotEmpty()) {
                IconButton(onClick = { onValueChange("") }) {
                    Icon(
                        Icons.Filled.Close,
                        contentDescription = "清空搜索",
                        modifier = Modifier.size(18.dp),
                    )
                }
            }
        },
        shape = RoundedCornerShape(10.dp),
    )
}
