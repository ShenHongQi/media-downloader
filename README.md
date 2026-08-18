# Media Downloader

个人自用的流媒体链接解析下载工具。粘贴分享链接，获取无水印图片/视频资源。

## 支持平台

| 平台 | 支持类型 | 链接格式 |
|------|----------|----------|
| 抖音 | 视频、图文 | `v.douyin.com/xxx` 或 `douyin.com/video/xxx` |
| B站 | 视频 | `bilibili.com/video/BVxxx` 或 `b23.tv/xxx` |
| 小红书 | 图文、视频 | `xiaohongshu.com/explore/xxx` 或 `xhslink.com/xxx` |
| 快手 | 视频 | `v.kuaishou.com/xxx` 或 `kuaishou.com/short-video/xxx` |
| TikTok | 视频 | `vm.tiktok.com/xxx` 或 `tiktok.com/@user/video/xxx` |
| Instagram | 图片、视频、图集 | `instagram.com/p/xxx` 或 `instagram.com/reel/xxx` |

> TikTok 和 Instagram 需要能访问对应站点的网络环境。

---

## 快速开始

提供多种使用方式，选择最适合你的：

### 方式一：Windows 安装包（双击即用）

**完全独立，不需要安装 Python、Docker 或任何依赖。**

在 Windows 电脑上操作：

```powershell
# 1. 拉取代码（或解压 zip 包）
git clone https://github.com/ShenHongQi/media-downloader.git
cd media-downloader

# 2. 一键构建
packaging\windows\build.bat
```

构建完成后得到 `packaging/windows/dist/MediaDownloader.exe`，双击运行即可。

**前置条件：** Windows 10/11 + Python 3.12+（安装时勾选 "Add to PATH"）

### 方式二：Android APK（安装即用）

**内置解析引擎，无需连接服务器。**

在有 Android Studio 的电脑上构建：

```bash
cd packaging/android

# 1. 安装依赖
npm install

# 2. 初始化 Android 项目（首次）
npx cap add android

# 3. 同步代码
npx cap sync android

# 4. 构建 APK
cd android
./gradlew assembleDebug
```

APK 输出: `android/app/build/outputs/apk/debug/app-debug.apk`

发送到手机安装即可使用。

**前置条件：** Node.js 18+ / Android Studio / JDK 17

**Android App 支持两种模式：**
- **本地解析（默认）**：无需服务器，App 直接解析
- **远程服务器**：点右上角 ⚙ 切换，填入后端地址

### 方式三：Docker 部署（推荐服务器/NAS）

```bash
git clone https://github.com/ShenHongQi/media-downloader.git
cd media-downloader
docker compose up -d
```

访问 **http://localhost:8080**

停止服务：`docker compose down`

### 方式四：macOS / Linux 本地运行

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 启动 API
uvicorn app.main:app --reload --port 8000

# 另开终端，启动前端
cd frontend
python -m http.server 8080
```

访问 **http://localhost:8080**

### 方式五：Windows 本地运行（不打包）

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

另开终端：

```powershell
cd frontend
python -m http.server 8080
```

访问 **http://localhost:8080**

---

## 使用方法

### Web / 桌面端

1. 打开页面，在输入框粘贴分享链接（支持直接粘贴含链接的分享文本，自动提取 URL）
2. 点击 **解析**（或 `Ctrl+Enter` / `Cmd+Enter`）
3. 等待解析完成，页面展示封面预览、标题、作者
4. 点击 **下载** 保存无水印资源

支持一次粘贴多个链接（每行一个），批量解析。

### Android App

1. 从抖音/B站/小红书等 App 复制分享链接
2. 打开 Media Downloader，粘贴链接
3. 点击「解析」
4. 点击「下载」保存

### API 直接调用

```bash
# 单个链接
curl "http://localhost:8000/api/parse?url=https://v.douyin.com/xxx/"

# 批量解析
curl -X POST http://localhost:8000/api/parse \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://v.douyin.com/xxx/", "https://www.bilibili.com/video/BVxxx"]}'

# 代理下载
curl -o video.mp4 "http://localhost:8000/api/download?url=<资源URL>&platform=douyin&filename=video.mp4"

# 查看支持的平台
curl http://localhost:8000/api/platforms
```

---

## 项目结构

```
media-downloader/
├── backend/                  # Python 后端（FastAPI）
│   ├── app/
│   │   ├── main.py           # 入口
│   │   ├── models.py         # 数据模型
│   │   ├── api/              # API 路由（解析 + 下载代理）
│   │   ├── parsers/          # 各平台解析器（插件式）
│   │   └── utils/            # HTTP 客户端、短链解析
│   └── requirements.txt
├── frontend/                  # Web 前端（原生 HTML/CSS/JS）
├── packaging/
│   ├── windows/              # Windows exe 打包
│   │   ├── build.bat         # 一键构建脚本
│   │   ├── build.spec        # PyInstaller 配置
│   │   └── app_entry.py      # 桌面入口（pywebview）
│   └── android/              # Android APK 打包
│       ├── www/              # 前端 + JS 解析器
│       │   ├── parsers.js    # 6 平台解析器（JS 版）
│       │   └── ...
│       ├── capacitor.config.json
│       └── package.json
├── nginx/                     # Nginx 配置（Docker 用）
├── Dockerfile
└── docker-compose.yml
```

## 添加新平台

**后端（Python）：**

在 `backend/app/parsers/` 下新建 `.py` 文件，继承 `BaseParser`：

```python
import re
from app.models import MediaItem, MediaResult, MediaType, Platform
from app.parsers.base import BaseParser

class XxxParser(BaseParser):
    platform_name = "xxx"
    url_patterns = [re.compile(r"xxx\.com/video/(\w+)")]

    async def parse(self, url: str) -> MediaResult:
        # 实现解析逻辑
        ...
```

重启服务自动注册，无需其他配置。

**Android（JavaScript）：**

在 `packaging/android/www/parsers.js` 中添加新的 Parser 类，并在 `ParserRegistry` 构造函数中注册。

## 配置

通过环境变量或 `.env` 文件配置（后端）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HTTP_TIMEOUT` | 30 | HTTP 请求超时秒数 |
| `DOWNLOAD_PROXY` | 空 | 代理地址（用于 TikTok/Instagram） |
| `REDIS_URL` | 空 | Redis 地址（可选缓存） |
| `CACHE_TTL` | 3600 | 缓存过期时间（秒） |

## 注意事项

- 本工具仅供个人学习研究使用
- 各平台接口可能随时变动，如解析失败请更新解析逻辑
- TikTok/Instagram 需要可访问对应站点的网络环境
- B站高清视频为 DASH 格式（音视频分离），当前返回合并后的 MP4 流
