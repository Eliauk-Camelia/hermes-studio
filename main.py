"""
Hermes Studio — 本地 AI Agent 平台

启动方式：
    python main.py                 # 启动 Web + WebSocket 服务（含聊天界面）
    python main.py --cli           # 终端模式
    python main.py --port 9000     # 指定端口

环境变量：
    OPENAI_API_KEY   OpenAI API 密钥（必填）
    OPENAI_BASE_URL  自定义 API 地址（默认 OpenAI 官方）
    LLM_MODEL        模型名称（默认 gpt-4o-mini）

使用 Ollama 本地模型：
    OPENAI_BASE_URL=http://localhost:11434/v1
    LLM_MODEL=qwen2.5:7b
"""

import argparse
import asyncio
import sys


def main():
    parser = argparse.ArgumentParser(description="Hermes Studio — 本地 AI Agent")
    parser.add_argument("--cli", action="store_true", help="终端模式")
    parser.add_argument("--port", type=int, default=8648, help="Web 服务端口（默认 8648）")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本地）")
    args = parser.parse_args()

    if args.cli:
        from adapters.cli import run_cli
        asyncio.run(run_cli())
    else:
        from bus.server import run_server
        print(f"""
╔══════════════════════════════════════════════════╗
║         Hermes Studio v0.1.0                     ║
║                                                  ║
║  Web 界面:  http://localhost:{args.port}            ║
║  API 文档:  http://localhost:{args.port}/docs       ║
║  健康检查:  http://localhost:{args.port}/api/health ║
║                                                  ║
║  多端接入:                                        ║
║  - 浏览器打开 Web 界面                            ║
║  - CLI: python main.py --cli                      ║
║  - WebSocket: ws://localhost:{args.port}/ws        ║
╚══════════════════════════════════════════════════╝
        """.strip())
        run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
