// --- Settings ---
let parseMode = localStorage.getItem("parseMode") || "local";
let serverUrl = localStorage.getItem("serverUrl") || "";

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
        results.innerHTML = `<div class="error-card">解析失败: ${e.message}</div>`;
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
            container.innerHTML += `<div class="error-card">${url}: ${e.message}</div>`;
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
                container.innerHTML += `<div class="error-card">${err.url}: ${err.error}</div>`;
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
            <div class="card-actions">
                ${renderDownloadButtons(result)}
            </div>
        </div>
    `;

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

function renderDownloadButtons(result) {
    if (parseMode === "remote" && serverUrl) {
        const apiBase = serverUrl.replace(/\/$/, "") + "/api";
        if (result.media_type === "video") {
            const params = new URLSearchParams({ url: result.items[0].url, platform: result.platform, filename: "video.mp4" });
            return `<a href="${apiBase}/download?${params}" target="_blank">⬇ 下载视频</a>`;
        }
        return result.items.map((item, i) => {
            const ext = item.url.includes(".mp4") ? "mp4" : "jpg";
            const params = new URLSearchParams({ url: item.url, platform: result.platform, filename: `${result.platform}_${i+1}.${ext}` });
            return `<a href="${apiBase}/download?${params}" target="_blank">⬇ ${i + 1}</a>`;
        }).join("");
    }

    // Local mode: direct link download
    if (result.media_type === "video") {
        return `<a href="${result.items[0].url}" target="_blank" download="video.mp4">⬇ 下载视频</a>`;
    }
    return result.items.map((item, i) => {
        const ext = item.url.includes(".mp4") ? "mp4" : "jpg";
        return `<a href="${item.url}" target="_blank" download="${result.platform}_${i+1}.${ext}">⬇ ${i + 1}</a>`;
    }).join("");
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

document.getElementById("urlInput").addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        handleParse();
    }
});
