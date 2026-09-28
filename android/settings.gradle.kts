// 仓库说明：
//   repo1.maven.org / repo.maven.apache.org（Maven Central 官方源）在部分网络环境下不可达，
//   GitHub 直链还会撞上证书链问题。这里改用国内镜像作为主源，
//   官方源保留在最后作为兜底，换到网络通畅的环境也能直接用。
//   经实测可用：maven.aliyun.com、mirrors.cloud.tencent.com

pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        // Maven Central 镜像（Kotlin 编译器、Compose 插件等在此）
        maven {
            url = uri("https://maven.aliyun.com/repository/public")
        }
        maven {
            url = uri("https://mirrors.cloud.tencent.com/nexus/repository/maven-public/")
        }
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        // AndroidX / Google 系构件：dl.google.com 实测可达
        google()
        maven {
            url = uri("https://maven.aliyun.com/repository/google")
        }
        // Maven Central 镜像
        maven {
            url = uri("https://maven.aliyun.com/repository/public")
        }
        maven {
            url = uri("https://mirrors.cloud.tencent.com/nexus/repository/maven-public/")
        }
        // 官方源兜底
        mavenCentral()
    }
}

rootProject.name = "FeeNote"
include(":app")
