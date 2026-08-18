// --- Plugins (plain JS access, no bundler) ---
const { App, Filesystem, Media } =
  (window.Capacitor && window.Capacitor.Plugins) || {};

// --- Settings ---
let parseMode = localStorage.getItem("parseMode") || "local";
let serverUrl = localStorage.getItem("serverUrl") || "";

// --- Lightbox state (for back button handling) ---
let lightboxOpen = false;

function overlayOpen() {
    return (
        lightboxOpen ||
        !document.getElementById("settingsPanel").classList.contains("hidden")
    );
}

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
            const result = await parserRegistry.parse(url);
            container.appendChild(createCard(result));
        } catch (e) {
            container.innerHTML += `<div class="error-card">${escapeHtml(url)}: ${escapeHtml(e.message)}</div>`;
        }
    }
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
            <div class="card-actions" id="actions-${result.platform}"></div>
        </div>
    `;
    // Build action buttons after insertion
    const actions = card.querySelector(`#actions-${result.platform}`);
    actions.appendChild(renderActions(result));
    // Wire up image clicks for lightbox
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
        allBtn.onclick = () => downloadAll(result);
        wrap.appendChild(allBtn);
    }

    // Per-item buttons
    result.items.forEach((item, i) => {
        const btn = document.createElement("button");
        btn.className = "dl-btn";
        if (result.media_type === "video") {
            btn.textContent = "⬇ 下载视频";
        } else {
            btn.textContent = `⬇ 第${i + 1}张`;
        }
        const ext = item.url.includes(".mp4") ? "mp4" : "jpg";
        const filename = `${result.platform}_${i + 1}.${ext}`;
        btn.onclick = () => downloadMedia(item.url, filename, result.media_type === "video" ? "video" : "image", btn);
        wrap.appendChild(btn);
    });

    return wrap;
}

// --- Download via native plugins ---
// Media.savePhoto/saveVideo accept `path`: a web URL, base64 data URI, or local file path.
function getBase64DataUri(url, isVideo) {
    const mime = isVideo ? "video/mp4" : "image/jpeg";
    return fetch(url)
        .then((r) => r.blob())
        .then(
            (blob) =>
                new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result.replace(`data:application/octet-stream`, `data:${mime}`));
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                })
        )
        .then((dataUri) => dataUri.startsWith("data:") ? dataUri : `data:${mime};base64,${dataUri}`);
}

async function downloadMedia(url, filename, type, btn) {
    if (!Media) {
        alert("下载插件未就绪，请用远程模式（需后端服务器代理下载）");
        return;
    }
    const isVideo = type === "video";
    const original = btn ? btn.textContent : "";
    if (btn) {
        btn.disabled = true;
        btn.textContent = "下载中...";
    }
    try {
        const dataUri = await getBase64DataUri(url, isVideo);
        if (isVideo) {
            await Media.saveVideo({ path: dataUri });
        } else {
            await Media.savePhoto({ path: dataUri });
        }
        if (btn) btn.textContent = "✓ 已保存到相册";
        setTimeout(() => { if (btn) { btn.textContent = original; btn.disabled = false; } }, 2000);
    } catch (e) {
        if (btn) { btn.textContent = original; btn.disabled = false; }
        alert("下载失败: " + e.message);
    }
}

async function downloadAll(result) {
    if (!Media) {
        alert("下载插件未就绪");
        return;
    }
    let ok = 0;
    let fail = 0;
    for (let i = 0; i < result.items.length; i++) {
        const item = result.items[i];
        const isVideo = item.url.includes(".mp4") || result.media_type === "video";
        try {
            const dataUri = await getBase64DataUri(item.url, isVideo);
            if (isVideo) {
                await Media.saveVideo({ path: dataUri });
            } else {
                await Media.savePhoto({ path: dataUri });
            }
            ok++;
        } catch (e) {
            console.error("item", i, e);
            fail++;
        }
    }
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
