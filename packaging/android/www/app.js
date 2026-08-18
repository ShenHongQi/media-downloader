// Server URL from settings or default
function getApiBase() {
    const saved = localStorage.getItem("serverUrl");
    if (saved) return saved.replace(/\/$/, "") + "/api";
    return null;
}

let API_BASE = getApiBase();

function toggleSettings() {
    const panel = document.getElementById("settingsPanel");
    panel.classList.toggle("hidden");
    if (!panel.classList.contains("hidden")) {
        document.getElementById("serverUrl").value =
            localStorage.getItem("serverUrl") || "";
    }
}

function saveSettings() {
    const url = document.getElementById("serverUrl").value.trim();
    if (!url) {
        localStorage.removeItem("serverUrl");
        API_BASE = null;
    } else {
        localStorage.setItem("serverUrl", url);
        API_BASE = url.replace(/\/$/, "") + "/api";
    }
    document.getElementById("settingsPanel").classList.add("hidden");
    alert("已保存");
}

function extractUrls(text) {
    const urlRegex = /https?:\/\/[^\s<>"']+/g;
    return [...new Set(text.match(urlRegex) || [])];
}

async function handleParse() {
    if (!API_BASE) {
        toggleSettings();
        alert("请先配置服务器地址");
        return;
    }

    const input = document.getElementById("urlInput").value.trim();
    if (!input) return;

    const urls = extractUrls(input);
    if (urls.length === 0) {
        alert("未检测到有效链接");
        return;
    }

    const btn = document.getElementById("parseBtn");
    const loading = document.getElementById("loading");
    const results = document.getElementById("results");

    btn.disabled = true;
    loading.classList.remove("hidden");
    results.innerHTML = "";

    try {
        const resp = await fetch(`${API_BASE}/parse`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ urls }),
        });

        const data = await resp.json();
        renderResults(data.results, data.errors);
    } catch (e) {
        results.innerHTML = `<div class="error-card">请求失败: ${e.message}<br>请检查服务器地址是否正确</div>`;
    } finally {
        btn.disabled = false;
        loading.classList.add("hidden");
    }
}

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
            .map((item) => {
                const src = item.thumbnail || item.url;
                return `<img src="${src}" alt="" loading="lazy">`;
            })
            .join("");
        return `<div class="media-preview">${imgs}</div>`;
    }
    return "";
}

function renderDownloadButtons(result) {
    if (result.media_type === "video") {
        const url = buildDownloadUrl(result.items[0].url, result.platform, "video.mp4");
        return `<a href="${url}" target="_blank">⬇ 下载视频</a>`;
    }

    return result.items
        .map((item, i) => {
            const ext = item.url.includes(".mp4") ? "mp4" : "jpg";
            const filename = `${result.platform}_${i + 1}.${ext}`;
            const url = buildDownloadUrl(item.url, result.platform, filename);
            return `<a href="${url}" target="_blank">⬇ ${i + 1}</a>`;
        })
        .join("");
}

function buildDownloadUrl(resourceUrl, platform, filename) {
    const params = new URLSearchParams({
        url: resourceUrl,
        platform: platform,
        filename: filename,
    });
    return `${API_BASE}/download?${params.toString()}`;
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

// Show settings on first launch if no server configured
if (!API_BASE) {
    setTimeout(() => toggleSettings(), 500);
}
