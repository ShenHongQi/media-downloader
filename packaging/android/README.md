# Android APK 打包说明

## 前置条件

- Node.js 18+
- Android Studio（提供 Android SDK）
- JDK 17

## 构建步骤

```bash
cd packaging/android

# 1. 安装依赖
npm install

# 2. 初始化 Android 项目（首次）
npx cap add android

# 3. 同步前端代码到 Android 项目
npx cap sync android

# 4. 命令行构建 APK
cd android
./gradlew assembleDebug
```

APK 位置: `android/app/build/outputs/apk/debug/app-debug.apk`

或者用 Android Studio 构建：
```bash
npx cap open android
# 菜单 Build → Build APK(s)
```

## 使用说明

安装 APK 后直接打开即可使用，**无需服务器**。

### 两种模式

- **本地解析（默认）**：App 内置解析逻辑，直接在手机上完成解析，无需任何服务器
- **远程服务器**：点击右上角 ⚙ 切换为远程模式，输入后端服务器地址

### 操作步骤

1. 从抖音/B站/小红书等 App 复制分享链接
2. 打开 Media Downloader，粘贴链接
3. 点击「解析」
4. 点击「下载」保存无水印资源

## 支持平台

- 抖音（视频、图文）
- B站（视频）
- 小红书（图文、视频）
- 快手（视频）
- TikTok（需要可访问 TikTok 的网络）
- Instagram（需要可访问 Instagram 的网络）
