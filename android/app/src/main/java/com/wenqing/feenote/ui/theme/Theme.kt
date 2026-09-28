package com.wenqing.feenote.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightScheme = lightColorScheme(
    primary = BrandBlue,
    onPrimary = Color.White,
    primaryContainer = BrandBlueSoft,
    onPrimaryContainer = Color(0xFF0A3A75),

    secondary = AccentViolet,
    onSecondary = Color.White,
    secondaryContainer = AccentVioletSoft,
    onSecondaryContainer = Color(0xFF2B2F7A),

    tertiary = AmountCoral,
    onTertiary = Color.White,
    tertiaryContainer = AmountCoralSoft,
    onTertiaryContainer = Color(0xFF7A2E10),

    background = BgLight,
    onBackground = TextLight,
    surface = SurfaceLight,
    onSurface = TextLight,
    surfaceVariant = ContainerLight,
    onSurfaceVariant = TextMutedLight,

    outline = OutlineLight,
    outlineVariant = Color(0xFFE6EEF7),

    error = Color(0xFFE5484D),
    onError = Color.White,
    errorContainer = Color(0xFFFFDAD8),
    onErrorContainer = Color(0xFF7A1215),
)

private val DarkScheme = darkColorScheme(
    primary = BrandBlueOnDark,
    onPrimary = Color(0xFF00305F),
    primaryContainer = Color(0xFF17457F),
    onPrimaryContainer = Color(0xFFD6E7FF),

    secondary = AccentVioletOnDark,
    onSecondary = Color(0xFF232877),
    secondaryContainer = Color(0xFF3A3F9E),
    onSecondaryContainer = Color(0xFFE2E3FF),

    tertiary = AmountCoralOnDark,
    onTertiary = Color(0xFF5E1F05),
    tertiaryContainer = Color(0xFF8A3A16),
    onTertiaryContainer = Color(0xFFFFDBCE),

    background = BgDark,
    onBackground = TextDark,
    surface = SurfaceDark,
    onSurface = TextDark,
    surfaceVariant = ContainerDark,
    onSurfaceVariant = TextMutedDark,

    outline = OutlineDark,
    outlineVariant = Color(0xFF2A3542),

    error = Color(0xFFFFB4AB),
    onError = Color(0xFF690005),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6),
)

@Composable
fun FeeNoteTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkScheme else LightScheme,
        content = content,
    )
}
