# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目定位

Camelia Studio — 受 Hermes Studio 启发的自建 AI Agent。山茶花 = 理想·谦逊·坚韧。
**用户是大二嵌入式学生，代码自己写，Claude 出题给提示不代写。**

## 运行方式

```bash
./run-electron.sh           # Electron 桌面应用（推荐）
python src/desktop.py       # pywebview 轻量桌面壳
python src/server.py        # Web 服务 (http://localhost:8648)
python src/agent.py         # CLI 终端模式
```

## 架构

```
src/agent.py   Agent 引擎 — async 生成器
  ├── call_llm()        非流式调用（检测 tool_call）
  ├── agent_loop()      async yield: tool_start → tool_end → stream → text
  ├── execute_tool()    6 个工具的 if/elif 路由
  └── TOOLS             6 个工具 (OpenAI Function Calling 格式)

src/server.py  Web 服务 — FastAPI
  ├── HTTP API          /api/sessions CRUD + /api/sessions/{id}/star
  ├── WebSocket         async for event in agent_loop → 逐事件推送前端
  └── 会话存储          ~/.camelia-studio/sessions/*.json, 30天自动过期

src/static/index.html   聊天界面 — 山茶花深色主题
  ├── 流式渲染          stream 事件追加 textContent → text 事件 renderMarkdown
  ├── Markdown          ```代码块 + `行内代码, escapeHtml 防 XSS
  └── 会话管理          侧边栏 + 星标 + 切换/删除

electron/               Electron 桌面壳
  ├── main.js           启动 Python 后端 → 等待就绪 → 打开 BrowserWindow
  └── package.json      electron-builder + GitHub Release auto-update
```

## 数据流

```
浏览器/Electron → WebSocket → server.py → async for agent_loop → call_llm → DeepSeek
                                    ↑                                  ↓
                               save_session                    execute_tool()
                              (自动保存到JSON)                 (读文件/跑命令/...)
```

## 技术栈

- Python 3.14: FastAPI + uvicorn + openai + pywebview
- Node.js: Electron + electron-builder + electron-updater
- LLM: DeepSeek API (`deepseek-chat`), OpenAI 兼容
- 存储: JSON 文件, `~/.camelia-studio/sessions/`

## 分支策略

```
main ← 稳定版本，每个版本一个 tag (v0.0.1 ~ v0.0.5)
dev/v0.0.X ← 开发分支，多功能攒够后 merge
```

## 安全边界

- 本地单用户 (127.0.0.1)，不暴露公网
- 文件操作 `_check_path()` 限制在 ~/、~/Desktop、/tmp
- `run_command` shell=True 是设计决策（需管道/重定向），本地工具不加固
- 前端: textContent + DOM API + renderMarkdown escapeHtml，无 XSS
