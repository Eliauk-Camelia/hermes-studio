# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目定位

Camelia Studio — 受 Hermes Studio 启发的自建 AI Agent。山茶花 = 理想·谦逊·坚韧。
**用户是大二嵌入式学生，代码必须自己写，Claude 出题给提示不代写。**

## 运行

```bash
python src/server.py          # Web 服务 (http://localhost:8648)
python src/agent.py           # CLI 模式
```

`.env` 启动时自动加载，无需手动 source。

## 架构

```
src/agent.py   (290行)  Agent 引擎
  ├── call_llm()      给 DeepSeek 发 HTTP 请求
  ├── agent_loop()    yield 生成器：调 LLM → 执行工具 → 循环
  ├── execute_tool()   6 个工具的 if/elif 路由
  └── TOOLS            6 个工具 (OpenAI Function Calling 格式)

src/server.py  (125行)  Web 服务
  ├── HTTP API         会话列表/加载/删除
  ├── WebSocket        聊天管道 (yield 事件逐个推送)
  └── 会话存储         ~/.camelia-studio/sessions/*.json

src/static/index.html   聊天界面 (山茶花深色主题)
```

`agent_loop` 是 yiel 生成器——每次产出一个事件 (`tool_start` / `tool_end` / `text`)，调用方 `for event in agent_loop(...)` 逐个消费。CLI 和 WebSocket 共用同一个生成器。

## 技术栈

- Python 3.14，FastAPI + uvicorn (Web)，openai (LLM)，python-dotenv (配置)
- DeepSeek API (`deepseek-chat`)，OpenAI 兼容协议
- 会话持久化：JSON 文件 (`~/.camelia-studio/sessions/`)
- 版本管理：git flow，`dev/vX.X.X` 分支开发，合并 main 后打 tag

## 分支策略

```
main          ← 稳定版本，每个版本一个 tag
dev/v0.0.X    ← 当前开发分支，多个功能攒够了再 merge
```

当前开发分支: `dev/v0.0.4`，已含 6 个工具 + 会话管理 + 前端，待合并。

## 安全边界

- 本地单用户工具 (127.0.0.1)，不暴露公网
- 文件操作限制在 ~/、~/Desktop、/tmp 白名单目录
- `run_command` 用 `shell=True` 是设计决策（需支持管道/重定向），不在公网暴露
- 前端全部用 `textContent` + DOM API，无 `innerHTML` XSS 风险
