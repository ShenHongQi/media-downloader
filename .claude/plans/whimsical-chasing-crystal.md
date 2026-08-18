# Flutter 跨平台打包方案（Windows + Android）

## Context

已有一个 Python FastAPI 后端 + H5 前端的 media-downloader 工具，用户希望打包成独立安装包：
- Windows: .exe 安装包，双击即用
- Android: .apk 安装包，下载安装即可使用
- 两端均需支持：独立使用（内置解析）+ 连接远程服务器

## 方案：Flutter 统一开发

使用 Flutter 构建一个跨平台客户端，目标平台 Windows + Android。解析逻辑从 Python 移植到 Dart（HTTP 请求 + 正则 + JSON 解析，逻辑相同，语言不同）。

### 为什么选 Flutter 而不是其他方案

| 方案 | Windows | Android | 开发量 | 体验 |
|------|---------|---------|--------|------|
| Flutter（推荐） | ✅ 原生窗口 | ✅ 原生 APK | 一套代码 | 原生流畅 |
| PyInstaller + WebView | ✅ | ❌ 需另做 | 两套 | Windows 好，Android 无 |
| Electron + Capacitor | ✅ | ✅ | 包大(200MB+) | 重，吃内存 |
| React Native | ❌ 不支持 Win | ✅ | 只能 Android | 覆盖不全 |

## 项目结构

```
media-downloader/
├── backend/              # 保留，用于服务器部署
├── frontend/             # 保留，Web 版
├── flutter_app/          # 新增 Flutter 项目
│   ├── lib/
│   │   ├── main.dart
│   │   ├── models/
│   │   │   └── media_result.dart      # 数据模型（对应 Python models.py）
│   │   ├── parsers/
│   │   │   ├── base_parser.dart       # 解析器基类
│   │   │   ├── parser_registry.dart   # 注册表
│   │   │   ├── douyin_parser.dart     # 抖音
│   │   │   ├── bilibili_parser.dart   # B站
│   │   │   ├── xiaohongshu_parser.dart
│   │   │   ├── kuaishou_parser.dart
│   │   │   ├── tiktok_parser.dart
│   │   │   └── instagram_parser.dart
│   │   ├── services/
│   │   │   ├── parse_service.dart     # 解析调度（本地/远程）
│   │   │   └── download_service.dart  # 下载+保存
│   │   ├── pages/
│   │   │   ├── home_page.dart         # 主页（输入+结果）
│   │   │   └── settings_page.dart     # 设置（服务器地址等）
│   │   └── widgets/
│   │       ├── media_card.dart        # 结果卡片
│   │       └── platform_badge.dart
│   ├── android/
│   ├── windows/
│   └── pubspec.yaml
```

## 核心逻辑移植（Python → Dart）

解析逻辑本质是：
1. 正则匹配 URL → 识别平台
2. HTTP GET/POST 获取数据（重定向跟踪、Cookie 管理）
3. 正则/JSON 提取媒体资源 URL

Dart 完全能胜任（`http`/`dio` 包 + `RegExp` + `dart:convert`）。

### 移植对照

| Python | Dart |
|--------|------|
| `httpx.AsyncClient` | `dio` 包 |
| `re.search()` | `RegExp().firstMatch()` |
| `json.loads()` | `jsonDecode()` |
| `follow_redirects=False` | `dio.options.followRedirects = false` |

## 功能设计

### 双模式工作
- **本地模式（默认）**：解析逻辑内置在 App 中，无需服务器
- **远程模式**：连接用户部署的后端 API（设置页面配置服务器地址）

### 下载功能
- Windows：保存到"下载"文件夹，可自选路径
- Android：保存到相册/下载目录，请求存储权限

### UI 设计
- Material 3 风格
- 暗色主题为主（与 Web 版一致）
- 首页：输入框 + 解析按钮 + 结果列表
- 支持从其他 App 分享链接到本应用（Android Share Intent）

## 构建产物

- **Windows**: `flutter build windows` → 生成 exe + dll 目录，用 Inno Setup 打包为安装包
- **Android**: `flutter build apk` → 生成 .apk 文件，直接安装

## 实施顺序

1. 初始化 Flutter 项目，配置 Windows + Android 目标
2. 实现数据模型（MediaResult 等）
3. 移植解析器（先抖音 + B站，验证可行性）
4. 实现 UI（主页、结果卡片、设置页）
5. 实现下载功能（平台差异化处理）
6. 移植剩余解析器
7. 构建 Windows exe + Android apk
8. 测试

## 前置条件

需要在 Mac 上安装：
- Flutter SDK
- Android SDK（Android Studio）
- 注意：Mac 上无法直接构建 Windows exe（需要在 Windows 上构建），但可以构建 Android APK

## 验证方式

- `flutter run -d windows`（如在 Windows 上）或 `flutter run -d android` 测试
- Mac 上可以用 `flutter run -d macos` 验证逻辑，再到 Windows 上打最终包
- 用真实抖音/B站链接测试解析+下载
