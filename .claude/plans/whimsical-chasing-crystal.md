# 修复小红书：改用 CapacitorHttp 插件 API 取真实 finalUrl

## Context

小红书报错 `finalUrl=https://localhost/_capacitor_http_interceptor_?u=...`。

根因：当前 `XiaohongshuParser.parse` 用的是被 CapacitorHttp patch 过的 `fetch()`。patched fetch 会把请求包装成 `https://localhost/_capacitor_http_interceptor_?u=<原url>` 形式，导致 `resp.url` 返回拦截器地址而非真实重定向后的 URL。因此从 finalUrl 提取 noteId 永远失败，HTML 兜底也没匹配上（xhslink 可能是 JS 跳转 stub）。

抖音能成功是因为它走的是旧的 `resolveRedirect`（直接调 `CapacitorHttp.get` 读 Location header），不是 patched fetch。

## 方案

改回直接调用 `CapacitorHttp` 插件 API（已有的 `httpGet` helper），其 native 响应 `resp.url` 是跟随重定向后的真实地址、`resp.data` 是页面 HTML。

修改 `packaging/android/www/parsers.js` 的 `XiaohongshuParser.parse`：
- 把 `fetch(url, {redirect:"follow", headers})` + `resp.url`/`resp.text()` 换成 `httpGet(url, { headers: { "User-Agent": MOBILE_UA } })`
- `finalUrl = resp.url || url`，`html = typeof resp.data === "string" ? resp.data : (resp.data ? JSON.stringify(resp.data) : "")`
- noteId 多策略提取（已放宽字符集）保持不变
- 兜底请求 explore 页也用 `httpGet`
- 错误信息附 finalUrl 便于诊断（已有）

`httpGet` 在 Capacitor 环境走 `window.Capacitor.Plugins.CapacitorHttp.get`（follow redirects，返回真实 url + data）；非 Capacitor 环境 fallback 到 fetch。

## 涉及文件

- 修改：`packaging/android/www/parsers.js`（`XiaohongshuParser.parse` 内的请求方式）

## 验证

1. `npx cap copy android && cd android && ./gradlew assembleDebug`
2. 安装新 APK
3. 粘贴 `https://xhslink.cn/o/72Q1GlvETWE` → 解析出图文/视频并可下载
4. finalUrl 应为真实 `xiaohongshu.com/discovery/item/...` 或从 stub HTML 提取到 noteId
