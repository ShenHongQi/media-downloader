# 修复小红书 noteId 提取 + clipboard 粘贴 + 按钮布局

## Context

三个待解决：
1. **小红书仍报"无法提取小红书笔记 ID"**：fetch follow 成功了（否则会报"请求失败"），但 noteId 正则 `[a-f0-9]{8,}` 太严——小红书 noteId 是 24 位，可能含非 hex 字符，且落地 URL 形式多样。需放宽并从多处提取。
2. **粘贴失败**："无法读取剪切板"。`navigator.clipboard.readText()` 在 Capacitor WebView 不可靠。改用 `@capacitor/clipboard` 原生插件。
3. **按钮布局**：把粘贴/清除按钮做大，与"解析"按钮同行同级、等宽、同设计风格。

## 方案

### 1. 小红书 noteId 提取放宽（`packaging/android/www/parsers.js`）

`XiaohongshuParser.parse` 的提取改为多策略，字符集放宽为 `[A-Za-z0-9_-]`、长度 16~32：
- 优先从 `finalUrl` 匹配：`/(?:explore|discovery\/item|item|notes?)\/([A-Za-z0-9_-]{16,32})/`
- 其次从 HTML 找 `xiaohongshu.com/(explore|discovery/item)/([A-Za-z0-9_-]{16,32})`
- 再从 HTML 找 `"noteId"\s*[:=]\s*"([A-Za-z0-9_-]{16,32})"` 或 `note\/([A-Za-z0-9_-]{16,32})`
- 若都失败，把 `finalUrl` 片段附进错误信息方便诊断

### 2. 安装 `@capacitor/clipboard` 用原生剪贴板

- `npm install @capacitor/clipboard@6` + `npx cap sync android`
- `app.js` 的 `pasteFromClipboard()` 改为：优先 `window.Capacitor.Plugins.Clipboard.read()`（返回 `{ value }`），失败再 fallback `navigator.clipboard.readText()`

### 3. 按钮布局重构（`index.html` + `app.js` + `style.css`）

**HTML**：把工具栏合并进输入区，做成一行三个等宽按钮，粘贴/清除互斥显示：
```html
<div class="action-row">
    <button id="pasteBtn" class="action-btn" onclick="pasteFromClipboard()">📋 粘贴</button>
    <button id="clearBtn" class="action-btn hidden" onclick="clearInput()">✕ 清除</button>
    <button id="parseBtn" class="action-btn primary" onclick="handleParse()">解析</button>
</div>
```
（textarea 在按钮行上方或下方，保持原有结构）

**style.css**：
- `.action-row` flex、gap
- `.action-btn` 与原"解析"按钮同样式（padding 14px、border-radius 12px、字号 1rem），`flex:1` 等宽
- `.action-btn.primary` 用 `--accent` 强调色（解析按钮）
- 粘贴/清除用 `--surface2` 底色
- `.hidden` 保持 `display:none`

**app.js**：`toggleToolButtons()` 逻辑不变（有内容显示清除、隐藏粘贴；无内容反之）。按钮已用 `hidden` 类切换。

## 涉及文件

- 修改：`packaging/android/www/parsers.js`
- 修改：`packaging/android/www/index.html`
- 修改：`packaging/android/www/app.js`
- 修改：`packaging/android/www/style.css`
- 修改：`packaging/android/package.json`（加 @capacitor/clipboard）

## 验证

1. `npm install @capacitor/clipboard@6 && npx cap sync android && cd android && ./gradlew assembleDebug`
2. 安装新 APK
3. 粘贴小红书链接 → 正常解析出图文/视频并可下载
4. 点击"粘贴"按钮 → 从剪贴板自动填入（不再报错）
5. 三个按钮同行等宽、风格统一；空时显示"粘贴"，有内容时显示"清除"
