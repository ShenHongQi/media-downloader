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

# 4. 打开 Android Studio 构建 APK
npx cap open android
```

在 Android Studio 中：
- 菜单 **Build → Build Bundle(s) / APK(s) → Build APK(s)**
- APK 输出路径: `android/app/build/outputs/apk/debug/app-debug.apk`

## 或者命令行构建（不开 Android Studio）

```bash
cd android
./gradlew assembleDebug
```

APK 位置: `android/app/build/outputs/apk/debug/app-debug.apk`

## 使用说明

1. 将 APK 发送到手机，安装
2. 首次打开会弹出设置页面，输入你的后端服务器地址，如：
   - `http://192.168.1.100:8000`（局域网内）
   - `http://你的云主机IP:8000`（公网）
3. 保存后，粘贴分享链接即可解析和下载

## 注意事项

- App 本身只是前端界面，需要配合后端服务使用
- 后端可以部署在：
  - 同一局域网的电脑上（Docker 或直接运行）
  - 你的云主机上（172.29.5.110）
- Android 9+ 默认禁止 HTTP 明文请求，已在 capacitor.config.json 中开启 cleartext
