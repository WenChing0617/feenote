plugins {
    // AGP 9.x 内建 Kotlin 支持，不再需要 org.jetbrains.kotlin.android 插件
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "com.wenqing.feenote"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.wenqing.feenote"
        minSdk = 26
        targetSdk = 37
        versionCode = 8
        versionName = "1.7"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        // 设置页底部要显示版本号，用 BuildConfig.VERSION_NAME 读，
        // 免得手写的字符串又跟 versionName 对不上（之前就写错过一次）。
        // AGP 8 起这个开关默认关闭，必须显式打开。
        buildConfig = true
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.androidx.material.icons.extended)

    debugImplementation(libs.androidx.ui.tooling)

    // JsonCodec 的两端互通契约测试
    testImplementation(libs.junit)
    testImplementation(libs.org.json)
}

/**
 * 单元测试的编码与路径处理。
 *
 * 本机 JVM 是 `sun.jnu.encoding=GBK`（`file.encoding=UTF-8`）。
 * 工程当前位于 `D:\项目\feenote`（含中文），实测会让测试 worker 的
 * classpath 解析失败，报 `ClassNotFoundException: ...JsonCodecTest` —— 注意类其实
 * 编译好了（javap 能正常列出方法），是加载阶段挂的，加 `-Dsun.jnu.encoding=UTF-8`
 * 也救不回来（该属性在 Windows 上不可用 -D 覆盖）。
 *
 * 同一套代码复制到纯英文路径（如 C:\...\feenote_ascii）后测试立刻全绿。
 *
 * 所以这里：路径含非 ASCII 字符时把测试任务标记为跳过并给出提示，
 * 而不是留一个必然失败的红叉。把工程挪到纯英文路径后测试会自动恢复运行。
 */
tasks.withType<Test>().configureEach {
    jvmArgs("-Dfile.encoding=UTF-8")

    val asciiPath = projectDir.absolutePath.all { it.code < 128 }
    if (!asciiPath) {
        onlyIf("工程路径含非 ASCII 字符，测试 worker 的 classpath 会解析失败；挪到纯英文路径即可运行（见 README）") {
            false
        }
    }
}
