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

## 快速开始

### Docker 部署（推荐，全平台通用）

前提：安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)

```bash
git clone https://github.com/ShenHongQi/media-downloader.git
cd media-downloader
docker compose up -d
```

访问 **http://localhost:8080**

停止服务：`docker compose down`

### macOS / Linux 本地运行

```bash
# 1. 安装依赖
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 启动 API 服务
uvicorn app.main:app --reload --port 8000

# 3. 启动前端（另开终端）
cd frontend
python -m http.server 8080
```

打开浏览器访问 **http://localhost:8080**

### Windows 本地运行

前提：安装 [Python 3.12+](https://www.python.org/downloads/)（安装时勾选 "Add to PATH"）

```powershell
# 拉取代码
git clone https://github.com/ShenHongQi/media-downloader.git
cd media-downloader\backend

# 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 启动 API
uvicorn app.main:app --port 8000
```

另开一个终端启动前端：

```powershell
cd media-downloader\frontend
python -m http.server 8080
```

打开浏览器访问 **http://localhost:8080**

## 使用方法

### Web 界面

1. 打开浏览器访问前端页面
2. 在输入框粘贴分享链接（支持直接粘贴含链接的分享文本，会自动提取 URL）
3. 点击 **解析** 按钮（或按 `Ctrl+Enter` / `Cmd+Enter`）
4. 等待解析完成，页面会展示：
   - 平台标识
   - 标题和作者
   - 封面/图片预览
   - 下载按钮
5. 点击 **下载** 按钮即可保存无水印资源

支持一次粘贴多个链接（每行一个），批量解析。

### API 直接调用

**解析链接：**

```bash
# 单个链接
curl "http://localhost:8000/api/parse?url=https://v.douyin.com/xxx/"

# 批量解析
curl -X POST http://localhost:8000/api/parse \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://v.douyin.com/xxx/", "https://www.bilibili.com/video/BVxxx"]}'
```

**下载资源（通过代理中转）：**

```bash
curl -o video.mp4 "http://localhost:8000/api/download?url=<资源URL>&platform=douyin&filename=video.mp4"
```

**查看支持的平台：**

```bash
curl http://localhost:8000/api/platforms
```

### iOS 快捷指令（可选）

可创建 iOS 快捷指令实现"分享到快捷指令直接下载"：

1. 新建快捷指令
2. 添加"获取URL内容"操作，方法 POST，URL 填 `http://<你的服务器IP>:8000/api/parse`
3. Body 为 JSON: `{"urls": ["<快捷指令输入>"]}`
4. 解析返回的 JSON，提取 `items[0].url`
5. 下载该 URL 并保存到相册

## 项目结构

```
media-downloader/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py         # 配置
│   │   ├── models.py         # 数据模型
│   │   ├── api/              # API 路由
│   │   │   ├── parse.py      # 解析接口
│   │   │   └── download.py   # 下载代理
│   │   ├── parsers/          # 各平台解析器（插件式）
│   │   │   ├── base.py       # 基类
│   │   │   ├── registry.py   # 自动注册
│   │   │   ├── douyin.py
│   │   │   ├── bilibili.py
│   │   │   ├── xiaohongshu.py
│   │   │   ├── kuaishou.py
│   │   │   ├── tiktok.py
│   │   │   └── instagram.py
│   │   └── utils/            # 工具函数
│   └── requirements.txt
├── frontend/                  # 前端静态页面
├── nginx/                     # Nginx 配置
├── Dockerfile
└── docker-compose.yml
```

## 添加新平台

1. 在 `backend/app/parsers/` 下新建 `xxx.py`
2. 继承 `BaseParser`，实现 `platform_name`、`url_patterns` 和 `parse()` 方法
3. 在 `models.py` 的 `Platform` 枚举中添加新平台
4. 重启服务，新解析器会被自动注册

```python
# backend/app/parsers/xxx.py
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

## 配置

通过环境变量或 `.env` 文件配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HTTP_TIMEOUT` | 30 | HTTP 请求超时秒数 |
| `DOWNLOAD_PROXY` | 空 | 代理地址（用于 TikTok/Instagram） |
| `REDIS_URL` | 空 | Redis 地址（可选，用于缓存） |
| `CACHE_TTL` | 3600 | 缓存过期时间（秒） |

## 注意事项

- 本工具仅供个人学习研究使用
- 各平台接口可能随时变动，如解析失败请提 issue 或自行更新解析逻辑
- TikTok/Instagram 需要能访问对应站点的网络环境（可通过 `DOWNLOAD_PROXY` 配置代理）
- B站高清视频可能为 DASH 格式（音视频分离），当前返回的是合并后的低画质 MP4 流
