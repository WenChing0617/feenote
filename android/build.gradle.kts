// 顶层构建文件：只声明插件，不在这里配置具体模块
plugins {
    // AGP 9.x 内建 Kotlin 支持，不再需要 org.jetbrains.kotlin.android 插件
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.compose) apply false
}
