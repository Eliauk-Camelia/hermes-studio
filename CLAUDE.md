# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目定位

Camelia Studio — 受 Hermes Studio 启发的自建 AI Agent。山茶花 = 理想·谦逊·坚韧。
**用户是大二嵌入式学生，代码自己写，Claude 出题给提示不代写。**

## 运行方式

```bash
# ── Electron 桌面应用（推荐）──
cd electron && npm install          # 首次：安装 Node 依赖
./run-electron.sh                   # 开发模式启动

# ── 纯 Python 模式 ──
pip install -r requirements.txt     # 安装全部后端依赖
python src/server.py                # Web 服务 (http://localhost:8648)
python src/agent.py                 # CLI 终端模式

# ── 打包发布 ──
cd electron && npm run build        # 构建当前平台
cd electron && npm run build:linux  # 仅 Linux (AppImage + deb)
cd electron && npm run build:win    # 仅 Windows (NSIS)
cd electron && npm run build:mac    # 仅 macOS (DMG)
```

## 配置

**Electron 桌面模式（推荐）：**
API Key 和提供商通过设置界面管理（Electron 菜单 → 设置），加密存储于 `electron-store`。
支持多提供商：DeepSeek / 通义千问 / 自定义代理。首次启动无配置时自动进入设置引导页。

**纯 Python 模式（开发/CLI）：**
```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```
`.env` 由 `agent.py` 自动查找（`Path(__file__).parent.parent / ".env"`），
`OPENAI_BASE_URL` 默认 `https://api.deepseek.com/v1`，`LLM_MODEL` 默认 `deepseek-chat`。
端口硬编码 `8648`。Electron 模式下这三个变量由 main.js spawn 时注入。

## 架构

```
src/agent.py   Agent 引擎 — 单文件自包含
  ├── _get_client()     延迟初始化 OpenAI 客户端（模块导入时不检查 Key）
  ├── call_llm()        非流式调用 — 返回完整 message（检测 tool_call）
  ├── stream_llm()      真流式调用 — 存在但未使用，agent_loop 自己模拟流式
  ├── agent_loop()      async generator，最多 10 轮工具调用循环
  │                      流式阶段不是真流式：拿到 msg.content 后 chunk_size=3 切块
  │                      逐块 yield + asyncio.sleep(0.02)，免额外 API 调用
  ├── execute_tool()    8 个工具的 if/elif 路由
  └── TOOLS             8 个工具 (OpenAI Function Calling 格式):
                         get_time / calc / read_file / write_file / list_dir / run_command
                         list_serial_ports / read_serial (嵌入式调试)

src/memory.py  ChromaDB 向量记忆系统 — 模块导入时自动初始化
  ├── add_session()     对话结束后嵌入存储（按 800 字符分块）
  ├── search()          语义检索，返回最相关 N 条
  ├── format_memories() 格式化为 system prompt 上下文
  └── memory_count()    返回存储文档块数
  嵌入模型: all-MiniLM-L6-v2 (ONNX, 首次自动下载 ~80MB)
  存储路径: ~/.camelia-studio/memory/

src/server.py  Web 服务 — FastAPI
  ├── HTTP API          GET/DELETE /api/sessions, POST /api/sessions/{id}/star
  │                     GET /api/health, GET /api/config
  │                     GET /api/memory/search?q=  (语义搜索)
  │                     GET /api/memory/stats       (文档块计数)
  ├── WebSocket /ws     事件流: session_created/reconnected → memory_found →
  │                     tool_start → tool_end → stream → text → session_saved → session_renamed
  │                     会话 JSON: ~/.camelia-studio/sessions/{id}.json
  │                     启动时清理 >30 天旧会话
  ├── 记忆注入          首次用户消息时自动 search → format → 注入 system prompt
  │                     保存会话前恢复原始 system prompt（不写入磁盘）
  ├── 记忆存储          对话结束后 add_session() 写入 ChromaDB
  ├── generate_title()  后台 LLM 生成标题（≤15字），asyncio.create_task 不阻塞
  └── StaticFiles       挂载 / 提供 CSS/JS/图标等静态资源

src/static/index.html   单文件聊天界面 — 山茶花深色主题
  ├── 侧边栏            标签切换: 会话列表 | 记忆搜索
  │                     会话: 星标置顶 + 删除，DOM API + textContent 防 XSS
  │                     记忆: 输入关键词 → 调用 /api/memory/search → 展示结果
  ├── 模型切换器        header 下拉框，生成中切换自动排队
  ├── 消息队列          send() 生成中将消息入队 → finishGeneration() 自动出队
  ├── WebSocket 客户端  createWebSocket() 可重建，重连发 reconnect 消息恢复历史
  ├── 流式渲染策略      stream 事件 → textContent 逐字追加
  │                     text 事件  → renderMarkdown() 替换为完整 HTML
  ├── Markdown          仅处理 ```代码块 + `行内代码，escapeHtml 后正则替换
  └── 响应式            移动端侧边栏滑入/遮罩层

electron/               Electron 桌面壳
  ├── main.js           启动: 检查活跃提供商 → spawn Python (注入 env) → loadURL
  │                     无配置 → loadFile(settings.html) 引导页
  │                     启动时 session.clearCache() + URL 时间戳防缓存
  │                     IPC: 提供商 CRUD / 连接测试 / 后端启停
  │                     加密: SHA256(hostname+username+userData) 确定性派生
  ├── preload.js        contextBridge: window.camelia / window.settings
  ├── settings.html     提供商管理 — 快捷配置(Ollama/DeepSeek/通义千问) + 连接测试
  └── package.json      electron-builder → GitHub Release 自动更新
```

## 数据流

```
浏览器/Electron → WebSocket → server.py → async for agent_loop → call_llm → LLM
      ↑              ↑                           ↑                             ↓
  WebSocket        HTTP API              agent_loop yield             execute_tool()
  (实时推送)    (会话 CRUD)            (stream/tool/text)      (8 个工具 → 结果字符串)
                                          ↓
                                    save_session() → add_session()
                                   (JSON 会话)     (ChromaDB 嵌入)
                                          
  新对话: 用户消息 → search_memory() → format_memories() → 注入 system prompt
```

## agent.py 关键实现细节

### 延迟初始化客户端

`_get_client()` 在首次调用时才创建 `OpenAI` 实例。模块导入时不检查 API Key，
使 server.py 可以在无 Key 环境下启动（Electron 稍后注入）。

### tool_call 时的 messages 顺序

LLM 返回 tool_calls 后，向 `messages` 插入两样东西：
1. **assistant 消息**（含 tool_calls 声明）→ `messages.insert(-len(tool_calls), ...)`
   插入到工具结果之前，保持 assistant → tool 的正确顺序
2. **tool 消息**（每个工具一条）→ `messages.append(...)`

### 路径安全沙箱

`_check_path()` 白名单：`Path.home()`, `/home/arch/Desktop`, `/tmp`
先用 `expanduser().resolve()` 防 `../` 逃逸，再检查是否在白名单前缀内。

### calc 工具安全

使用 Python `ast` 模块解析表达式，仅允许 `BinOp` (+-*/), `Constant`, `UnaryOp`(-) 节点。

## memory.py 关键实现细节

### 嵌入模型

使用 ChromaDB 内置 `DefaultEmbeddingFunction`（`all-MiniLM-L6-v2` ONNX 格式）。
首次运行自动下载模型到 `~/.cache/chroma/onnx_models/`，约 80MB。
不需要单独安装 PyTorch 或 sentence-transformers。

### 会话去重

`add_session()` 先检查是否已有同 session_id 的记录，有则删除旧的后重新写入。
确保同一会话多次保存不会产生重复嵌入。

### system prompt 恢复

server.py 在保存会话前将 `messages[0]["content"]` 恢复为原始 `SYSTEM_PROMPT`，
保存后再恢复内存中的版本。这样磁盘上的 JSON 不含注入的记忆上下文，
下次加载时根据新查询重新检索。

## 技术栈

- Python 3.14: FastAPI + uvicorn + openai + python-dotenv + pyserial + chromadb + onnxruntime
- Node.js: Electron 35 + electron-builder 26 + electron-updater + electron-store 8
- LLM: 多提供商（DeepSeek / 通义千问 / Ollama 本地 / 自定义 OpenAI 兼容 API）
- 嵌入: all-MiniLM-L6-v2 (ONNX, ChromaDB 内置)
- 存储: JSON 文件 (`~/.camelia-studio/sessions/`), ChromaDB (`~/.camelia-studio/memory/`), electron-store 加密 (`config.json`)

## 项目状态

当前 dev/v0.0.5（开发中）。分支策略：`main` 是稳定标签线，`dev/v0.0.X` 是功能累积线。

### 三大支柱（详见 ROADMAP.md）

1. **IDE 壳** — Monaco Editor + xterm.js + 文件树，对标 VS Code 布局
2. **嵌入式工具链** — 一键烧录 + AI 调参闭环 (PID/滤波器/标定)
3. **持久化记忆** — ChromaDB 向量存储 + RAG 语义检索 (✅ 已实现)

### 版本规划

| 版本 | 目标 | 状态 |
|---|---|---|
| v0.0.1~v0.0.4 | 核心引擎 + Web 界面 + 文件工具 + 串口 | ✅ |
| v0.0.5 | 多提供商 + Electron 桌面壳 + 记忆系统 | ✅ 当前 |
| v0.0.6 | 记忆持久化 (ChromaDB + RAG) | ✅ 已提前完成 |
| v0.0.7 | Monaco Editor + 文件树 | |
| v0.0.8 | xterm.js 终端面板 | |
| v0.0.9 | 烧录工具 (OpenOCD / DSLite) | |
| v0.0.10 | AI 调参闭环 (write_serial + 阶跃分析 + PID) | |
| v0.1.0 | 三面板 IDE 整合 + 可扩展插件系统 | |

### UI 设计原则 (经验教训)

- **聊天是核心，不能坏**。任何布局改动必须保证聊天功能正常后再提交。
- **山茶花主题是项目的视觉标识**（深绿底色 + 山茶粉 accent），不要随意替换。
- **单文件 HTML** 是刻意设计，不引入 React/Vue 构建工具链。
- **渐进增强**：一次只加一个面板/功能，验证通过再继续。
- ChromaDB 嵌入模型首次启动自动下载 ~80MB，注意首次启动延迟。

## 安全边界

- 本地单用户 (127.0.0.1 + contextIsolation + nodeIntegration: false)，不暴露公网
- API Key 加密存储于 electron-store，加密密钥由 SHA256(机器指纹) 确定性派生，每台机器唯一
- Electron spawn 只注入 5 个白名单 env（OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL, PATH, HOME）
- 文件操作 `_check_path()` 限制在 ~/、~/Desktop、/tmp
- `run_command` shell=True 是设计决策（需管道/重定向），本地工具不加固
- 前端防 XSS: textContent + DOM API（无 innerHTML）+ renderMarkdown 先 escapeHtml 后正则替换
