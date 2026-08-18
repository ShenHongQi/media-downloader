# 修复小红书解析 + 添加粘贴/清除按钮

## Context

抖音下载已成功。两个待解决：
1. **小红书短链解析失败**："无法提取小红书笔记 ID"。根因：`xhslink.cn` 短链 302 重定向后的落地 URL 是 `xiaohongshu.com/discovery/item/<noteId>`，但 `XiaohongshuParser.parse` 只匹配 `/explore/([a-f0-9]+)`，匹配不到就报错。
2. **UI 完善**：空输入时提供"一键粘贴"按钮（从剪贴板粘入）；有内容时提供"一键清除"按钮。

## 方案

### 1. 修复小红书解析（`packaging/android/www/parsers.js`）

重写 `XiaohongshuParser.parse`：
- 不再单独依赖 `resolveRedirect`，直接 `fetch(url, { redirect: "follow", headers: { "User-Agent": MOBILE_UA } })` 一次请求拿到**最终 URL + 页面 HTML**（CapacitorHttp 已 patch fetch，原生层无 CORS、自动跟随重定向）
- noteId 提取正则扩展为：`/(?:explore|discovery\/item|item)\/([a-f0-9]{8,})/`，优先从 `resp.url` 取，取不到再从 HTML 里搜 `xiaohongshu.com/(explore|discovery/item)/...`
- HTML 里若有 `__INITIAL_STATE__` 直接用；否则用 noteId 兜底请求 `https://www.xiaohongshu.com/explore/{noteId}` 再解析
- 用最终落地 URL（含 xsec_token 等）请求，比重建 explore URL 更稳

同时把 `resolveRedirect` 简化为 `fetch follow` 取 `resp.url`（抖音/b23.tv/快手仍走此函数，保持兼容）。

### 2. 添加粘贴/清除按钮（`packaging/android/www/index.html` + `app.js` + `style.css`）

**HTML**：在 textarea 上方加一个工具栏：
```html
<div class="input-toolbar">
    <button id="pasteBtn" class="tool-btn">📋 粘贴链接</button>
    <button id="clearBtn" class="tool-btn hidden">✕ 清除</button>
</div>
```

**app.js**：
- `pasteFromClipboard()`：`navigator.clipboard.readText()` 读剪贴板写入 textarea（Capacitor WebView origin 为 `https://localhost`，clipboard API 在用户点击手势下可用），失败时 alert 提示手动粘贴
- `clearInput()`：清空 textarea，focus 回输入框
- textarea 的 `input` 事件 → `toggleToolButtons()`：有内容显示清除按钮、隐藏粘贴按钮；无内容反之
- 初始化时调用一次 toggle

**style.css**：`.input-toolbar` flex 布局，`.tool-btn` 小按钮样式，复用暗色主题变量；`.hidden` 复用已有的 `display:none`。

## 涉及文件

- 修改：`packaging/android/www/parsers.js`（resolveRedirect + XiaohongshuParser）
- 修改：`packaging/android/www/index.html`（input-toolbar）
- 修改：`packaging/android/www/app.js`（粘贴/清除/toggle 逻辑）
- 修改：`packaging/android/www/style.css`（工具栏样式）

## 验证

1. `npx cap copy android && cd android && ./gradlew assembleDebug`
2. 安装新 APK
3. 粘贴小红书链接 `https://xhslink.cn/o/72Q1GlvETWE` → 解析出图文/视频、可下载
4. 空输入时显示"粘贴链接"按钮，点击自动填入剪贴板内容；有内容时显示"清除"按钮
5. 抖音/B站回归测试仍正常
