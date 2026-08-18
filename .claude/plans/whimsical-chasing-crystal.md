# 修复 Android 下载：自建原生下载器替代 @capacitor-community/media

## Context

当前 Android APK 下载功能持续失败，报两个错：
1. "Missing the following permissions in AndroidManifest.xml: READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE"
2. "Input file path is required"

根因：`@capacitor-community/media` 插件问题多——
- 权限流走 `requestAllPermissions`，依赖 Capacitor 对 `@Permission` 注解的 manifest 校验，版本/API 敏感（API 29/33 走不同 alias），极易失败
- `_saveMedia` 硬性要求 `albumIdentifier`（须先 `getAlbums()`）
- 即便走通也脆弱、依赖运行时权限授予

**目标：** 用自建原生 Capacitor 插件直接通过 Android `MediaStore` 写入相册，API 29+ 完全无需运行时权限，最稳定可靠；同时让 B站视频（需 Referer）也能下载。

## 方案

### 1. 新建原生插件 `DownloaderPlugin.java`

路径：`packaging/android/android/app/src/main/java/com/shq/mediadownloader/DownloaderPlugin.java`

接受参数：`{ url, filename, isVideo, referer }`，用 OkHttp 下载（可带 Referer 头解决 B站 403），然后：
- **API 29+ (Android 10+)**：用 `MediaStore.Images/Video.Media` + `RELATIVE_PATH` 插入到 `Pictures/MediaDownloader` 或 `Movies/MediaDownloader`，**无需任何权限**
- **API < 29**：写到 `Environment.getExternalStoragePublicDirectory(...)`（manifest 已声明 WRITE_EXTERNAL_STORAGE）

返回成功/失败。OkHttp 已通过 Capacitor 核心依赖可用。

### 2. 注册插件到 `MainActivity.java`

```java
package com.shq.mediadownloader;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(DownloaderPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
```

### 3. 改写 `packaging/android/www/app.js` 下载逻辑

- `downloadMedia(url, filename, isVideo, platform, btn)`：直接调 `window.Capacitor.Plugins.Downloader.save({url, filename, isVideo, referer})`，**不再 fetch blob/base64**（省内存，大视频也 OK）
- 平台 → Referer 映射：
  - douyin → https://www.douyin.com/
  - bilibili → https://www.bilibili.com/
  - xiaohongshu → https://www.xiaohongshu.com/
  - kuaishou → https://v.kuaishou.com/
  - tiktok → https://www.tiktok.com/
  - instagram → https://www.instagram.com/
- `downloadAll`：循环调 `Downloader.save`
- 保留 @capacitor/app 的返回键逻辑、lightbox

### 4. 清理依赖（可选）

- 卸载 `@capacitor-community/media`（不再使用）
- 卸载 `@capacitor/filesystem`（不再使用，下载在原生层完成）
- `npx cap sync android` 刷新

保留 `@capacitor/app`（返回键需要）。

## 涉及文件

- 新增：`packaging/android/android/app/src/main/java/com/shq/mediadownloader/DownloaderPlugin.java`
- 修改：`packaging/android/android/app/src/main/java/com/shq/mediadownloader/MainActivity.java`
- 修改：`packaging/android/www/app.js`
- 可选：`packaging/android/package.json`（移除 media/filesystem）

## 验证

1. `npx cap sync android && cd android && ./gradlew assembleDebug` 构建成功
2. 安装新 APK
3. 抖音图文：点单张下载 → 看相册 `Pictures/MediaDownloader` 出现图片；点"全部下载" → 全部入相册
4. B站视频：下载 → `Movies/MediaDownloader` 出现视频（Referer 头解决 403）
5. 不再有权限弹窗（API 29+）和报错
