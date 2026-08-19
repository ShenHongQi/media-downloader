// --- Plugins (plain JS access, no bundler) ---
const { App } = (window.Capacitor && window.Capacitor.Plugins) || {};
const Downloader = (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Downloader) || null;

// Platform -> Referer header (bilibili needs it to avoid 403)
const PLATFORM_REFERER = {
    douyin: "https://www.douyin.com/",
    bilibili: "https://www.bilibili.com/",
    xiaohongshu: "https://www.xiaohongshu.com/",
    kuaishou: "https://v.kuaishou.com/",
    tiktok: "https://www.tiktok.com/",
    instagram: "https://www.instagram.com/",
};

// --- Settings ---
let parseMode = localStorage.getItem("parseMode") || "local";
let serverUrl = localStorage.getItem("serverUrl") || "";

// --- Lightbox state (for back button handling) ---
let lightboxOpen = false;

// --- Android back button ---
if (App) {
    App.addListener("backButton", () => {
        if (lightboxOpen) {
            closeLightbox();
        } else if (!document.getElementById("settingsPanel").classList.contains("hidden")) {
            document.getElementById("settingsPanel").classList.add("hidden");
        } else {
            App.exitApp();
        }
    });
}

// --- Settings UI ---
function toggleSettings() {
    const panel = document.getElementById("settingsPanel");
    panel.classList.toggle("hidden");
    if (!panel.classList.contains("hidden")) {
        document.getElementById("serverUrl").value = serverUrl;
        updateModeUI();
    }
}

function setMode(mode) {
    parseMode = mode;
    updateModeUI();
}

function updateModeUI() {
    document.getElementById("modeLocal").classList.toggle("active", parseMode === "local");
    document.getElementById("modeRemote").classList.toggle("active", parseMode === "remote");
    document.getElementById("remoteConfig").classList.toggle("hidden", parseMode !== "remote");
}

function saveSettings() {
    localStorage.setItem("parseMode", parseMode);
    serverUrl = document.getElementById("serverUrl").value.trim();
    localStorage.setItem("serverUrl", serverUrl);
    document.getElementById("settingsPanel").classList.add("hidden");
}

// --- URL extraction ---
function extractUrls(text) {
    const urlRegex = /https?:\/\/[^\s<>"']+/g;
    return [...new Set(text.match(urlRegex) || [])];
}

// --- Paste / Clear toolbar ---
function toggleToolButtons() {
    const text = document.getElementById("urlInput").value.trim();
    document.getElementById("pasteBtn").classList.toggle("hidden", text.length > 0);
    document.getElementById("clearBtn").classList.toggle("hidden", text.length === 0);
}

async function pasteFromClipboard() {
    let text = "";
    try {
        const Clip = window.Capacitor?.Plugins?.Clipboard;
        if (Clip) {
            const res = await Clip.read();
            text = res.value || "";
        } else if (navigator.clipboard && navigator.clipboard.readText) {
            text = await navigator.clipboard.readText();
        }
    } catch (e) {
        // fall through
    }
    if (text) {
        const ta = document.getElementById("urlInput");
        ta.value = (ta.value ? ta.value + "\n" : "") + text;
        toggleToolButtons();
    } else {
        alert("无法读取剪贴板，请手动长按输入框粘贴");
    }
}

function clearInput() {
    const ta = document.getElementById("urlInput");
    ta.value = "";
    toggleToolButtons();
    ta.focus();
}

// --- Parse ---
async function handleParse() {
    const input = document.getElementById("urlInput").value.trim();
    if (!input) return;

    const urls = extractUrls(input);
    if (urls.length === 0) {
        alert("未检测到有效链接");
        return;
    }

    if (parseMode === "remote" && !serverUrl) {
        toggleSettings();
        alert("请先配置服务器地址");
        return;
    }

    const btn = document.getElementById("parseBtn");
    const loading = document.getElementById("loading");
    const results = document.getElementById("results");

    btn.disabled = true;
    loading.classList.remove("hidden");
    results.innerHTML = "";

    try {
        if (parseMode === "local") {
            await parseLocal(urls);
        } else {
            await parseRemote(urls);
        }
    } catch (e) {
        results.innerHTML = `<div class="error-card">解析失败: ${escapeHtml(e.message)}</div>`;
    } finally {
        btn.disabled = false;
        loading.classList.add("hidden");
    }
}

async function parseLocal(urls) {
    const container = document.getElementById("results");
    for (const url of urls) {
        try {
            // 小红书/Instagram 走远程后端（需服务器配置）；其余平台本地解析不变
            if (isXiaohongshu(url)) {
                const r = await parseXhsRemote(url);
                container.appendChild(createCard(r));
                continue;
            }
            if (isInstagram(url)) {
                const r = await parseInstagramRemote(url);
                container.appendChild(createCard(r));
                continue;
            }
            const result = await parserRegistry.parse(url);
            container.appendChild(createCard(result));
        } catch (e) {
            container.innerHTML += `<div class="error-card">${escapeHtml(url)}: ${escapeHtml(e.message)}</div>`;
        }
    }
}

function isXiaohongshu(url) {
    return /xhslink\.(com|cn)\//.test(url) ||
        /xiaohongshu\.com\/(explore|discovery|note|item)/.test(url);
}

function isInstagram(url) {
    return /instagram\.com\/(p|reel)\/[\w-]+/.test(url);
}

async function parseXhsRemote(url) {
    if (!serverUrl) {
        throw new Error("小红书需后端签名支持，请点右上角⚙配置服务器地址（部署 xhs 后端）");
    }
    const apiBase = serverUrl.replace(/\/$/, "") + "/api";
    const resp = await fetch(`${apiBase}/xhs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
    });
    if (!resp.ok) {
        const txt = await resp.text().catch(() => "");
        throw new Error(`${resp.status} ${txt}`.slice(0, 200));
    }
    return await resp.json();
}

async function parseInstagramRemote(url) {
    if (!serverUrl) {
        throw new Error("Instagram 需后端支持，请点右上角⚙配置服务器地址（部署 instagram 后端，需服务器能访问 ins）");
    }
    const apiBase = serverUrl.replace(/\/$/, "") + "/api";
    const resp = await fetch(`${apiBase}/instagram`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
    });
    if (!resp.ok) {
        const txt = await resp.text().catch(() => "");
        throw new Error(`${resp.status} ${txt}`.slice(0, 200));
    }
    return await resp.json();
}

async function parseRemote(urls) {
    const apiBase = serverUrl.replace(/\/$/, "") + "/api";
    const resp = await fetch(`${apiBase}/parse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls }),
    });
    const data = await resp.json();
    renderResults(data.results, data.errors);
}

// --- Render ---
function renderResults(resultList, errors) {
    const container = document.getElementById("results");
    container.innerHTML = "";
    resultList.forEach((result, i) => {
        if (!result) {
            const err = errors[i];
            if (err) {
                container.innerHTML += `<div class="error-card">${escapeHtml(err.url)}: ${escapeHtml(err.error)}</div>`;
            }
            return;
        }
        container.appendChild(createCard(result));
    });
}

function createCard(result) {
    // unique id in case multiple results share platform
    const uid = `${result.platform}-${Math.random().toString(36).slice(2, 8)}`;
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
        <div class="card-header">
            <span class="platform-badge">${result.platform}</span>
            <span class="title">${escapeHtml(result.title || "无标题")}</span>
            <span class="author">${escapeHtml(result.author || "")}</span>
        </div>
        <div class="card-body">
            ${renderPreview(result)}
            <div class="card-actions" id="actions-${uid}"></div>
        </div>
    `;
    const actions = card.querySelector(`#actions-${uid}`);
    actions.appendChild(renderActions(result));
    card.querySelectorAll(".media-preview img").forEach((img) => {
        img.addEventListener("click", () => openLightbox(img.src));
    });
    return card;
}

function renderPreview(result) {
    if (result.media_type === "video" && result.cover) {
        return `<div class="media-preview"><img src="${result.cover}" alt="cover" loading="lazy"></div>`;
    }
    if (result.media_type === "album" || result.media_type === "image") {
        const imgs = result.items
            .slice(0, 9)
            .map((item) => `<img src="${item.url}" alt="" loading="lazy">`)
            .join("");
        return `<div class="media-preview">${imgs}</div>`;
    }
    return "";
}

function renderActions(result) {
    const wrap = document.createElement("div");
    wrap.style.display = "contents";

    // Download-all button (for albums / multi-item)
    if (result.items.length > 1) {
        const allBtn = document.createElement("button");
        allBtn.className = "dl-btn";
        allBtn.textContent = `⬇ 全部下载 (${result.items.length})`;
        allBtn.onclick = () => downloadAll(result, allBtn);
        wrap.appendChild(allBtn);
    }

    // Per-item buttons
    result.items.forEach((item, i) => {
        const btn = document.createElement("button");
        btn.className = "dl-btn";
        const isVideo = result.media_type === "video" || item.url.includes(".mp4");
        if (result.media_type === "video") {
            btn.textContent = "⬇ 下载视频";
        } else {
            btn.textContent = `⬇ 第${i + 1}张`;
        }
        const ext = isVideo ? "mp4" : "jpg";
        const filename = `${result.platform}_${i + 1}`;
        btn.onclick = () => downloadMedia(item.url, filename, isVideo, result.platform, btn);
        wrap.appendChild(btn);
    });

    return wrap;
}

// --- Download via native Downloader plugin ---
// Pass URL directly to native; native downloads + saves to gallery via MediaStore.
async function downloadMedia(url, filename, isVideo, platform, btn) {
    if (!Downloader) {
        alert("下载插件未就绪");
        return;
    }
    const original = btn ? btn.textContent : "";
    if (btn) {
        btn.disabled = true;
        btn.textContent = "下载中...";
    }
    try {
        await Downloader.save({
            url: url,
            filename: filename,
            isVideo: isVideo,
            referer: PLATFORM_REFERER[platform] || null,
        });
        if (btn) btn.textContent = "✓ 已保存到相册";
        setTimeout(() => { if (btn) { btn.textContent = original; btn.disabled = false; } }, 2000);
    } catch (e) {
        if (btn) { btn.textContent = original; btn.disabled = false; }
        alert("下载失败: " + (e.message || e));
    }
}

async function downloadAll(result, btn) {
    if (!Downloader) {
        alert("下载插件未就绪");
        return;
    }
    const original = btn.textContent;
    let ok = 0;
    let fail = 0;
    for (let i = 0; i < result.items.length; i++) {
        const item = result.items[i];
        const isVideo = result.media_type === "video" || item.url.includes(".mp4");
        if (btn) btn.textContent = `下载中 ${i + 1}/${result.items.length}`;
        try {
            await Downloader.save({
                url: item.url,
                filename: `${result.platform}_${i + 1}`,
                isVideo: isVideo,
                referer: PLATFORM_REFERER[result.platform] || null,
            });
            ok++;
        } catch (e) {
            console.error("item", i, e);
            fail++;
        }
    }
    if (btn) { btn.textContent = original; btn.disabled = false; }
    alert(`已保存 ${ok} 个${fail ? `，失败 ${fail} 个` : ""}到相册`);
}

// --- Lightbox ---
function openLightbox(src) {
    lightboxOpen = true;
    const lb = document.getElementById("lightbox");
    lb.querySelector("img").src = src;
    lb.classList.remove("hidden");
}

function closeLightbox() {
    lightboxOpen = false;
    document.getElementById("lightbox").classList.add("hidden");
}

// --- Helpers ---
function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
}

document.getElementById("urlInput").addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        handleParse();
    }
});

document.getElementById("urlInput").addEventListener("input", toggleToolButtons);
// initial toggle
toggleToolButtons();
