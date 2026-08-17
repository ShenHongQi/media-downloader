# Media Downloader

个人自用的流媒体链接解析下载工具。解析抖音、TikTok、Instagram、小红书、快手、B站的分享链接，获取无水印图片/视频资源。

## 支持平台

- 抖音
- TikTok
- Instagram
- 小红书
- 快手
- B站

## 本地开发

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

访问 http://localhost:8000/api/health 确认服务正常。

## Docker 部署

```bash
docker compose up -d
```

访问 http://localhost:8080
