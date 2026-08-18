"""
Media Downloader - Windows Desktop Entry Point
启动内嵌的 FastAPI 后端 + pywebview 原生窗口
"""

import multiprocessing
import sys
import threading
import time

import uvicorn
import webview


def start_server():
    """在子线程中启动 FastAPI 服务"""
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=18090,
        log_level="warning",
    )


def wait_for_server(url, timeout=10):
    """等待后端启动完成"""
    import urllib.request
    import urllib.error

    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(f"{url}/api/health")
            return True
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.1)
    return False


def main():
    multiprocessing.freeze_support()

    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    api_url = "http://127.0.0.1:18090"
    if not wait_for_server(api_url):
        print("Failed to start backend server")
        sys.exit(1)

    window = webview.create_window(
        title="Media Downloader",
        url=api_url + "/index.html",
        width=900,
        height=700,
        min_size=(400, 500),
    )
    webview.start()


if __name__ == "__main__":
    main()
