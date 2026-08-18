# 回退 resolveRedirect 恢复抖音/B站 + 修复小红书

## Context

抖音、B站、小红书现在全部解析失败。根因：
- `1896f4b` 把 `resolveRedirect` 从 `CapacitorHttp.get(disableRedirects:true)` 读 `Location` header（native 真实 header，可靠），改成 `fetch(url,{redirect:"follow"})` + `resp.url`。但 CapacitorHttp 的 **patched fetch** 会把请求包装成 `https://localhost/_capacitor_http_interceptor_?u=...`，`resp.url` 返回的是拦截器地址而非真实重定向 URL。
- 抖音 `_extractId`、B站 `_extractBvid`、小红书都依赖 `resolveRedirect`，于是全部提取不出 ID。

`dc5a83c` 时抖音/B站正常（用读 Location header 的方式）。

## 方案

### 1. 回退 `resolveRedirect` 到 dc5a83c 版本（`packaging/android/www/parsers.js`）

恢复为 `CapacitorHttp.get({ url, disableRedirects: true, headers:{UA} })`，看状态码：
- 302/301/... → 返回 `resp.headers["Location"] || resp.headers["location"]`（native 真实 header）
- 否则 → 返回 `resp.url || url`
- 非 Capacitor 环境 fallback 到 `fetch(url,{redirect:"manual"})` 读 location

这直接恢复抖音（v.douyin.com 302）和B站（b23.tv 302）。

### 2. 小红书用回退后的 resolveRedirect + 宽松正则 + HTML 兜底

重写 `XiaohongshuParser.parse`：
```
let pageUrl = url;
if (url.includes("xhslink")) pageUrl = await resolveRedirect(url);

const ID = "[A-Za-z0-9_-]{16,32}";
let m = pageUrl.match(/(?:explore|discovery\/item|item|notes?)\/(ID)/);
let html = "";
if (!m) {
    // resolveRedirect may not follow JS-redirect stubs; fetch the stub HTML
    const r = await httpGet(pageUrl, { headers: { "User-Agent": MOBILE_UA } });
    html = typeof r.data === "string" ? r.data : (r.data ? JSON.stringify(r.data) : "");
    m = html.match(/xiaohongshu\.com\/(?:explore|discovery\/item)\/(ID)/);
    if (!m) m = html.match(/"noteId"\s*[:=]\s*"(ID)"/);
}
if (!m) throw new Error("无法提取小红书笔记 ID (url=" + pageUrl.slice(0,80) + ")");
const noteId = m[1];

// __INITIAL_STATE__: prefer fetched html, else fetch explore page
let stateHtml = html;
let stateMatch = stateHtml.match(/window\.__INITIAL_STATE__\s*=\s*(.+?)<\/script>/);
if (!stateMatch) {
    const r2 = await httpGet(`https://www.xiaohongshu.com/explore/${noteId}`, { headers:{UA} });
    stateHtml = ...;
    stateMatch = ...;
}
```

注意：**不依赖** `httpGet` 的 `resp.url`（它是拦截器 URL 不可靠），只用 `resp.data`（真实 HTML）和从 `resolveRedirect` 读到的真实 Location。

### 3. 保留 9bc0fc7/55083de 的 UI 改进

- 保留 `@capacitor/clipboard` + 粘贴/清除/解析 action-row 按钮（这些是好的，不动）
- 只动 parsers.js 的 resolveRedirect 和 XiaohongshuParser

## 涉及文件

- 修改：`packaging/android/www/parsers.js`（`resolveRedirect` 回退；`XiaohongshuParser.parse` 重写）

## 验证

1. `npx cap copy android && cd android && ./gradlew assembleDebug`
2. 安装新 APK
3. **抖音**图文链接 → 正常解析下载（回归）
4. **B站**链接 → 正常解析下载（回归）
5. **小红书** `https://xhslink.cn/o/72Q1GlvETWE` → 正常解析下载
6. 粘贴/清除按钮、action-row 布局仍正常
