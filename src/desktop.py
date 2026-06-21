"""
Camelia Studio — 桌面应用壳
============================
pywebview 原生窗口，内嵌 FastAPI 服务。
双击运行，独立窗口，任务栏图标。
"""

import threading
import webview
import uvicorn
from server import app

WINDOW_TITLE = "Camelia Studio"
HOST = "127.0.0.1"
PORT = 8648


def start_server():
    """在后台线程启动 FastAPI 服务"""
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    # 启动服务线程
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # 创建原生窗口
    webview.create_window(
        title=WINDOW_TITLE,
        url=f"http://{HOST}:{PORT}",
        width=1000,
        height=700,
        min_size=(600, 400),
        text_select=True,
    )

    webview.start()
