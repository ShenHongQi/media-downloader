# 小红书：多数据源解析 + 诊断

## Context

小红书报 `无法获取笔记内容 (noteDetailMap keys=)`：带 token 的 pageUrl 请求回来的页面，`__INITIAL_STATE__.note.noteDetailMap` 是空对象，raw JSON 里也没有 `masterUrl`/`urlDefault`。说明小红书 web 现在是 CSR 为主，note 详情靠 JS 异步从签名 API 加载，SSR 不注入媒体数据。

我无法在 Mac 上真机测试（公司网络拦截 xhslink），需要一次覆盖尽可能多的数据源，失败时带诊断信息方便定位。不影响抖音/B站（只改 `XiaohongshuParser.parse`）。

## 方案（`packaging/android/www/parsers.js` 的 `XiaohongshuParser.parse`）

拿到 HTML 后，按优先级尝试多数据源，第一个成功即返回：

### 数据源 1：`__INITIAL_STATE__` 结构化（现有）
`noteDetailMap` → `note` → imageList/video。保留。

### 数据源 2：`__INITIAL_STATE__` raw 正则（现有）
`"masterUrl"`, `"urlDefault"`, `"title"`, `"nickname"`。保留。

### 数据源 3：og / meta 标签
从 HTML head 提取：
- `og:image` → 图片（封面，图集可能只首张）
- `og:video` / `og:video:url` / `og:video:secure_url` → 视频直链
- `og:title` → 标题
- `og:description` → 描述
- 用正则 `<meta[^>]+(?:property|name)=["']og:(\w+)["'][^>]*content=["']([^"']+)["']`，以及 video 专门的 `<meta[^>]+property=["']og:video[^"']*["'][^>]*content=["']([^"']+)["']`

### 数据源 4：全 HTML 小红书 CDN 媒体正则
在**整个 HTML**（不限于 `__INITIAL_STATE__`）里找小红书 CDN 媒体直链：
- 图片：`https?://(?:sns-img[^.]*\.xhscdn\.com|ci\.xiaohongshu\.com|sns-webpic[^.]*\.xhscdn\.com)/[^\s"'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"'<>]*)?`，去重
- 视频：`https?://[^\s"'<>]+\.mp4[^\s"'<>]*`，过滤含 xhscdn 或 xiaohongshu 的

若数据源 1-4 都拿不到媒体，抛出带诊断的错误：
```
无法获取笔记内容 (pageUrl=..., htmlLen=..., hasState=true/false, hasOgImage=true/false, ogVideo=...)
```

这样：
- 若 SSR 注入了数据 → 数据源 1/2 命中
- 若有 og 标签 → 数据源 3 命中（至少封面图 + 标题）
- 若页面 HTML 直接含 CDN 链接 → 数据源 4 命中
- 都失败 → 诊断信息让我精准定位（很可能需要走签名 API，到时据诊断决定）

## 涉及文件

- 修改：`packaging/android/www/parsers.js`（仅 `XiaohongshuParser.parse`，扩展数据源与诊断）

## 验证

1. `npx cap copy android && cd android && ./gradlew assembleDebug`
2. 安装新 APK
3. 小红书 `https://xhslink.cn/o/72Q1GlvETWE` → 若解析成功则下载；若仍失败，错误信息带 pageUrl/htmlLen/hasOgImage 等，把完整错误贴我，据此决定是否需实现签名 API
4. 抖音、B站回归不受影响
