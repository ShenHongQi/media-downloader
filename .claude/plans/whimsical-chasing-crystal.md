# 修复小红书笔记内容获取（带 xsec_token + 正则兜底）

## Context

小红书报"无法获取笔记内容"——noteId 提取已成功，但 `__INITIAL_STATE__.note.noteDetailMap` 为空。

根因：当前用重建的 `https://www.xiaohongshu.com/explore/{noteId}` 请求页面，**丢失了 xsec_token 访问令牌**。小红书对无 token 的 explore 请求返回空 noteDetailMap 骨架页。而短链重定向后的真实 URL `xiaohongshu.com/discovery/item/{id}?xsec_token=...&xsec_source=...` 才带令牌，用它请求才能拿到 note 数据。

抖音不受影响（走 iesdouyin API，独立路径），本次只改 `XiaohongshuParser.parse`，不碰 `resolveRedirect`。

## 方案（`packaging/android/www/parsers.js` 的 `XiaohongshuParser.parse`）

### 1. 用含 token 的真实 URL 请求页面

- `resolveRedirect(xhslink)` 得到 `pageUrl`（含 `?xsec_token=...`）
- 提取 noteId 后，**用 pageUrl 本身**（完整含 token）`httpGet` 拿 HTML，而不是重建 `explore/{noteId}` 丢 token
- 仅当 pageUrl 不是 xiaohongshu.com（极端情况）才回退到 explore/{noteId}

### 2. 结构化解析 + 正则兜底

拿到 `__INITIAL_STATE__` 后：
- 先按原结构取 `noteDetailMap` → `note`
- 若 `note` 为空（noteDetailMap 空对象），从 `__INITIAL_STATE__` 的 raw JSON 字符串里**正则兜底提取**媒体与元信息：
  - 视频：`"masterUrl"\s*:\s*"(https?:[^"]+)"`（取第一个）→ media_type=video
  - 图片：`"urlDefault"\s*:\s*"(https?:[^"]+)"`（去重后全部）→ image/album
  - 标题：`"title"\s*:\s*"([^"]+)"` 或 `"desc"\s*:\s*"([^"]+)"`
  - 作者：`"nickname"\s*:\s*"([^"]+)"`
  - 封面：第一张图片 urlDefault
- 兜底也取不到才报错（附 noteDetailMap keys 便于诊断）

这样无论 SSR 注入到 noteDetailMap 还是其他位置，都能拿到媒体。

### 3. 不动抖音/B站

`resolveRedirect` 保持当前（读 Location header）版本，抖音 `_extractId`、B站 `_extractBvid` 不变。只重写 `XiaohongshuParser.parse` 内部。

## 涉及文件

- 修改：`packaging/android/www/parsers.js`（仅 `XiaohongshuParser.parse`）

## 验证

1. `npx cap copy android && cd android && ./gradlew assembleDebug`
2. 安装新 APK
3. **小红书** `https://xhslink.cn/o/72Q1GlvETWE` → 解析出图文/视频并可下载到相册
4. **抖音**图文 → 仍正常（回归，不受影响）
5. **B站** → 仍正常（回归）
