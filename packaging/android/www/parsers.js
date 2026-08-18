/**
 * Media Parsers - JavaScript implementation (runs locally in WebView)
 * Uses Capacitor HTTP plugin to bypass CORS
 */

class ParserRegistry {
    constructor() {
        this.parsers = [
            new DouyinParser(),
            new BilibiliParser(),
            new XiaohongshuParser(),
            new KuaishouParser(),
            new TiktokParser(),
            new InstagramParser(),
        ];
    }

    getParser(url) {
        return this.parsers.find((p) => p.detect(url)) || null;
    }

    async parse(url) {
        const parser = this.getParser(url);
        if (!parser) throw new Error("不支持的平台");
        return await parser.parse(url);
    }
}

// --- HTTP Helper ---

async function httpGet(url, options = {}) {
    const { headers = {}, followRedirects = true } = options;

    // Use Capacitor HTTP if available (native, no CORS)
    if (window.Capacitor && window.Capacitor.Plugins.CapacitorHttp) {
        const resp = await window.Capacitor.Plugins.CapacitorHttp.get({
            url,
            headers,
            readTimeout: 15000,
            connectTimeout: 10000,
            disableRedirects: !followRedirects,
        });
        return { status: resp.status, data: resp.data, headers: resp.headers, url: resp.url };
    }

    // Fallback: standard fetch (works when served from same-origin or CORS allowed)
    const resp = await fetch(url, {
        headers,
        redirect: followRedirects ? "follow" : "manual",
    });
    const text = await resp.text();
    let data;
    try { data = JSON.parse(text); } catch { data = text; }
    return { status: resp.status, data, headers: Object.fromEntries(resp.headers), url: resp.url };
}

async function httpPost(url, body, options = {}) {
    const { headers = {} } = options;

    if (window.Capacitor && window.Capacitor.Plugins.CapacitorHttp) {
        const resp = await window.Capacitor.Plugins.CapacitorHttp.post({
            url,
            headers: { "Content-Type": "application/json", ...headers },
            data: body,
            readTimeout: 15000,
            connectTimeout: 10000,
        });
        return { status: resp.status, data: resp.data, headers: resp.headers };
    }

    const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify(body),
    });
    const text = await resp.text();
    let data;
    try { data = JSON.parse(text); } catch { data = text; }
    return { status: resp.status, data, headers: Object.fromEntries(resp.headers) };
}

async function resolveRedirect(url) {
    // Use the CapacitorHttp plugin API directly and read the real Location header
    // from the native response. (Patched fetch wraps the URL as an interceptor and
    // its resp.url is unusable.)
    if (window.Capacitor && window.Capacitor.Plugins.CapacitorHttp) {
        const resp = await window.Capacitor.Plugins.CapacitorHttp.get({
            url,
            headers: {
                "User-Agent": MOBILE_UA,
            },
            disableRedirects: true,
            readTimeout: 10000,
            connectTimeout: 10000,
        });
        if ([301, 302, 303, 307, 308].includes(resp.status)) {
            return resp.headers["Location"] || resp.headers["location"] || url;
        }
        return resp.url || url;
    }

    const resp = await fetch(url, { redirect: "manual" });
    if (resp.type === "opaqueredirect" || [301, 302, 303, 307, 308].includes(resp.status)) {
        return resp.headers.get("location") || url;
    }
    return resp.url || url;
}

// --- Parsers ---

const MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1";
const DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";

class DouyinParser {
    detect(url) {
        return /v\.douyin\.com\/\w+/.test(url) ||
            /www\.douyin\.com\/video\/\d+/.test(url) ||
            /www\.douyin\.com\/note\/\d+/.test(url);
    }

    async parse(url) {
        const awemeId = await this._extractId(url);
        const ttwid = await this._getTtwid();
        const detail = await this._fetchDetail(awemeId, ttwid);
        return this._buildResult(detail, url);
    }

    async _extractId(url) {
        if (url.includes("v.douyin.com")) {
            url = await resolveRedirect(url);
        }
        const m = url.match(/\/(?:video|note)\/(\d+)/) || url.match(/modal_id=(\d+)/);
        if (m) return m[1];
        throw new Error("无法提取抖音 ID: " + url);
    }

    async _getTtwid() {
        const resp = await httpPost("https://ttwid.bytedance.com/ttwid/union/register/", {
            region: "cn", aid: 1128, needFid: false,
            service: "www.douyin.com",
            migrate_info: { ticket: "", source: "node" },
            cbUrlProtocol: "https", union: true,
        });
        // Extract ttwid from set-cookie header
        const cookies = resp.headers["Set-Cookie"] || resp.headers["set-cookie"] || "";
        const m = cookies.match(/ttwid=([^;]+)/);
        if (m) return m[1];
        // Capacitor might return it differently
        if (typeof resp.data === "object" && resp.data.data) return resp.data.data;
        throw new Error("获取 ttwid 失败");
    }

    async _fetchDetail(awemeId, ttwid) {
        const resp = await httpGet(
            `https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id=${awemeId}&aid=6383`,
            { headers: { Referer: "https://www.douyin.com/", Cookie: `ttwid=${ttwid}` } }
        );
        const data = typeof resp.data === "string" ? JSON.parse(resp.data) : resp.data;
        if (!data.aweme_detail) throw new Error("抖音解析失败");
        return data.aweme_detail;
    }

    _buildResult(detail, originalUrl) {
        const images = detail.images;
        if (images && images.length > 0) {
            return {
                platform: "douyin",
                media_type: "album",
                title: detail.desc || "",
                author: detail.author?.nickname || "",
                cover: images[0].url_list?.slice(-1)[0] || "",
                items: images.map((img) => ({ url: img.url_list?.slice(-1)[0] || "" })),
                original_url: originalUrl,
            };
        }
        const video = detail.video || {};
        const playAddr = video.play_addr?.url_list || [];
        return {
            platform: "douyin",
            media_type: "video",
            title: detail.desc || "",
            author: detail.author?.nickname || "",
            cover: video.cover?.url_list?.[0] || "",
            items: [{ url: playAddr[0] || "", duration: (video.duration || 0) / 1000 }],
            original_url: originalUrl,
        };
    }
}

class BilibiliParser {
    detect(url) {
        return /bilibili\.com\/video\/BV\w+/.test(url) || /b23\.tv\/\w+/.test(url);
    }

    async parse(url) {
        const bvid = await this._extractBvid(url);
        const info = await this._fetchInfo(bvid);
        const playUrl = await this._fetchPlayUrl(bvid, info.cid);
        return {
            platform: "bilibili",
            media_type: "video",
            title: info.title,
            author: info.author,
            cover: info.cover,
            items: [{ url: playUrl, duration: info.duration }],
            original_url: url,
        };
    }

    async _extractBvid(url) {
        if (url.includes("b23.tv")) url = await resolveRedirect(url);
        const m = url.match(/(BV\w+)/);
        if (m) return m[1];
        throw new Error("无法提取 BV 号");
    }

    async _fetchInfo(bvid) {
        const resp = await httpGet(
            `https://api.bilibili.com/x/web-interface/view?bvid=${bvid}`,
            { headers: { Referer: "https://www.bilibili.com/" } }
        );
        const data = typeof resp.data === "string" ? JSON.parse(resp.data) : resp.data;
        if (data.code !== 0) throw new Error("B站 API 错误: " + data.message);
        return {
            cid: data.data.cid,
            title: data.data.title,
            author: data.data.owner?.name || "",
            cover: data.data.pic,
            duration: data.data.duration,
        };
    }

    async _fetchPlayUrl(bvid, cid) {
        const resp = await httpGet(
            `https://api.bilibili.com/x/player/playurl?bvid=${bvid}&cid=${cid}&qn=80&fnval=1&fourk=1`,
            { headers: { Referer: "https://www.bilibili.com/" } }
        );
        const data = typeof resp.data === "string" ? JSON.parse(resp.data) : resp.data;
        if (data.code !== 0) throw new Error("B站播放地址获取失败");
        const durl = data.data?.durl || [];
        if (durl.length > 0) return durl[0].url;
        throw new Error("无法获取播放地址");
    }
}

class XiaohongshuParser {
    detect(url) {
        return /xiaohongshu\.com\/explore\/[a-f0-9]+/.test(url) ||
            /xhslink\.(com|cn)\//.test(url);
    }

    async parse(url) {
        // Resolve short link via Location header (native, reliable). Do NOT rely on
        // httpGet's resp.url — it's the interceptor URL and unusable.
        let pageUrl = url;
        if (url.includes("xhslink")) pageUrl = await resolveRedirect(url);

        const ID = "[A-Za-z0-9_-]{16,32}";
        let m = pageUrl.match(new RegExp(`(?:explore|discovery/item|item|notes?)/(${ID})`));
        let stubHtml = "";
        if (!m) {
            // resolveRedirect may not follow JS-redirect stubs; fetch the stub HTML
            const r = await httpGet(pageUrl, { headers: { "User-Agent": MOBILE_UA } });
            stubHtml = typeof r.data === "string" ? r.data : (r.data ? JSON.stringify(r.data) : "");
            m = stubHtml.match(new RegExp(`xiaohongshu\\.com/(?:explore|discovery/item)/(${ID})`));
            if (!m) m = stubHtml.match(new RegExp(`"noteId"\\s*[:=]\\s*"(${ID})"`));
        }
        if (!m) {
            throw new Error("无法提取小红书笔记 ID (url=" + pageUrl.slice(0, 80) + ")");
        }
        const noteId = m[1];

        // Fetch the note page using the FULL token-bearing URL (pageUrl) — the
        // xsec_token in it is what makes Xiaohongshu inject the note data into
        // __INITIAL_STATE__. Rebuilding explore/{noteId} (no token) returns an
        // empty skeleton. Fall back to explore/{noteId} only if pageUrl isn't xhs.
        const fetchUrl = pageUrl.includes("xiaohongshu.com")
            ? pageUrl
            : `https://www.xiaohongshu.com/explore/${noteId}`;
        const r = await httpGet(fetchUrl, { headers: { "User-Agent": MOBILE_UA } });
        const html = typeof r.data === "string" ? r.data : (r.data ? JSON.stringify(r.data) : "");

        const stateMatch = html.match(/window\.__INITIAL_STATE__\s*=\s*(.+?)<\/script>/);
        if (!stateMatch) throw new Error("小红书页面解析失败");

        const raw = stateMatch[1].replace(/undefined/g, "null");
        const state = JSON.parse(raw);

        // Structured path
        const noteMap = state.note?.noteDetailMap || {};
        let noteData = Object.values(noteMap)[0]?.note;

        // If structured note missing, try multiple fallback data sources.
        if (!noteData) {
            // Source 2: regex on the __INITIAL_STATE__ raw JSON
            const videoUrlMatch = raw.match(/"masterUrl"\s*:\s*"(https?:[^"]+)"/);
            const imageUrlsState = [...new Set(
                [...raw.matchAll(/"urlDefault"\s*:\s*"(https?:[^"]+)"/g)].map((x) => x[1])
            )];
            const titleMatch = raw.match(/"title"\s*:\s*"([^"]+)"/);
            const descMatch = raw.match(/"desc"\s*:\s*"([^"]*)"/);
            const nickMatch = raw.match(/"nickname"\s*:\s*"([^"]+)"/);
            const title = titleMatch ? titleMatch[1] : (descMatch ? descMatch[1] : "");
            const author = nickMatch ? nickMatch[1] : "";

            if (videoUrlMatch) {
                return {
                    platform: "xiaohongshu",
                    media_type: "video",
                    title, author,
                    cover: imageUrlsState[0] || "",
                    items: [{ url: videoUrlMatch[1] }],
                    original_url: url,
                };
            }
            if (imageUrlsState.length > 0) {
                return {
                    platform: "xiaohongshu",
                    media_type: imageUrlsState.length > 1 ? "album" : "image",
                    title, author,
                    cover: imageUrlsState[0],
                    items: imageUrlsState.map((u) => ({ url: u })),
                    original_url: url,
                };
            }

            // Source 3: og / meta tags
            const ogVideo = (html.match(/<meta[^>]+property=["']og:video(?::url|:secure_url)?["'][^>]*content=["']([^"']+)["']/i) || [])[1]
                || (html.match(/<meta[^>]+property=["']og:video[^"']*["'][^>]*content=["']([^"']+)["']/i) || [])[1];
            const ogImages = [...html.matchAll(/<meta[^>]+property=["']og:image["'][^>]*content=["']([^"']+)["']/gi)].map((x) => x[1]);
            const ogTitle = (html.match(/<meta[^>]+property=["']og:title["'][^>]*content=["']([^"']+)["']/i) || [])[1];
            const ogDesc = (html.match(/<meta[^>]+property=["']og:description["'][^>]*content=["']([^"']+)["']/i) || [])[1];
            const ogAuthor = (html.match(/<meta[^>]+(?:property|name)=["']og:article:author["'][^>]*content=["']([^"']+)["']/i)
                || html.match(/<meta[^>]+name=["']author["'][^>]*content=["']([^"']+)["']/i) || [])[1];

            if (ogVideo) {
                return {
                    platform: "xiaohongshu",
                    media_type: "video",
                    title: ogTitle || ogDesc || "",
                    author: ogAuthor || "",
                    cover: ogImages[0] || "",
                    items: [{ url: ogVideo }],
                    original_url: url,
                };
            }
            if (ogImages.length > 0) {
                return {
                    platform: "xiaohongshu",
                    media_type: ogImages.length > 1 ? "album" : "image",
                    title: ogTitle || ogDesc || "",
                    author: ogAuthor || "",
                    cover: ogImages[0],
                    items: ogImages.map((u) => ({ url: u })),
                    original_url: url,
                };
            }

            // Source 4: whole-HTML xiaohongshu CDN media regex
            const cdnImg = [...new Set(
                [...html.matchAll(/https?:\/\/(?:sns-img[^.]*\.xhscdn\.com|ci\.xiaohongshu\.com|sns-webpic[^.]*\.xhscdn\.com)\/[^\s"'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"'<>]*)?/gi)]
                    .map((x) => x[0])
            )];
            const cdnVideo = [...new Set(
                [...html.matchAll(/https?:\/\/[^\s"'<>]+\.mp4[^\s"'<>]*/gi)]
                    .map((x) => x[0])
                    .filter((u) => /xhs|xiaohongshu/.test(u))
            )];

            if (cdnVideo.length > 0) {
                return {
                    platform: "xiaohongshu",
                    media_type: "video",
                    title: ogTitle || ogDesc || "",
                    author: ogAuthor || "",
                    cover: cdnImg[0] || "",
                    items: [{ url: cdnVideo[0] }],
                    original_url: url,
                };
            }
            if (cdnImg.length > 0) {
                return {
                    platform: "xiaohongshu",
                    media_type: cdnImg.length > 1 ? "album" : "image",
                    title: ogTitle || ogDesc || "",
                    author: ogAuthor || "",
                    cover: cdnImg[0],
                    items: cdnImg.map((u) => ({ url: u })),
                    original_url: url,
                };
            }

            // Diagnostics
            throw new Error(
                "无法获取笔记内容 (pageUrl=" + pageUrl.slice(0, 60) +
                ", htmlLen=" + html.length +
                ", noteMapKeys=" + Object.keys(noteMap).join(",") +
                ", ogImg=" + ogImages.length + ", ogVideo=" + (ogVideo ? "y" : "n") +
                ")"
            );
        }

        // Structured result below (noteData present)
        if (noteData.type === "video") {
            const video = noteData.video || {};
            const streams = video.media?.stream?.h264 || [];
            const videoUrl = streams[0]?.masterUrl || "";
            return {
                platform: "xiaohongshu",
                media_type: "video",
                title: noteData.title || noteData.desc || "",
                author: noteData.user?.nickname || "",
                cover: noteData.imageList?.[0]?.urlDefault || "",
                items: [{ url: videoUrl }],
                original_url: url,
            };
        }

        const images = noteData.imageList || [];
        return {
            platform: "xiaohongshu",
            media_type: images.length > 1 ? "album" : "image",
            title: noteData.title || noteData.desc || "",
            author: noteData.user?.nickname || "",
            cover: images[0]?.urlDefault || "",
            items: images.map((img) => ({
                url: (img.urlDefault || "").startsWith("//") ? "https:" + img.urlDefault : img.urlDefault || "",
                width: img.width,
                height: img.height,
            })),
            original_url: url,
        };
    }
}

class KuaishouParser {
    detect(url) {
        return /v\.kuaishou\.com\/\w+/.test(url) ||
            /kuaishou\.com\/short-video\/\w+/.test(url);
    }

    async parse(url) {
        if (url.includes("v.kuaishou.com")) url = await resolveRedirect(url);
        const m = url.match(/\/short-video\/(\w+)/) || url.match(/photoId=(\w+)/);
        if (!m) throw new Error("无法提取快手视频 ID");

        const resp = await httpPost(
            "https://v.m.chenzhongtech.com/rest/wd/photo/info",
            { photoId: m[1], isLongVideo: false },
            { headers: { Referer: "https://v.kuaishou.com/" } }
        );
        const data = typeof resp.data === "string" ? JSON.parse(resp.data) : resp.data;
        if (data.result !== 1) throw new Error("快手 API 错误");

        const photo = data.photo || {};
        return {
            platform: "kuaishou",
            media_type: "video",
            title: photo.caption || "",
            author: data.user?.userName || "",
            cover: photo.coverUrl || "",
            items: [{ url: photo.mainMvUrl || photo.photoUrl || "", duration: (photo.duration || 0) / 1000 }],
            original_url: url,
        };
    }
}

class TiktokParser {
    detect(url) {
        return /vm\.tiktok\.com\/\w+/.test(url) ||
            /tiktok\.com\/@[^/]+\/video\/\d+/.test(url) ||
            /tiktok\.com\/t\/\w+/.test(url);
    }

    async parse(url) {
        if (url.includes("vm.tiktok.com") || url.includes("/t/")) {
            url = await resolveRedirect(url);
        }
        const m = url.match(/\/video\/(\d+)/);
        if (!m) throw new Error("无法提取 TikTok 视频 ID");

        const resp = await httpGet(url, { headers: { "User-Agent": DESKTOP_UA } });
        const html = typeof resp.data === "string" ? resp.data : "";
        const dataMatch = html.match(/<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.+?)<\/script>/);
        if (!dataMatch) throw new Error("TikTok 页面解析失败（需要可访问 TikTok 的网络）");

        const pageData = JSON.parse(dataMatch[1]);
        const item = pageData.__DEFAULT_SCOPE__?.["webapp.video-detail"]?.itemInfo?.itemStruct;
        if (!item) throw new Error("无法提取 TikTok 视频信息");

        const video = item.video || {};
        return {
            platform: "tiktok",
            media_type: "video",
            title: item.desc || "",
            author: item.author?.nickname || "",
            cover: video.cover || "",
            items: [{ url: video.playAddr || video.downloadAddr || "", duration: video.duration || 0 }],
            original_url: url,
        };
    }
}

class InstagramParser {
    detect(url) {
        return /instagram\.com\/(p|reel)\/[\w-]+/.test(url);
    }

    async parse(url) {
        const m = url.match(/\/(p|reel)\/([\w-]+)/);
        if (!m) throw new Error("无法提取 Instagram shortcode");
        const shortcode = m[2];

        const resp = await httpGet(
            `https://www.instagram.com/p/${shortcode}/embed/captioned/`,
            { headers: { "User-Agent": DESKTOP_UA } }
        );
        const html = typeof resp.data === "string" ? resp.data : "";

        const videoMatch = html.match(/"video_url":"([^"]+)"/);
        const imageMatch = html.match(/"display_url":"([^"]+)"/);

        if (!videoMatch && !imageMatch) {
            throw new Error("Instagram 解析失败（可能需要登录或网络不通）");
        }

        if (videoMatch) {
            return {
                platform: "instagram",
                media_type: "video",
                title: "",
                author: "",
                cover: imageMatch ? imageMatch[1].replace(/\\u0026/g, "&") : "",
                items: [{ url: videoMatch[1].replace(/\\u0026/g, "&") }],
                original_url: url,
            };
        }

        return {
            platform: "instagram",
            media_type: "image",
            title: "",
            author: "",
            cover: imageMatch[1].replace(/\\u0026/g, "&"),
            items: [{ url: imageMatch[1].replace(/\\u0026/g, "&") }],
            original_url: url,
        };
    }
}

// Global instance
const parserRegistry = new ParserRegistry();
